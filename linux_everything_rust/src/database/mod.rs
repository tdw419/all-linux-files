use rusqlite::{Connection, Result, params};
use std::path::PathBuf;
use serde::Serialize;

#[derive(Debug, Serialize)]
pub struct SearchResult {
    pub path: String,
    pub modified_time: f64,
    pub size: u64,
}

pub struct Database {
    conn: Connection,
}

impl Database {
    pub fn new() -> Result<Self> {
        let db_path = PathBuf::from("linux_everything.db");
        Self::open_at(db_path)
    }

    fn open_at(db_path: PathBuf) -> Result<Self> {
        let conn = Connection::open(&db_path)?;

        // Enable WAL mode for better concurrency
        conn.pragma_update(None, "journal_mode", "WAL")?;
        conn.pragma_update(None, "synchronous", "NORMAL")?;
        conn.pragma_update(None, "temp_store", "MEMORY")?;

        // Create tables
        Self::setup_schema(&conn)?;

        Ok(Self { conn })
    }

    fn setup_schema(conn: &Connection) -> Result<()> {
        // Create main files table
        conn.execute(
            "CREATE TABLE IF NOT EXISTS files (
                path TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                modified_time REAL NOT NULL,
                is_dir INTEGER NOT NULL,
                size INTEGER NOT NULL DEFAULT 0
            )",
            [],
        )?;

        // Add size column if it doesn't exist, for backward compatibility
        if conn.query_row("SELECT sql FROM sqlite_master WHERE name='files' AND type='table'", [], |row| {
            let sql: String = row.get(0)?;
            Ok(!sql.contains("size"))
        }).unwrap_or(false) {
            conn.execute("ALTER TABLE files ADD COLUMN size INTEGER NOT NULL DEFAULT 0", [])?;
        }

