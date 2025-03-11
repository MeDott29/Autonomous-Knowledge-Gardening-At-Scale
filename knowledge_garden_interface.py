import os
import sys
import json
import argparse
from pathlib import Path
import base64
import re
from typing import List, Optional
import datetime
import tempfile

# Flask for web interface
from flask import Flask, request, render_template, redirect, url_for, flash, jsonify, send_from_directory
from werkzeug.utils import secure_filename

# Import the knowledge garden
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from knowledge_garden import KnowledgeGarden, KnowledgeGardenAgent, initialize_openai_client

# Global variables
client = None
garden = None
agent = None

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configure upload settings
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'md', 'docx', 'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB limit

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_image_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

def process_text_file(file_path):
    """Extract content from a text file"""
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()

def process_markdown_file(file_path):
    """Process a markdown file, extracting content and metadata if available"""
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # Extract title from first heading if available
    title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
    title = title_match.group(1) if title_match else Path(file_path).stem
    
    # Extract tags if they exist in the format "Tags: tag1, tag2, tag3"
    tags = []
    tags_match = re.search(r'Tags: (.+)$', content, re.MULTILINE)
    if tags_match:
        tags = [tag.strip() for tag in tags_match.group(1).split(',')]
    
    return title, content, tags

def process_image_file(file_path):
    """Process an image file, creating a markdown note with the embedded image"""
    # Get the filename as the title
    title = Path(file_path).stem
    
    # Create a relative path to the image
    # Store images in the uploads directory which is served by the web server
    # This ensures the images are accessible via URL
    uploads_dir = Path(app.config['UPLOAD_FOLDER'])
    
    # Make sure the image is in the uploads directory
    if not str(file_path).startswith(str(uploads_dir)):
        # If it's not already in uploads, we need to copy it there
        import shutil
        new_path = uploads_dir / Path(file_path).name
        shutil.copy2(file_path, new_path)
        file_path = new_path
    
    # Create a web-accessible URL for the image
    image_url = f"/uploads/{Path(file_path).name}"
    
    # Create markdown content with embedded image
    # Use absolute URL to ensure it's accessible in the web interface
    content = f"![{title}]({image_url})\n\n"
    
    # Add base64 encoding of the image for GPT-4o to see the image
    try:
        import base64
        from PIL import Image
        import io
        
        # Open the image and convert to base64
        img = Image.open(file_path)
        
        # Resize large images to reduce size
        max_size = (1200, 1200)
        if img.width > max_size[0] or img.height > max_size[1]:
            img.thumbnail(max_size, Image.LANCZOS)
        
        # Convert to base64
        buffer = io.BytesIO()
        img_format = Path(file_path).suffix[1:].upper()
        if img_format not in ['JPEG', 'PNG', 'GIF']:
            img_format = 'PNG'  # Default to PNG for unsupported formats
        
        img.save(buffer, format=img_format)
        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        # Add base64 data to the content (commented out so it doesn't show in the UI)
        content += f"<!-- Base64 image data for AI models: data:image/{img_format.lower()};base64,{img_base64} -->\n\n"
        
        # Add image metadata
        content += f"Image uploaded on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        content += f"Dimensions: {img.width}x{img.height} pixels\n"
        
    except Exception as e:
        # If there's an error with the image processing, just add basic info
        content += f"Image uploaded on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        content += f"Error processing image details: {str(e)}\n"
    
    return title, content, []

def extract_insights_from_file(file_path):
    """Use the agent to extract insights from a file"""
    content = process_text_file(file_path)
    
    # Use the garden to extract insights
    insights = garden.extract_insights(content)
    return insights

@app.route('/')
def index():
    """Home page with options to upload files or interact with the garden"""
    # Get all notes from the garden
    notes = garden.index.get("notes", {})
    tags = garden.index.get("tags", {})
    
    # Calculate graph statistics
    node_count = len(notes)
    edge_count = calculate_edge_count(notes)
    hub_nodes = identify_hub_nodes(notes, threshold=5)  # Nodes with 5+ connections
    bridge_nodes = identify_bridge_nodes(notes)
    
    # Generate graph preview
    graph_preview = generate_graph_preview(notes)
    recent_changes = get_recent_changes(notes, limit=5)
    
    # Get the last updated time
    last_updated = "Never"
    if notes:
        # Find the most recent note
        latest_note = max(notes.values(), key=lambda n: n.get('created', '2000-01-01'), default=None)
        if latest_note and 'created' in latest_note:
            last_updated = latest_note['created']
    
    # Format recent updates for display
    recent_updates = []
    for change in recent_changes:
        recent_updates.append({
            'action': 'Added' if change.get('action') == 'add' else 'Updated',
            'title': change.get('title', 'Unknown'),
            'time': change.get('time', 'Unknown time')
        })
    
    return render_template('index.html', 
                          notes=notes, 
                          tags=tags, 
                          node_count=node_count,
                          edge_count=edge_count,
                          hub_nodes=hub_nodes,
                          bridge_nodes=bridge_nodes,
                          graph_preview=graph_preview,
                          recent_changes=recent_changes,
                          recent_updates=recent_updates,
                          last_updated=last_updated)

def calculate_edge_count(notes):
    """Calculate the total number of edges in the knowledge graph"""
    edge_count = 0
    
    # Count related notes as edges
    for title, note in notes.items():
        if 'related_notes' in note:
            edge_count += len(note['related_notes'])
    
    return edge_count

def identify_hub_nodes(notes, threshold=5):
    """Identify hub nodes (nodes with many connections)"""
    hub_count = 0
    
    # Count incoming connections for each node
    connections = {}
    for title, note in notes.items():
        connections[title] = 0
        
    # Count outgoing connections
    for title, note in notes.items():
        if 'related_notes' in note:
            for related in note['related_notes']:
                if related in connections:
                    connections[related] += 1
    
    # Count nodes with connections above threshold
    for title, count in connections.items():
        outgoing = len(notes.get(title, {}).get('related_notes', []))
        if count + outgoing >= threshold:
            hub_count += 1
    
    return hub_count

