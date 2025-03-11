import os
import json
import datetime
import time
import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
import openai
import random

# Initialize the OpenAI client with better error handling
def initialize_openai_client(api_key=None):
    """Initialize the OpenAI client with the provided API key or from environment variable"""
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        print("Error: OpenAI API key not found. Please provide it using --api-key or set the OPENAI_API_KEY environment variable.")
        sys.exit(1)
    return openai.OpenAI(api_key=key)

# Client will be initialized in main()
client = None

# Define tool schemas
knowledge_garden_tools = [
    {
        "type": "function",
        "function": {
            "name": "add_note",
            "description": "Add a new note to the knowledge garden",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "The title of the note"
                    },
                    "content": {
                        "type": "string",
                        "description": "The content of the note"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags to categorize the note"
                    },
                    "related_notes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Titles of related notes in the garden"
                    }
                },
                "required": ["title", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_notes",
            "description": "Search for notes in the knowledge garden",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by tags"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "expand_knowledge",
            "description": "Generate new knowledge based on existing notes",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_title": {
                        "type": "string",
                        "description": "Title of the note to expand upon"
                    },
                    "expansion_type": {
                        "type": "string",
                        "enum": ["elaborate", "contrast", "question", "application", "connection"],
                        "description": "Type of knowledge expansion to perform"
                    },
                    "depth": {
                        "type": "integer",
                        "description": "Depth of expansion (1-3)",
                        "minimum": 1,
                        "maximum": 3,
                        "default": 1
                    }
                },
                "required": ["note_title", "expansion_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "extract_insights",
            "description": "Extract key insights from a text and add them as separate notes",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to extract insights from"
                    },
                    "parent_note": {
                        "type": "string",
                        "description": "The title of the parent note these insights relate to"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags to apply to all extracted insights"
                    }
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_exploration_path",
            "description": "Create a structured exploration path for a topic",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "The main topic to explore"
                    },
                    "subtopics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of subtopics to explore"
                    },
                    "description": {
                        "type": "string",
                        "description": "Description of this exploration path"
                    }
                },
                "required": ["topic", "subtopics"]
            }
        }
    }
]

