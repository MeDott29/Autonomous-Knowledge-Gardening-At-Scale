#!/usr/bin/env python3
import os
import json
import sys
import http.server
import socketserver
from urllib.parse import urlparse, parse_qs
from pathlib import Path

# Add the parent directory to the path to import the knowledge graph analyzer
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
import knowledge_graph_analysis

# Configuration
PORT = 8001
API_DIR = Path(__file__).parent
GARDEN_DIR = API_DIR.parent.parent  # knowledge_garden directory

class APIHandler(http.server.SimpleHTTPRequestHandler):
    """Handler for API requests"""
    
    def __init__(self, *args, **kwargs):
        self.analyzer = None
        super().__init__(*args, **kwargs)
    
    def initialize_analyzer(self):
        """Initialize the knowledge graph analyzer if needed"""
        if self.analyzer is None:
            try:
                self.analyzer = knowledge_graph_analysis.KnowledgeGraphAnalyzer(str(GARDEN_DIR))
            except Exception as e:
                self.send_error(500, f"Error initializing analyzer: {str(e)}")
                return False
        return True
    
    def do_GET(self):
        """Handle GET requests"""
        # Parse the URL
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query = parse_qs(parsed_url.query)
        
        # Handle API endpoints
        if path == '/api/graph-analysis.json':
            self.handle_graph_analysis()
        elif path == '/api/semantic-connections.json':
            self.handle_semantic_connections()
        elif path == '/api/communities.json':
            self.handle_communities()
        elif path == '/api/centrality.json':
            self.handle_centrality()
        elif path == '/api/paths.json':
            self.handle_paths(query)
        elif path == '/api/subgraph.json':
            self.handle_subgraph(query)
        else:
            # Serve static files
            super().do_GET()
    
    def handle_graph_analysis(self):
        """Handle graph analysis API endpoint"""
        # Check if the analysis file exists
        analysis_file = API_DIR / 'graph-analysis.json'
        if analysis_file.exists():
            with open(analysis_file, 'r') as f:
                analysis_data = json.load(f)
            self.send_json_response(analysis_data)
            return
        
        # Generate the analysis if the file doesn't exist
        if not self.initialize_analyzer():
            return
        
        try:
            analysis_data = self.analyzer.generate_graph_report()
            
            # Save the analysis data
            with open(analysis_file, 'w') as f:
                json.dump(analysis_data, f, indent=2)
            
            self.send_json_response(analysis_data)
        except Exception as e:
            self.send_error(500, f"Error generating graph analysis: {str(e)}")
    
    def handle_semantic_connections(self):
        """Handle semantic connections API endpoint"""
        # Check if the connections file exists
        connections_file = API_DIR / 'semantic-connections.json'
        if connections_file.exists():
            with open(connections_file, 'r') as f:
                connections_data = json.load(f)
            self.send_json_response(connections_data)
            return
        
        # Generate the connections if the file doesn't exist
        if not self.initialize_analyzer():
            return
        
        try:
            # Initialize embeddings if needed
            if not self.analyzer.embedding_model:
                self.analyzer.initialize_embeddings()
            
            connections_data = self.analyzer.find_semantic_connections()
            
            # Save the connections data
            with open(connections_file, 'w') as f:
                json.dump(connections_data, f, indent=2)
            
            self.send_json_response(connections_data)
        except Exception as e:
            self.send_error(500, f"Error finding semantic connections: {str(e)}")
    
    def handle_communities(self):
        """Handle communities API endpoint"""
        # Check if the communities file exists
        communities_file = API_DIR / 'communities.json'
        if communities_file.exists():
            with open(communities_file, 'r') as f:
                communities_data = json.load(f)
            self.send_json_response(communities_data)
            return
        
        # Generate the communities if the file doesn't exist
        if not self.initialize_analyzer():
            return
        
        try:
            communities_data = self.analyzer.detect_communities()
            
            # Save the communities data
            with open(communities_file, 'w') as f:
                json.dump(communities_data, f, indent=2)
            
            self.send_json_response(communities_data)
        except Exception as e:
            self.send_error(500, f"Error detecting communities: {str(e)}")
    
    def handle_centrality(self):
        """Handle centrality API endpoint"""
        # Check if the centrality file exists
        centrality_file = API_DIR / 'centrality.json'
        if centrality_file.exists():
            with open(centrality_file, 'r') as f:
                centrality_data = json.load(f)
            self.send_json_response(centrality_data)
            return
        
        # Generate the centrality if the file doesn't exist
        if not self.initialize_analyzer():
            return
        
        try:
            centrality_data = self.analyzer.compute_centrality_measures()
            
            # Save the centrality data
            with open(centrality_file, 'w') as f:
                json.dump(centrality_data, f, indent=2)
            
            self.send_json_response(centrality_data)
        except Exception as e:
            self.send_error(500, f"Error computing centrality measures: {str(e)}")
    
    def handle_paths(self, query):
        """Handle paths API endpoint"""
        if not self.initialize_analyzer():
            return
        
        # Get the source and target nodes from the query
        source = query.get('source', [''])[0]
        target = query.get('target', [''])[0]
        
        if not source or not target:
            self.send_error(400, "Missing source or target parameter")
            return
        
        try:
            paths = self.analyzer.agentic_path_finding(source, target)
            self.send_json_response(paths)
        except Exception as e:
            self.send_error(500, f"Error finding paths: {str(e)}")
    
    def handle_subgraph(self, query):
        """Handle subgraph API endpoint"""
        if not self.initialize_analyzer():
            return
        
        # Get the central node and distance from the query
        node = query.get('node', [''])[0]
        distance = int(query.get('distance', ['2'])[0])
        
        if not node:
            self.send_error(400, "Missing node parameter")
            return
        
        try:
            subgraph = self.analyzer.extract_subgraph(node, distance)
            
            if subgraph is None:
                self.send_json_response({"nodes": [], "edges": []})
                return
            
            # Convert the subgraph to a serializable format
            result = {
                "nodes": list(subgraph.nodes()),
                "edges": [{"source": u, "target": v} for u, v in subgraph.edges()]
            }
            
            self.send_json_response(result)
        except Exception as e:
            self.send_error(500, f"Error extracting subgraph: {str(e)}")
    
    def send_json_response(self, data):
        """Send a JSON response"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

def start_api_server(port=8001):
    """
    Start the API server on the specified port.
    
    Args:
        port (int): The port to run the server on (default: 8001)
    """
    # Ensure API directory exists
    os.makedirs(API_DIR, exist_ok=True)
    
    # Start the server
    try:
        with socketserver.TCPServer(("", port), APIHandler) as httpd:
            print(f"API Server started at http://localhost:{port}")
            httpd.serve_forever()
    except OSError as e:
        if e.errno == 98:  # Address already in use
            print(f"Error: Port {port} is already in use. Try a different port.")
            sys.exit(1)
        else:
            raise
    except KeyboardInterrupt:
        print("\nShutting down API server...")
        sys.exit(0)

if __name__ == "__main__":
    # If run directly, start the server
    start_api_server() 