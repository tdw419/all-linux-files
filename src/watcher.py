import sys
import time
import os
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
from .db import Database
from .indexer import Indexer

# Directories to always ignore
IGNORED_DIRS = {'.git', '.venv', 'node_modules', '__pycache__', '.idea', '.vscode', 'dist', 'build'}

class SafeDatabaseEventHandler(PatternMatchingEventHandler):
    """Handles file system events and updates the DB, ignoring junk."""
    
    def __init__(self):
        # Ignore junk directories and hidden files/dirs starting with .
        ignore_patterns = [f"*/{d}/*" for d in IGNORED_DIRS] + ["*/.*", "*.tmp", "*.swp"]
        super().__init__(ignore_patterns=ignore_patterns, ignore_directories=True, case_sensitive=True)

    def _get_db(self):
        return Database()

    def on_any_event(self, event):
        # Manual check to be sure we don't process ignored dirs
        # (PatternMatchingEventHandler handles most, but safe to be sure)
        if any(ignored in event.src_path.split(os.sep) for ignored in IGNORED_DIRS):
            return

    def on_created(self, event):
        self._update_db(event.src_path)

    def on_moved(self, event):
        self._update_db(event.dest_path)
    
    def on_modified(self, event):
        self._update_db(event.src_path)

    def _update_db(self, path):
        try:
            db = self._get_db()
            db.bulk_insert([(path, os.path.basename(path), 0, time.time())])
            db.close()
        except Exception:
            pass

def start_daemon_watcher(path):
    """Start watcher in a background thread with automatic fallback"""
    def watcher_loop():
        while True:
            try:
                observer = Observer()
                event_handler = SafeDatabaseEventHandler()
                observer.schedule(event_handler, path, recursive=True)
                observer.start()
                print(f"Watcher started for {path}")
                observer.join()
            except Exception as e:
                print(f"Watcher failed: {e}. Starting polling fallback...")
                # Polling fallback - rescan the directory every 10 seconds
                while True:
                    try:
                        print(f"Polling fallback: rescanning {path}")
                        db = Database()
                        indexer = Indexer(db, path)
                        indexer.scan()
                        db.close()
                        print(f"Polling rescan completed for {path}")
                    except Exception as scan_e:
                        print(f"Polling scan failed: {scan_e}")
                    time.sleep(10)

    # Start the watcher loop in a daemon thread
    import threading
    thread = threading.Thread(target=watcher_loop, daemon=True)
    thread.start()
    return thread

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    start_daemon_watcher(path)
    while True:
        time.sleep(1)