class KnowledgeGarden:
    """A garden of knowledge notes with semantic search capabilities"""
    
    def __init__(self, garden_dir="knowledge_garden"):
        """Initialize the knowledge garden"""
        self.garden_dir = Path(garden_dir)
        self.notes_dir = self.garden_dir / "notes"
        self.index_file = self.garden_dir / "index.json"
        self.index = {}
        self.exploration_paths = {}
        # Store a reference to the global client
        global client
        self.client = client
        
        # Set up the garden directory structure
        self.setup_garden()
        
    def setup_garden(self):
        """Set up the knowledge garden directory structure"""
        self.garden_dir.mkdir(exist_ok=True)
        self.notes_dir.mkdir(exist_ok=True)
        self.paths_dir = self.garden_dir / "paths"
        self.paths_dir.mkdir(exist_ok=True)
        
        if not self.index_file.exists():
            # Initialize empty index
            with open(self.index_file, "w") as f:
                json.dump({
                    "notes": {},
                    "tags": {},
                    "paths": {},
                    "last_updated": datetime.datetime.now().isoformat()
                }, f, indent=2)
    
    def load_index(self):
        """Load the knowledge garden index"""
        with open(self.index_file, "r") as f:
            self.index = json.load(f)
            # Ensure paths key exists
            if "paths" not in self.index:
                self.index["paths"] = {}
    
    def save_index(self):
        """Save the knowledge garden index"""
        self.index["last_updated"] = datetime.datetime.now().isoformat()
        with open(self.index_file, "w") as f:
            json.dump(self.index, f, indent=2)
    
    def add_note(self, title, content, tags=None, related_notes=None):
        """Add a new note to the knowledge garden"""
        # Normalize title to use as filename
        filename = title.lower().replace(" ", "_").replace("/", "_")
        note_path = self.notes_dir / f"{filename}.md"
        
        # Format the markdown content
        md_content = f"# {title}\n\n{content}\n"
        
        # Add metadata
        tags = tags or []
        related_notes = related_notes or []
        
        metadata = {
            "title": title,
            "created": datetime.datetime.now().isoformat(),
            "tags": tags,
            "related_notes": related_notes
        }
        
        md_content += "\n---\n"
        md_content += f"Created: {metadata['created']}\n"
        md_content += f"Tags: {', '.join(tags)}\n"
        if related_notes:
            md_content += f"Related: {', '.join(related_notes)}\n"
        
        # Save the note
        with open(note_path, "w") as f:
            f.write(md_content)
        
        # Update the index
        self.index["notes"][title] = {
            "path": str(note_path.relative_to(self.garden_dir)),
            "created": metadata["created"],
            "tags": tags,
            "related_notes": related_notes
        }
        
        # Update tag index
        for tag in tags:
            if tag not in self.index["tags"]:
                self.index["tags"][tag] = []
            if title not in self.index["tags"][tag]:
                self.index["tags"][tag].append(title)
        
        # Update related notes (bidirectional linking)
        for related in related_notes:
            if related in self.index["notes"]:
                if title not in self.index["notes"][related]["related_notes"]:
                    self.index["notes"][related]["related_notes"].append(title)
                    
                    # Update the related note file with the new relationship
                    related_path = self.garden_dir / self.index["notes"][related]["path"]
                    if related_path.exists():
                        with open(related_path, "r") as f:
                            related_content = f.read()
                        
                        # Add the new relation if it doesn't exist
                        if f"Related: " in related_content:
                            # Update existing Related section
                            lines = related_content.split("\n")
                            for i, line in enumerate(lines):
                                if line.startswith("Related: "):
                                    if title not in line:
                                        if line.endswith("Related: "):
                                            lines[i] += f"{title}"
                                        else:
                                            lines[i] += f", {title}"
                                    break
                            
                            related_content = "\n".join(lines)
                        else:
                            # Add new Related section
                            related_content += f"Related: {title}\n"
                        
                        with open(related_path, "w") as f:
                            f.write(related_content)
        
        self.save_index()
        
        return f"Note '{title}' added to the knowledge garden"
    
    def search_notes(self, query, tags=None, limit=5):
        """Search for notes in the knowledge garden"""
        results = []
        
        # Filter by tags if provided
        candidate_notes = self.index["notes"].items()
        if tags:
            tag_filtered_notes = set()
            for tag in tags:
                if tag in self.index["tags"]:
                    tag_filtered_notes.update(self.index["tags"][tag])
            
            candidate_notes = [(title, data) for title, data in candidate_notes 
                               if title in tag_filtered_notes]
        
        # Search by query
        for title, data in candidate_notes:
            note_path = self.garden_dir / data["path"]
            if note_path.exists():
                with open(note_path, "r") as f:
                    content = f.read()
                
                # Simple search - check if query is in title or content
                if query.lower() in title.lower() or query.lower() in content.lower():
                    results.append({
                        "title": title,
                        "preview": content[:200] + "..." if len(content) > 200 else content,
                        "tags": data["tags"],
                        "created": data["created"],
                        "related_notes": data["related_notes"]
                    })
        
        # Sort by relevance (very basic - title matches first)
        results.sort(key=lambda x: query.lower() in x["title"].lower(), reverse=True)
        
        return results[:limit]
    
    def get_note_content(self, title):
        """Get the content of a note by title"""
        if title in self.index["notes"]:
            note_path = self.garden_dir / self.index["notes"][title]["path"]
            if note_path.exists():
                with open(note_path, "r") as f:
                    return f.read()
        
        return None
    
    def expand_knowledge(self, note_title, expansion_type, depth=1):
        """Generate new knowledge based on existing notes"""
        # Get the content of the note to expand
        note_content = self.get_note_content(note_title)
        if not note_content:
            return f"Note '{note_title}' not found in the knowledge garden"
        
        # Prepare the expansion prompt based on the expansion type
        if expansion_type == "elaborate":
            prompt = f"Elaborate on the concepts in this note, providing more detail and examples:\n\n{note_content}"
        elif expansion_type == "contrast":
            prompt = f"Contrast the ideas in this note with alternative perspectives:\n\n{note_content}"
        elif expansion_type == "question":
            prompt = f"Generate thought-provoking questions related to this note:\n\n{note_content}"
        elif expansion_type == "application":
            prompt = f"Explore practical applications of the concepts in this note:\n\n{note_content}"
        elif expansion_type == "connection":
            prompt = f"Identify connections between this note and other domains or concepts:\n\n{note_content}"
        else:
            return f"Unknown expansion type: {expansion_type}"
        
        # Get related notes for context if depth > 1
        if depth > 1:
            related_titles = self.index["notes"].get(note_title, {}).get("related_notes", [])
            related_contents = []
            
            for related_title in related_titles[:depth]:
                related_content = self.get_note_content(related_title)
                if related_content:
                    related_contents.append(f"Related note '{related_title}':\n{related_content}")
            
            if related_contents:
                prompt += "\n\nAdditional context from related notes:\n\n" + "\n\n".join(related_contents)
        
        # Call the AI to generate new knowledge
        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a knowledge gardener. Generate new insights based on existing notes."},
                {"role": "user", "content": prompt}
            ]
        )
        
        expansion_content = response.choices[0].message.content
        
        # Create a new note with the expanded knowledge
        expansion_title = f"{note_title} - {expansion_type.capitalize()}"
        expansion_tags = self.index["notes"].get(note_title, {}).get("tags", []) + [expansion_type]
        
        return self.add_note(
            title=expansion_title,
            content=expansion_content,
            tags=expansion_tags,
            related_notes=[note_title]
        )
    
    def extract_insights(self, text, parent_note=None, tags=None):
        """Extract key insights from text and add them as separate notes"""
        prompt = f"""
        Extract 3-5 key insights from the following text. For each insight:
        1. Create a clear, concise title (5-10 words)
        2. Write a detailed explanation (2-3 paragraphs)
        3. Suggest 3-5 relevant tags

        Text to analyze:
        {text}
        
        Format your response as follows for each insight:
        
        INSIGHT TITLE: [Title]
        
        CONTENT:
        [Detailed explanation]
        
        TAGS: [tag1], [tag2], [tag3]
        
        ---
        """
        
        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a knowledge gardener. Extract key insights from text."},
                {"role": "user", "content": prompt}
            ]
        )
        
        insights_text = response.choices[0].message.content
        
        # Parse the insights
        insight_pattern = r"INSIGHT TITLE: (.*?)\s*\n+CONTENT:\s*(.*?)\s*\n+TAGS: (.*?)(?:\s*\n+---|$)"
        insights = re.findall(insight_pattern, insights_text, re.DOTALL)
        
        results = []
        for title, content, tags_str in insights:
            # Clean up the extracted data
            title = title.strip()
            content = content.strip()
            insight_tags = [tag.strip() for tag in tags_str.split(",")]
            
            # Add user-provided tags
            if tags:
                insight_tags.extend(tags)
            
            # Set up related notes
            related = []
            if parent_note:
                related.append(parent_note)
            
            # Add the note
            result = self.add_note(
                title=title,
                content=content,
                tags=insight_tags,
                related_notes=related
            )
            results.append(result)
        
        return f"Extracted {len(insights)} insights from the text"
    
    def create_exploration_path(self, topic, subtopics, description=None):
        """Create a structured exploration path for a topic"""
        path_id = topic.lower().replace(" ", "_")
        path_file = self.paths_dir / f"{path_id}.json"
        
        path_data = {
            "topic": topic,
            "subtopics": subtopics,
            "description": description or f"Exploration path for {topic}",
            "created": datetime.datetime.now().isoformat(),
            "notes": []
        }
        
        # Save the path file
        with open(path_file, "w") as f:
            json.dump(path_data, f, indent=2)
        
        # Update the index
        self.index["paths"][topic] = {
            "path": str(path_file.relative_to(self.garden_dir)),
            "created": path_data["created"],
            "subtopics": subtopics
        }
        
        self.save_index()
        
        return f"Created exploration path for '{topic}' with {len(subtopics)} subtopics"
    
    def add_note_to_path(self, path_topic, note_title):
        """Add a note to an exploration path"""
        if path_topic not in self.index["paths"]:
            return f"Path '{path_topic}' not found"
        
        if note_title not in self.index["notes"]:
            return f"Note '{note_title}' not found"
        
        path_file = self.garden_dir / self.index["paths"][path_topic]["path"]
        
        with open(path_file, "r") as f:
            path_data = json.load(f)
        
        if note_title not in path_data["notes"]:
            path_data["notes"].append(note_title)
            
            with open(path_file, "w") as f:
                json.dump(path_data, f, indent=2)
            
            return f"Added note '{note_title}' to path '{path_topic}'"
        else:
            return f"Note '{note_title}' already in path '{path_topic}'"

