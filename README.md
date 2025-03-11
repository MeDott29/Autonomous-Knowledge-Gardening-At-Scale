# Autonomous Knowledge Gardening At Scale

This project implements an autonomous knowledge gardening system that can explore topics, generate insights, and visualize the resulting knowledge graph.

## Features

- **Autonomous Exploration**: Automatically explore topics and generate interconnected notes
- **Knowledge Extraction**: Extract key insights from generated content
- **Structured Organization**: Organize knowledge into exploration paths and subtopics
- **Interactive Visualization**: Visualize the knowledge garden as an interactive graph
- **Real-time Updates**: See the knowledge garden grow in real-time

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/Autonomous-Knowledge-Gardening-At-Scale.git
   cd Autonomous-Knowledge-Gardening-At-Scale
   ```

2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up your OpenAI API key:
   ```bash
   export OPENAI_API_KEY="your-api-key"
   ```

## Usage

### Autonomous Exploration

To start autonomous exploration on a topic:

```bash
python knowledge-graphing.py --explore "your topic" --iterations 3 --visualize
```

Options:
- `--explore`: The topic to explore
- `--iterations`: Number of exploration iterations (default: 5)
- `--api-key`: Your OpenAI API key (alternatively, set the OPENAI_API_KEY environment variable)
- `--visualize`: Launch the visualization after exploration

### Interactive Mode

To interact with the knowledge garden:

```bash
python knowledge-graphing.py --interactive
```

### Visualization

To visualize an existing knowledge garden:

```bash
python knowledge-graphing.py --view
```

Or run the visualization server directly:

```bash
python serve_visualization.py
```

Then open your browser to http://localhost:8000/visualize.html

## Knowledge Garden Structure

The knowledge garden is organized as follows:

- `knowledge_garden/notes/`: Contains all the notes as Markdown files
- `knowledge_garden/paths/`: Contains exploration paths as JSON files
- `knowledge_garden/index.json`: The main index of all notes, tags, and paths
- `knowledge_garden/visualize.html`: The visualization interface

## Visualization Features

The visualization interface provides:

- Interactive graph of notes, tags, and exploration paths
- Zoom and pan controls
- Note details in the sidebar
- Garden statistics
- Real-time updates

## How It Works

1. The system starts with a seed topic and generates an initial note
2. It extracts key insights from the note and creates separate notes for each
3. It explores subtopics in a structured way, creating new notes and connections
4. It generates a summary at the end of exploration
5. The visualization shows the resulting knowledge graph with all connections

## License

MIT 