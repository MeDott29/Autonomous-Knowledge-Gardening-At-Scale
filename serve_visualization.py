#!/usr/bin/env python3
import http.server
import socketserver
import os
import sys
import webbrowser
import threading
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Configuration
PORT = 8000
GARDEN_DIR = "knowledge_garden"
VISUALIZATION_FILE = os.path.join(GARDEN_DIR, "visualize.html")

class KnowledgeGardenHandler(FileSystemEventHandler):
    """Handler for file system events in the knowledge garden"""
    
    def __init__(self, server_address):
        self.server_address = server_address
        self.last_update = time.time()
        
    def on_any_event(self, event):
        # Debounce events (avoid multiple rapid updates)
        current_time = time.time()
        if current_time - self.last_update < 1.0:
            return
            
        self.last_update = current_time
        
        # Only process events for notes, index.json, or path files
        if event.is_directory:
            return
            
        path = Path(event.src_path)
        if (path.suffix.lower() in ['.md', '.json'] and 
            (GARDEN_DIR in path.parts or path.name == 'index.json')):
            print(f"Knowledge garden updated: {path.name}")
            
            # You could add a WebSocket notification here to auto-refresh the browser
            # For now, we'll just print a message
            print(f"Visualization can be refreshed at http://{self.server_address[0]}:{self.server_address[1]}/")

class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP request handler with CORS support"""
    
    def end_headers(self):
        # Add CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()
        
    def log_message(self, format, *args):
        # Customize logging
        if args[0].startswith('GET'):
            sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))

def start_server():
    """Start the HTTP server"""
    # Change to the knowledge garden directory
    os.chdir(GARDEN_DIR)
    
    # Create a server
    handler = CustomHTTPRequestHandler
    server_address = ('', PORT)
    httpd = socketserver.TCPServer(server_address, handler)
    
    # Set up file system monitoring
    event_handler = KnowledgeGardenHandler(server_address)
    observer = Observer()
    observer.schedule(event_handler, path='.', recursive=True)
    observer.start()
    
    print(f"Serving Knowledge Garden visualization at http://localhost:{PORT}/visualize.html")
    print("Press Ctrl+C to stop the server")
    
    try:
        # Open the visualization in a browser
        webbrowser.open(f"http://localhost:{PORT}/visualize.html")
        
        # Start the server
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        observer.stop()
        observer.join()
        httpd.server_close()
        print("Server stopped")

if __name__ == "__main__":
    # Check if the visualization file exists
    if not os.path.exists(VISUALIZATION_FILE):
        print(f"Error: Visualization file not found at {VISUALIZATION_FILE}")
        print("Make sure you've created the visualization file first.")
        sys.exit(1)
        
    # Start the server
    start_server() 