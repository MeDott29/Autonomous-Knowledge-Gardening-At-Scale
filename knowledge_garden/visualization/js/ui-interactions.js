// UI Interactions for Knowledge Garden Visualization

document.addEventListener('DOMContentLoaded', function() {
    // Set up tab switching
    setupTabs();
    
    // Load initial data
    loadData();
    
    // Load analysis data
    loadGraphAnalysis();
});

/**
 * Sets up tab switching functionality
 */
function setupTabs() {
    const tabs = document.querySelectorAll('.tab');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Remove active class from all tabs and contents
            tabs.forEach(t => t.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));
            
            // Add active class to clicked tab
            tab.classList.add('active');
            
            // Get the corresponding content and activate it
            const contentId = tab.id + '-content';
            document.getElementById(contentId).classList.add('active');
            
            // If switching to analysis tab and data not loaded yet, load it
            if (tab.id === 'analysis-tab' && !analysisDataLoaded) {
                loadGraphAnalysis();
            }
            
            // If switching to communities tab and data not loaded yet, load it
            if (tab.id === 'communities-tab' && !communitiesDataLoaded) {
                loadCommunityData();
            }
            
            // If switching to centrality tab and data not loaded yet, load it
            if (tab.id === 'centrality-tab' && !centralityDataLoaded) {
                loadCentralityData();
            }
            
            // If switching to connections tab and data not loaded yet, load it
            if (tab.id === 'connections-tab' && !semanticConnectionsLoaded) {
                loadSemanticConnections();
            }
        });
    });
}

/**
 * Find paths between two nodes
 */
function findPaths() {
    const source = document.getElementById('path-source').value.trim();
    const target = document.getElementById('path-target').value.trim();
    
    if (!source || !target) {
        document.getElementById('paths-result').innerHTML = 
            '<div class="error">Please enter both source and target node titles.</div>';
        return;
    }
    
    document.getElementById('paths-result').innerHTML = 
        '<div class="loading">Finding paths...</div>';
    
    // Find source and target nodes in our data
    const sourceNode = nodes.find(n => n.title.toLowerCase() === source.toLowerCase());
    const targetNode = nodes.find(n => n.title.toLowerCase() === target.toLowerCase());
    
    if (!sourceNode) {
        document.getElementById('paths-result').innerHTML = 
            `<div class="error">Source node "${source}" not found.</div>`;
        return;
    }
    
    if (!targetNode) {
        document.getElementById('paths-result').innerHTML = 
            `<div class="error">Target node "${target}" not found.</div>`;
        return;
    }
    
    // Call the API to find paths
    fetch(`api/paths?source=${encodeURIComponent(sourceNode.id)}&target=${encodeURIComponent(targetNode.id)}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            if (data.paths.length === 0) {
                document.getElementById('paths-result').innerHTML = 
                    '<div class="info">No paths found between these nodes.</div>';
                return;
            }
            
            // Display the paths
            let html = `<div class="success">Found ${data.paths.length} path(s):</div>`;
            html += '<ul class="paths-list">';
            
            data.paths.forEach((path, index) => {
                html += `<li><strong>Path ${index + 1}</strong> (${path.length - 1} steps): `;
                html += path.map(nodeId => {
                    const node = nodes.find(n => n.id === nodeId);
                    return node ? node.title : nodeId;
                }).join(' → ');
                html += `<button onclick="highlightPath(${JSON.stringify(path)})">Highlight</button>`;
                html += '</li>';
            });
            
            html += '</ul>';
            document.getElementById('paths-result').innerHTML = html;
        })
        .catch(error => {
            console.error('Error finding paths:', error);
            document.getElementById('paths-result').innerHTML = 
                '<div class="error">Error finding paths. Please try again.</div>';
        });
}

/**
 * Highlight a path in the graph
 */
function highlightPath(pathNodeIds) {
    // Reset any previous highlighting
    resetHighlighting();
    
    // Highlight the nodes in the path
    d3.selectAll('.node')
        .classed('highlighted', d => pathNodeIds.includes(d.id))
        .classed('dimmed', d => !pathNodeIds.includes(d.id));
    
    // Highlight the links in the path
    d3.selectAll('.link')
        .classed('highlighted', d => {
            for (let i = 0; i < pathNodeIds.length - 1; i++) {
                if ((d.source.id === pathNodeIds[i] && d.target.id === pathNodeIds[i+1]) ||
                    (d.target.id === pathNodeIds[i] && d.source.id === pathNodeIds[i+1])) {
                    return true;
                }
            }
            return false;
        })
        .classed('dimmed', d => {
            for (let i = 0; i < pathNodeIds.length - 1; i++) {
                if ((d.source.id === pathNodeIds[i] && d.target.id === pathNodeIds[i+1]) ||
                    (d.target.id === pathNodeIds[i] && d.source.id === pathNodeIds[i+1])) {
                    return false;
                }
            }
            return true;
        });
}

/**
 * Extract a subgraph around a central node
 */
function extractSubgraph() {
    const centerNode = document.getElementById('subgraph-center').value.trim();
    const distance = document.getElementById('subgraph-distance').value;
    
    if (!centerNode) {
        document.getElementById('subgraph-result').innerHTML = 
            '<div class="error">Please enter a central node title.</div>';
        return;
    }
    
    document.getElementById('subgraph-result').innerHTML = 
        '<div class="loading">Extracting subgraph...</div>';
    
    // Find center node in our data
    const node = nodes.find(n => n.title.toLowerCase() === centerNode.toLowerCase());
    
    if (!node) {
        document.getElementById('subgraph-result').innerHTML = 
            `<div class="error">Node "${centerNode}" not found.</div>`;
        return;
    }
    
    // Call the API to extract subgraph
    fetch(`api/subgraph?node=${encodeURIComponent(node.id)}&distance=${distance}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            // Display the subgraph info
            let html = `<div class="success">Extracted subgraph with ${data.nodes.length} nodes and ${data.links.length} links.</div>`;
            
            // Highlight the subgraph
            highlightSubgraph(data.nodes);
            
            document.getElementById('subgraph-result').innerHTML = html;
        })
        .catch(error => {
            console.error('Error extracting subgraph:', error);
            document.getElementById('subgraph-result').innerHTML = 
                '<div class="error">Error extracting subgraph. Please try again.</div>';
        });
}

/**
 * Highlight a subgraph in the visualization
 */
function highlightSubgraph(subgraphNodeIds) {
    // Reset any previous highlighting
    resetHighlighting();
    
    // Highlight the nodes in the subgraph
    d3.selectAll('.node')
        .classed('highlighted', d => subgraphNodeIds.includes(d.id))
        .classed('dimmed', d => !subgraphNodeIds.includes(d.id));
    
    // Highlight the links in the subgraph
    d3.selectAll('.link')
        .classed('highlighted', d => 
            subgraphNodeIds.includes(d.source.id) && subgraphNodeIds.includes(d.target.id))
        .classed('dimmed', d => 
            !subgraphNodeIds.includes(d.source.id) || !subgraphNodeIds.includes(d.target.id));
}

/**
 * Reset any highlighting in the graph
 */
function resetHighlighting() {
    d3.selectAll('.node')
        .classed('highlighted', false)
        .classed('dimmed', false);
    
    d3.selectAll('.link')
        .classed('highlighted', false)
        .classed('dimmed', false);
} 