// Graph visualization variables
let svg, width, height, simulation, nodes = [], links = [];
let nodeElements, linkElements, textElements;
let zoom, showLabels = true;
let previousNodes = new Set(); // Track previous nodes for animation
let previousLinks = new Set(); // Track previous links for animation

// Initialize the visualization
function initGraph() {
    const graphContainer = document.querySelector('.graph-container');
    width = graphContainer.clientWidth;
    height = graphContainer.clientHeight;
    
    svg = d3.select('#graph')
        .attr('width', width)
        .attr('height', height);
        
    // Add zoom behavior
    zoom = d3.zoom()
        .scaleExtent([0.1, 4])
        .on('zoom', (event) => {
            svg.select('g').attr('transform', event.transform);
        });
        
    svg.call(zoom);
    
    // Create a group for all elements
    svg.append('g');
    
    // Initialize the force simulation
    simulation = d3.forceSimulation()
        .force('link', d3.forceLink().id(d => d.id).distance(100))
        .force('charge', d3.forceManyBody().strength(-300))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(50));
}

// Load data from the knowledge garden
function loadData() {
    document.getElementById('loading').style.display = 'block';
    
    // Store current nodes and links for comparison
    previousNodes = new Set(nodes.map(n => n.id));
    previousLinks = new Set(links.map(l => `${l.source.id || l.source}-${l.target.id || l.target}`));
    
    fetch('../index.json')
        .then(response => response.json())
        .then(data => {
            processData(data);
            document.getElementById('loading').style.display = 'none';
            updateStats(data);
            
            // Load graph analysis data if available
            loadGraphAnalysis();
        })
        .catch(error => {
            console.error('Error loading knowledge garden data:', error);
            document.getElementById('loading').textContent = 'Error loading data. Please check if the knowledge garden exists.';
        });
}

// Process the data and create graph elements
function processData(data) {
    nodes = [];
    links = [];
    
    // Process notes as nodes
    Object.entries(data.notes).forEach(([title, noteData]) => {
        nodes.push({
            id: title,
            type: 'note',
            title: title,
            path: noteData.path,
            tags: noteData.tags,
            created: noteData.created,
            related_notes: noteData.related_notes
        });
        
        // Process related notes as links
        noteData.related_notes.forEach(relatedNote => {
            links.push({
                source: title,
                target: relatedNote,
                type: 'related'
            });
        });
    });
    
    // Process tags as nodes and create links to notes
    Object.entries(data.tags).forEach(([tag, taggedNotes]) => {
        nodes.push({
            id: `tag:${tag}`,
            type: 'tag',
            title: tag
        });
        
        taggedNotes.forEach(note => {
            links.push({
                source: `tag:${tag}`,
                target: note,
                type: 'tagged'
            });
        });
    });
    
    // Process exploration paths if they exist
    if (data.paths) {
        Object.entries(data.paths).forEach(([topic, pathData]) => {
            nodes.push({
                id: `path:${topic}`,
                type: 'path',
                title: topic,
                subtopics: pathData.subtopics
            });
            
            // Try to find notes related to this path
            Object.entries(data.notes).forEach(([title, noteData]) => {
                if (noteData.tags.includes(topic.toLowerCase()) || 
                    title.toLowerCase().includes(topic.toLowerCase())) {
                    links.push({
                        source: `path:${topic}`,
                        target: title,
                        type: 'path'
                    });
                }
            });
        });
    }
    
    updateGraph();
}

// Update the graph visualization
function updateGraph() {
    // Clear previous elements
    svg.select('g').selectAll('*').remove();
    
    // Create links
    linkElements = svg.select('g')
        .selectAll('.link')
        .data(links)
        .enter()
        .append('line')
        .attr('class', d => {
            // Check if this is a new link
            const linkId = `${d.source}-${d.target}`;
            return previousLinks.has(linkId) ? 'link' : 'link edge-added';
        })
        .attr('stroke-width', d => d.type === 'related' ? 2 : 1)
        .attr('stroke-dasharray', d => d.type === 'tagged' ? '5,5' : null);
    
    // Create node groups
    const nodeGroups = svg.select('g')
        .selectAll('.node')
        .data(nodes)
        .enter()
        .append('g')
        .attr('class', 'node')
        .call(d3.drag()
            .on('start', dragStarted)
            .on('drag', dragged)
            .on('end', dragEnded))
        .on('click', showNoteDetails);
    
    // Add circles to nodes
    nodeElements = nodeGroups
        .append('circle')
        .attr('r', d => getNodeRadius(d))
        .attr('fill', d => getNodeColor(d))
        .attr('class', d => {
            // Check if this is a new node
            return previousNodes.has(d.id) ? '' : 'node-added';
        });
    
    // Add text labels to nodes
    textElements = nodeGroups
        .append('text')
        .text(d => d.title)
        .attr('dx', d => getNodeRadius(d) + 5)
        .attr('dy', 4)
        .attr('display', showLabels ? null : 'none');
    
    // Update the simulation
    simulation.nodes(nodes)
        .on('tick', ticked);
        
    simulation.force('link')
        .links(links);
        
    // Restart the simulation
    simulation.alpha(1).restart();
}

// Update node and link positions on each tick
function ticked() {
    linkElements
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);
        
    nodeElements
        .attr('cx', d => d.x)
        .attr('cy', d => d.y);
        
    textElements
        .attr('x', d => d.x)
        .attr('y', d => d.y);
}