        // Create FTS5 virtual table for search
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS search_index
             USING fts5(name, path, content='files', content_rowid='rowid')",
            [],
        )?;

        // dir_state for sweep progress
        conn.execute(
            "CREATE TABLE IF NOT EXISTS dir_state (
                path TEXT PRIMARY KEY,
                last_mtime REAL NOT NULL,
                last_scan_ts REAL NOT NULL
            )",
            [],
        )?;

        // recent_events for UX
        conn.execute(
            "CREATE TABLE IF NOT EXISTS recent_events (
                path TEXT PRIMARY KEY,
                mtime REAL NOT NULL,
                ts REAL NOT NULL,
                kind INTEGER NOT NULL
            )",
            [],
        )?;

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_recent_ts ON recent_events(ts DESC)",
            [],
        )?;

        Ok(())
    }

    pub fn insert_batch(&mut self, files: &[FileEntry]) -> Result<()> {
        let tx = self.conn.transaction()?;
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs_f64();

        // Insert into main table
        for file in files {
            tx.execute(
                "INSERT OR REPLACE INTO files (path, name, modified_time, is_dir, size) VALUES (?1, ?2, ?3, ?4, ?5)",
                params![file.path, file.name, file.modified_time, file.is_dir, file.size],
            )?;

            // Also upsert into recent_events
            tx.execute(
                "INSERT OR REPLACE INTO recent_events (path, mtime, ts, kind) VALUES (?1, ?2, ?3, ?4)",
                params![file.path, file.modified_time, now, 1],
            )?;
        }

        // Insert into FTS index
        for file in files {
            tx.execute(
                "INSERT INTO search_index (name, path) VALUES (?1, ?2)",
                params![file.name, file.path],
            )?;
        }

        tx.commit()?;
        Ok(())
    }

    pub fn search(&self, query: &str, filter_type: Option<&str>) -> Result<Vec<SearchResult>> {
        let mut results = Vec::new();

        // Handle regex search
        if query.starts_with("re:") {
            let pattern = &query[3..];
            let mut stmt = self.conn.prepare(&format!(
                "SELECT path, modified_time, size FROM files WHERE name REGEXP ? {} LIMIT 100",
                Self::get_filter_clause(filter_type)
            ))?;

            let mut rows = stmt.query(params![pattern])?;
            while let Some(row) = rows.next()? {
                results.push(SearchResult {
                    path: row.get(0)?,
                    modified_time: row.get(1)?,
                    size: row.get(2)?,
                });
            }
        } else {
            // Standard FTS search
            let cleaned_query = query.replace('"', "''");
            let fts_query = format!("\"{}\"*", cleaned_query);

            let filter_clause = Self::get_filter_clause(filter_type);
            let sql = format!(
                "SELECT path, modified_time, size
                 FROM files
                 WHERE rowid IN (
                     SELECT rowid FROM search_index WHERE search_index MATCH ? LIMIT 500
                 )
                 {} LIMIT 100",
                filter_clause
            );

            let mut stmt = self.conn.prepare(&sql)?;
            let mut rows = stmt.query(params![fts_query])?;

            while let Some(row) = rows.next()? {
                results.push(SearchResult {
                    path: row.get(0)?,
                    modified_time: row.get(1)?,
                    size: row.get(2)?,
                });
            }
        }

        Ok(results)
    }

    fn get_filter_clause(filter_type: Option<&str>) -> String {
        match filter_type {
            Some("image") => " AND (name LIKE '%.jpg' OR name LIKE '%.jpeg' OR name LIKE '%.png' OR name LIKE '%.gif' OR name LIKE '%.bmp' OR name LIKE '%.webp' OR name LIKE '%.svg' OR name LIKE '%.tiff' OR name LIKE '%.ico')",
            Some("audio") => " AND (name LIKE '%.mp3' OR name LIKE '%.wav' OR name LIKE '%.flac' OR name LIKE '%.aac' OR name LIKE '%.ogg' OR name LIKE '%.m4a' OR name LIKE '%.wma')",
            Some("video") => " AND (name LIKE '%.mp4' OR name LIKE '%.mkv' OR name LIKE '%.avi' OR name LIKE '%.mov' OR name LIKE '%.webm' OR name LIKE '%.flv' OR name LIKE '%.wmv' OR name LIKE '%.m4v')",
            Some("doc") => " AND (name LIKE '%.pdf' OR name LIKE '%.doc' OR name LIKE '%.docx' OR name LIKE '%.txt' OR name LIKE '%.md' OR name LIKE '%.rtf' OR name LIKE '%.odt' OR name LIKE '%.xls' OR name LIKE '%.xlsx' OR name LIKE '%.ppt' OR name LIKE '%.pptx' OR name LIKE '%.csv' OR name LIKE '%.json' OR name LIKE '%.xml')",
            _ => "",
        }.to_string()
    }

    pub fn get_recent(&self, limit: usize) -> Result<Vec<SearchResult>> {
        let mut results = Vec::new();
        let mut stmt = self.conn.prepare(
            "SELECT r.path, r.mtime, f.size
             FROM recent_events r
             JOIN files f ON r.path = f.path
             ORDER BY r.ts DESC
             LIMIT ?"
        )?;

        let mut rows = stmt.query(params![limit])?;
        while let Some(row) = rows.next()? {
            results.push(SearchResult {
                path: row.get(0)?,
                modified_time: row.get(1)?,
                size: row.get(2)?,
            });
        }

        Ok(results)
    }

    pub fn get_all_files(&self, limit: usize) -> Result<Vec<SearchResult>> {
        let mut results = Vec::new();
        let mut stmt = self.conn.prepare(
            "SELECT path, modified_time, size FROM files ORDER BY modified_time DESC LIMIT ?"
        )?;

        let mut rows = stmt.query(params![limit])?;
        while let Some(row) = rows.next()? {
            results.push(SearchResult {
                path: row.get(0)?,
                modified_time: row.get(1)?,
                size: row.get(2)?,
            });
        }

        Ok(results)
    }

    pub fn get_oldest_dirs(&self, limit: usize) -> Result<Vec<(String, f64)>> {
        let mut results = Vec::new();
        let mut stmt = self.conn.prepare(
            "SELECT path, last_mtime FROM dir_state ORDER BY last_scan_ts ASC LIMIT ?"
        )?;
        let mut rows = stmt.query(params![limit])?;
        while let Some(row) = rows.next()? {
            results.push((row.get(0)?, row.get(1)?));
        }
        Ok(results)
    }

    pub fn update_dir_state(&mut self, path: &str, mtime: f64, ts: f64) -> Result<()> {
        self.conn.execute(
            "INSERT OR REPLACE INTO dir_state (path, last_mtime, last_scan_ts) VALUES (?1, ?2, ?3)",
            params![path, mtime, ts],
        )?;
        Ok(())
    }
}

#[derive(Debug)]
pub struct FileEntry {
    pub path: String,
    pub name: String,
    pub modified_time: f64,
    pub is_dir: i32,
    pub size: u64,
}