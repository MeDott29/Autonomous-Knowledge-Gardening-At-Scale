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
    def __init__(self, garden_dir="knowledge_garden"):
        """Initialize the knowledge garden"""
        self.garden_dir = Path(garden_dir)
        self.notes_dir = self.garden_dir / "notes"
        self.index_path = self.garden_dir / "index.json"
        self.paths_dir = self.garden_dir / "paths"
        self.setup_garden()
        self.load_index()
        
    def setup_garden(self):
        """Set up the knowledge garden directory structure"""
        self.garden_dir.mkdir(exist_ok=True)
        self.notes_dir.mkdir(exist_ok=True)
        self.paths_dir.mkdir(exist_ok=True)
        
        if not self.index_path.exists():
            # Initialize empty index
            with open(self.index_path, "w") as f:
                json.dump({
                    "notes": {},
                    "tags": {},
                    "paths": {},
                    "last_updated": datetime.datetime.now().isoformat()
                }, f, indent=2)
    
    def load_index(self):
        """Load the knowledge garden index"""
        with open(self.index_path, "r") as f:
            self.index = json.load(f)
            # Ensure paths key exists
            if "paths" not in self.index:
                self.index["paths"] = {}
    
    def save_index(self):
        """Save the knowledge garden index"""
        self.index["last_updated"] = datetime.datetime.now().isoformat()
        with open(self.index_path, "w") as f:
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
        response = client.chat.completions.create(
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
        
        response = client.chat.completions.create(
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
    
    def process_query(self, query, model="gpt-4o"):
        """Process a user query with the AI assistant"""
        messages = [
            {"role": "system", "content": "You are a knowledge gardener. Your goal is to build a rich, interconnected knowledge garden by creating notes, extracting insights, and establishing connections between concepts."},
            {"role": "user", "content": query}
        ]
        
        response = client.chat.completions.create(
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
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    } for tc in assistant_message.tool_calls
                ]
            })
            
            for idx, tc in enumerate(assistant_message.tool_calls):
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_results[idx]
                })
            
            # Get a final response from the model
            final_response = client.chat.completions.create(
                model=model,
                messages=messages
            )
            
            assistant_message = final_response.choices[0].message
        
        return assistant_message.content, assistant_message.tool_calls
    
    def autonomous_exploration(self, seed_topic, iterations=5, depth=2):
        """Autonomously explore and expand a topic"""
        print(f"Starting autonomous exploration on topic: {seed_topic}")
        
        # Create an exploration path for this topic
        subtopics_prompt = f"""
        Generate 5-7 key subtopics for exploring '{seed_topic}'. 
        These subtopics should cover different aspects or dimensions of the main topic.
        Format your response as a simple comma-separated list of subtopics.
        """
        
        subtopics_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a knowledge organization expert."},
                {"role": "user", "content": subtopics_prompt}
            ]
        )
        
        subtopics_text = subtopics_response.choices[0].message.content
        subtopics = [s.strip() for s in subtopics_text.split(",")]
        
        # Create the exploration path
        self.garden.create_exploration_path(
            topic=seed_topic,
            subtopics=subtopics,
            description=f"Autonomous exploration of {seed_topic}"
        )
        
        # Initial seed
        prompt = f"""
        I'd like you to start a knowledge garden on the topic: '{seed_topic}'.
        
        First, create an initial note that introduces this topic comprehensively.
        Then, extract 3-5 key insights from your introduction as separate notes.
        
        Make sure to:
        1. Use appropriate tags for each note
        2. Establish relationships between notes
        3. Organize the knowledge in a structured way
        """
        
        for i in range(iterations):
            print(f"\nIteration {i+1}/{iterations}:")
            
            # Process the current prompt
            response_text, tool_calls = self.process_query(prompt)
            
            # Store the exploration history
            self.exploration_history.append({
                "iteration": i+1,
                "prompt": prompt,
                "response": response_text,
                "tool_calls": [
                    {
                        "name": tc.function.name,
                        "args": json.loads(tc.function.arguments)
                    } for tc in (tool_calls or [])
                ]
            })
            
            print(f"Agent response: {response_text}\n{'-'*40}")
            
            # If this isn't the last iteration, generate a new direction for exploration
            if i < iterations - 1:
                # Choose the next subtopic to explore
                current_subtopic = subtopics[min(i, len(subtopics)-1)]
                
                exploration_prompt = f"""
                Let's explore the subtopic '{current_subtopic}' related to our main topic '{seed_topic}'.
                
                1. First, search for any existing notes that might be relevant to this subtopic.
                2. Then, either:
                   a) Create a new comprehensive note about this subtopic, or
                   b) Expand on an existing note if it's closely related.
                3. Extract key insights from your new content.
                4. Establish connections with other notes in our garden.
                
                Focus on depth rather than breadth - it's better to explore one aspect thoroughly
                than to cover many aspects superficially.
                """
                
                # Generate the next prompt
                prompt = exploration_prompt
            
            # Add a small delay to avoid API rate limits
            time.sleep(1)
        
        # Save the exploration history
        history_path = self.garden.paths_dir / f"{seed_topic.lower().replace(' ', '_')}_history.json"
        with open(history_path, "w") as f:
            json.dump(self.exploration_history, f, indent=2)
        
        # Generate a summary of the exploration
        summary_prompt = f"""
        Create a summary of our exploration on '{seed_topic}'. 
        Review the notes we've created and synthesize the key findings and insights.
        """
        
        summary_response, _ = self.process_query(summary_prompt)
        
        # Add the summary as a note
        self.garden.add_note(
            title=f"{seed_topic} - Exploration Summary",
            content=summary_response,
            tags=["summary", "exploration"] + [seed_topic.lower()],
            related_notes=[]  # Will be filled by the extract_insights function
        )
        
        # Extract insights from the summary
        self.garden.extract_insights(
            text=summary_response,
            parent_note=f"{seed_topic} - Exploration Summary",
            tags=["summary", "key insight", seed_topic.lower()]
        )
        
        print("\nAutonomous exploration complete!")
        print(f"Knowledge garden has been populated with insights on '{seed_topic}'")
        print(f"A summary note and key insights have been added to synthesize the exploration.")

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