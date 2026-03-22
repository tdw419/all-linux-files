#!/bin/bash

# All Linux Files (ALF) - Launcher Script
# This script helps you quickly scan, search, or launch the GUI.

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_EXEC="python3"
RUST_DIR="$PROJECT_ROOT/linux_everything_rust"

function show_help() {
    echo "Usage: ./alf [command]"
    echo ""
    echo "Commands:"
    echo "  scan [path]   Index your files (default: ~)"
    echo "  search [term] Instant search for a filename"
    echo "  web           Launch the Web GUI (http://127.0.0.1:5000)"
    echo "  rust-scan     High-performance index using Rust"
    echo "  rust-search   High-performance search using Rust"
    echo "  setup         Install required dependencies"
    echo ""
}

case "$1" in
    setup)
        echo "Installing Python dependencies..."
        $PYTHON_EXEC -m pip install flask watchdog PyQt6
        echo "Checking Rust environment..."
        if command -v cargo &> /dev/null; then
            echo "Rust found. Ready to build."
        else
            echo "Warning: Rust (cargo) not found. Rust commands will not work."
        fi
        ;;
    scan)
        $PYTHON_EXEC "$PROJECT_ROOT/src/main.py" scan --path "${2:-~}"
        ;;
    search)
        if [ -z "$2" ]; then
            echo "Error: Please provide a search term."
            exit 1
        fi
        $PYTHON_EXEC "$PROJECT_ROOT/src/main.py" search "$2"
        ;;
    web)
        echo "Starting Web GUI at http://127.0.0.1:5000"
        $PYTHON_EXEC "$PROJECT_ROOT/src/main.py" web
        ;;
    rust-scan)
        cd "$RUST_DIR" && cargo run --release -- scan --path "${2:-~}"
        ;;
    rust-search)
        if [ -z "$2" ]; then
            echo "Error: Please provide a search term."
            exit 1
        fi
        cd "$RUST_DIR" && cargo run --release -- search "$2"
        ;;
    *)
        show_help
        ;;
esac
