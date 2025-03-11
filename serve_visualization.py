#!/usr/bin/env python3
import http.server
import socketserver
import os
import sys
import webbrowser
import threading
import time
import json
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import websockets
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

# Configuration
PORT = 8000
WS_PORT = 8001
GARDEN_DIR = "knowledge_garden"
VISUALIZATION_FILE = os.path.join(GARDEN_DIR, "visualize.html")

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global variables
connected_clients = set()
tool_usage_history = []

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
            logger.info(f"Knowledge garden updated: {path.name}")
            
            # Send WebSocket notification to all connected clients
            asyncio.run(notify_clients({"type": "garden_update", "file": path.name}))

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
            logger.info("%s - %s" % (self.address_string(), format % args))

async def websocket_handler(websocket, path):
    """Handle WebSocket connections"""
    # Register the client
    connected_clients.add(websocket)
    logger.info(f"New client connected. Total clients: {len(connected_clients)}")
    
    try:
        # Send initial tool usage history
        if tool_usage_history:
            await websocket.send(json.dumps({
                "type": "tool_history",
                "data": tool_usage_history
            }))
        
        # Keep the connection alive and handle messages
        async for message in websocket:
            try:
                data = json.loads(message)
                if data.get("type") == "ping":
                    await websocket.send(json.dumps({"type": "pong"}))
            except json.JSONDecodeError:
                logger.warning(f"Received invalid JSON: {message}")
    except websockets.exceptions.ConnectionClosed:
        logger.info("Client disconnected")
    finally:
        # Unregister the client
        connected_clients.remove(websocket)

async def notify_clients(data):
    """Send a notification to all connected clients"""
    if not connected_clients:
        return
        
    message = json.dumps(data)
    await asyncio.gather(
        *[client.send(message) for client in connected_clients],
        return_exceptions=True
    )

async def start_websocket_server():
    """Start the WebSocket server"""
    server = await websockets.serve(websocket_handler, "localhost", WS_PORT)
    logger.info(f"WebSocket server started on ws://localhost:{WS_PORT}")
    await server.wait_closed()

def record_tool_usage(tool_name, args, result):
    """Record tool usage for visualization"""
    tool_usage_history.append({
        "timestamp": time.time(),
        "tool": tool_name,
        "args": args,
        "result": result
    })
    
    # Limit history size
    if len(tool_usage_history) > 100:
        tool_usage_history.pop(0)
    
    # Notify clients about the tool usage
    asyncio.run(notify_clients({
        "type": "tool_usage",
        "data": {
            "timestamp": time.time(),
            "tool": tool_name,
            "args": args,
            "result": result
        }
    }))

def start_http_server():
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
    
    logger.info(f"Serving Knowledge Garden visualization at http://localhost:{PORT}/visualize.html")
    logger.info("Press Ctrl+C to stop the server")
    
    try:
        # Open the visualization in a browser
        webbrowser.open(f"http://localhost:{PORT}/visualize.html")
        
        # Start the server
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("\nShutting down server...")
        observer.stop()
        observer.join()
        httpd.server_close()
        logger.info("Server stopped")

def start_servers():
    """Start both HTTP and WebSocket servers"""
    # Start WebSocket server in a separate thread
    ws_thread = threading.Thread(target=lambda: asyncio.run(start_websocket_server()))
    ws_thread.daemon = True
    ws_thread.start()
    
    # Start HTTP server in the main thread
    start_http_server()

if __name__ == "__main__":
    # Check if the visualization file exists
    if not os.path.exists(VISUALIZATION_FILE):
        logger.error(f"Error: Visualization file not found at {VISUALIZATION_FILE}")
        logger.error("Make sure you've created the visualization file first.")
        sys.exit(1)
        
    # Start the servers
    start_servers() 