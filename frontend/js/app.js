// Smart Backend URL configuration:
// Automatically connects to local/LAN Flask backend when testing locally or from other devices on the same Wi-Fi,
// and seamlessly falls back to Render cloud backend in production or when the local server is unreachable.
const CLOUD_BACKEND_URL = "https://web-traffic-anomaly-detector.onrender.com";

function getLocalBackendUrl() {
    if (window.location.protocol === 'file:') {
        return "http://127.0.0.1:5000";
    }
    const host = window.location.hostname;
    const protocol = window.location.protocol === 'https:' ? 'https:' : 'http:';
    // Use the same host/IP that served the frontend page, but on port 5000
    return `${protocol}//${host || '127.0.0.1'}:5000`;
}

function isLocalOrLanNetwork() {
    if (window.location.protocol === 'file:') return true;
    const host = window.location.hostname;
    return (
        host === 'localhost' ||
        host === '127.0.0.1' ||
        host.startsWith('192.168.') ||
        host.startsWith('10.') ||
        /^172\.(1[6-9]|2[0-9]|3[0-1])\./.test(host)
    );
}

const isLocalOrLan = isLocalOrLanNetwork();
const LOCAL_BACKEND_URL = getLocalBackendUrl();

let BACKEND_URL = isLocalOrLan ? LOCAL_BACKEND_URL : CLOUD_BACKEND_URL;
let FALLBACK_BACKEND_URL = isLocalOrLan ? CLOUD_BACKEND_URL : LOCAL_BACKEND_URL;

function getCurrentPageName() {
    const path = window.location.pathname.split('/').pop();
    return path || 'index.html';
}

function isLoginPage() {
    return getCurrentPageName() === 'login.html';
}

function isProtectedPage() {
    const page = getCurrentPageName();
    return ['index.html', 'products.html', 'search.html', 'contact.html', 'admin.html'].includes(page);
}

function enforceLoginFlow() {
    const currentUser = getCurrentUser();
    const page = getCurrentPageName();

    if (!currentUser && isProtectedPage() && !isLoginPage()) {
        window.location.replace('login.html');
        return true;
    }

    if (currentUser && isLoginPage()) {
        const target = currentUser.role === 'admin' ? 'admin.html' : 'products.html';
        window.location.replace(target);
        return true;
    }

    if (currentUser && currentUser.role === 'user' && page === 'admin.html') {
        window.location.replace('products.html');
        return true;
    }

    return false;
}

/**
 * Sends a background track request to the Flask API so the traffic
 * can be monitored by the anomaly detection engine.
 * Returns the fetch Promise so callers can await response if desired.
 */
async function trackRequest(path, method = 'GET', data = null) {
    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json'
        }
    };

    if (data && method !== 'GET') {
        options.body = JSON.stringify(data);
    }

    try {
        return await fetch(BACKEND_URL + path, options);
    } catch (err) {
        // Fallback to secondary backend URL if primary fails (e.g. local backend not running)
        if (FALLBACK_BACKEND_URL && BACKEND_URL !== FALLBACK_BACKEND_URL) {
            try {
                const fallbackRes = await fetch(FALLBACK_BACKEND_URL + path, options);
                BACKEND_URL = FALLBACK_BACKEND_URL; // Switch to working backend
                return fallbackRes;
            } catch (fallbackErr) {
                console.warn("Both primary and fallback backend failed:", fallbackErr);
            }
        }
        console.error("Tracking error:", err);
    }
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
    const navAuth = document.querySelector('#navAuth');
    if (!navAuth) return;

    const user = getCurrentUser();

    if (user && user.username) {
        if (user.role === 'admin') {
            navAuth.innerHTML = `
                <li class="nav-item dropdown">
                    <a class="nav-link dropdown-toggle text-warning fw-bold" href="#" id="authDropdown" role="button" data-bs-toggle="dropdown" aria-expanded="false">
                        🛡️ ${user.username}
                    </a>
                    <ul class="dropdown-menu dropdown-menu-end" aria-labelledby="authDropdown">
                        <li><span class="dropdown-item-text text-muted small">SecOps Admin</span></li>
                        <li><hr class="dropdown-divider"></li>
                        <li><a class="dropdown-item" href="admin.html">Admin Dashboard</a></li>
                        <li><a class="dropdown-item" href="index.html">Storefront</a></li>
                        <li><a class="dropdown-item" href="products.html">Products</a></li>
                        <li><hr class="dropdown-divider"></li>
                        <li><a class="dropdown-item text-danger" href="javascript:void(0)" onclick="logout()">Logout</a></li>
                    </ul>
                </li>
            `;
        } else {
            navAuth.innerHTML = `
                <li class="nav-item dropdown">
                    <a class="nav-link dropdown-toggle text-info fw-bold" href="#" id="authDropdown" role="button" data-bs-toggle="dropdown" aria-expanded="false">
                        👤 ${user.username}
                    </a>
                    <ul class="dropdown-menu dropdown-menu-end" aria-labelledby="authDropdown">
                        <li><span class="dropdown-item-text text-muted small">Customer</span></li>
                        <li><hr class="dropdown-divider"></li>
                        <li><a class="dropdown-item" href="products.html">Products</a></li>
                        <li><a class="dropdown-item" href="search.html">Search</a></li>
                        <li><a class="dropdown-item" href="contact.html">Contact</a></li>
                        <li><hr class="dropdown-divider"></li>
                        <li><a class="dropdown-item text-danger" href="javascript:void(0)" onclick="logout()">Logout</a></li>
                    </ul>
                </li>
            `;
        }
    } else {
        navAuth.innerHTML = `<li class="nav-item"><a class="nav-link active" href="login.html">Login</a></li>`;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const restricted = enforceLoginFlow();
    if (restricted) {
        return;
    }
    updateNavbarAuth();
});

// Automatically track basic page views (if not overridden by specific logic)
if (window.location.pathname.endsWith('index.html') || window.location.pathname === '/' || window.location.pathname.endsWith('/')) {
    const user = getCurrentUser();
    if (user) {
        trackRequest('/api/home');
    }
}
