# Rust Implementation Plan for Linux Everything

## Overview

This document outlines the architecture and implementation plan for creating a production-grade Rust version of the Linux Everything search tool. The Rust version will address the performance and distribution limitations of the Python prototype while maintaining full feature parity.

## Architecture

### Core Components

#### 1. Indexer Module
- **Purpose**: High-speed filesystem scanning and indexing
- **Implementation**: Use the `ignore` crate (same engine as ripgrep)
- **Features**:
  - Parallel directory traversal
  - Smart exclusion patterns
  - Progress reporting
  - Batch processing for large filesystems

#### 2. Database Module
- **Purpose**: Storage and retrieval of file metadata
- **Implementation**: Use `rusqlite` with FTS5 extension
- **Features**:
  - Thread-safe connection pooling
  - Efficient bulk inserts
  - Full-text search capabilities
  - Schema migration support

#### 3. Watcher Module
- **Purpose**: Real-time filesystem monitoring
- **Implementation**: Use `notify` crate with fallback mechanisms
- **Features**:
  - Inotify-based monitoring for Linux
  - Smart delta watching (curated directories only)
  - Automatic polling fallback
  - Event debouncing

#### 4. Web Interface
- **Purpose**: User-friendly search interface
- **Implementation**: Use Axum web framework
- **Features**:
  - Embedded static assets
  - Real-time updates via Server-Sent Events
  - RESTful API endpoints
  - Responsive design

### Project Structure

```
linux_everything_rust/
├── Cargo.toml
├── src/
│   ├── main.rs
│   ├── indexer/
│   │   ├── mod.rs
│   │   ├── scanner.rs
│   │   └── progress.rs
│   ├── database/
│   │   ├── mod.rs
│   │   ├── schema.rs
│   │   └── queries.rs
│   ├── watcher/
│   │   ├── mod.rs
│   │   ├── inotify.rs
│   │   └── poller.rs
│   ├── web/
│   │   ├── mod.rs
│   │   ├── api.rs
│   │   └── static.rs
│   └── cli/
│       ├── mod.rs
│       └── commands.rs
├── assets/
│   ├── index.html
│   ├── styles.css
│   └── script.js
└── build.rs
```

## Implementation Phases

### Phase 1: Core Engine (2-3 weeks)
- Implement indexer with `ignore` crate
- Create database module with `rusqlite`
- Build basic CLI interface
- Implement initial scanning functionality

### Phase 2: Real-time Monitoring (1-2 weeks)
- Implement inotify-based watcher
- Add polling fallback mechanism
- Integrate with database for updates
- Test edge cases and error handling

### Phase 3: Web Interface (2 weeks)
- Set up Axum web server
- Create API endpoints for search and monitoring
- Embed static assets in binary
- Implement real-time updates

### Phase 4: Advanced Features (1-2 weeks)
- Add regex search support
- Implement type filtering
- Add systemd service integration
- Implement performance optimizations

## Technical Details

### Indexer Implementation

```rust
use ignore::WalkBuilder;
use std::path::Path;

pub struct Indexer {
    db: Database,
    root_path: String,
    ignore_patterns: Vec<String>,
}

impl Indexer {
    pub fn new(db: Database, root_path: String) -> Self {
        Self {
            db,
            root_path,
            ignore_patterns: vec![
                ".git".to_string(),
                ".venv".to_string(),
                "node_modules".to_string(),
                "__pycache__".to_string(),
            ],
        }
    }

    pub fn scan(&self) -> Result<(), Box<dyn std::error::Error>> {
        let walker = WalkBuilder::new(&self.root_path)
            .add_custom_ignore_filename(".ignore")
            .build();

        for result in walker {
            let entry = result?;
            let path = entry.path();
            let metadata = entry.metadata()?;

            if metadata.is_file() {
                self.db.insert_file(
                    path.to_string_lossy().into_owned(),
                    path.file_name().unwrap().to_string_lossy().into_owned(),
                    false,
                    metadata.modified()?,
                )?;
            }
        }

        Ok(())
    }
}
```

### Database Schema

```sql
CREATE TABLE IF NOT EXISTS files (
    path TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    is_dir INTEGER NOT NULL,
    modified_time REAL NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS search_index
USING fts5(name, path, content='files', content_rowid='rowid');
```

### Watcher Implementation

```rust
use notify::{RecommendedWatcher, RecursiveMode, Watcher, Event};
use std::sync::mpsc::channel;
use std::time::Duration;

pub struct FileWatcher {
    db: Database,
    watch_path: String,
}

impl FileWatcher {
    pub fn new(db: Database, watch_path: String) -> Self {
        Self { db, watch_path }
    }

    pub fn start(&self) -> Result<(), Box<dyn std::error::Error>> {
        let (tx, rx) = channel();

        let mut watcher = RecommendedWatcher::new(tx, notify::Config::default())?;
        watcher.watch(&self.watch_path, RecursiveMode::Recursive)?;

        for event in rx {
            match event {
                Ok(Event {
                    kind: notify::EventKind::Create(_) | notify::EventKind::Modify(_),
                    paths,
                    ..
                }) => {
                    for path in paths {
                        if let Ok(metadata) = std::fs::metadata(&path) {
                            if metadata.is_file() {
                                self.db.update_file(
                                    path.to_string_lossy().into_owned(),
                                    path.file_name().unwrap().to_string_lossy().into_owned(),
                                    false,
                                    metadata.modified()?,
                                )?;
                            }
                        }
                    }
                }
                Err(e) => eprintln!("Watch error: {:?}", e),
            }
        }

        Ok(())
    }
}
```

## Performance Targets

- **Indexing Speed**: 10x-50x faster than Python version
- **Memory Usage**: <5MB idle, <50MB during active scan
- **Search Latency**: <1ms for FTS5 queries
- **Startup Time**: <100ms

## Distribution

- **Packaging**: Single binary with embedded assets
- **Installation**: Simple copy to `/usr/bin/linux-everything`
- **Dependencies**: None (fully static build)
- **Platform Support**: Linux x86_64, ARM64

## Next Steps

1. Set up Rust project structure
2. Implement core indexer module
3. Create database integration
4. Build basic CLI interface
5. Test and optimize performance

This plan provides a clear roadmap for creating a production-grade Rust version of the Linux Everything search tool that will match or exceed the performance and reliability of the original Windows version.