#!/usr/bin/env python3
"""
Web-based GUI interface for Linux Everything search tool
Uses Flask for a simple web interface that works without system dependencies
"""

import os
import threading
from flask import Flask, render_template, request, jsonify
from .db import Database
from .indexer import Indexer
from .watcher import start_daemon_watcher

app = Flask(__name__)

# Global database connection
db = Database()
current_scan_status = "Idle"

@app.route('/')
def index():
    """Main search page"""
    return render_template('index.html')

@app.route('/scan_status', methods=['GET'])
def get_scan_status():
    return jsonify({"status": current_scan_status})

@app.route('/search', methods=['GET'])
def search():
    """Search endpoint"""
    query = request.args.get('q', '').strip()
    filter_type = request.args.get('type', '').strip()
    
    if not query:
        return jsonify([])

    local_db = None
    try:
        local_db = Database()
        # Pass filter_type to search
        results = local_db.search(query, filter_type=filter_type)
        
        # Convert to list of dicts for JSON serialization
        search_results = [{"path": row[0], "time": row[1] if len(row) > 1 else 0} for row in results]
        return jsonify(search_results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if local_db:
            try:
                local_db.close()
            except:
                pass

@app.route('/recent', methods=['GET'])
def recent():
    """Get recent files"""
    local_db = None
    try:
        local_db = Database()
        results = local_db.get_recent(limit=100)
        # Convert to list of dicts for JSON serialization
        recent_results = [{"path": row[0], "time": row[1]} for row in results]
        return jsonify(recent_results)
    except Exception as e:
        print(f"Error in recent: {e}") # Debug print
        return jsonify({"error": str(e)}), 500
    finally:
        if local_db:
            try:
                local_db.close()
            except:
                pass

@app.route('/scan', methods=['POST'])
def start_scan():
    """Start filesystem scan"""
    path = request.json.get('path', '/')
    global current_scan_status

    def update_status(msg):
        global current_scan_status
        current_scan_status = msg

    def scan_task():
        global current_scan_status
        thread_db = None
        try:
            current_scan_status = "Starting scan..."
            # Create a new database connection for this thread to avoid SQLite threading errors
            thread_db = Database()
            indexer = Indexer(thread_db, path)
            indexer.scan(status_callback=update_status)
            current_scan_status = "Scan completed"
            return {"status": "success", "message": "Scan completed"}
        except Exception as e:
            current_scan_status = f"Error: {str(e)}"
            return {"status": "error", "message": str(e)}
        finally:
            if thread_db:
                thread_db.close()

    # Run scan in background thread
    thread = threading.Thread(target=scan_task)
    thread.start()

    return jsonify({"status": "started", "message": "Scan started in background"})

def create_templates_dir():
    """Create templates directory if it doesn't exist"""
    templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
    os.makedirs(templates_dir, exist_ok=True)
    return templates_dir

def create_html_template():
    """Create the HTML template"""
    templates_dir = create_templates_dir()
    template_path = os.path.join(templates_dir, 'index.html')

    html_content = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Linux Everything</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 800px;
            margin: 0 auto;
        }

        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }

        .header h1 {
            font-size: 2.5rem;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }

        .search-container {
            background: white;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            overflow: hidden;
        }

        .search-box {
            display: flex;
            padding: 20px;
            background: #f8f9fa;
        }

        .search-box input {
            flex: 1;
            padding: 15px 20px;
            border: none;
            border-radius: 8px;
            font-size: 1.1rem;
            outline: none;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }

        .live-monitor {
            margin-left: 15px;
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.95rem;
            color: #555;
            cursor: pointer;
            user-select: none;
        }

        .search-box button {
            margin-left: 10px;
            padding: 15px 30px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 1.1rem;
            cursor: pointer;
            transition: all 0.3s;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        
        .recent-btn {
            background: linear-gradient(135deg, #FF9800 0%, #F44336 100%) !important;
        }
        
        .filter-bar {
            display: flex;
            gap: 10px;
            padding: 0 20px 20px 20px;
            background: #f8f9fa;
        }
        
        .filter-chip {
            padding: 6px 16px;
            border-radius: 20px;
            border: 1px solid #dee2e6;
            background: white;
            color: #495057;
            cursor: pointer;
            transition: all 0.2s;
            font-size: 0.9rem;
        }
        
        .filter-chip:hover {
            background: #e9ecef;
        }
        
        .filter-chip.active {
            background: #667eea;
            color: white;
            border-color: #667eea;
            box-shadow: 0 2px 4px rgba(102, 126, 234, 0.3);
        }

        .search-box button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }

        .scan-section {
            padding: 15px 20px;
            background: #f8f9fa;
            border-top: 1px solid #e9ecef;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .scan-section input {
            flex: 1;
            padding: 10px 15px;
            border: 1px solid #ddd;
            border-radius: 5px;
            margin-right: 10px;
        }

        .scan-section button {
            padding: 10px 20px;
            background: #28a745;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
        }

        .results {
            max-height: 500px;
            overflow-y: auto;
        }

        .result-item {
            padding: 15px 20px;
            border-bottom: 1px solid #e9ecef;
            cursor: pointer;
            transition: background 0.2s;
            display: flex;
            justify-content: space-between;
        }

        .result-item:hover {
            background: #f8f9fa;
        }

        .result-item:last-child {
            border-bottom: none;
        }

        .result-path {
            color: #495057;
            font-size: 0.95rem;
            word-break: break-all;
        }
        
        .result-time {
            font-size: 0.8rem;
            color: #999;
            margin-left: 10px;
            min-width: 150px;
            text-align: right;
        }

        .status {
            padding: 15px 20px;
            text-align: center;
            color: #6c757d;
            font-size: 0.9rem;
        }

        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid rgba(0,0,0,.1);
            border-radius: 50%;
            border-top-color: #667eea;
            animation: spin 1s ease-in-out infinite;
            margin-left: 10px;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        .no-results {
            padding: 30px;
            text-align: center;
            color: #6c757d;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Linux Everything</h1>
            <p>Instant file search for Linux</p>
        </div>

        <div class="search-container">
            <div class="search-box">
                <input type="text" id="searchInput" placeholder="Search for files..." autocomplete="off">
                <button onclick="searchFiles()">Search</button>
                <button onclick="showRecent()" class="recent-btn">Recent</button>
                <label class="live-monitor">
                    <input type="checkbox" id="autoRefresh" onchange="toggleAutoRefresh(this)"> Live
                </label>
            </div>
            
            <div class="filter-bar">
                <button class="filter-chip active" onclick="setFilter('')">All</button>
                <button class="filter-chip" onclick="setFilter('image')">Images</button>
                <button class="filter-chip" onclick="setFilter('audio')">Audio</button>
                <button class="filter-chip" onclick="setFilter('video')">Video</button>
                <button class="filter-chip" onclick="setFilter('doc')">Docs</button>
            </div>

            <div class="scan-section">
                <input type="text" id="scanPath" placeholder="Path to scan (e.g., /home)" value="/">
                <button onclick="startScan()">Scan Filesystem</button>
            </div>

            <div class="results" id="results">
                <div class="no-results">
                    Enter a search query or click Recent
                </div>
            </div>

            <div class="status" id="status">
                Ready
            </div>
        </div>
    </div>

    <script>
        let searchTimeout;
        let currentFilter = '';
        let refreshInterval;
        const resultsDiv = document.getElementById('results');
        const statusDiv = document.getElementById('status');
        const searchInput = document.getElementById('searchInput');

        function toggleAutoRefresh(cb) {
            if (cb.checked) {
                showRecent(true);
                refreshInterval = setInterval(() => showRecent(true), 2000);
            } else {
                clearInterval(refreshInterval);
            }
        }

        function setFilter(type) {
            currentFilter = type;
            // Update UI
            document.querySelectorAll('.filter-chip').forEach(chip => {
                chip.classList.remove('active');
                // Simple heuristic to match button text/onclick
                // Or better: check the onclick attribute content
                if (chip.getAttribute('onclick').includes(`'${type}'`)) {
                    chip.classList.add('active');
                }
            });
            // trigger search if there is a query
            if (searchInput.value.trim()) {
                searchFiles();
            }
        }

        function formatTime(timestamp) {
            if (!timestamp) return '';
            return new Date(timestamp * 1000).toLocaleString();
        }

        function renderResults(data) {
             if (data.length === 0) {
                resultsDiv.innerHTML = '<div class="no-results">No results found</div>';
                statusDiv.textContent = 'No results found';
                return;
            }

            // Display results
            resultsDiv.innerHTML = data.map(item =>
                `<div class="result-item" onclick="openFile('${item.path.replace(/'/g, "\\'")}')">
                    <div class="result-path">${item.path}</div>
                    ${item.time ? `<div class="result-time">${formatTime(item.time)}</div>` : ''}
                </div>`
            ).join('');

            statusDiv.textContent = `Found ${data.length} results`;
        }

        function showRecent(isAuto=false) {
             if (!isAuto) {
                 statusDiv.innerHTML = 'Fetching recent files... <span class="loading"></span>';
             }
             // Add cache buster
             fetch('/recent?_=' + new Date().getTime())
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        if (!isAuto) resultsDiv.innerHTML = `<div class="no-results">Error: ${data.error}</div>`;
                        statusDiv.textContent = 'Error occurred';
                        return;
                    }
                    // renderResults replaces innerHTML. 
                    renderResults(data);
                    if (isAuto) {
                         statusDiv.textContent = `Found ${data.length} results (Live: ${new Date().toLocaleTimeString()})`;
                    }
                })
                .catch(error => {
                     if (!isAuto) resultsDiv.innerHTML = `<div class="no-results">Error: ${error.message}</div>`;
                     statusDiv.textContent = 'Failed to fetch recent files';
                });
        }

        function searchFiles() {
            const query = searchInput.value.trim();
            if (!query) {
                resultsDiv.innerHTML = '<div class="no-results">Enter a search query to find files</div>';
                return;
            }

            // Show loading state
            statusDiv.innerHTML = 'Searching... <span class="loading"></span>';

            // Debounce search
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                const typeParam = currentFilter ? `&type=${currentFilter}` : '';
                fetch(`/search?q=${encodeURIComponent(query)}${typeParam}`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.error) {
                            resultsDiv.innerHTML = `<div class="no-results">Error: ${data.error}</div>`;
                            statusDiv.textContent = 'Error occurred';
                            return;
                        }

                        renderResults(data);
                    })
                    .catch(error => {
                        resultsDiv.innerHTML = `<div class="no-results">Error: ${error.message}</div>`;
                        statusDiv.textContent = 'Search failed';
                    });
            }, 300);
        }

        function startScan() {
            const path = document.getElementById('scanPath').value.trim();
            if (!path) {
                statusDiv.textContent = 'Please enter a path to scan';
                return;
            }

            statusDiv.innerHTML = 'Starting scan... <span class="loading"></span>';

            fetch('/scan', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({path: path})
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'started') {
                    statusDiv.textContent = 'Scan started in background';
                    pollStatus();
                } else {
                    statusDiv.textContent = data.message || 'Scan failed';
                }
            })
            .catch(error => {
                statusDiv.textContent = `Scan error: ${error.message}`;
            });
        }
        
        function pollStatus() {
            fetch('/scan_status')
                .then(response => response.json())
                .then(data => {
                    statusDiv.textContent = data.status;
                    if (data.status.startsWith('Scanning') || data.status.startsWith('Starting') || data.status.startsWith('Indexing')) {
                         setTimeout(pollStatus, 500);
                    }
                })
                .catch(e => console.log(e));
        }

        function openFile(path) {
            // In a real application, this would open the file
            // For now, we'll just show a notification
            statusDiv.textContent = `Would open: ${path}`;
        }

        // Add event listener for Enter key
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                searchFiles();
            }
        });
    </script>
</body>
</html>
'''
    with open(template_path, 'w') as f:
        f.write(html_content)

def main():
    """Main function to start the web GUI"""
    # Create HTML template
    create_html_template()
    
    # Start background monitor (Curated List Strategy)
    try:
        # We watch only the source code for this demo to avoid inotify limits
        # In a real app, this would be user-configurable list of paths
        project_root = os.getcwd() 
        src_dir = os.path.join(project_root, 'src')
        
        target_dir = src_dir if os.path.exists(src_dir) else project_root
        
        print(f" * Starting Optimized Live Monitor for {target_dir}...")
        start_daemon_watcher(target_dir)
        print(f" * Live Monitor ACTIVE for {target_dir}")
            
    except Exception as e:
        print(f" * Failed to start monitor: {e}")

    # Start Flask app
    app.run(debug=True, host='0.0.0.0', port=5001)

if __name__ == "__main__":
    main()