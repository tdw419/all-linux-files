use clap::{Parser, Subcommand};
use std::path::PathBuf;

#[derive(Parser)]
#[command(name = "linux_everything")]
#[command(about = "Linux Everything - Instant File Search", long_about = None)]
pub struct Cli {
    #[command(subcommand)]
    pub command: Command,
}

#[derive(Subcommand)]
pub enum Command {
    /// Re-index the filesystem
    Scan {
        /// Path to index (default: /)
        #[arg(default_value = "/")]
        path: PathBuf,
    },
    /// Search for files
    Search {
        /// Search term
        query: String,
    },
    /// Launch GUI interface
    Gui,
    /// Start the background file monitor daemon
    Daemon,
}