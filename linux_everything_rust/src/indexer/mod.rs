use crate::database::{Database, FileEntry};
use ignore::WalkBuilder;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use tokio::sync::Mutex;
use anyhow::Result;
use tracing::{info, debug};

pub struct Indexer {
    db: Arc<Mutex<Database>>,
    root_path: PathBuf,
}

impl Indexer {
    pub fn new(db: Database, root_path: impl AsRef<Path>) -> Result<Self> {
        let root_path = root_path.as_ref().to_path_buf();

        // Expand ~ to home directory
        let root_path = if root_path.to_string_lossy() == "~" {
            dirs::home_dir().unwrap_or_else(|| PathBuf::from("/"))
        } else {
            root_path
        };

        Ok(Self {
            db: Arc::new(Mutex::new(db)),
            root_path,
        })
    }

    pub fn get_mounts() -> Vec<PathBuf> {
        let mut mounts = Vec::new();
        if let Ok(content) = std::fs::read_to_string("/proc/self/mountinfo") {
            for line in content.lines() {
                let parts: Vec<&str> = line.split_whitespace().collect();
                if parts.len() > 9 {
                    let mount_point = parts[4];
                    let fs_type = parts[parts.len() - 3];
                    
                    // Filter for "real" filesystems
                    match fs_type {
                        "ext4" | "xfs" | "btrfs" | "zfs" | "ntfs" | "ntfs3" | "msdos" | "vfat" => {
                            mounts.push(PathBuf::from(mount_point));
                        }
                        _ => {}
                    }
                }
            }
        }
        
        if mounts.is_empty() {
            mounts.push(PathBuf::from("/"));
        }
        mounts
    }

    pub async fn scan(&self) -> Result<()> {
        info!("Starting scan of {}", self.root_path.display());

        let start_time = std::time::Instant::now();
        let mut count = 0;
        let batch_size = 5000; // Smaller batches for more frequent dir_state updates
        let mut batch = Vec::with_capacity(batch_size);
        let mut dirs_to_update = Vec::new();

        let walker = WalkBuilder::new(&self.root_path)
            .add_custom_ignore_filename(".ignore")
            .hidden(false)
            .build();

        for result in walker {
            let entry = match result {
                Ok(entry) => entry,
                Err(e) => {
                    debug!("Skipping path due to error: {}", e);
                    continue;
                }
            };
            let path = entry.path();
            let metadata = match entry.metadata() {
                Ok(m) => m,
                Err(e) => {
                    debug!("Skipping metadata for {} due to error: {}", path.display(), e);
                    continue;
                }
            };

            let modified_time = metadata.modified()
                .unwrap_or(std::time::SystemTime::UNIX_EPOCH)
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs_f64();

            if metadata.is_file() {
                batch.push(FileEntry {
                    path: path.to_string_lossy().into_owned(),
                    name: path.file_name().unwrap_or_default().to_string_lossy().into_owned(),
                    modified_time,
                    is_dir: 0,
                    size: metadata.len(),
                });
            } else if metadata.is_dir() {
                batch.push(FileEntry {
                    path: path.to_string_lossy().into_owned(),
                    name: path.file_name().unwrap_or_default().to_string_lossy().into_owned(),
                    modified_time,
                    is_dir: 1,
                    size: 0,
                });
                dirs_to_update.push((path.to_string_lossy().into_owned(), modified_time));
            }

            if batch.len() >= batch_size {
                self.flush_batch(&batch, &dirs_to_update).await?;
                count += batch.len();
                batch.clear();
                dirs_to_update.clear();
                debug!("Indexed {} items...", count);
            }
        }

        if !batch.is_empty() {
            self.flush_batch(&batch, &dirs_to_update).await?;
            count += batch.len();
        }

        let duration = start_time.elapsed();
        info!("Scan complete. {} items indexed in {:.2} seconds.", count, duration.as_secs_f64());

        Ok(())
    }

    async fn flush_batch(&self, batch: &[FileEntry], dirs: &[(String, f64)]) -> Result<()> {
        let mut db = self.db.lock().await;
        db.insert_batch(batch)?;
        
        // Update dir_state
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs_f64();
            
        for (path, mtime) in dirs {
            db.update_dir_state(path, *mtime, now)?;
        }
        
        Ok(())
    }
}