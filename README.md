# All Linux Files (ALF)

**All Linux Files (ALF)** is a high-performance file indexing and search engine for Linux, inspired by the Windows "Everything" utility. It provides near-instant search results by maintaining a local database of the filesystem.

## Features
- **Fast Initial Scan**: Optimized directory traversal to build the initial index.
- **Real-Time Updates**: Monitors filesystem changes using `inotify` to keep the index synchronized.
- **Instant Search**: Sub-millisecond query resolution using SQLite with FTS5 (Full Text Search).
- **Dual Implementation**: 
  - **Python**: Rapid prototype with CLI and Web GUI.
  - **Rust**: Production-grade, high-performance core for maximum efficiency.

## Project Structure
- `src/`: Python implementation (Prototype).
- `linux_everything_rust/`: Rust implementation (High-performance core).
- `assets/`: UI assets and systemd service templates.

## Quick Start
### Python (Prototype)
```bash
python3 src/main.py scan
python3 src/main.py search "query"
```

### Rust (Core)
```bash
cd linux_everything_rust
cargo run --release -- scan
cargo run --release -- search "query"
```

## License
MIT
