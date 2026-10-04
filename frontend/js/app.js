const BACKEND_URL = 'http://127.0.0.1:5000'; // Change to Render URL in production

/**
 * Sends a background track request to the Flask API so the traffic
 * can be monitored by the anomaly detection engine.
 */
function trackRequest(path, method = 'GET', data = null) {
    const url = BACKEND_URL + path;
    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json'
        }
    };
    
    if (data && method !== 'GET') {
        options.body = JSON.stringify(data);
    }
    
    // We don't care about the response, just firing it for the backend to log
    fetch(url, options).catch(err => console.error("Tracking error:", err));
}

// Automatically track basic page views (if not overridden by specific logic)
if (window.location.pathname.endsWith('index.html') || window.location.pathname === '/') {
    trackRequest('/api/home');
}
