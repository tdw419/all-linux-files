use crate::database::{Database, FileEntry};
use notify::{RecommendedWatcher, RecursiveMode, Watcher, Event, Config};
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::Mutex;
use anyhow::Result;
use tracing::{info, error, debug};

pub struct FileWatcher {
    db: Arc<Mutex<Database>>,
    watch_path: PathBuf,
}

impl FileWatcher {
    pub fn new(db: Database, watch_path: impl AsRef<Path>) -> Self {
        let watch_path = watch_path.as_ref().to_path_buf();

        Self {
            db: Arc::new(Mutex::new(db)),
            watch_path,
        }
    }

    pub async fn start(&self) -> Result<()> {
        info!("Starting watcher for {}", self.watch_path.display());

        let (tx, rx) = std::sync::mpsc::channel();
        let watch_path = self.watch_path.clone();
        let db = self.db.clone();

        let mut watcher = RecommendedWatcher::new(tx, Config::default())?;
        watcher.watch(&self.watch_path, RecursiveMode::Recursive)?;

        tokio::spawn(async move {
            let watcher_instance = FileWatcher { db, watch_path };
            while let Ok(event) = rx.recv() {
                watcher_instance.handle_event(event).await;
            }
        });

        Ok(())
    }

    async fn handle_event(&self, event: Result<Event, notify::Error>) {
        match event {
            Ok(event) => {
                match event.kind {
                    notify::EventKind::Create(_) | notify::EventKind::Modify(_) => {
                        for path in event.paths {
                            if let Ok(metadata) = std::fs::metadata(&path) {
                                if metadata.is_file() {
                                    self.update_file(&path).await;
                                }
                            }
                        }
                    }
                    _ => {}
                }
            }
            Err(e) => {
                error!("Watch error: {:?}", e);
            }
        }
    }

    async fn update_file(&self, path: &Path) {
        if let Ok(metadata) = std::fs::metadata(path) {
            let modified_time = metadata.modified().unwrap_or(std::time::SystemTime::UNIX_EPOCH)
                .duration_since(std::time::UNIX_EPOCH).unwrap().as_secs_f64();

            let file_entry = FileEntry {
                path: path.to_string_lossy().into_owned(),
                name: path.file_name().unwrap_or_default().to_string_lossy().into_owned(),
                modified_time,
                is_dir: 0,
                size: metadata.len(),
            };

            {
                let mut db = self.db.lock().await;
                if let Err(e) = db.insert_batch(&[file_entry]) {
                    error!("Failed to update file in database: {}", e);
                }
            }
        }
    }

    pub async fn start_with_fallback(&self) -> Result<()> {
        let db = self.db.clone();

        // Start the Budgeted Incremental Sweep
        tokio::spawn(async move {
            let mut interval = tokio::time::interval(Duration::from_millis(500));
            loop {
                interval.tick().await;
                
                let dirs_to_scan = {
                    let db_lock = db.lock().await;
                    db_lock.get_oldest_dirs(10).unwrap_or_default()
                };

                if dirs_to_scan.is_empty() {
                    // If no dirs yet, wait for first scan
                    tokio::time::sleep(Duration::from_secs(5)).await;
                    continue;
                }

                for (path_str, last_mtime) in dirs_to_scan {
                    let path = Path::new(&path_str);
                    if let Ok(metadata) = std::fs::metadata(path) {
                        let current_mtime = metadata.modified()
                            .unwrap_or(std::time::SystemTime::UNIX_EPOCH)
                            .duration_since(std::time::UNIX_EPOCH)
                            .unwrap_or_default()
                            .as_secs_f64();

                        if current_mtime > last_mtime {
                            debug!("Sweep detected change in {}", path_str);
                            // Run a shallow scan of this directory
                            let mut db_lock = db.lock().await;
                            if let Ok(mut entries) = std::fs::read_dir(&path) {
                                let mut batch = Vec::new();
                                while let Some(Ok(entry)) = entries.next() {
                                    if let Ok(m) = entry.metadata() {
                                        let etime = m.modified()
                                            .unwrap_or(std::time::SystemTime::UNIX_EPOCH)
                                            .duration_since(std::time::UNIX_EPOCH)
                                            .unwrap_or_default()
                                            .as_secs_f64();
                                        
                                        batch.push(FileEntry {
                                            path: entry.path().to_string_lossy().into_owned(),
                                            name: entry.file_name().to_string_lossy().into_owned(),
                                            modified_time: etime,
                                            is_dir: if m.is_dir() { 1 } else { 0 },
                                            size: if m.is_dir() { 0 } else { m.len() },
                                        });
                                    }
                                }
                                let _ = db_lock.insert_batch(&batch);
                            }
                            let now = std::time::SystemTime::now()
                                .duration_since(std::time::UNIX_EPOCH)
                                .unwrap()
                                .as_secs_f64();
                            let _ = db_lock.update_dir_state(&path_str, current_mtime, now);
                        } else {
                            // Even if no change, update last_scan_ts to rotate
                            let mut db_lock = db.lock().await;
                            let now = std::time::SystemTime::now()
                                .duration_since(std::time::UNIX_EPOCH)
                                .unwrap()
                                .as_secs_f64();
                            let _ = db_lock.update_dir_state(&path_str, last_mtime, now);
                        }
                    }
                }
            }
        });

        // Try to start inotify watcher as accelerator
        if let Err(e) = self.start().await {
            error!("Inotify watcher failed: {}. Sweep will provide correctness.", e);
        }

        Ok(())
    }
}