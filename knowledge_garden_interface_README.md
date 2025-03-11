# Knowledge Garden Interface

A web-based interface for the Knowledge Garden that makes it easy to add images and large text files to your knowledge garden. This interface allows you and your team to collaboratively grow information about your projects.

## Features

- **Upload Files**: Add text files, markdown documents, and images to your knowledge garden
- **Extract Insights**: Automatically extract insights from uploaded documents
- **Team Collaboration**: Web interface makes it easy for your entire team to use
- **Query the Garden**: Ask questions about the content in your knowledge garden
- **Image Analysis**: Attach images to your queries to get insights from GPT-4o
- **Explore Topics**: Start autonomous exploration on topics of interest
- **Browse Content**: View all notes and tags in your knowledge garden

## Requirements

- Python 3.7+
- Flask
- OpenAI API key (GPT-4o recommended for image analysis)
- Pillow (for image processing)
- The existing `knowledge_garden.py` script

## Installation

1. Make sure you have the required packages installed:

```bash
pip install -r requirements.txt
```

2. Place the `knowledge_garden_interface.py` file in the same directory as your existing `knowledge_garden.py` file.

## Usage

1. Run the interface:

```bash
python knowledge_garden_interface.py --api-key YOUR_OPENAI_API_KEY
```

Or set your API key as an environment variable:

```bash
export OPENAI_API_KEY=your_api_key
python knowledge_garden_interface.py
```

2. Open your browser and navigate to `http://localhost:5000` (or the appropriate host/port if you changed the defaults).

3. Use the web interface to:
   - Upload files (text, markdown, images)
   - Ask questions to the knowledge garden
   - Attach images to your queries
   - Explore topics
   - Browse existing notes and tags

## Working with Images

The interface now has enhanced support for images:

1. **Uploading Images**: You can upload images directly through the upload form. The system will create a note with the embedded image.

2. **Attaching Images to Queries**: When asking a question, you can attach an image to your query. This is especially useful with GPT-4o, which can analyze the image and provide insights.

3. **Viewing Images**: Images have a dedicated view that makes them accessible to both humans and AI models like GPT-4o.

4. **Base64 Encoding**: Images are automatically encoded in base64 format in the notes, making them visible to GPT-4o when you ask questions about them.

## Command Line Options

- `--garden`: Directory for the knowledge garden (default: "knowledge_garden")
- `--port`: Port to run the web server on (default: 5000)
- `--host`: Host to run the web server on (default: "0.0.0.0")
- `--api-key`: OpenAI API key (alternatively, set the OPENAI_API_KEY environment variable)

## Team Usage

For team usage, you can run the interface on a shared server that everyone can access. Make sure to:

1. Run the interface on a machine that's accessible to all team members
2. Use a shared directory for the knowledge garden that everyone has access to
3. Consider setting up authentication if needed for security

## File Types Supported

- Text files (.txt)
- Markdown files (.md)
- PDF documents (.pdf)
- Word documents (.docx)
- Images (.png, .jpg, .jpeg, .gif)

## Example Workflow

1. Upload your project documentation (like Autonomous-Knowledge-Gardening-at-Scale.md)
2. The system will automatically extract insights and add them to your knowledge garden
3. Upload related images or diagrams of your project
4. Ask questions about your project, attaching relevant images when needed
5. Explore related topics to expand your knowledge garden
6. Share the URL with your team so they can contribute and access the knowledge

## Troubleshooting

- If you encounter issues with image uploads, check that the file size is under 50MB
- For large text files, the processing might take some time due to API calls
- If images aren't displaying correctly, check that the uploads directory is accessible to the web server
- If GPT-4o isn't seeing your images, make sure you're using the latest version of the interface with base64 encoding 