// Graph analysis variables
let graphAnalysisData = null;
let semanticConnections = [];
let communities = [];
let centralityMeasures = {};

// Load graph analysis data
function loadGraphAnalysis() {
    // Fetch graph analysis data from the API
    fetch('api/graph-analysis.json')
        .then(response => {
            if (!response.ok) {
                throw new Error('Graph analysis data not available');
            }
            return response.json();
        })
        .then(data => {
            graphAnalysisData = data;
            updateAnalysisView();
        })
        .catch(error => {
            console.warn('Could not load graph analysis:', error);
            document.getElementById('analysis-tab-content').innerHTML = `
                <div class="analysis-section">
                    <h3>Graph Analysis</h3>
                    <p>Graph analysis data is not available. Run the knowledge graph analyzer to generate analysis data.</p>
                    <p>You can run the analyzer with:</p>
                    <pre>python knowledge_graph_analysis.py --report --output knowledge_garden/visualization/api/graph-analysis.json</pre>
                </div>
            `;
        });
    
    // Fetch semantic connections
    fetch('api/semantic-connections.json')
        .then(response => {
            if (!response.ok) {
                throw new Error('Semantic connections data not available');
            }
            return response.json();
        })
        .then(data => {
            semanticConnections = data;
            updateSemanticConnections();
        })
        .catch(error => {
            console.warn('Could not load semantic connections:', error);
        });
    
    // Fetch community data
    fetch('api/communities.json')
        .then(response => {
            if (!response.ok) {
                throw new Error('Community data not available');
            }
            return response.json();
        })
        .then(data => {
            communities = data;
            updateCommunityView();
        })
        .catch(error => {
            console.warn('Could not load community data:', error);
        });
    
    // Fetch centrality measures
    fetch('api/centrality.json')
        .then(response => {
            if (!response.ok) {
                throw new Error('Centrality data not available');
            }
            return response.json();
        })
        .then(data => {
            centralityMeasures = data;
            updateCentralityView();
        })
        .catch(error => {
            console.warn('Could not load centrality data:', error);
        });
}

