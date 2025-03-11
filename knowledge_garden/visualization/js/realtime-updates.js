/**
 * Real-time updates for the Knowledge Garden visualization
 * Handles WebSocket connections and updates the graph in real-time
 */

// WebSocket connection
let wsReconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_DELAY = 3000; // 3 seconds

// Initialize WebSocket connection
function initWebSocket() {
    // Get the current hostname and use the WebSocket port
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = window.location.hostname || 'localhost';
    const wsPort = 8001; // This should match the WS_PORT in serve_visualization.py
    
    const wsUrl = `${wsProtocol}//${wsHost}:${wsPort}`;
    
    try {
        websocket = new WebSocket(wsUrl);
        
        websocket.onopen = function(event) {
            console.log('WebSocket connection established');
            updateConnectionStatus(true);
            wsReconnectAttempts = 0;
            
            // Send a ping to keep the connection alive
            setInterval(function() {
                if (websocket.readyState === WebSocket.OPEN) {
                    websocket.send(JSON.stringify({ type: 'ping' }));
                }
            }, 30000); // Every 30 seconds
        };
        
        websocket.onmessage = function(event) {
            handleWebSocketMessage(event.data);
        };
        
        websocket.onerror = function(error) {
            console.error('WebSocket error:', error);
            updateConnectionStatus(false);
        };
        
        websocket.onclose = function(event) {
            console.log('WebSocket connection closed');
            updateConnectionStatus(false);
            
            // Try to reconnect if not closed cleanly
            if (wsReconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                wsReconnectAttempts++;
                setTimeout(initWebSocket, RECONNECT_DELAY);
                addActivityMessage(`Connection lost. Reconnecting (attempt ${wsReconnectAttempts})...`);
            } else {
                addActivityMessage('Connection lost. Please refresh the page to reconnect.');
            }
        };
    } catch (error) {
        console.error('Error initializing WebSocket:', error);
        updateConnectionStatus(false);
    }
}

// Update the connection status indicator
function updateConnectionStatus(isConnected) {
    const statusElement = document.getElementById('connection-status');
    
    if (isConnected) {
        statusElement.textContent = 'Online';
        statusElement.classList.remove('offline');
        statusElement.classList.add('online');
    } else {
        statusElement.textContent = 'Offline';
        statusElement.classList.remove('online');
        statusElement.classList.add('offline');
    }
}

// Handle incoming WebSocket messages
function handleWebSocketMessage(data) {
    try {
        const message = JSON.parse(data);
        
        switch (message.type) {
            case 'garden_update':
                handleGardenUpdate(message);
                break;
            case 'tool_usage':
                handleToolUsage(message.data);
                break;
            case 'tool_history':
                handleToolHistory(message.data);
                break;
            case 'pong':
                // Ping response, do nothing
                break;
            default:
                console.log('Unknown message type:', message.type);
        }
    } catch (error) {
        console.error('Error handling WebSocket message:', error);
    }
}

// Handle garden update notifications
function handleGardenUpdate(message) {
    if (!realtimeUpdatesEnabled) {
        showNotification(`Garden updated (${message.file}). Updates paused.`);
        return;
    }
    
    // Reload the data
    loadData();
    
    // Show notification
    showNotification(`Garden updated: ${message.file}`);
    
    // Add to activity log
    addActivityMessage(`Garden updated: ${message.file}`);
}

// Handle tool usage notifications
function handleToolUsage(data) {
    // Add to activity log
    const toolName = data.tool;
    const args = data.args;
    
    let message = `Tool used: ${formatToolName(toolName)}`;
    
    // Add specific details based on the tool
    switch (toolName) {
        case 'add_note':
            message += ` - Added note "${args.title}"`;
            // Highlight the new node in the graph
            highlightNewNode(args.title);
            break;
        case 'search_notes':
            message += ` - Searched for "${args.query}"`;
            break;
        case 'expand_knowledge':
            message += ` - Expanded "${args.note_title}" (${args.expansion_type})`;
            break;
        case 'extract_insights':
            message += ` - Extracted insights`;
            if (args.parent_note) {
                message += ` from "${args.parent_note}"`;
            }
            break;
        case 'create_exploration_path':
            message += ` - Created path for "${args.topic}"`;
            break;
        case 'exploration_start':
            message += ` - Started exploration on "${args.seed_topic}"`;
            break;
        case 'create_seed_note':
            message += ` - Created seed note "${args.title}"`;
            // Highlight the new node in the graph
            highlightNewNode(args.title);
            break;
    }
    
    addActivityMessage(message);
}