def identify_bridge_nodes(notes):
    """Identify bridge nodes (nodes that connect different clusters)"""
    # This is a simplified implementation
    # A more sophisticated approach would use community detection algorithms
    
    # For now, we'll consider a node a bridge if it connects to notes with different tag sets
    bridge_count = 0
    
    for title, note in notes.items():
        if 'related_notes' in note and len(note['related_notes']) > 1:
            # Get the tags of this note
            note_tags = set(note.get('tags', []))
            
            # Get the tags of related notes
            related_tags_sets = []
            for related in note['related_notes']:
                if related in notes:
                    related_tags = set(notes[related].get('tags', []))
                    related_tags_sets.append(related_tags)
            
            # Check if this note connects different tag clusters
            if len(related_tags_sets) > 1:
                # Check if the tag sets are significantly different
                different_clusters = False
                for i, tags1 in enumerate(related_tags_sets):
                    for tags2 in related_tags_sets[i+1:]:
                        # If the overlap is less than 50%, consider them different clusters
                        if len(tags1.intersection(tags2)) < min(len(tags1), len(tags2)) / 2:
                            different_clusters = True
                            break
                    if different_clusters:
                        break
                
                if different_clusters:
                    bridge_count += 1
    
    return bridge_count

def generate_graph_preview(notes, max_nodes=10):
    """Generate an HTML preview of the knowledge graph structure"""
    if not notes:
        return '<div class="empty-graph">No notes in the knowledge garden yet.</div>'
    
    # Take a sample of nodes, prioritizing those with more connections
    sorted_nodes = sorted(notes.items(), key=lambda x: len(x[1].get('related_notes', [])), reverse=True)
    sample_nodes = sorted_nodes[:max_nodes]
    
    # Create a simple HTML visualization
    html = ['<div class="knowledge-graph">']
    
    # Add nodes
    html.append('<div class="graph-nodes">')
    for title, note in sample_nodes:
        related = note.get('related_notes', [])
        tags = note.get('tags', [])
        
        # Determine node class based on connections
        node_class = "graph-node"
        if len(related) >= 5:
            node_class += " hub-node"
        elif any(tag in ["query-response", "image-analysis"] for tag in tags):
            node_class += " query-node"
        
        html.append(f'<div class="{node_class}" data-title="{title}">')
        html.append(f'<div class="node-title"><a href="/note/{title}">{title[:20]}{"..." if len(title) > 20 else ""}</a></div>')
        
        # Add tag indicators
        if tags:
            html.append('<div class="node-tags">')
            for tag in tags[:3]:
                html.append(f'<span class="node-tag">{tag}</span>')
            if len(tags) > 3:
                html.append(f'<span class="node-tag">+{len(tags) - 3}</span>')
            html.append('</div>')
        
        html.append('</div>')
    html.append('</div>')
    
    # Add connections
    html.append('<div class="graph-connections">')
    html.append('<ul>')
    for title, note in sample_nodes:
        related = [r for r in note.get('related_notes', []) if r in [n[0] for n in sample_nodes]]
        if related:
            html.append(f'<li><strong>{title}</strong> connects to: {", ".join(related[:3])}')
            if len(related) > 3:
                html.append(f' and {len(related) - 3} more')
            html.append('</li>')
    html.append('</ul>')
    html.append('</div>')
    
    # Add legend
    html.append('<div class="graph-legend">')
    html.append('<div><span class="legend-item hub-node"></span> Hub Node (5+ connections)</div>')
    html.append('<div><span class="legend-item query-node"></span> Query Response</div>')
    html.append('<div><span class="legend-item graph-node"></span> Standard Note</div>')
    html.append('</div>')
    
    # Add CSS
    html.append('<style>')
    html.append('.knowledge-graph { margin-top: 15px; }')
    html.append('.graph-nodes { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 15px; }')
    html.append('.graph-node { border: 1px solid #ddd; border-radius: 5px; padding: 8px; width: 120px; text-align: center; background: #f9f9f9; }')
    html.append('.hub-node { background: #e3f2fd; border-color: #2196F3; }')
    html.append('.query-node { background: #f1f8e9; border-color: #8bc34a; }')
    html.append('.node-title { font-weight: bold; margin-bottom: 5px; }')
    html.append('.node-tags { display: flex; flex-wrap: wrap; justify-content: center; gap: 3px; }')
    html.append('.node-tag { font-size: 0.7em; background: #eee; padding: 2px 4px; border-radius: 3px; }')
    html.append('.graph-connections { margin-top: 10px; font-size: 0.9em; }')
    html.append('.graph-legend { margin-top: 15px; display: flex; gap: 15px; font-size: 0.8em; }')
    html.append('.legend-item { display: inline-block; width: 15px; height: 15px; margin-right: 5px; border: 1px solid #ddd; border-radius: 3px; vertical-align: middle; }')
    html.append('</style>')
    
    html.append('</div>')
    
    return '\n'.join(html)

