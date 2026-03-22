import argparse
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db import Database
from src.indexer import Indexer

def main():
    parser = argparse.ArgumentParser(description="Linux Everything - Instant File Search")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # SCAN command
    scan_parser = subparsers.add_parser("scan", help="Re-index the filesystem")
    scan_parser.add_argument("--path", type=str, default=os.path.expanduser("~"), help="Path to index (default: ~)")

    # SEARCH command
    search_parser = subparsers.add_parser("search", help="Search for files")
    search_parser.add_argument("query", type=str, help="Search term")

    # GUI commands
    gui_parser = subparsers.add_parser("gui", help="Launch GUI interface")
    web_parser = subparsers.add_parser("web", help="Launch web-based GUI interface")

    args = parser.parse_args()

    db = Database()

    if args.command == "scan":
        indexer = Indexer(db, root_path=args.path)
        indexer.scan()
    elif args.command == "search":
        if not args.query:
            print("Please provide a query.")
            return

        results = db.search(args.query)
        print(f"Found {len(results)} matches:")
        for r in results:
            print(r[0])
    elif args.command == "gui":
        try:
            from src.gui import main as gui_main
            gui_main()
        except ImportError:
            print("Error: PyQt6 is required for GUI. Install with: pip install PyQt6")
            sys.exit(1)
    elif args.command == "web":
        try:
            from src.web_gui import main as web_main
            web_main()
        except ImportError:
            print("Error: Flask is required for web GUI. Install with: pip install flask")
            sys.exit(1)
    else:
        parser.print_help()

    db.close()

if __name__ == "__main__":
    main()
