import sqlite3
import os

DB_PATH = os.path.expanduser("~/.linux_everything.db")

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        # Register REGEX function for advanced search
        self.conn.create_function("REGEXP", 2, self._regexp)
        self.cursor = self.conn.cursor()
        self._setup()

    def _regexp(self, expr, item):
        import re
        try:
            reg = re.compile(expr)
            return reg.search(item) is not None
        except Exception:
            return False

    def _setup(self):
        # SPEED OPTIMIZATIONS
        self.conn.execute("PRAGMA journal_mode = WAL;")  # Write-Ahead Logging for concurrency
        self.conn.execute("PRAGMA synchronous = NORMAL;") 
        self.conn.execute("PRAGMA temp_store = MEMORY;")

        # Create main table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS files (
                path TEXT PRIMARY KEY,
                name TEXT,
                modified_time REAL,
                is_dir INTEGER
            )
        """)
        
        # Schema Migration: Add modified_time if it doesn't exist (for existing users)
        try:
            self.conn.execute("ALTER TABLE files ADD COLUMN modified_time REAL")
        except sqlite3.OperationalError:
            pass # Column likely exists

        # Create FTS5 virtual table for instant substring search
        try:
            self.conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS search_index 
                USING fts5(name, path, content='files', content_rowid='rowid');
            """)
        except sqlite3.OperationalError:
            print("Warning: FTS5 not supported. Search will be slower.")

        self.conn.commit()

    def bulk_insert(self, file_list):
        """
        file_list: list of tuples (path, name, is_dir, modified_time)
        """
        # Upsert or ignore
        self.conn.executemany("""
            INSERT OR REPLACE INTO files (path, name, is_dir, modified_time) VALUES (?, ?, ?, ?)
        """, file_list)

    def _rebuild_simple_schema(self):
        # Helper to ensure we have a clean simple schema for this run
        self.conn.execute("DROP TABLE IF EXISTS search_index")
        self.conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS search_index 
            USING fts5(name, path);
        """)
        self.conn.commit()

    def insert_batch(self, file_list):
        # file_list: [(path, name, is_dir, modified_time)]
        
        # 1. Insert into main table
        self.conn.executemany("""
            INSERT OR REPLACE INTO files (path, name, is_dir, modified_time) VALUES (?, ?, ?, ?)
        """, file_list)
        
        # 2. Insert into FTS index (name, path)
        # Prepare data for FTS: just name and path
        fts_data = [(x[1], x[0]) for x in file_list]
        self.conn.executemany("""
            INSERT INTO search_index (name, path) VALUES (?, ?)
        """, fts_data)
        
        self.conn.commit()

    def search(self, query, filter_type=None):
        # Type filters
        extensions = {
            'image': ('jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg', 'tiff', 'ico'),
            'audio': ('mp3', 'wav', 'flac', 'aac', 'ogg', 'm4a', 'wma'),
            'video': ('mp4', 'mkv', 'avi', 'mov', 'webm', 'flv', 'wmv', 'm4v'),
            'doc': ('pdf', 'doc', 'docx', 'txt', 'md', 'rtf', 'odt', 'xls', 'xlsx', 'ppt', 'pptx', 'csv', 'json', 'xml')
        }

        # Build filter clause
        filter_sql = ""
        params = []
        if filter_type and filter_type in extensions:
            # Construct: AND (name LIKE '%.jpg' OR name LIKE '%.png' ...)
            clauses = [f"name LIKE '%.{ext}'" for ext in extensions[filter_type]]
            filter_sql = " AND (" + " OR ".join(clauses) + ")"

        # Check for Regex prefix
        if query.startswith("re:"):
            pattern = query[3:]
            try:
                # Regex search on main table
                sql = f"SELECT path, modified_time FROM files WHERE name REGEXP ? {filter_sql} LIMIT 100"
                return self.cursor.execute(sql, (pattern,)).fetchall()
            except Exception as e:
                return [("Error in Regex: " + str(e),)]
        
        # Standard FTS search
        # FTS syntax check: clean up query to prevent syntax errors
        cleaned_query = query.replace('"', '""')
        q = f'"{cleaned_query}"*' 
        
        try:
            sql = f"""
                SELECT path, modified_time 
                FROM files 
                WHERE rowid IN (
                    SELECT rowid FROM search_index WHERE search_index MATCH ? LIMIT 500
                )
                {filter_sql}
                LIMIT 100
            """
            return self.cursor.execute(sql, (q,)).fetchall()
        except sqlite3.OperationalError as e:
            return [("Error: " + str(e),)]

    def get_recent(self, limit=50):
        """Get most recently modified files"""
        try:
            return self.cursor.execute("""
                SELECT path, modified_time 
                FROM files 
                WHERE is_dir = 0 
                ORDER BY modified_time DESC 
                LIMIT ?
            """, (limit,)).fetchall()
        except Exception as e:
            return []

    def close(self):
        self.conn.close()
