const BACKEND_URL = 'http://127.0.0.1:5000'; // Change to Render URL in production

/**
 * Sends a background track request to the Flask API so the traffic
 * can be monitored by the anomaly detection engine.
 * Returns the fetch Promise so callers can await response if desired.
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
    
    return fetch(url, options).catch(err => {
        console.error("Tracking error:", err);
        throw err;
    });
}

/**
 * Auth state management helpers
 */
function getCurrentUser() {
    try {
        const userJson = localStorage.getItem('currentUser');
        return userJson ? JSON.parse(userJson) : null;
    } catch (e) {
        return null;
    }
}

function setCurrentUser(user) {
    if (user) {
        localStorage.setItem('currentUser', JSON.stringify(user));
    } else {
        localStorage.removeItem('currentUser');
    }
    updateNavbarAuth();
}

function logout() {
    localStorage.removeItem('currentUser');
    window.location.href = 'login.html';
}

function updateNavbarAuth() {
    const navAuth = document.querySelector('.navbar .collapse .navbar-nav:last-child');
    if (!navAuth) return;

    const user = getCurrentUser();
    if (user && user.username) {
        if (user.role === 'admin') {
            navAuth.innerHTML = `
                <li class="nav-item dropdown">
                    <a class="nav-link dropdown-toggle text-warning fw-bold" href="#" id="authDropdown" role="button" data-bs-toggle="dropdown" aria-expanded="false">
                        🛡️ Admin
                    </a>
                    <ul class="dropdown-menu dropdown-menu-end" aria-labelledby="authDropdown">
                        <li><span class="dropdown-item-text text-muted small">${user.username}</span></li>
                        <li><hr class="dropdown-divider"></li>
                        <li><a class="dropdown-item" href="admin.html">SecOps Dashboard</a></li>
                        <li><hr class="dropdown-divider"></li>
                        <li><a class="dropdown-item text-danger" href="javascript:void(0)" onclick="logout()">Logout</a></li>
                    </ul>
                </li>
            `;
        } else {
            navAuth.innerHTML = `
                <li class="nav-item dropdown">
                    <a class="nav-link dropdown-toggle text-info" href="#" id="authDropdown" role="button" data-bs-toggle="dropdown" aria-expanded="false">
                        👤 ${user.username}
                    </a>
                    <ul class="dropdown-menu dropdown-menu-end" aria-labelledby="authDropdown">
                        <li><span class="dropdown-item-text text-muted small">Standard User</span></li>
                        <li><hr class="dropdown-divider"></li>
                        <li><a class="dropdown-item text-danger" href="javascript:void(0)" onclick="logout()">Logout</a></li>
                    </ul>
                </li>
            `;
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    updateNavbarAuth();
});

// Automatically track basic page views (if not overridden by specific logic)
if (window.location.pathname.endsWith('index.html') || window.location.pathname === '/' || window.location.pathname.endsWith('/')) {
    trackRequest('/api/home');
}
