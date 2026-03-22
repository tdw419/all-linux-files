import os
import time
from .db import Database

IGNORE_DIRS = {
    '/proc', '/sys', '/dev', '/run', '/tmp', 
    '/var/lib/docker', '/snap', 
    '/mnt', '/media' # Avoid external drives for initial test? better safe.
}

class Indexer:
    def __init__(self, db, root_path="/"):
        self.db = db
        self.root_path = root_path
        self.batch_size = 20000
        self.buffer = []

    def scan(self, status_callback=None):
        print(f"Starting scan of {self.root_path}...")
        
        # Ensure schema is correct for our batch logic
        self.db._rebuild_simple_schema()
        
        start_time = time.time()
        count = 0
        
        for root, dirs, files in os.walk(self.root_path, topdown=True):
            # Prune ignored directories
            # We must modify 'dirs' in-place to affect os.walk traversal
            dirs[:] = [d for d in dirs if os.path.join(root, d) not in IGNORE_DIRS]
            
            # Update status occasionally (every dir or so, or every N files)
            # Just sending the current root is often enough context without slowing down too much
            if status_callback and count % 100 == 0:
                 status_callback(f"Scanning: {root} ({count} items)")

            # Add files
            for name in files:
                full_path = os.path.join(root, name)
                try:
                    mtime = os.path.getmtime(full_path)
                except OSError:
                    mtime = 0.0
                self.buffer.append((full_path, name, 0, mtime))
                count += 1
                
                if len(self.buffer) >= self.batch_size:
                    self.flush()
                    if status_callback:
                        status_callback(f"Indexing batch... ({count} total)")
                    else:
                        print(f"Indexed {count} items...", end='\r')

            # Add directories
            for name in dirs:
                full_path = os.path.join(root, name)
                self.buffer.append((full_path, name, 1, 0.0))
                count += 1
        
        self.flush()
        duration = time.time() - start_time
        msg = f"Scan complete. {count} items indexed in {duration:.2f} seconds."
        print("\n" + msg)
        if status_callback:
            status_callback(msg)

    def flush(self):
        if self.buffer:
            self.db.insert_batch(self.buffer)
            self.buffer = []