def get_recent_changes(notes, limit=5):
    """Get the most recent changes to the knowledge garden"""
    # Collect notes with creation or update timestamps
    timestamped_notes = []
    for title, note in notes.items():
        # Check for created timestamp
        if 'created' in note:
            timestamped_notes.append({
                'title': title,
                'time': note['created'],
                'action': 'add',
                'tags': note.get('tags', []),
                'related_notes': note.get('related_notes', [])
            })
        
        # Check for last_updated timestamp (if different from created)
        if 'last_updated' in note and note.get('last_updated') != note.get('created'):
            timestamped_notes.append({
                'title': title,
                'time': note['last_updated'],
                'action': 'update',
                'tags': note.get('tags', []),
                'related_notes': note.get('related_notes', [])
            })
    
    # Sort by timestamp (most recent first)
    timestamped_notes.sort(key=lambda x: x['time'], reverse=True)
    
    # Take the most recent changes
    recent_changes = timestamped_notes[:limit]
    
    # If we don't have enough changes with timestamps, add some without timestamps
    if len(recent_changes) < limit:
        # Add notes without timestamps (sorted by title as a fallback)
        untimed_notes = [
            {
                'title': title,
                'time': 'Unknown',
                'action': 'add',
                'tags': note.get('tags', []),
                'related_notes': note.get('related_notes', [])
            }
            for title, note in sorted(notes.items())
            if 'created' not in note and 'last_updated' not in note
        ]
        
        # Add untimed notes until we reach the limit
        recent_changes.extend(untimed_notes[:limit - len(recent_changes)])
    
    return recent_changes

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file uploads"""
    if 'file' not in request.files:
        flash('No file part')
        return redirect(url_for('index'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('index'))
    
    # Check if the file extension is allowed
    if not '.' in file.filename:
        flash('Invalid filename - no extension detected')
        return redirect(url_for('index'))
    
    extension = file.filename.rsplit('.', 1)[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        flash(f'Invalid file type: .{extension}. Allowed types are: {", ".join(ALLOWED_EXTENSIONS)}')
        return redirect(url_for('index'))
    
    # At this point, we know the file type is allowed
    filename = secure_filename(file.filename)
    
    # Create uploads directory if it doesn't exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)
    
    try:
        # Process the file based on its type
        if is_image_file(filename):
            # For images, create a note with the embedded image
            title, content, tags = process_image_file(file_path)
            
            # Add tags from the form if provided
            form_tags = request.form.get('tags', '').split(',') if request.form.get('tags') else []
            form_tags = [tag.strip() for tag in form_tags if tag.strip()]
            tags.extend(form_tags)
            
            # Use custom title if provided
            if request.form.get('title'):
                title = request.form.get('title')
            
            # Add the note to the garden
            garden.add_note(title, content, tags)
            flash(f'Image "{title}" added to the knowledge garden')
        else:
            # For text files, extract content and add as a note
            if filename.endswith('.md'):
                title, content, tags = process_markdown_file(file_path)
            else:
                title = request.form.get('title', Path(file_path).stem)
                content = process_text_file(file_path)
                tags = request.form.get('tags', '').split(',') if request.form.get('tags') else []
                tags = [tag.strip() for tag in tags if tag.strip()]
            
            # Add the note to the garden
            garden.add_note(title, content, tags)
            
            # If extract insights is checked, also extract insights
            if request.form.get('extract_insights') == 'on':
                try:
                    insights = garden.extract_insights(content, parent_note=title)
                    flash(f'Extracted insights from "{title}"')
                except Exception as e:
                    flash(f'Error extracting insights: {str(e)}')
            
            flash(f'File "{title}" added to the knowledge garden')
        
        return redirect(url_for('index'))
    except Exception as e:
        # If there's an error processing the file, provide a helpful error message
        flash(f'Error processing file: {str(e)}')
        # Log the error for debugging
        print(f"Error processing file {filename}: {str(e)}")
        import traceback
        traceback.print_exc()
        return redirect(url_for('index'))

@app.route('/query', methods=['POST'])
def process_query():
    """Process a query to the knowledge garden agent using graph-based reasoning"""
    query = request.form.get('query', '')
    if not query:
        flash('Please enter a query')
        return redirect(url_for('index'))
    
    # Get query parameters
    query_type = request.form.get('query_type', 'direct')
    max_context_nodes = int(request.form.get('max_context_nodes', 5))
    reasoning_depth = int(request.form.get('reasoning_depth', 2))
    image_detail = request.form.get('image_detail', 'auto')  # Get image detail level from form
    add_to_garden = request.form.get('add_to_garden') == 'on'  # Check if insights should be added to garden
    
    # Check if an image was uploaded with the query
    image_url = None
    image_data = None
    if 'image' in request.files and request.files['image'].filename:
        image_file = request.files['image']
        if is_image_file(image_file.filename):
            # Save the image
            filename = secure_filename(image_file.filename)
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(file_path)
            
            # Get the URL for the image
            image_url = f"/uploads/{filename}"
            
            # Process the image according to OpenAI API standards
            try:
                # Use the specified detail level or default to "auto"
                image_data = process_image_for_query(file_path, detail=image_detail)
                if not image_data:
                    flash('Warning: Could not process the uploaded image')
            except Exception as e:
                flash(f'Warning: Error processing image: {str(e)}')
                print(f"Error processing image for query: {str(e)}")
    
    try:
        # Step 1: Find relevant nodes in the knowledge graph
        relevant_nodes = find_relevant_nodes(query, max_nodes=max_context_nodes)
        
        # Step 2: Process the query using the graph-based approach
        if query_type == 'direct':
            # Direct query - answer from existing knowledge
            response = process_direct_query(query, relevant_nodes, image_url, image_data)
        elif query_type == 'expand':
            # Expand knowledge - generate new insights
            response = process_expand_query(query, relevant_nodes, reasoning_depth, image_url, image_data)
        elif query_type == 'connect':
            # Connect concepts - find relationships
            response = process_connect_query(query, relevant_nodes, reasoning_depth, image_url, image_data)
        elif query_type == 'synthesize':
            # Synthesize knowledge - create new understanding
            response = process_synthesize_query(query, relevant_nodes, reasoning_depth, image_url, image_data)
        else:
            # Default to direct query
            response = process_direct_query(query, relevant_nodes, image_url, image_data)
        
        # Step 3: Add insights to the knowledge garden if requested
        if add_to_garden:
            # Create a title based on the query
            title = f"Query: {query[:50]}..." if len(query) > 50 else f"Query: {query}"
            
            # Add tags based on query type and content
            tags = [query_type, "query-response"]
            if image_url:
                tags.append("image-analysis")
            
            # Add related notes based on the relevant nodes used
            related_notes = list(relevant_nodes.keys())
            
            # Add the response as a note to the knowledge garden
            garden.add_note(
                title=title,
                content=f"Query: {query}\n\nResponse: {response}",
                tags=tags,
                related_notes=related_notes
            )
            
            # Extract additional insights if it's an expand or synthesize query
            if query_type in ['expand', 'synthesize'] and len(response) > 200:
                garden.extract_insights(response, parent_note=title, tags=tags)
                flash('Insights from this query have been added to the knowledge garden')
        
        flash(f'Response: {response}')
        return redirect(url_for('index'))
        
    except Exception as e:
        flash(f"Error processing query: {str(e)}")
        import traceback
        traceback.print_exc()
        return redirect(url_for('index'))

def find_relevant_nodes(query, max_nodes=5):
    """Find the most relevant nodes in the knowledge graph for a query using agentic principles"""
    global garden
    
    # Get all notes
    notes = garden.index.get("notes", {})
    
    # If there are no notes, return an empty dict
    if not notes:
        return {}
    
    # Extract keywords from the query
    keywords = set(query.lower().split())
    # Remove common words
    stop_words = {'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'with', 'by', 'about', 'as', 'of', 'and', 'or', 'is', 'are', 'what', 'how', 'why', 'when', 'where', 'who', 'which'}
    keywords = keywords - stop_words
    
    # Score each note based on multiple factors (agentic knowledge graph principles)
    scored_notes = []
    for title, note in notes.items():
        # Initialize with different scoring components
        keyword_score = 0
        recency_score = 0
        connection_score = 0
        importance_score = 0
        
        # 1. Keyword matching (content relevance)
        title_lower = title.lower()
        for keyword in keywords:
            if keyword in title_lower:
                keyword_score += 3  # Higher weight for title matches
        
        # Check content
        if 'content' in note:
            content_lower = note['content'].lower()
            for keyword in keywords:
                keyword_score += content_lower.count(keyword)
        
        # Check tags
        if 'tags' in note:
            for tag in note['tags']:
                tag_lower = tag.lower()
                for keyword in keywords:
                    if keyword in tag_lower:
                        keyword_score += 2  # Higher weight for tag matches
        
        # 2. Recency (temporal relevance)
        if 'created' in note:
            # Calculate days since creation (newer notes get higher scores)
            try:
                created_date = datetime.datetime.fromisoformat(note['created'])
                days_old = (datetime.datetime.now() - created_date).days
                recency_score = max(0, 10 - (days_old / 30))  # Higher score for newer notes
            except (ValueError, TypeError):
                pass
        
        # 3. Connection density (graph centrality)
        if 'related_notes' in note:
            connection_score = len(note.get('related_notes', [])) * 0.5  # More connections = higher score
        
        # 4. Importance (based on note length and structure)
        if 'content' in note:
            content_length = len(note['content'])
            importance_score = min(5, content_length / 500)  # Longer notes up to a point
        
        # Calculate final score with weighted components
        final_score = (
            keyword_score * 1.0 +  # Primary factor
            recency_score * 0.3 +  # Recency matters but less than relevance
            connection_score * 0.5 +  # Connections are important
            importance_score * 0.2   # Note importance is a minor factor
        )
        
        scored_notes.append((title, note, final_score))
    
    # Sort by score and take the top N
    scored_notes.sort(key=lambda x: x[2], reverse=True)
    
    # Get the top nodes
    top_nodes = {title: note for title, note, _ in scored_notes[:max_nodes]}
    
    # If we have less than max_nodes, try to add related notes to provide more context
    if len(top_nodes) < max_nodes and len(top_nodes) > 0:
        # Collect all related notes from our top nodes
        related_titles = set()
        for note in top_nodes.values():
            if 'related_notes' in note:
                related_titles.update(note['related_notes'])
        
        # Remove notes we already have
        related_titles = related_titles - set(top_nodes.keys())
        
        # Add related notes until we reach max_nodes
        for title in related_titles:
            if title in notes and len(top_nodes) < max_nodes:
                top_nodes[title] = notes[title]
    
    return top_nodes

def process_direct_query(query, relevant_nodes, image_url=None, image_data=None):
    """Process a direct query using the relevant nodes"""
    # Generate the system message
    system_message = generate_system_message('direct', relevant_nodes)
    
    # Generate the user message
    user_message = generate_user_message(query, 'direct', image_data)
    
    # Use the agent to process the query with the relevant nodes
    global agent
    messages = [system_message, user_message]
    response = agent.process_query_with_messages(messages)
    
    return response

def process_expand_query(query, relevant_nodes, reasoning_depth=2, image_url=None, image_data=None):
    """Process a query to expand knowledge using iterative reasoning"""
    # Generate the system message
    system_message = generate_system_message('expand', relevant_nodes)
    
    # Generate the user message
    user_message = generate_user_message(query, 'expand', image_data)
    
    # Use the agent to process the query with the relevant nodes
    global agent
    messages = [system_message, user_message]
    response = agent.process_query_with_messages(messages)
    
    return response

def process_connect_query(query, relevant_nodes, reasoning_depth=2, image_url=None, image_data=None):
    """Process a query to connect concepts using graph-based reasoning"""
    # Generate the system message
    system_message = generate_system_message('connect', relevant_nodes)
    
    # Generate the user message
    user_message = generate_user_message(query, 'connect', image_data)
    
    # Initial response
    global agent
    messages = [system_message, user_message]
    response = agent.process_query_with_messages(messages)
    
    # Iterative reasoning to identify deeper connections
    for i in range(reasoning_depth - 1):
        # Add the previous response to the messages
        messages.append({"role": "assistant", "content": response})
        
        # Add a follow-up prompt
        messages.append({
            "role": "user", 
            "content": [{"type": "text", "text": "Please identify additional connections and patterns between these concepts."}]
        })
        
        # Get the next response
        response = agent.process_query_with_messages(messages)
    
    return response

def process_synthesize_query(query, relevant_nodes, reasoning_depth=2, image_url=None, image_data=None):
    """Process a query to synthesize new knowledge using iterative reasoning"""
    # Generate the system message
    system_message = generate_system_message('synthesize', relevant_nodes)
    
    # Generate the user message
    user_message = generate_user_message(query, 'synthesize', image_data)
    
    # Initial response
    global agent
    messages = [system_message, user_message]
    response = agent.process_query_with_messages(messages)
    
    # Iterative reasoning to synthesize new knowledge
    for i in range(reasoning_depth - 1):
        # Add the previous response to the messages
        messages.append({"role": "assistant", "content": response})
        
        # Add a follow-up prompt
        messages.append({
            "role": "user", 
            "content": [{"type": "text", "text": "Please continue synthesizing new knowledge based on these concepts."}]
        })
        
        # Get the next response
        response = agent.process_query_with_messages(messages)
    
    return response

@app.route('/note/<title>')
def view_note(title):
    """View a specific note"""
    content = garden.get_note_content(title)
    return render_template('note.html', title=title, content=content)

@app.route('/tag/<tag>')
def view_tag(tag):
    """View all notes with a specific tag"""
    notes_with_tag = garden.index.get("tags", {}).get(tag, [])
    return render_template('tag.html', tag=tag, notes=notes_with_tag)

@app.route('/explore', methods=['POST'])
def explore_topic():
    """Start autonomous exploration on a topic using graph-based reasoning"""
    topic = request.form.get('topic', '')
    iterations = int(request.form.get('iterations', 3))
    exploration_type = request.form.get('exploration_type', 'breadth')
    
    if not topic:
        flash('Please enter a topic to explore')
        return redirect(url_for('index'))
    
    # Start exploration in a background thread
    import threading
    def run_exploration():
        try:
            if exploration_type == 'breadth':
                # Breadth-first exploration - explore many related concepts
                agent.autonomous_exploration(topic, iterations=iterations, depth=1, exploration_type='breadth')
                flash(f'Breadth-first exploration of "{topic}" completed with {iterations} iterations')
            elif exploration_type == 'depth':
                # Depth-first exploration - explore fewer concepts in detail
                agent.autonomous_exploration(topic, iterations=iterations, depth=3, exploration_type='depth')
                flash(f'Depth-first exploration of "{topic}" completed with {iterations} iterations')
            elif exploration_type == 'hub':
                # Hub-focused exploration - build around central concepts
                agent.autonomous_exploration(topic, iterations=iterations, depth=2, exploration_type='hub')
                flash(f'Hub-focused exploration of "{topic}" completed with {iterations} iterations')
            elif exploration_type == 'bridge':
                # Bridge-focused exploration - connect disparate knowledge areas
                agent.autonomous_exploration(topic, iterations=iterations, depth=2, exploration_type='bridge')
                flash(f'Bridge-focused exploration of "{topic}" completed with {iterations} iterations')
            else:
                # Default to breadth-first
                agent.autonomous_exploration(topic, iterations=iterations)
                flash(f'Exploration of "{topic}" completed with {iterations} iterations')
        except Exception as e:
            flash(f'Error during exploration: {str(e)}')
            import traceback
            traceback.print_exc()
    
    # Start the exploration in a background thread
    thread = threading.Thread(target=run_exploration)
    thread.daemon = True
    thread.start()
    
    flash(f'Started exploration of "{topic}" with {iterations} iterations. This will run in the background.')
    return redirect(url_for('index'))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/image/<title>')
def view_image(title):
    """View a specific image note with enhanced display for GPT-4o"""
    content = garden.get_note_content(title)
    
    # Extract the image URL from the markdown content
    import re
    image_match = re.search(r'!\[.*?\]\((.*?)\)', content)
    image_url = image_match.group(1) if image_match else None
    
    # Extract base64 data if available
    base64_match = re.search(r'<!-- Base64 image data for AI models: (data:image/.*?) -->', content)
    base64_data = base64_match.group(1) if base64_match else None
    
    return render_template('image.html', title=title, content=content, 
                          image_url=image_url, base64_data=base64_data)

@app.route('/preview_query', methods=['POST'])
def preview_query():
    """Preview the query that will be sent to the AI assistant"""
    query = request.form.get('query', '')
    if not query:
        return jsonify({"error": "No query provided"}), 400
    
    # Get query parameters
    query_type = request.form.get('query_type', 'direct')
    max_context_nodes = int(request.form.get('max_context_nodes', 5))
    image_detail = request.form.get('image_detail', 'auto')  # Get image detail level from form
    
    # Check if an image was uploaded with the query
    image_data = None
    if 'image' in request.files and request.files['image'].filename:
        image_file = request.files['image']
        if is_image_file(image_file.filename):
            # Save the image
            filename = secure_filename(image_file.filename)
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(file_path)
            
            # Process the image according to OpenAI API standards
            try:
                # Use the specified detail level
                image_data = process_image_for_query(file_path, detail=image_detail)
            except Exception as e:
                print(f"Error processing image for preview: {str(e)}")
    
    # Find relevant nodes in the knowledge graph
    relevant_nodes = find_relevant_nodes(query, max_nodes=max_context_nodes)
    
    # Generate the system message
    system_message = generate_system_message(query_type, relevant_nodes)
    
    # Generate the user message
    user_message = generate_user_message(query, query_type, image_data)
    
    # Estimate token count
    token_count = estimate_token_count(system_message["content"], 
                                      user_message["content"][0]["text"] if isinstance(user_message["content"], list) else user_message["content"])
    
    # Prepare the preview data
    preview_data = {
        "system_message": system_message["content"],
        "user_message": user_message["content"][0]["text"] if isinstance(user_message["content"], list) else user_message["content"],
        "has_image": image_data is not None,
        "image_detail": image_detail if image_data else None,
        "token_count": token_count,
        "node_count": len(relevant_nodes),
        "relevant_nodes": list(relevant_nodes.keys())
    }
    
    return jsonify(preview_data)

def generate_system_message(query_type, relevant_nodes):
    """Generate a system message based on the query type and relevant nodes"""
    system_message = "You are an advanced AI knowledge gardener with vision capabilities that helps users explore and grow their knowledge graph. "
    system_message += "You can analyze images and connect visual information with the knowledge graph. "
    system_message += "You are part of an autonomous knowledge gardening system that uses agentic principles to grow and maintain a knowledge graph. "
    
    if query_type == 'direct':
        system_message += "Answer the user's question directly using the knowledge provided below. If an image is provided, analyze it and incorporate your analysis into your response. "
    elif query_type == 'expand':
        system_message += "Expand on the user's topic by generating new insights and connections. If an image is provided, use it to enrich your expansion with visual insights. "
    elif query_type == 'connect':
        system_message += "Identify connections between concepts related to the user's query. If an image is provided, find connections between the visual content and the knowledge graph. "
    elif query_type == 'synthesize':
        system_message += "Synthesize new knowledge based on the concepts provided by the user. If an image is provided, incorporate visual information into your synthesis. "
    
    # Add relevant nodes to the system message
    if relevant_nodes:
        system_message += "\n\nHere is the relevant knowledge from the graph:\n\n"
        for title, note in relevant_nodes.items():
            content = note.get('content', 'No content available')
            system_message += f"--- {title} ---\n{content}\n\n"
    
    # Return the message in the format expected by the OpenAI API
    return {"role": "system", "content": system_message}

def generate_user_message(query, query_type, image_data=None):
    """Generate a user message based on the query type"""
    image_instruction = ""
    if image_data:
        image_instruction = " I've attached an image that you should analyze as part of your response. Use your vision capabilities to extract information from the image and connect it with the knowledge graph."
    
    if query_type == 'direct':
        user_message = f"Please answer my question using the knowledge provided in the system message: {query}{image_instruction}"
    elif query_type == 'expand':
        user_message = f"Please expand on this topic using the knowledge provided and generate new insights: {query}{image_instruction}"
    elif query_type == 'connect':
        user_message = f"Please identify connections between concepts related to: {query}{image_instruction}"
    elif query_type == 'synthesize':
        user_message = f"Please synthesize new knowledge based on these concepts: {query}{image_instruction}"
    else:
        user_message = f"Please respond to this query: {query}{image_instruction}"
    
    # Return the message in the format expected by the OpenAI API
    message = {"role": "user", "content": [{"type": "text", "text": user_message}]}
    
    # Add image data if provided
    if image_data:
        message["content"].append(image_data)
    
    return message

def estimate_token_count(system_message, user_message):
    """Estimate the token count for a query"""
    # A very rough estimate: 1 token ≈ 4 characters for English text
    # This is a simplification; actual tokenization is more complex
    
    # Calculate the total character count
    total_chars = len(system_message) + len(user_message)
    
    # Add overhead for image if present (rough estimate)
    if "image" in user_message.lower():
        # Add a rough estimate for image tokens
        # Low detail: ~85 tokens, High detail: ~170 tokens
        total_chars += 340  # Equivalent to ~85 tokens
    
    # Estimate tokens (4 chars per token is a rough approximation)
    estimated_tokens = total_chars // 4
    
    return estimated_tokens

def create_templates():
    """Create the necessary template files for the web interface"""
    templates_dir = Path('templates')
    templates_dir.mkdir(exist_ok=True)
    
    # Create index.html
    index_html = """<!DOCTYPE html>
