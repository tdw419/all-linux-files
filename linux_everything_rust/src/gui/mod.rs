use eframe::egui;
use crate::database::{Database, SearchResult};
use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};

pub fn run_gui(db: Database) -> anyhow::Result<()> {
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([800.0, 600.0])
            .with_title("Linux Everything"),
        ..Default::default()
    };

    let app = LinuxEverythingApp::new(db);

    eframe::run_native(
        "Linux Everything",
        options,
        Box::new(|cc| {
            // Request repaint every second to keep "Recent" fresh
            ctx_repaint_loop(cc.egui_ctx.clone());
            Ok(Box::new(app))
        }),
    ).map_err(|e| anyhow::anyhow!("GUI Error: {}", e))
}

fn ctx_repaint_loop(ctx: egui::Context) {
    tokio::spawn(async move {
        loop {
            tokio::time::sleep(std::time::Duration::from_secs(1)).await;
            ctx.request_repaint();
        }
    });
}

struct LinuxEverythingApp {
    db: Arc<Mutex<Database>>,
    query: String,
    results: Vec<SearchResult>,
    status_message: String,
    search_time: f64,
    daemon_active: bool,
    show_all_files: bool,
}

impl LinuxEverythingApp {
    fn new(db: Database) -> Self {
        let mut app = Self {
            db: Arc::new(Mutex::new(db)),
            query: String::new(),
            results: Vec::new(),
            status_message: String::from("Ready"),
            search_time: 0.0,
            daemon_active: false,
            show_all_files: false,
        };
        app.check_daemon_status();
        // Load recent files on startup
        app.refresh_recent();
        app
    }

    fn check_daemon_status(&mut self) {
        let output = std::process::Command::new("systemctl")
            .arg("is-active")
            .arg("linux-everything-daemon")
            .output();
        
        if let Ok(output) = output {
            self.daemon_active = String::from_utf8_lossy(&output.stdout).trim() == "active";
        }
    }

    fn toggle_daemon(&mut self) {
        let command = if self.daemon_active { "stop" } else { "start" };
        let status = std::process::Command::new("pkexec")
            .arg("systemctl")
            .arg(command)
            .arg("linux-everything-daemon")
            .status();
        
        match status {
            Ok(s) if s.success() => {
                self.check_daemon_status();
                self.status_message = format!("Daemon {}", if self.daemon_active { "started" } else { "stopped" });
            }
            Ok(_) => {
                self.status_message = "Permission denied or failed".to_string();
            }
            Err(e) => {
                self.status_message = format!("Execution error: {}", e);
            }
        }
    }

    fn refresh_recent(&mut self) {
        if let Ok(db) = self.db.lock() {
            let start = std::time::Instant::now();
            let result = if self.show_all_files {
                db.get_all_files(5000)
            } else {
                db.get_recent(50)
            };

            match result {
                Ok(files) => {
                    self.results = files;
                    self.status_message = if self.show_all_files {
                        format!("Showing {} most recently modified files from index", self.results.len())
                    } else {
                        format!("Showing {} recently changed files", self.results.len())
                    };
                }
                Err(e) => {
                    self.status_message = format!("Error loading files: {}", e);
                }
            }
            self.search_time = start.elapsed().as_secs_f64() * 1000.0;
        }
    }

    fn perform_search(&mut self) {
        if self.query.is_empty() {
            self.refresh_recent();
            return;
        }

        if let Ok(db) = self.db.lock() {
            let start = std::time::Instant::now();
            match db.search(&self.query, None) {
                Ok(files) => {
                    self.results = files;
                    self.status_message = format!("Found {} matches", self.results.len());
                }
                Err(e) => {
                    self.status_message = format!("Search error: {}", e);
                }
            }
            self.search_time = start.elapsed().as_secs_f64() * 1000.0;
        }
    }
}