class KnowledgeGardenAgent:
    """Agent to autonomously manage and grow the knowledge garden"""
    
    def __init__(self, garden):
        self.garden = garden
        self.exploration_history = []
        # Store a reference to the global client
        global client
        self.client = client
        
    def handle_tool_calls(self, tool_calls):
        """Process tool calls from the assistant"""
        results = []
        
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            
            if function_name == "add_note":
                title = function_args.get("title")
                content = function_args.get("content")
                tags = function_args.get("tags", [])
                related_notes = function_args.get("related_notes", [])
                
                result = self.garden.add_note(title, content, tags, related_notes)
                results.append(result)
                
            elif function_name == "search_notes":
                query = function_args.get("query")
                tags = function_args.get("tags", [])
                limit = function_args.get("limit", 5)
                
                search_results = self.garden.search_notes(query, tags, limit)
                result = json.dumps(search_results, indent=2)
                results.append(result)
                
            elif function_name == "expand_knowledge":
                note_title = function_args.get("note_title")
                expansion_type = function_args.get("expansion_type")
                depth = function_args.get("depth", 1)
                
                result = self.garden.expand_knowledge(note_title, expansion_type, depth)
                results.append(result)
                
            elif function_name == "extract_insights":
                text = function_args.get("text")
                parent_note = function_args.get("parent_note")
                tags = function_args.get("tags", [])
                
                result = self.garden.extract_insights(text, parent_note, tags)
                results.append(result)
                
            elif function_name == "create_exploration_path":
                topic = function_args.get("topic")
                subtopics = function_args.get("subtopics")
                description = function_args.get("description")
                
                result = self.garden.create_exploration_path(topic, subtopics, description)
                results.append(result)
        
        return results
    
    def process_query(self, query, model="gpt-4o", context_notes=None, system_message=None):
        """Process a user query with the AI assistant
        
        Args:
            query: The user's query text
            model: The OpenAI model to use
            context_notes: Optional dict of notes to use as context (for limiting context size)
            system_message: Optional custom system message to use
        """
        # Create system message with context from the knowledge garden
        if system_message is None:
            system_message = "You are a knowledge gardener. Your goal is to build a rich, interconnected knowledge garden by creating notes, extracting insights, and establishing connections between concepts."
            
            # Add context from the knowledge garden if available
            if context_notes is not None:
                # Use the provided limited context
                context = []
                for title, note in context_notes.items():
                    content = note.get('content', '')
                    tags = note.get('tags', [])
                    context.append(f"Note: {title}\nContent: {content}\nTags: {', '.join(tags)}\n---")
                
                if context:
                    system_message += "\n\nHere are some notes from the knowledge garden that might be relevant:\n\n"
                    system_message += "\n".join(context)
            else:
                # Use all notes (original behavior)
                notes = self.garden.index.get("notes", {})
                if notes:
                    context = []
                    for title, note in notes.items():
                        content = note.get('content', '')
                        tags = note.get('tags', [])
                        context.append(f"Note: {title}\nContent: {content}\nTags: {', '.join(tags)}\n---")
                    
                    system_message += "\n\nHere are some notes from the knowledge garden that might be relevant:\n\n"
                    system_message += "\n".join(context)
        
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": query}
        ]
        
        # Estimate token count before sending
        token_count = (len(system_message) + len(query)) // 4  # Rough estimate
        print(f"Estimated token count: {token_count}")
        
        # Check if we're likely to exceed the token limit
        if token_count > 100000:  # GPT-4o limit is 128k, leave some margin
            print(f"Warning: Large token count ({token_count}). Truncating context.")
            # Truncate the system message to reduce tokens
            max_system_length = 100000 * 4  # Approximate character limit
            if len(system_message) > max_system_length:
                # Keep the beginning and end of the system message
                beginning = system_message[:max_system_length // 2]
                ending = system_message[-max_system_length // 2:]
                system_message = beginning + "\n\n... [content truncated due to length] ...\n\n" + ending
                messages[0]["content"] = system_message
                print(f"System message truncated. New estimated token count: {(len(system_message) + len(query)) // 4}")
        
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            tools=knowledge_garden_tools,
            tool_choice="auto"
        )
        
        assistant_message = response.choices[0].message
        
        # Check if the model wants to use tools
        if assistant_message.tool_calls:
            # Handle the tool calls
            tool_results = self.handle_tool_calls(assistant_message.tool_calls)
            
            # Add the tool results to the conversation
            messages.append({
                "role": "assistant",
                "content": assistant_message.content,
                "tool_calls": assistant_message.tool_calls
            })
            
            for i, result in enumerate(tool_results):
                messages.append({
                    "role": "tool",
                    "tool_call_id": assistant_message.tool_calls[i].id,
                    "content": result
                })
            
            # Get a final response from the model
            final_response = self.client.chat.completions.create(
                model=model,
                messages=messages
            )
            
            return final_response.choices[0].message.content, tool_results
        
        return assistant_message.content, []
    
    def process_query_with_messages(self, messages, model="gpt-4o"):
        """Process a query using properly formatted messages for the OpenAI API
        
        Args:
            messages: List of message objects formatted for the OpenAI API
            model: The OpenAI model to use
            
        Returns:
            The assistant's response text
        """
        try:
            # Ensure we're using a model with vision capabilities
            vision_models = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4.5-preview", "o1"]
            if model not in vision_models:
                model = "gpt-4o"  # Default to gpt-4o if the specified model doesn't have vision capabilities
            
            # Create the initial response with tools
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                tools=knowledge_garden_tools,
                tool_choice="auto",
                max_tokens=4000  # Ensure we have enough tokens for a comprehensive response
            )
            
            assistant_message = response.choices[0].message
            
            # Check if the model wants to use tools
            if assistant_message.tool_calls:
                # Handle the tool calls
                tool_results = self.handle_tool_calls(assistant_message.tool_calls)
                
                # Add the assistant message to the conversation
                messages.append({
                    "role": "assistant",
                    "content": assistant_message.content,
                    "tool_calls": assistant_message.tool_calls
                })
                
                # Add the tool results to the conversation
                for i, result in enumerate(tool_results):
                    messages.append({
                        "role": "tool",
                        "tool_call_id": assistant_message.tool_calls[i].id,
                        "content": result
                    })
                
                # Get a final response from the model
                final_response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=4000  # Ensure we have enough tokens for a comprehensive response
                )
                
                return final_response.choices[0].message.content
            
            return assistant_message.content
        except Exception as e:
            print(f"Error in process_query_with_messages: {str(e)}")
            return f"I encountered an error while processing your query: {str(e)}"
    
    def autonomous_exploration(self, seed_topic, iterations=5, depth=2, exploration_type='breadth'):
        """
        Autonomously explore a topic and expand the knowledge garden
        
        Args:
            seed_topic: The initial topic to explore
            iterations: Number of exploration iterations
            depth: Depth of reasoning in each iteration
            exploration_type: Type of exploration strategy ('breadth', 'depth', 'hub', 'bridge')
        """
        print(f"Starting autonomous exploration on '{seed_topic}' with {iterations} iterations")
        print(f"Exploration type: {exploration_type}, Depth: {depth}")
        
        # Create an initial note for the seed topic if it doesn't exist
        if seed_topic not in self.garden.index.get("notes", {}):
            # Generate initial content for the seed topic
            prompt = f"""
            Create an initial knowledge note about the topic: {seed_topic}
            
            Include:
            1. A clear definition or explanation
            2. Key aspects or components
            3. Potential applications or implications
            4. Suggested tags for categorization
            
            Format your response as follows:
            
            CONTENT:
            [Your detailed explanation]
            
            TAGS: [tag1], [tag2], [tag3]
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a knowledge gardener. Create an initial note about a topic."},
                    {"role": "user", "content": prompt}
                ]
            )
            
            content = response.choices[0].message.content
            
            # Extract tags
            tags_match = re.search(r'TAGS: (.*?)$', content, re.MULTILINE | re.DOTALL)
            tags = []
            if tags_match:
                tags_text = tags_match.group(1).strip()
                tags = [tag.strip() for tag in tags_text.split(',')]
                # Remove the tags line from the content
                content = re.sub(r'TAGS: .*?$', '', content, flags=re.MULTILINE | re.DOTALL).strip()
            
            # Extract the content
            content_match = re.search(r'CONTENT:(.*?)(?=TAGS:|$)', content, re.MULTILINE | re.DOTALL)
            if content_match:
                content = content_match.group(1).strip()
            
            # Add the seed topic note
            self.garden.add_note(seed_topic, content, tags)
            print(f"Created initial note for '{seed_topic}'")
        
        # Perform exploration based on the specified type
        if exploration_type == 'breadth':
            # Breadth-first exploration - explore many related concepts
            self._breadth_first_exploration(seed_topic, iterations, depth)
        elif exploration_type == 'depth':
            # Depth-first exploration - explore fewer concepts in detail
            self._depth_first_exploration(seed_topic, iterations, depth)
        elif exploration_type == 'hub':
            # Hub-focused exploration - build around central concepts
            self._hub_focused_exploration(seed_topic, iterations, depth)
        elif exploration_type == 'bridge':
            # Bridge-focused exploration - connect disparate knowledge areas
            self._bridge_focused_exploration(seed_topic, iterations, depth)
        else:
            # Default to original exploration method
            self._original_exploration(seed_topic, iterations, depth)
            
    def _original_exploration(self, seed_topic, iterations, depth):
        """Original exploration method (for backward compatibility)"""
        # This is the original implementation
        for i in range(iterations):
            print(f"Iteration {i+1}/{iterations}")
            
            # Get all notes from the garden
            notes = self.garden.index.get("notes", {})
            
            # Choose a random note to expand on
            if notes:
                note_title = random.choice(list(notes.keys()))
                note_content = self.garden.get_note_content(note_title)
                
                # Generate a prompt for expansion
                prompt = f"""
                Based on the following note:
                
                Title: {note_title}
                Content: {note_content}
                
                Generate new insights or related concepts that would expand our knowledge garden.
                
                For each new concept:
                1. Provide a clear title
                2. Write a detailed explanation
                3. Explain how it relates to {note_title}
                4. Suggest relevant tags
                
                Format your response as follows for each concept:
                
                CONCEPT TITLE: [Title]
                
                CONTENT:
                [Detailed explanation]
                
                TAGS: [tag1], [tag2], [tag3]
                
                ---
                """
                
                response = self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "You are a knowledge gardener. Generate new concepts to expand a knowledge garden."},
                        {"role": "user", "content": prompt}
                    ]
                )
                
                concepts_text = response.choices[0].message.content
                
                # Parse the concepts
                concept_pattern = r"CONCEPT TITLE: (.*?)\s*\n+CONTENT:\s*(.*?)\s*\n+TAGS: (.*?)(?:\s*\n+---|$)"
                concepts = re.findall(concept_pattern, concepts_text, re.DOTALL)
                
                # Process each concept
                for title, content, tags_str in concepts:
                    # Clean up the extracted data
                    title = title.strip()
                    content = content.strip()
                    tags = [tag.strip() for tag in tags_str.split(",")]
                    
                    # Add the concept as a new note
                    self.garden.add_note(title, content, tags, related_notes=[note_title])
                    print(f"Added concept '{title}' related to '{note_title}'")
            else:
                # If no notes exist yet, create one for the seed topic
                self.garden.extract_insights(f"The topic of {seed_topic} is interesting and worth exploring.", parent_note=seed_topic)
                print(f"Created initial insights for '{seed_topic}'")
                
    def _breadth_first_exploration(self, seed_topic, iterations, depth):
        """Breadth-first exploration strategy - explore many related concepts"""
        # Implementation will be added in the next update
        print(f"Using breadth-first exploration for '{seed_topic}'")
        self._original_exploration(seed_topic, iterations, depth)
        
    def _depth_first_exploration(self, seed_topic, iterations, depth):
        """Depth-first exploration strategy - explore fewer concepts in detail"""
        # Implementation will be added in the next update
        print(f"Using depth-first exploration for '{seed_topic}'")
        self._original_exploration(seed_topic, iterations, depth)
        
    def _hub_focused_exploration(self, seed_topic, iterations, depth):
        """Hub-focused exploration strategy - build around central concepts"""
        # Implementation will be added in the next update
        print(f"Using hub-focused exploration for '{seed_topic}'")
        self._original_exploration(seed_topic, iterations, depth)
        
    def _bridge_focused_exploration(self, seed_topic, iterations, depth):
        """Bridge-focused exploration strategy - connect disparate knowledge areas"""
        # Implementation will be added in the next update
        print(f"Using bridge-focused exploration for '{seed_topic}'")
        self._original_exploration(seed_topic, iterations, depth)

def main():
    parser = argparse.ArgumentParser(description="Knowledge Garden Manager")
    parser.add_argument("--garden", default="knowledge_garden", help="Directory for the knowledge garden")
    parser.add_argument("--explore", type=str, help="Start autonomous exploration on a topic")
    parser.add_argument("--iterations", type=int, default=5, help="Number of iterations for autonomous exploration")
    parser.add_argument("--interactive", action="store_true", help="Start interactive mode")
    parser.add_argument("--api-key", type=str, help="OpenAI API key (alternatively, set OPENAI_API_KEY environment variable)")
    parser.add_argument("--visualize", action="store_true", help="Launch visualization after exploration")
    parser.add_argument("--view", action="store_true", help="Launch visualization of the existing knowledge garden")
    
    args = parser.parse_args()
    
    # Function to launch visualization
    def launch_visualization():
        try:
            import subprocess
            import sys
            
            print("\nLaunching knowledge garden visualization...")
            
            # Check if watchdog is installed
            try:
                import watchdog
            except ImportError:
                print("Installing required packages for visualization...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", "watchdog"])
            
            # Run the visualization server
            subprocess.Popen([sys.executable, "serve_visualization.py"])
            print("Visualization server started. You can view the knowledge garden in your browser.")
        except Exception as e:
            print(f"Error launching visualization: {e}")
            print("You can manually start the visualization with: python serve_visualization.py")
    
    # Just view the existing knowledge garden
    if args.view:
        launch_visualization()
        return
    
    # Initialize OpenAI client
    global client
    client = initialize_openai_client(args.api_key)
    
    garden = KnowledgeGarden(args.garden)
    agent = KnowledgeGardenAgent(garden)
    
    if args.explore:
        agent.autonomous_exploration(args.explore, args.iterations)
        
        # Launch visualization if requested
        if args.visualize:
            launch_visualization()
    elif args.interactive:
        print("Welcome to the Knowledge Garden!")
        print("Enter your queries or commands (type 'exit' to quit)")
        
        while True:
            query = input("\nYou: ")
            if query.lower() in ["exit", "quit", "q"]:
                break
            
            response, _ = agent.process_query(query)
            print(f"\nAssistant: {response}")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()