# Knowledge Garden Visualization

This directory contains the visualization system for the Knowledge Garden project. It provides an interactive web-based interface to explore and analyze your knowledge graph.

## Features

- **Interactive Graph Visualization**: Explore your notes, tags, and connections visually
- **Graph Analysis**: View metrics and properties of your knowledge graph
- **Community Detection**: Identify clusters of related notes
- **Centrality Measures**: Find the most important nodes in your graph
- **Path Finding**: Discover connections between different notes
- **Subgraph Extraction**: Focus on specific areas of your knowledge garden

## Getting Started

### Prerequisites

- Python 3.7+
- D3.js (included via CDN)

### Running the Visualization

To launch the visualization server, run:

```bash
python launch_visualization.py
```

This will start both the HTTP server for static files and the API server for dynamic data. Your default web browser should open automatically to display the visualization.

### Command-line Options

The launcher script supports several command-line options:

- `--no-browser`: Don't open the browser automatically
- `--http-port PORT`: Specify a custom port for the HTTP server (default: 8000)
- `--api-port PORT`: Specify a custom port for the API server (default: 8001)

Example:
```bash
python launch_visualization.py --http-port 8080 --api-port 8081 --no-browser
```

## Directory Structure

- `css/`: Stylesheet files
- `js/`: JavaScript files for visualization and analysis
- `api/`: API server for dynamic data
- `index.html`: Main HTML file
- `index.json`: Data file containing notes, tags, and connections
- `launch_visualization.py`: Script to start the visualization server

## API Endpoints

The API server provides several endpoints:

- `/api/graph-analysis.json`: Graph analysis metrics
- `/api/semantic-connections.json`: Semantic connections between notes
- `/api/communities.json`: Community detection results
- `/api/centrality.json`: Centrality measures for nodes
- `/api/paths?source=X&target=Y`: Find paths between nodes X and Y
- `/api/subgraph?node=X&distance=N`: Extract a subgraph around node X with distance N

## Usage Tips

1. **Navigation**: Use mouse wheel to zoom, drag to pan, and click on nodes to view details
2. **Refresh**: Click the "Refresh" button to reload data if you've made changes to your knowledge garden
3. **Analysis**: Switch to the Analysis tab to view metrics about your knowledge graph
4. **Communities**: The Communities tab shows clusters of related notes
5. **Centrality**: The Centrality tab highlights the most important nodes
6. **Tools**: Use the Tools tab for path finding and subgraph extraction

## Troubleshooting

- If the visualization doesn't load, check that both servers are running
- If you see "No data available" messages, ensure your knowledge garden has been processed
- If the browser doesn't open automatically, navigate to `http://localhost:8000` manually 