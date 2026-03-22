#!/usr/bin/env python3
"""
GUI interface for Linux Everything search tool
Uses PyQt6 for a native-looking interface
"""

import sys
import os
import threading
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                            QLineEdit, QPushButton, QListWidget, QLabel,
                            QWidget, QFileDialog, QMessageBox, QProgressBar)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon

from .db import Database
from .indexer import Indexer

class IndexerThread(QThread):
    """Thread for running the indexer in background"""
    progress_signal = pyqtSignal(int)
    message_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, db, root_path):
        super().__init__()
        self.db = db
        self.root_path = root_path
        self.indexer = Indexer(db, root_path)

    def run(self):
        try:
            self.message_signal.emit(f"Starting scan of {self.root_path}...")
            self.indexer.scan()
            self.message_signal.emit("Scan completed successfully!")
        except Exception as e:
            self.message_signal.emit(f"Error during scan: {str(e)}")
        finally:
            self.finished_signal.emit()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Linux Everything")
        self.setWindowIcon(QIcon.fromTheme("system-search"))
        self.setGeometry(100, 100, 800, 600)

        # Database connection
        self.db = Database()

        # UI Setup
        self.init_ui()

        # Start watcher in background
        self.start_watcher()

    def init_ui(self):
        """Initialize the user interface"""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        # Main layout
        layout = QVBoxLayout()
        main_widget.setLayout(layout)

        # Search section
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search for files...")
        self.search_input.returnPressed.connect(self.search_files)

        search_button = QPushButton("Search")
        search_button.clicked.connect(self.search_files)

        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_button)
        layout.addLayout(search_layout)

        # Results list
        self.results_list = QListWidget()
        self.results_list.itemDoubleClicked.connect(self.open_file)
        layout.addWidget(self.results_list)

        # Status bar
        self.status_label = QLabel("Ready")
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)

        status_layout = QHBoxLayout()
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.progress_bar)
        layout.addLayout(status_layout)

        # Control buttons
        control_layout = QHBoxLayout()
        scan_button = QPushButton("Scan Filesystem")
        scan_button.clicked.connect(self.start_scan)

        settings_button = QPushButton("Settings")
        # settings_button.clicked.connect(self.open_settings)

        control_layout.addWidget(scan_button)
        control_layout.addWidget(settings_button)
        layout.addLayout(control_layout)

    def start_watcher(self):
        """Start the file watcher in background"""
        try:
            from .watcher import start_watcher
            watcher_thread = threading.Thread(
                target=start_watcher,
                args=(self.db,),
                daemon=True
            )
            watcher_thread.start()
            self.status_label.setText("Watcher started")
        except Exception as e:
            self.status_label.setText(f"Watcher error: {str(e)}")

    def start_scan(self):
        """Start filesystem scan"""
        # Ask for directory to scan
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Directory to Scan",
            os.path.expanduser("~")
        )

        if path:
            self.indexer_thread = IndexerThread(self.db, path)
            self.indexer_thread.progress_signal.connect(self.update_progress)
            self.indexer_thread.message_signal.connect(self.update_status)
            self.indexer_thread.finished_signal.connect(self.scan_finished)

            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.search_input.setEnabled(False)

            self.indexer_thread.start()

    def update_progress(self, value):
        """Update progress bar"""
        self.progress_bar.setValue(value)

    def update_status(self, message):
        """Update status label"""
        self.status_label.setText(message)

    def scan_finished(self):
        """Handle scan completion"""
        self.progress_bar.setVisible(False)
        self.search_input.setEnabled(True)
        self.status_label.setText("Scan completed. Ready for search.")

    def search_files(self):
        """Search for files based on user input"""
        query = self.search_input.text().strip()
        if not query:
            return

        self.status_label.setText(f"Searching for '{query}'...")
        self.results_list.clear()

        try:
            results = self.db.search(query)
            if results:
                for row in results:
                    self.results_list.addItem(row[0])
                self.status_label.setText(f"Found {len(results)} results")
            else:
                self.status_label.setText("No results found")
        except Exception as e:
            self.status_label.setText(f"Search error: {str(e)}")

    def open_file(self, item):
        """Open the selected file"""
        file_path = item.text()
        if os.path.isdir(file_path):
            # Open directory in file manager
            os.system(f'xdg-open "{file_path}"')
        else:
            # Open file with default application
            os.system(f'xdg-open "{file_path}"')

    def closeEvent(self, event):
        """Clean up on window close"""
        self.db.close()
        event.accept()

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()