// Update the analysis view with graph analysis data
function updateAnalysisView() {
    if (!graphAnalysisData) return;
    
    const analysisContent = document.getElementById('analysis-tab-content');
    
    // Basic graph properties
    const properties = graphAnalysisData.graph_properties;
    let propertiesHtml = `
        <div class="analysis-section">
            <h3>Graph Properties</h3>
            <div class="metric">
                <span class="metric-name">Nodes:</span>
                <span class="metric-value">${properties.num_nodes}</span>
            </div>
            <div class="metric">
                <span class="metric-name">Edges:</span>
                <span class="metric-value">${properties.num_edges}</span>
            </div>
            <div class="metric">
                <span class="metric-name">Density:</span>
                <span class="metric-value">${properties.density.toFixed(4)}</span>
            </div>
            <div class="metric">
                <span class="metric-name">Connected:</span>
                <span class="metric-value">${properties.is_connected ? 'Yes' : 'No'}</span>
            </div>
            <div class="metric">
                <span class="metric-name">Connected Components:</span>
                <span class="metric-value">${properties.num_connected_components}</span>
            </div>
            <div class="metric">
                <span class="metric-name">Average Clustering:</span>
                <span class="metric-value">${properties.average_clustering.toFixed(4)}</span>
            </div>
    `;
    
    // Add path length metrics if available
    if (properties.is_connected) {
        propertiesHtml += `
            <div class="metric">
                <span class="metric-name">Average Path Length:</span>
                <span class="metric-value">${properties.average_shortest_path_length.toFixed(2)}</span>
            </div>
            <div class="metric">
                <span class="metric-name">Diameter:</span>
                <span class="metric-value">${properties.diameter}</span>
            </div>
        `;
    } else if (properties.largest_component_size) {
        propertiesHtml += `
            <div class="metric">
                <span class="metric-name">Largest Component Size:</span>
                <span class="metric-value">${properties.largest_component_size}</span>
            </div>
            <div class="metric">
                <span class="metric-name">Largest Component Avg Path Length:</span>
                <span class="metric-value">${properties.largest_component_avg_path_length.toFixed(2)}</span>
            </div>
            <div class="metric">
                <span class="metric-name">Largest Component Diameter:</span>
                <span class="metric-value">${properties.largest_component_diameter}</span>
            </div>
        `;
    }
    
    propertiesHtml += `</div>`;
    
    // Community structure
    const community = graphAnalysisData.community_structure;
    const communityHtml = `
        <div class="analysis-section">
            <h3>Community Structure</h3>
            <div class="metric">
                <span class="metric-name">Number of Communities:</span>
                <span class="metric-value">${community.num_communities}</span>
            </div>
            <div class="metric">
                <span class="metric-name">Modularity:</span>
                <span class="metric-value">${community.modularity.toFixed(4)}</span>
            </div>
            <div class="metric">
                <span class="metric-name">Largest Community Size:</span>
                <span class="metric-value">${community.largest_community_size}</span>
            </div>
        </div>
    `;
    
    // Hierarchical structure
    const hierarchy = graphAnalysisData.hierarchical_structure;
    let hierarchyHtml = `
        <div class="analysis-section">
            <h3>Hierarchical Structure</h3>
            <div class="metric">
                <span class="metric-name">Maximum Core Number:</span>
                <span class="metric-value">${hierarchy.max_core}</span>
            </div>
            <div class="metric">
                <span class="metric-name">Core Distribution:</span>
                <span class="metric-value"></span>
            </div>
    `;
    
    // Add core distribution
    hierarchyHtml += `<div style="margin-top: 10px;">`;
    Object.entries(hierarchy.core_distribution).forEach(([core, count]) => {
        hierarchyHtml += `
            <div class="metric" style="margin-left: 15px;">
                <span class="metric-name">Core ${core}:</span>
                <span class="metric-value">${count} nodes</span>
            </div>
        `;
    });
    hierarchyHtml += `</div></div>`;
    
    // Degree distribution
    const degree = graphAnalysisData.degree_distribution;
    let degreeHtml = `
        <div class="analysis-section">
            <h3>Degree Distribution</h3>
            <div class="metric">
                <span class="metric-name">Average Degree:</span>
                <span class="metric-value">${degree.avg_degree.toFixed(2)}</span>
            </div>
            <div class="metric">
                <span class="metric-name">Maximum Degree:</span>
                <span class="metric-value">${degree.max_degree}</span>
            </div>
            <div class="metric">
                <span class="metric-name">Power Law Distribution:</span>
                <span class="metric-value">${degree.is_power_law ? 'Yes' : 'No'}</span>
            </div>
    `;
    
    if (degree.is_power_law && degree.alpha) {
        degreeHtml += `
            <div class="metric">
                <span class="metric-name">Power Law Exponent (α):</span>
                <span class="metric-value">${degree.alpha.toFixed(4)}</span>
            </div>
        `;
    }
    
    degreeHtml += `</div>`;
    
    // Top central nodes
    let centralNodesHtml = `
        <div class="analysis-section">
            <h3>Top Central Nodes</h3>
            <div style="margin-top: 10px;">
    `;
    
    graphAnalysisData.top_central_nodes.forEach(([node, centrality], index) => {
        centralNodesHtml += `
            <div class="metric">
                <span class="metric-name">${index + 1}. ${node}</span>
                <span class="metric-value">${centrality.toFixed(4)}</span>
            </div>
        `;
    });
    
    centralNodesHtml += `</div></div>`;
    
    // Combine all sections
    analysisContent.innerHTML = propertiesHtml + communityHtml + hierarchyHtml + degreeHtml + centralNodesHtml;
}

// Update the view with semantic connections
function updateSemanticConnections() {
    if (!semanticConnections || semanticConnections.length === 0) return;
    
    const connectionsContent = document.getElementById('connections-tab-content');
    let html = `<div class="analysis-section">
        <h3>Semantic Connections</h3>
        <p>These connections were found based on semantic similarity between notes.</p>
    `;
    
    semanticConnections.forEach(connection => {
        html += `
            <div class="path">
                <div class="path-nodes">
                    <span class="path-node">${connection.source}</span>
                    <span class="path-arrow">→</span>
                    <span class="path-node">${connection.target}</span>
                </div>
                <div style="font-size: 12px; color: #7f8c8d; margin-top: 5px;">
                    Similarity: ${connection.similarity.toFixed(4)}
                </div>
            </div>
        `;
    });
    
    html += `</div>`;
    connectionsContent.innerHTML = html;
    
    // Add these connections to the graph
    semanticConnections.forEach(connection => {
        // Check if both nodes exist
        const sourceNode = nodes.find(n => n.id === connection.source);
        const targetNode = nodes.find(n => n.id === connection.target);
        
        if (sourceNode && targetNode) {
            // Check if this connection already exists
            const existingLink = links.find(l => 
                (l.source.id === connection.source && l.target.id === connection.target) ||
                (l.source.id === connection.target && l.target.id === connection.source)
            );
            
            if (!existingLink) {
                // Add a new semantic link
                links.push({
                    source: connection.source,
                    target: connection.target,
                    type: 'semantic',
                    similarity: connection.similarity
                });
            }
        }
    });
    
    // Update the graph with new connections
    updateGraph();
}

