#!/usr/bin/env python3
"""
Knowledge Garden Visualization Launcher

This script launches the visualization server for the Knowledge Garden.
It starts both the HTTP server for static files and the API server for dynamic data.
"""

import os
import sys
import json
import subprocess
import webbrowser
import time
import argparse
from pathlib import Path
import http.server
import socketserver
import threading

# Add parent directory to path to import from knowledge_garden
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from knowledge_garden.visualization.api.api_handler import start_api_server

# Constants
VISUALIZATION_DIR = Path(__file__).resolve().parent
HTTP_PORT = 8000
API_PORT = 8001

def ensure_index_json():
    """
    Ensure that index.json exists in the visualization directory.
    If it doesn't exist, create it with empty data.
    """
    index_path = VISUALIZATION_DIR / "index.json"
    if not index_path.exists():
        print("Creating empty index.json file...")
        empty_data = {
            "notes": [],
            "tags": [],
            "paths": [],
            "metadata": {
                "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
                "version": "1.0.0"
            }
        }
        with open(index_path, 'w') as f:
            json.dump(empty_data, f, indent=2)

def start_http_server():
    """
    Start the HTTP server for serving static files.
    """
    os.chdir(VISUALIZATION_DIR)
    
    class HttpHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            # Customize logging to be more concise
            if args[0].startswith('GET'):
                print(f"HTTP: {args[0]} {args[1]}")
    
    httpd = socketserver.TCPServer(("", HTTP_PORT), HttpHandler)
    print(f"HTTP Server started at http://localhost:{HTTP_PORT}")
    httpd.serve_forever()

def main():
    """
    Main function to parse arguments and start the servers.
    """
    parser = argparse.ArgumentParser(description="Launch Knowledge Garden Visualization")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser automatically")
    parser.add_argument("--http-port", type=int, default=HTTP_PORT, help=f"HTTP server port (default: {HTTP_PORT})")
    parser.add_argument("--api-port", type=int, default=API_PORT, help=f"API server port (default: {API_PORT})")
    args = parser.parse_args()
    
    # Update ports if specified
    global HTTP_PORT, API_PORT
    HTTP_PORT = args.http_port
    API_PORT = args.api_port
    
    # Ensure index.json exists
    ensure_index_json()
    
    # Start API server in a separate thread
    api_thread = threading.Thread(target=start_api_server, args=(API_PORT,), daemon=True)
    api_thread.start()
    
    # Open browser if requested
    if not args.no_browser:
        print("Opening browser...")
        webbrowser.open(f"http://localhost:{HTTP_PORT}")
    
    # Start HTTP server (this will block)
    try:
        start_http_server()
    except KeyboardInterrupt:
        print("\nShutting down servers...")
        sys.exit(0)

if __name__ == "__main__":
    main() 