// Get node radius based on type
function getNodeRadius(node) {
    switch(node.type) {
        case 'note': return 10;
        case 'tag': return 7;
        case 'path': return 15;
        default: return 8;
    }
}

// Get node color based on type
function getNodeColor(node) {
    switch(node.type) {
        case 'note': return '#3498db';
        case 'tag': return '#e74c3c';
        case 'path': return '#2ecc71';
        default: return '#95a5a6';
    }
}

// Handle drag events
function dragStarted(event, d) {
    if (!event.active) simulation.alphaTarget(0.3).restart();
    d.fx = d.x;
    d.fy = d.y;
}

function dragged(event, d) {
    d.fx = event.x;
    d.fy = event.y;
}

function dragEnded(event, d) {
    if (!event.active) simulation.alphaTarget(0);
    d.fx = null;
    d.fy = null;
}

// Show note details in the sidebar
function showNoteDetails(event, d) {
    const noteDetails = document.getElementById('note-details');
    const noteTitle = document.getElementById('note-title');
    const noteContent = document.getElementById('note-content');
    const noteTags = document.getElementById('note-tags');
    const noteCreated = document.getElementById('note-created');
    
    if (d.type === 'note') {
        // Fetch and display note content
        fetch(`../${d.path}`)
            .then(response => response.text())
            .then(content => {
                noteTitle.textContent = d.title;
                
                // Format the markdown content (simple version)
                const formattedContent = content
                    .replace(/^# .*$/m, '') // Remove the title
                    .replace(/^---.*$/ms, '') // Remove the metadata section
                    .trim();
                    
                noteContent.textContent = formattedContent;
                
                // Display tags
                noteTags.innerHTML = '';
                d.tags.forEach(tag => {
                    const tagElement = document.createElement('span');
                    tagElement.className = 'tag';
                    tagElement.textContent = tag;
                    noteTags.appendChild(tagElement);
                });
                
                // Format date
                const date = new Date(d.created);
                noteCreated.textContent = date.toLocaleString();
                
                noteDetails.style.display = 'block';
                
                // Switch to the Details tab
                switchTab('details-tab');
            })
            .catch(error => {
                console.error('Error loading note content:', error);
                noteContent.textContent = 'Error loading note content.';
            });
    } else if (d.type === 'tag') {
        noteTitle.textContent = `Tag: ${d.title}`;
        noteContent.textContent = `Notes tagged with "${d.title}"`;
        noteTags.innerHTML = '';
        noteCreated.textContent = '';
        noteDetails.style.display = 'block';
        
        // Switch to the Details tab
        switchTab('details-tab');
    } else if (d.type === 'path') {
        noteTitle.textContent = `Exploration Path: ${d.title}`;
        noteContent.textContent = `Subtopics: ${d.subtopics.join(', ')}`;
        noteTags.innerHTML = '';
        noteCreated.textContent = '';
        noteDetails.style.display = 'block';
        
        // Switch to the Details tab
        switchTab('details-tab');
    }
}

// Reset zoom to default view
function resetZoom() {
    svg.transition()
        .duration(750)
        .call(zoom.transform, d3.zoomIdentity);
}

// Toggle node labels
function toggleLabels() {
    showLabels = !showLabels;
    textElements.attr('display', showLabels ? null : 'none');
}

// Update statistics
function updateStats(data) {
    document.getElementById('notes-count').textContent = Object.keys(data.notes).length;
    document.getElementById('tags-count').textContent = Object.keys(data.tags).length;
    document.getElementById('connections-count').textContent = links.length;
    
    const date = new Date(data.last_updated);
    document.getElementById('last-updated').textContent = date.toLocaleString();
}

// Switch between tabs
function switchTab(tabId) {
    // Hide all tab contents
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    
    // Deactivate all tabs
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Activate the selected tab and content
    document.getElementById(tabId).classList.add('active');
    document.getElementById(tabId + '-content').classList.add('active');
}

// Initialize the visualization and load data
window.onload = function() {
    initGraph();
    loadData();
    
    // Set up tab switching
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            switchTab(tab.id);
        });
    });
    
    // Handle window resize
    window.addEventListener('resize', function() {
        width = document.querySelector('.graph-container').clientWidth;
        height = document.querySelector('.graph-container').clientHeight;
        
        svg.attr('width', width)
           .attr('height', height);
           
        simulation.force('center', d3.forceCenter(width / 2, height / 2));
        simulation.alpha(0.3).restart();
    });
};

// Add a new node to the graph (for real-time updates)
function addNodeToGraph(nodeData) {
    // Check if the node already exists
    if (nodes.some(n => n.id === nodeData.id)) {
        return;
    }
    
    // Add the node
    nodes.push(nodeData);
    
    // Update the graph
    updateGraph();
    
    // Highlight the new node
    highlightNewNode(nodeData.id);
}

// Add a new link to the graph (for real-time updates)
function addLinkToGraph(linkData) {
    // Check if the link already exists
    const linkId = `${linkData.source}-${linkData.target}`;
    if (links.some(l => `${l.source.id || l.source}-${l.target.id || l.target}` === linkId)) {
        return;
    }
    
    // Add the link
    links.push(linkData);
    
    // Update the graph
    updateGraph();
} 