// Update the community view
function updateCommunityView() {
    if (!communities || !communities.communities) return;
    
    const communitiesContent = document.getElementById('communities-tab-content');
    let html = `<div class="analysis-section">
        <h3>Communities</h3>
        <p>The knowledge graph has been partitioned into ${communities.num_communities} communities using the Louvain algorithm.</p>
    `;
    
    // Sort communities by size (largest first)
    const sortedCommunities = Object.entries(communities.communities)
        .sort((a, b) => b[1].length - a[1].length);
    
    sortedCommunities.forEach(([communityId, nodes], index) => {
        html += `
            <div class="community">
                <div class="community-title">Community ${index + 1} (${nodes.length} nodes)</div>
                <div class="community-nodes">${nodes.join(', ')}</div>
            </div>
        `;
    });
    
    html += `</div>`;
    communitiesContent.innerHTML = html;
    
    // Color nodes by community
    if (communities.partition && nodeElements) {
        const communityColors = [
            '#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6',
            '#1abc9c', '#d35400', '#34495e', '#16a085', '#c0392b'
        ];
        
        nodeElements.attr('fill', d => {
            if (d.type !== 'note') return getNodeColor(d);
            
            const communityId = communities.partition[d.id];
            if (communityId !== undefined) {
                return communityColors[communityId % communityColors.length];
            }
            return getNodeColor(d);
        });
    }
}

// Update the centrality view
function updateCentralityView() {
    if (!centralityMeasures || !centralityMeasures.combined_centrality) return;
    
    const centralityContent = document.getElementById('centrality-tab-content');
    let html = `<div class="analysis-section">
        <h3>Node Centrality</h3>
        <p>Centrality measures identify the most important nodes in the knowledge graph.</p>
    `;
    
    // Get the combined centrality and sort by value (highest first)
    const sortedCentrality = Object.entries(centralityMeasures.combined_centrality)
        .sort((a, b) => b[1] - a[1]);
    
    // Find the maximum centrality value for normalization
    const maxCentrality = sortedCentrality[0][1];
    
    sortedCentrality.forEach(([node, centrality]) => {
        // Normalize the centrality value for the bar width
        const normalizedWidth = (centrality / maxCentrality) * 100;
        
        html += `
            <div>
                <div class="centrality-bar" style="width: ${normalizedWidth}%;"></div>
                <div class="centrality-label">
                    <span>${node}</span>
                    <span>${centrality.toFixed(4)}</span>
                </div>
            </div>
        `;
    });
    
    html += `</div>`;
    centralityContent.innerHTML = html;
    
    // Adjust node sizes based on centrality
    if (nodeElements) {
        nodeElements.attr('r', d => {
            if (d.type !== 'note') return getNodeRadius(d);
            
            const centrality = centralityMeasures.combined_centrality[d.id];
            if (centrality !== undefined) {
                // Scale the radius based on centrality (min 10, max 25)
                return 10 + (centrality / maxCentrality) * 15;
            }
            return getNodeRadius(d);
        });
    }
}