// Handle tool history (initial load)
function handleToolHistory(history) {
    // Clear existing messages
    const activityLog = document.getElementById('activity-log');
    activityLog.innerHTML = '';
    
    // Add each history item
    history.forEach(item => {
        handleToolUsage(item);
    });
    
    // Add a message if no history
    if (history.length === 0) {
        addActivityMessage('No recent activity.');
    }
}

// Format tool name for display
function formatToolName(toolName) {
    switch (toolName) {
        case 'add_note':
            return '<span class="tool-icon add-note">AN</span>Add Note';
        case 'search_notes':
            return '<span class="tool-icon search-notes">SN</span>Search Notes';
        case 'expand_knowledge':
            return '<span class="tool-icon expand-knowledge">EK</span>Expand Knowledge';
        case 'extract_insights':
            return '<span class="tool-icon extract-insights">EI</span>Extract Insights';
        case 'create_exploration_path':
            return '<span class="tool-icon create-path">CP</span>Create Path';
        case 'exploration_start':
            return '<span class="tool-icon expand-knowledge">EK</span>Start Exploration';
        case 'create_seed_note':
            return '<span class="tool-icon add-note">AN</span>Create Seed Note';
        default:
            return toolName;
    }
}

// Add a message to the activity log
function addActivityMessage(message) {
    const activityLog = document.getElementById('activity-log');
    const messageElement = document.createElement('div');
    messageElement.className = 'activity-message';
    
    // Add timestamp
    const timestamp = new Date().toLocaleTimeString();
    const timestampElement = document.createElement('span');
    timestampElement.className = 'activity-timestamp';
    timestampElement.textContent = timestamp;
    
    messageElement.appendChild(timestampElement);
    
    // Add message content
    const contentElement = document.createElement('span');
    contentElement.innerHTML = message;
    messageElement.appendChild(contentElement);
    
    // Add to log
    activityLog.appendChild(messageElement);
    
    // Scroll to bottom
    activityLog.scrollTop = activityLog.scrollHeight;
}

// Clear the activity log
function clearActivityLog() {
    const activityLog = document.getElementById('activity-log');
    activityLog.innerHTML = '';
    addActivityMessage('Activity log cleared.');
}

// Show a notification
function showNotification(message) {
    const notification = document.getElementById('realtime-notification');
    const notificationText = document.getElementById('notification-text');
    
    notificationText.textContent = message;
    notification.style.display = 'block';
    
    // Hide after 5 seconds
    setTimeout(dismissNotification, 5000);
}

// Dismiss the notification
function dismissNotification() {
    const notification = document.getElementById('realtime-notification');
    notification.style.display = 'none';
}

// Toggle real-time updates
function toggleRealTimeUpdates() {
    realtimeUpdatesEnabled = !realtimeUpdatesEnabled;
    
    const toggleButton = document.getElementById('realtime-toggle');
    
    if (realtimeUpdatesEnabled) {
        toggleButton.textContent = 'Pause Updates';
        addActivityMessage('Real-time updates enabled.');
    } else {
        toggleButton.textContent = 'Resume Updates';
        addActivityMessage('Real-time updates paused.');
    }
}

// Highlight a new node in the graph
function highlightNewNode(nodeId) {
    if (!nodes || !nodeElements) return;
    
    // Find the node
    const node = nodes.find(n => n.id === nodeId);
    if (!node) return;
    
    // Find the node element
    const nodeElement = nodeElements.filter(d => d.id === nodeId).node();
    if (!nodeElement) return;
    
    // Add the animation class
    d3.select(nodeElement).classed('node-added', true);
    
    // Remove the class after animation completes
    setTimeout(() => {
        d3.select(nodeElement).classed('node-added', false);
    }, 1000);
}

// Initialize when the page loads
document.addEventListener('DOMContentLoaded', function() {
    // Initialize WebSocket connection
    initWebSocket();
    
    // Set up tab switching for the activity tab
    document.getElementById('activity-tab').addEventListener('click', function() {
        // Switch to the activity tab
        document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
        
        document.getElementById('activity-tab').classList.add('active');
        document.getElementById('activity-tab-content').classList.add('active');
    });
}); 