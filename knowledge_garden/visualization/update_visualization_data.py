#!/usr/bin/env python3
"""
Update Visualization Data

This script updates the visualization data from the knowledge garden.
It processes the notes, tags, and paths from the knowledge garden and
generates the index.json file used by the visualization system.
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime

# Add parent directory to path to import from knowledge_garden
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

# Constants
VISUALIZATION_DIR = Path(__file__).resolve().parent
INDEX_JSON_PATH = VISUALIZATION_DIR / "index.json"

def load_knowledge_garden(garden_dir):
    """
    Load notes, tags, and paths from the knowledge garden.
    
    Args:
        garden_dir (Path): Path to the knowledge garden directory
        
    Returns:
        tuple: (notes, tags, paths)
    """
    notes = []
    tags = []
    paths = []
    
    # Check if garden directory exists
    if not garden_dir.exists():
        print(f"Error: Knowledge garden directory not found: {garden_dir}")
        return notes, tags, paths
    
    # Load notes
    notes_dir = garden_dir / "notes"
    if notes_dir.exists():
        for note_file in notes_dir.glob("*.md"):
            note_id = note_file.stem
            
            # Read note content
            with open(note_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract title from first line (assuming # Title format)
            title = note_id
            first_line = content.split('\n', 1)[0].strip()
            if first_line.startswith('# '):
                title = first_line[2:].strip()
            
            # Extract tags from content (assuming #tag format)
            note_tags = []
            for word in content.split():
                if word.startswith('#') and len(word) > 1 and not word.startswith('##'):
                    tag = word[1:].strip().lower()
                    if tag and tag not in note_tags:
                        note_tags.append(tag)
                        # Add to global tags if not already there
                        if tag not in tags:
                            tags.append(tag)
            
            # Get file stats
            stats = note_file.stat()
            created = datetime.fromtimestamp(stats.st_ctime).strftime('%Y-%m-%d %H:%M:%S')
            modified = datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            
            # Create note object
            note = {
                "id": note_id,
                "title": title,
                "content": content,
                "tags": note_tags,
                "created": created,
                "modified": modified
            }
            
            notes.append(note)
    
    # Extract paths (connections between notes)
    for note in notes:
        content = note["content"]
        lines = content.split('\n')
        
        # Look for links to other notes
        for line in lines:
            # Find markdown links: [text](note_id)
            link_start = line.find('[')
            while link_start != -1:
                link_end = line.find(']', link_start)
                if link_end != -1:
                    link_text = line[link_start+1:link_end]
                    if line[link_end+1:link_end+2] == '(':
                        url_start = link_end + 2
                        url_end = line.find(')', url_start)
                        if url_end != -1:
                            url = line[url_start:url_end]
                            # Check if this is a link to another note
                            if not url.startswith('http') and not url.startswith('/'):
                                # Remove .md extension if present
                                if url.endswith('.md'):
                                    url = url[:-3]
                                
                                # Check if target note exists
                                if any(n["id"] == url for n in notes):
                                    # Add path
                                    path = {
                                        "source": note["id"],
                                        "target": url,
                                        "type": "link"
                                    }
                                    paths.append(path)
                    
                    # Find next link
                    link_start = line.find('[', link_end)
                else:
                    break
    
    return notes, tags, paths

def update_visualization_data(garden_dir=None):
    """
    Update the visualization data from the knowledge garden.
    
    Args:
        garden_dir (Path, optional): Path to the knowledge garden directory.
            If None, will try to find it automatically.
            
    Returns:
        bool: True if successful, False otherwise
    """
    # If garden_dir not provided, try to find it
    if garden_dir is None:
        # Try parent directory
        garden_dir = VISUALIZATION_DIR.parent
    
    print(f"Loading knowledge garden from: {garden_dir}")
    
    # Load knowledge garden data
    notes, tags, paths = load_knowledge_garden(garden_dir)
    
    if not notes:
        print("Warning: No notes found in the knowledge garden.")
    
    # Create visualization data
    visualization_data = {
        "notes": notes,
        "tags": tags,
        "paths": paths,
        "metadata": {
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
            "version": "1.0.0",
            "notes_count": len(notes),
            "tags_count": len(tags),
            "paths_count": len(paths)
        }
    }
    
    # Save to index.json
    with open(INDEX_JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(visualization_data, f, indent=2)
    
    print(f"Visualization data updated: {INDEX_JSON_PATH}")
    print(f"Notes: {len(notes)}, Tags: {len(tags)}, Paths: {len(paths)}")
    
    return True

def main():
    """
    Main function to parse arguments and update visualization data.
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Update Knowledge Garden Visualization Data")
    parser.add_argument("--garden-dir", type=str, help="Path to the knowledge garden directory")
    args = parser.parse_args()
    
    garden_dir = None
    if args.garden_dir:
        garden_dir = Path(args.garden_dir)
    
    success = update_visualization_data(garden_dir)
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main() 