// Find paths between nodes
function findPaths() {
    const sourceNode = document.getElementById('path-source').value;
    const targetNode = document.getElementById('path-target').value;
    
    if (!sourceNode || !targetNode) {
        alert('Please select both source and target nodes');
        return;
    }
    
    fetch(`api/paths.json?source=${encodeURIComponent(sourceNode)}&target=${encodeURIComponent(targetNode)}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Could not find paths');
            }
            return response.json();
        })
        .then(paths => {
            displayPaths(paths, sourceNode, targetNode);
        })
        .catch(error => {
            console.error('Error finding paths:', error);
            alert('Error finding paths between the selected nodes');
        });
}

// Display paths between nodes
function displayPaths(paths, sourceNode, targetNode) {
    const pathsContent = document.getElementById('paths-result');
    
    if (!paths || paths.length === 0) {
        pathsContent.innerHTML = `<p>No paths found between "${sourceNode}" and "${targetNode}".</p>`;
        return;
    }
    
    let html = `<h3>Paths from "${sourceNode}" to "${targetNode}"</h3>`;
    
    paths.forEach((path, index) => {
        html += `
            <div class="path">
                <div class="path-title">Path ${index + 1} (${path.length} nodes)</div>
                <div class="path-nodes">
        `;
        
        path.forEach((node, i) => {
            html += `<span class="path-node">${node}</span>`;
            if (i < path.length - 1) {
                html += `<span class="path-arrow">→</span>`;
            }
        });
        
        html += `</div></div>`;
    });
    
    pathsContent.innerHTML = html;
    
    // Highlight the paths in the graph
    highlightPaths(paths);
}

// Highlight paths in the graph
function highlightPaths(paths) {
    // Reset all links and nodes
    linkElements.attr('stroke', d => {
        switch(d.type) {
            case 'related': return '#999';
            case 'tagged': return '#999';
            case 'path': return '#999';
            case 'semantic': return '#9b59b6';
            default: return '#999';
        }
    }).attr('stroke-opacity', 0.6).attr('stroke-width', d => d.type === 'related' ? 2 : 1);
    
    nodeElements.attr('stroke', '#fff').attr('stroke-width', 2);
    
    // Highlight the paths
    const pathColors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6'];
    
    paths.forEach((path, pathIndex) => {
        const color = pathColors[pathIndex % pathColors.length];
        
        // Highlight nodes in the path
        nodeElements.filter(d => path.includes(d.id))
            .attr('stroke', color)
            .attr('stroke-width', 3);
        
        // Highlight links in the path
        for (let i = 0; i < path.length - 1; i++) {
            const source = path[i];
            const target = path[i + 1];
            
            linkElements.filter(d => 
                (d.source.id === source && d.target.id === target) || 
                (d.source.id === target && d.target.id === source)
            )
            .attr('stroke', color)
            .attr('stroke-opacity', 1)
            .attr('stroke-width', 3);
        }
    });
}

// Extract a subgraph around a central node
function extractSubgraph() {
    const centralNode = document.getElementById('subgraph-center').value;
    const distance = parseInt(document.getElementById('subgraph-distance').value);
    
    if (!centralNode) {
        alert('Please select a central node');
        return;
    }
    
    fetch(`api/subgraph.json?node=${encodeURIComponent(centralNode)}&distance=${distance}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Could not extract subgraph');
            }
            return response.json();
        })
        .then(subgraph => {
            displaySubgraph(subgraph, centralNode, distance);
        })
        .catch(error => {
            console.error('Error extracting subgraph:', error);
            alert('Error extracting subgraph around the selected node');
        });
}

// Display a subgraph
function displaySubgraph(subgraph, centralNode, distance) {
    const subgraphContent = document.getElementById('subgraph-result');
    
    if (!subgraph || !subgraph.nodes || subgraph.nodes.length === 0) {
        subgraphContent.innerHTML = `<p>No subgraph found around "${centralNode}" with distance ${distance}.</p>`;
        return;
    }
    
    let html = `<h3>Subgraph around "${centralNode}" (distance ${distance})</h3>`;
    
    html += `
        <div class="analysis-section">
            <div class="metric">
                <span class="metric-name">Nodes:</span>
                <span class="metric-value">${subgraph.nodes.length}</span>
            </div>
            <div class="metric">
                <span class="metric-name">Edges:</span>
                <span class="metric-value">${subgraph.edges.length}</span>
            </div>
        </div>
        
        <div class="community">
            <div class="community-title">Nodes in subgraph</div>
            <div class="community-nodes">${subgraph.nodes.join(', ')}</div>
        </div>
    `;
    
    subgraphContent.innerHTML = html;
    
    // Highlight the subgraph in the main graph
    highlightSubgraph(subgraph.nodes);
}

// Highlight a subgraph in the main graph
function highlightSubgraph(subgraphNodes) {
    // Dim all nodes and links
    nodeElements.attr('opacity', 0.2);
    linkElements.attr('opacity', 0.1);
    textElements.attr('opacity', 0.2);
    
    // Highlight nodes in the subgraph
    nodeElements.filter(d => subgraphNodes.includes(d.id))
        .attr('opacity', 1);
    
    // Highlight links in the subgraph
    linkElements.filter(d => 
        subgraphNodes.includes(d.source.id) && subgraphNodes.includes(d.target.id)
    ).attr('opacity', 1);
    
    // Highlight text labels in the subgraph
    textElements.filter(d => subgraphNodes.includes(d.id))
        .attr('opacity', 1);
}

// Reset graph highlighting
function resetHighlighting() {
    nodeElements.attr('opacity', 1).attr('stroke', '#fff').attr('stroke-width', 2);
    linkElements.attr('opacity', 1).attr('stroke-width', d => d.type === 'related' ? 2 : 1)
        .attr('stroke-opacity', 0.6)
        .attr('stroke', d => {
            switch(d.type) {
                case 'related': return '#999';
                case 'tagged': return '#999';
                case 'path': return '#999';
                case 'semantic': return '#9b59b6';
                default: return '#999';
            }
        });
    textElements.attr('opacity', 1);
} 