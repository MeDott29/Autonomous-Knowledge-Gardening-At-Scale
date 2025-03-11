#!/usr/bin/env python3
"""
Import Document Script

This script helps you import large documents like Autonomous-Knowledge-Gardening-at-Scale.md
into your knowledge garden with automatic chunking and insight extraction.
"""

import os
import sys
import argparse
from pathlib import Path
import re

# Import the knowledge garden
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from knowledge_garden import KnowledgeGarden, KnowledgeGardenAgent, initialize_openai_client

def chunk_document(content, max_chunk_size=8000, overlap=500):
    """Split a document into chunks with overlap"""
    chunks = []
    
    # Try to split on section headers
    sections = re.split(r'\n#+\s+', content)
    
    # If the first element doesn't start with a header, add the header prefix back to the others
    if not content.startswith('#'):
        header_content = sections[0]
        sections = sections[1:]
        sections = [f"# {s}" for s in sections]
        sections.insert(0, header_content)
    else:
        sections = [f"# {s}" for s in sections]
    
    current_chunk = ""
    
    for section in sections:
        # If adding this section would make the chunk too big, save the current chunk and start a new one
        if len(current_chunk) + len(section) > max_chunk_size and current_chunk:
            chunks.append(current_chunk)
            # Start new chunk with overlap from the end of the previous chunk
            if len(current_chunk) > overlap:
                current_chunk = current_chunk[-overlap:] + "\n\n" + section
            else:
                current_chunk = section
        else:
            if current_chunk:
                current_chunk += "\n\n" + section
            else:
                current_chunk = section
    
    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks

def extract_title_from_chunk(chunk, default_title="Untitled Section"):
    """Extract a title from a chunk of text"""
    # Try to find a heading
    title_match = re.search(r'^# (.+)$', chunk, re.MULTILINE)
    if title_match:
        return title_match.group(1)
    
    # If no heading, use the first line that's not empty
    lines = chunk.split('\n')
    for line in lines:
        if line.strip():
            # Limit title length
            title = line.strip()
            if len(title) > 50:
                title = title[:47] + "..."
            return title
    
    return default_title

def main():
    parser = argparse.ArgumentParser(description="Import a document into the Knowledge Garden")
    parser.add_argument("file", help="Path to the document file to import")
    parser.add_argument("--garden", default="knowledge_garden", help="Directory for the knowledge garden")
    parser.add_argument("--api-key", help="OpenAI API key (alternatively, set OPENAI_API_KEY environment variable)")
    parser.add_argument("--chunk-size", type=int, default=8000, help="Maximum chunk size in characters")
    parser.add_argument("--extract-insights", action="store_true", help="Extract insights from each chunk")
    parser.add_argument("--tags", help="Comma-separated list of tags to apply to all notes")
    
    args = parser.parse_args()
    
    # Check if file exists
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: File {args.file} does not exist")
        sys.exit(1)
    
    # Read the file
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # Initialize OpenAI client
    client = initialize_openai_client(args.api_key)
    
    # Initialize knowledge garden and agent
    garden = KnowledgeGarden(args.garden)
    agent = KnowledgeGardenAgent(garden)
    
    # Get document title from filename or first heading
    document_title = file_path.stem
    title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
    if title_match:
        document_title = title_match.group(1)
    
    # Process tags
    tags = []
    if args.tags:
        tags = [tag.strip() for tag in args.tags.split(',') if tag.strip()]
    
    # Add document info
    print(f"Importing document: {document_title}")
    print(f"File: {file_path}")
    print(f"Size: {len(content)} characters")
    
    # Chunk the document
    chunks = chunk_document(content, args.chunk_size)
    print(f"Document split into {len(chunks)} chunks")
    
    # Process each chunk
    for i, chunk in enumerate(chunks):
        # Extract title for this chunk
        chunk_title = extract_title_from_chunk(chunk, f"{document_title} - Part {i+1}")
        
        # Add the chunk as a note
        print(f"Adding note: {chunk_title}")
        garden.add_note(chunk_title, chunk, tags)
        
        # Extract insights if requested
        if args.extract_insights:
            print(f"Extracting insights from: {chunk_title}")
            try:
                agent.extract_insights(chunk, parent_note=chunk_title, tags=tags)
                print("  Insights extracted successfully")
            except Exception as e:
                print(f"  Error extracting insights: {str(e)}")
    
    print(f"Document imported successfully into {args.garden}")

if __name__ == "__main__":
    main() 