<html>
<head>
    <title>Knowledge Garden Interface</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            max-width: 1200px;
            margin: 0 auto;
            color: #333;
        }
        h1, h2, h3 {
            color: #2c3e50;
        }
        .container {
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
        }
        .card {
            background: #f9f9f9;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            flex: 1;
            min-width: 300px;
        }
        .form-group {
            margin-bottom: 15px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
        }
        input[type="text"], textarea {
            width: 100%;
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        button {
            background: #3498db;
            color: white;
            border: none;
            padding: 10px 15px;
            border-radius: 4px;
            cursor: pointer;
        }
        button:hover {
            background: #2980b9;
        }
        .flash-messages {
            margin-bottom: 20px;
        }
        .flash-message {
            padding: 10px;
            background: #d4edda;
            border-radius: 4px;
            margin-bottom: 10px;
        }
        .notes-list {
            list-style: none;
            padding: 0;
        }
        .notes-list li {
            margin-bottom: 8px;
        }
        .notes-list a {
            color: #3498db;
            text-decoration: none;
        }
        .notes-list a:hover {
            text-decoration: underline;
        }
        .tags-list {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 10px;
        }
        .tag {
            background: #e0e0e0;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.9em;
            color: #333;
            text-decoration: none;
        }
        .tag:hover {
            background: #d0d0d0;
        }
        .help-text {
            font-size: 0.8em;
            color: #666;
            margin-top: 5px;
        }
    </style>
</head>
<body>
    <h1>Knowledge Garden Interface</h1>
    
    <div class="flash-messages">
        {% for message in get_flashed_messages() %}
            <div class="flash-message">{{ message }}</div>
        {% endfor %}
    </div>
    
    <div class="container">
        <div class="card">
            <h2>Upload File</h2>
            <form action="/upload" method="post" enctype="multipart/form-data">
                <div class="form-group">
                    <label for="file">Select File:</label>
                    <input type="file" id="file" name="file" required>
                </div>
                <div class="form-group">
                    <label for="title">Title (optional, will use filename if empty):</label>
                    <input type="text" id="title" name="title">
                </div>
                <div class="form-group">
                    <label for="tags">Tags (comma separated):</label>
                    <input type="text" id="tags" name="tags" placeholder="tag1, tag2, tag3">
                </div>
                <div class="form-group">
                    <label>
                        <input type="checkbox" name="extract_insights" checked>
                        Extract insights from this file
                    </label>
                </div>
                <button type="submit">Upload</button>
            </form>
        </div>
        
        <div class="card">
            <h2>Ask the Knowledge Garden</h2>
            <form action="/query" method="post" enctype="multipart/form-data">
                <div class="form-group">
                    <label for="query">Your Query:</label>
                    <textarea id="query" name="query" rows="4" required placeholder="Ask a question or give a command..."></textarea>
                </div>
                <div class="form-group">
                    <label for="image">Attach Image (optional):</label>
                    <input type="file" id="image" name="image" accept="image/*">
                    <div class="help-text">
                        You can attach an image to your query to ask questions about it
                    </div>
                </div>
                <button type="submit">Submit</button>
            </form>
        </div>
        
        <div class="card">
            <h2>Explore a Topic</h2>
            <form action="/explore" method="post">
                <div class="form-group">
                    <label for="topic">Topic:</label>
                    <input type="text" id="topic" name="topic" required placeholder="Enter a topic to explore">
                </div>
                <div class="form-group">
                    <label for="iterations">Iterations:</label>
                    <input type="number" id="iterations" name="iterations" value="3" min="1" max="10">
                </div>
                <button type="submit">Start Exploration</button>
            </form>
        </div>
    </div>
    
    <div class="container" style="margin-top: 20px;">
        <div class="card">
            <h2>Notes in the Garden</h2>
            <ul class="notes-list">
                {% for title, note in notes.items() %}
                    <li>
                        <a href="/note/{{ title }}">{{ title }}</a>
                        <div class="tags-list">
                            {% for tag in note.tags %}
                                <a href="/tag/{{ tag }}" class="tag">{{ tag }}</a>
                            {% endfor %}
                        </div>
                    </li>
                {% endfor %}
            </ul>
        </div>
        
        <div class="card">
            <h2>Tags</h2>
            <div class="tags-list">
                {% for tag in tags %}
                    <a href="/tag/{{ tag }}" class="tag">{{ tag }}</a>
                {% endfor %}
            </div>
        </div>
    </div>
</body>
</html>"""
    
    # Create note.html
    note_html = """<!DOCTYPE html>
<html>
<head>
    <title>{{ title }} - Knowledge Garden</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            max-width: 1000px;
            margin: 0 auto;
            color: #333;
        }
        h1, h2, h3 {
            color: #2c3e50;
        }
        .note-content {
            background: #f9f9f9;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        a {
            color: #3498db;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
        .back-link {
            display: inline-block;
            margin-bottom: 20px;
        }
        img {
            max-width: 100%;
            height: auto;
            display: block;
            margin: 20px 0;
            border-radius: 4px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .image-container {
            margin: 20px 0;
        }
        .image-caption {
            font-style: italic;
            color: #666;
            margin-top: 8px;
            text-align: center;
        }
        .metadata {
            margin-top: 30px;
            padding-top: 15px;
            border-top: 1px solid #eee;
            font-size: 0.9em;
            color: #666;
        }
    </style>
</head>
<body>
    <a href="/" class="back-link">← Back to Knowledge Garden</a>
    
    <div class="note-content">
        {{ content | safe }}
    </div>

    <script>
        // Script to enhance image display
        document.addEventListener('DOMContentLoaded', function() {
            // Find all images in the content
            const images = document.querySelectorAll('.note-content img');
            
            // Process each image
            images.forEach(function(img) {
                // Create a container for the image
                const container = document.createElement('div');
                container.className = 'image-container';
                
                // Move the image into the container
                img.parentNode.insertBefore(container, img);
                container.appendChild(img);
                
                // Add a caption if the image has an alt text
                if (img.alt && img.alt !== '') {
                    const caption = document.createElement('div');
                    caption.className = 'image-caption';
                    caption.textContent = img.alt;
                    container.appendChild(caption);
                }
                
                // Make images clickable to view full size
                img.style.cursor = 'pointer';
                img.addEventListener('click', function() {
                    window.open(img.src, '_blank');
                });
            });
        });
    </script>
</body>
</html>"""
    
    # Create tag.html
    tag_html = """<!DOCTYPE html>
<html>
<head>
    <title>Tag: {{ tag }} - Knowledge Garden</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            max-width: 1000px;
            margin: 0 auto;
            color: #333;
        }
        h1, h2, h3 {
            color: #2c3e50;
        }
        .card {
            background: #f9f9f9;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        a {
            color: #3498db;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
        .back-link {
            display: inline-block;
            margin-bottom: 20px;
        }
        .notes-list {
            list-style: none;
            padding: 0;
        }
        .notes-list li {
            margin-bottom: 10px;
        }
    </style>
</head>
<body>
    <a href="/" class="back-link">← Back to Knowledge Garden</a>
    
    <h1>Notes tagged with "{{ tag }}"</h1>
    
    <div class="card">
        <ul class="notes-list">
            {% for title in notes %}
                <li><a href="/note/{{ title }}">{{ title }}</a></li>
            {% endfor %}
        </ul>
    </div>
</body>
</html>"""
    
    # Create image.html for enhanced image viewing
    image_html = """<!DOCTYPE html>
<html>
<head>
    <title>{{ title }} - Knowledge Garden</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            max-width: 1200px;
            margin: 0 auto;
            color: #333;
        }
        h1, h2, h3 {
            color: #2c3e50;
        }
        .container {
            display: flex;
            flex-direction: column;
            gap: 20px;
        }
        .image-card {
            background: #f9f9f9;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .image-container {
            text-align: center;
            margin: 20px 0;
        }
        img {
            max-width: 100%;
            height: auto;
            border-radius: 4px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .metadata {
            margin-top: 20px;
            padding-top: 15px;
            border-top: 1px solid #eee;
            font-size: 0.9em;
            color: #666;
        }
        a {
            color: #3498db;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
        .back-link {
            display: inline-block;
            margin-bottom: 20px;
        }
        .note-content {
            margin-top: 20px;
        }
        .hidden {
            display: none;
        }
    </style>
</head>
<body>
    <a href="/" class="back-link">← Back to Knowledge Garden</a>
    
    <h1>{{ title }}</h1>
    
    <div class="container">
        <div class="image-card">
            <div class="image-container">
                {% if image_url %}
                <img src="{{ image_url }}" alt="{{ title }}">
                {% else %}
                <p>No image found in this note.</p>
                {% endif %}
            </div>
            
            <div class="metadata">
                {% if image_data %}
                <!-- This base64 data is included for AI models like GPT-4o to see the image -->
                <img src="{{ image_data['type'] }}" alt="Base64 encoded image" class="hidden">
                {% endif %}
            </div>
        </div>
        
        <div class="image-card">
            <h2>Note Content</h2>
            <div class="note-content">
                {{ content | safe }}
            </div>
        </div>
    </div>
</body>
</html>"""
    
    # Write the template files
    with open(templates_dir / 'index.html', 'w') as f:
        f.write(index_html)
    
    with open(templates_dir / 'note.html', 'w') as f:
        f.write(note_html)
    
    with open(templates_dir / 'tag.html', 'w') as f:
        f.write(tag_html)
    
    with open(templates_dir / 'image.html', 'w') as f:
        f.write(image_html)

def main():
    """Main function to run the knowledge garden interface"""
    parser = argparse.ArgumentParser(description="Knowledge Garden Web Interface")
    parser.add_argument("--garden", default="knowledge_garden", help="Directory for the knowledge garden")
    parser.add_argument("--port", type=int, default=5000, help="Port to run the web server on")
    parser.add_argument("--host", default="0.0.0.0", help="Host to run the web server on")
    parser.add_argument("--api-key", type=str, help="OpenAI API key (alternatively, set OPENAI_API_KEY environment variable)")
    
    args = parser.parse_args()
    
    # Create template files
    create_templates()
    
    # Create uploads directory
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    # Initialize OpenAI client
    global client, garden, agent
    client = initialize_openai_client(args.api_key)
    
    # Make sure the client is also set in the knowledge_garden module
    import knowledge_garden
    knowledge_garden.client = client
    
    # Initialize knowledge garden and agent
    garden = KnowledgeGarden(args.garden)
    agent = KnowledgeGardenAgent(garden)
    
    print(f"Knowledge Garden Interface running at http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=True)

def process_image_for_query(file_path, detail="auto"):
    """Process an image for a query according to OpenAI API standards
    
    Args:
        file_path: Path to the image file
        detail: Level of detail for image analysis ('auto', 'low', or 'high')
        
    Returns:
        A dictionary formatted for the OpenAI API with the image data
    """
    try:
        import base64
        from PIL import Image
        import io
        
        # Open the image
        img = Image.open(file_path)
        
        # Resize images based on detail level according to OpenAI documentation
        if detail == "low":
            # For low detail, resize to 512x512
            img.thumbnail((512, 512), Image.LANCZOS)
        elif detail == "high":
            # For high detail, ensure the shortest side is 768px and longest side is under 2000px
            width, height = img.size
            
            # First, ensure the image fits within a 2048x2048 square
            if max(width, height) > 2048:
                scale_factor = 2048 / max(width, height)
                new_width = int(width * scale_factor)
                new_height = int(height * scale_factor)
                img = img.resize((new_width, new_height), Image.LANCZOS)
                width, height = new_width, new_height
            
            # Then, ensure the shortest side is 768px
            shortest_side = min(width, height)
            if shortest_side != 768:
                scale_factor = 768 / shortest_side
                new_width = int(width * scale_factor)
                new_height = int(height * scale_factor)
                img = img.resize((new_width, new_height), Image.LANCZOS)
        else:  # auto
            # For auto, let the API decide but still ensure reasonable dimensions
            width, height = img.size
            if max(width, height) > 2048:
                scale_factor = 2048 / max(width, height)
                new_width = int(width * scale_factor)
                new_height = int(height * scale_factor)
                img = img.resize((new_width, new_height), Image.LANCZOS)
        
        # Convert to base64
        buffer = io.BytesIO()
        img_format = Path(file_path).suffix[1:].upper()
        if img_format not in ['JPEG', 'PNG', 'GIF', 'WEBP']:
            img_format = 'PNG'  # Default to PNG for unsupported formats
        
        img.save(buffer, format=img_format)
        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        # Return the image data in the format expected by the OpenAI API
        return {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/{img_format.lower()};base64,{img_base64}",
                "detail": detail
            }
        }
        
    except Exception as e:
        print(f"Error processing image for query: {str(e)}")
        return None

if __name__ == "__main__":
    main() 