impl eframe::App for LinuxEverythingApp {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        // Periodic status check
        if ctx.input(|i| i.time) % 5.0 < 0.1 {
            self.check_daemon_status();
            if self.query.is_empty() {
                self.refresh_recent();
            }
        }

        egui::CentralPanel::default().show(ctx, |ui| {
            // Header
            ui.heading("Linux Everything");
            
            ui.horizontal(|ui| {
                if self.daemon_active {
                    ui.label(egui::RichText::new("● Running").color(egui::Color32::from_rgb(50, 200, 50)));
                } else {
                    ui.label(egui::RichText::new("○ Stopped").color(egui::Color32::from_rgb(200, 50, 50)));
                }
            });
            
            // Search Bar
            ui.horizontal(|ui| {
                ui.label("🔍");
                let response = ui.add(egui::TextEdit::singleline(&mut self.query).hint_text("Search files..."));
                if response.changed() {
                    self.perform_search();
                }
                if ui.button("Refresh Recent").clicked() {
                    self.query.clear();
                    self.refresh_recent();
                }

                if ui.checkbox(&mut self.show_all_files, "Show All").changed() {
                    self.refresh_recent();
                }

                ui.separator();

                let daemon_text = if self.daemon_active { "⏹ Stop Daemon" } else { "▶ Start Daemon" };
                let daemon_color = if self.daemon_active { egui::Color32::from_rgb(200, 50, 50) } else { egui::Color32::from_rgb(50, 150, 50) };
                
                if ui.add(egui::Button::new(egui::RichText::new(daemon_text).color(egui::Color32::WHITE)).fill(daemon_color)).clicked() {
                    self.toggle_daemon();
                }
            });

            // Status Line
            ui.separator();
            ui.horizontal(|ui| {
                ui.label(&self.status_message);
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    ui.label(format!("{:.2}ms", self.search_time));
                });
            });
            ui.separator();

            // Results List
            let text_height = egui::TextStyle::Body.resolve(ui.style()).size;
            let num_rows = self.results.len();
            
            egui::ScrollArea::vertical().show_rows(
                ui,
                text_height,
                num_rows,
                |ui, row_range| {
                    for index in row_range {
                        if let Some(result) = self.results.get(index) {
                            ui.horizontal(|ui| {
                                // Format time as relative string if possible, or simple timestamp
                                let time_str = format_time(result.modified_time);
                                ui.label(egui::RichText::new(&time_str).monospace().weak());
                                
                                // File path - allow it to take up available space
                                let path_text = egui::RichText::new(&result.path);
                                ui.label(path_text);
                                
                                // Spacer to push size to the right
                                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                                    // File size, formatted
                                    let size_str = format_size(result.size);
                                    ui.label(egui::RichText::new(&size_str).monospace().weak());
                                });
                            });
                        }
                    }
                },
            );
        });
    }
}

fn format_time(timestamp: f64) -> String {
    let system_time = UNIX_EPOCH + std::time::Duration::from_secs_f64(timestamp);
    if let Ok(duration) = SystemTime::now().duration_since(system_time) {
        if duration.as_secs() < 60 {
            return format!("{}s ago", duration.as_secs());
        }
        if duration.as_secs() < 3600 {
            return format!("{}m ago", duration.as_secs() / 60);
        }
        if duration.as_secs() < 86400 {
            return format!("{}h ago", duration.as_secs() / 3600);
        }
        return format!("{}d ago", duration.as_secs() / 86400);
    }
    "Future?".to_string()
}

fn format_size(bytes: u64) -> String {
    if bytes < 1024 {
        return format!("{} B", bytes);
    }
    let kb = bytes as f64 / 1024.0;
    if kb < 1024.0 {
        return format!("{:.1} KB", kb);
    }
    let mb = kb / 1024.0;
    if mb < 1024.0 {
        return format!("{:.1} MB", mb);
    }
    let gb = mb / 1024.0;
    if gb < 1024.0 {
        return format!("{:.1} GB", gb);
    }
    format!("{:.1} TB", gb / 1024.0)
}
