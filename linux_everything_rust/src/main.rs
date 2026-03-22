mod indexer;
mod database;
mod watcher;
mod gui;
mod cli;

use anyhow::Result;
use clap::Parser;
use cli::Cli;
use database::Database;
use indexer::Indexer;
use tracing::{info, error};

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize logging
    tracing_subscriber::fmt::init();

    info!("Starting Linux Everything");

    let cli = Cli::parse();

    // Initialize database
    let db = Database::new()?;

    match cli.command {
        cli::Command::Scan { path } => {
            let indexer = Indexer::new(db, path)?;
            indexer.scan().await?;
        }
        cli::Command::Search { query } => {
            let results = db.search(&query, None)?;
            println!("Found {} matches:", results.len());
            for result in results {
                println!("{}", result.path);
            }
        }
        cli::Command::Gui => {
            if let Err(e) = gui::run_gui(db) {
                error!("GUI Failed: {}", e);
            }
        }
        cli::Command::Daemon => {
            let mounts = Indexer::get_mounts();
            info!("Starting background watchers for {} mounts", mounts.len());
            
            let mut handles = Vec::new();
            for mount in mounts {
                let watcher_db = Database::new()?;
                let watcher = watcher::FileWatcher::new(watcher_db, mount);
                let handle = tokio::spawn(async move {
                    if let Err(e) = watcher.start_with_fallback().await {
                        error!("Watcher fatal error for mount: {}", e);
                    }
                });
                handles.push(handle);
            }
            
            // Wait for all watchers (they run indefinitely)
            for handle in handles {
                let _ = handle.await;
            }
        }
    }

    Ok(())
}
