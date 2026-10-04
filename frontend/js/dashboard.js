// Base URL referencing the Flask backend
const ADMIN_API_BASE = (typeof BACKEND_URL !== 'undefined' ? BACKEND_URL : 'https://web-traffic-anomaly-detector.onrender.com') + '/api/admin';

// --- Admin Geolocation & Device Time Management ---
let adminLongitude = null;

function initAdminGeolocation() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                adminLongitude = pos.coords.longitude;
                updateLongitudeBadge();
            },
            (err) => {
                const offsetMinutes = -new Date().getTimezoneOffset();
                adminLongitude = offsetMinutes / 4.0; // Estimate from timezone meridian
                updateLongitudeBadge();
            },
            { timeout: 6000 }
        );
    } else {
        const offsetMinutes = -new Date().getTimezoneOffset();
        adminLongitude = offsetMinutes / 4.0;
        updateLongitudeBadge();
    }
}

function updateLongitudeBadge() {
    const badge = document.getElementById('admin-lon-badge');
    if (!badge) return;
    const lon = (adminLongitude !== null) ? adminLongitude : (-new Date().getTimezoneOffset() / 4.0);
    const direction = lon >= 0 ? 'E' : 'W';
    badge.innerText = `📍 Admin Lon: ${Math.abs(lon).toFixed(2)}°${direction} (Local Synchronized)`;
}

/**
 * Formats a UTC ISO string directly to the admin's device local time.
 * Ensures the displayed time matches the admin's OS/device clock precisely (e.g. 17:48:xx).
 */
function formatAdminTime(utcIsoString) {
    if (!utcIsoString) return '';
    const utcStr = utcIsoString.endsWith('Z') ? utcIsoString : utcIsoString + 'Z';
    const date = new Date(utcStr);
    return date.toLocaleTimeString([], {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}

// Initialize admin location
initAdminGeolocation();

// --- Chart.js Setup (Smooth Spline + Numeric X-Axis) ---
let trafficChart = null;
let secondsElapsed = 0;
const MAX_DATA_POINTS = 25; // Show ~75 seconds of history (polling every 3s)

try {
    const canvas = document.getElementById('trafficChart');
    if (canvas && typeof Chart !== 'undefined') {
        const ctx = canvas.getContext('2d');
        trafficChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Requests per Second',
                    data: [],
                    borderColor: 'rgb(13, 110, 253)',
                    backgroundColor: 'rgba(13, 110, 253, 0.12)',
                    borderWidth: 2.5,
                    pointRadius: 3,
                    pointHoverRadius: 6,
                    pointBackgroundColor: 'rgb(13, 110, 253)',
                    tension: 0.4,                    // Smooth Bezier curve
                    cubicInterpolationMode: 'monotone', // Ultra smooth without overshoot
                    fill: 'start'
                }]
            },
            options: {
                responsive: true,
                animation: {
                    duration: 350,
                    easing: 'easeOutQuad'
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: function (context) {
                                return ` Traffic: ${context.parsed.y.toFixed(2)} req/sec`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        display: true,
                        title: {
                            display: true,
                            text: 'Timeline (Seconds Elapsed)',
                            color: '#495057',
                            font: { size: 11, weight: 'bold' }
                        },
                        grid: {
                            display: true,
                            color: 'rgba(0, 0, 0, 0.05)'
                        },
                        ticks: {
                            color: '#6c757d',
                            font: { size: 11 },
                            autoSkip: true,
                            maxTicksLimit: 10
                        }
                    },
                    y: {
                        display: true,
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Req / sec',
                            color: '#495057',
                            font: { size: 11, weight: 'bold' }
                        },
                        grid: {
                            color: 'rgba(0, 0, 0, 0.05)'
                        },
                        ticks: {
                            color: '#6c757d',
                            font: { size: 11 }
                        }
                    }
                }
            }
        });
    }
} catch (e) {
    console.warn("Chart.js initialization failed:", e);
}

function updateChart(reqPerSec) {
    if (!trafficChart) return;

    // Label using exact numeric seconds elapsed (0s, 3s, 6s, 9s...)
    const numericLabel = `${secondsElapsed}s`;
    trafficChart.data.labels.push(numericLabel);
    trafficChart.data.datasets[0].data.push(reqPerSec);

    if (trafficChart.data.labels.length > MAX_DATA_POINTS) {
        trafficChart.data.labels.shift();
        trafficChart.data.datasets[0].data.shift();
    }

    trafficChart.update();
    secondsElapsed += 3;
}

// --- Dashboard Polling ---
async function fetchMetrics() {
    try {
        const response = await fetch(`${ADMIN_API_BASE}/metrics`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

        const data = await response.json();

        // Update connection status
        const connBadge = document.getElementById('connection-status');
        if (connBadge) {
            connBadge.className = "badge bg-success";
            connBadge.innerText = "Connected";
        }

        // Update Generator UI
        const genBox = document.getElementById('gen-status-box');
        const genText = document.getElementById('gen-status-text');
        if (genBox && genText) {
            if (data.generator_running) {
                const mode = (data.generator_mode || 'normal').toLowerCase();
                let alertClass = 'alert-success';
                if (mode === 'attack') alertClass = 'alert-danger';
                else if (mode === 'error') alertClass = 'alert-warning';
                else if (mode === 'high-freq') alertClass = 'alert-primary';

                genBox.className = `alert py-1 text-center ${alertClass}`;
                genText.innerText = `RUNNING (${mode.toUpperCase()})`;
            } else {
                genBox.className = "alert alert-secondary py-1 text-center";
                genText.innerText = "STOPPED";
            }
        }

        // Update Top Metrics & Chart
        const windowData = data.window || {};
        const reqSec = windowData.req_per_sec || 0;
        const errRate = windowData.error_rate || 0;
        const riskLevel = windowData.risk_level || 'LOW';
        const anomalyScore = windowData.anomaly_score || 0;

        const reqSecElem = document.getElementById('req-sec');
        const errRateElem = document.getElementById('error-rate');
        const riskBadge = document.getElementById('risk-display');
        const anomalyElem = document.getElementById('anomaly-score');

        if (reqSecElem) reqSecElem.innerText = reqSec.toFixed(2);
        if (errRateElem) errRateElem.innerText = (errRate * 100).toFixed(1) + '%';

        if (riskBadge) {
            riskBadge.innerText = riskLevel;
            riskBadge.className = `py-2 rounded risk-${riskLevel}`;
        }

        if (anomalyElem) anomalyElem.innerText = anomalyScore.toFixed(3);

        // Push new value to smooth spline chart
        updateChart(reqSec);

        // Update Alerts Feed (using admin device-matched time)
        const alertList = document.getElementById('alert-feed');
        if (alertList && data.alerts) {
            if (data.alerts.length > 0) {
                alertList.innerHTML = '';
                data.alerts.forEach(a => {
                    const formattedTime = formatAdminTime(a.time);
                    alertList.innerHTML += `
                        <li class="list-group-item list-group-item-danger">
                            <div class="d-flex w-100 justify-content-between">
                                <h6 class="mb-1">${a.type}</h6>
                                <small class="fw-bold">${formattedTime}</small>
                            </div>
                            <p class="mb-1 small">${a.msg}</p>
                        </li>`;
                });
            } else {
                alertList.innerHTML = '<li class="list-group-item text-muted">No security alerts triggered yet.</li>';
            }
        }

        // Update Live Server Requests Feed (all requests, benign and attack)
        const requestList = document.getElementById('request-feed') || document.getElementById('attack-feed');
        const reqBadge = document.getElementById('req-count-badge');
        const requests = data.recent_requests || data.recent_attacks || [];

        if (reqBadge) reqBadge.innerText = requests.length;

        if (requestList) {
            if (requests.length > 0) {
                requestList.innerHTML = '';
                requests.forEach(req => {
                    const isAttack = (req.classification === 'ATTACK');
                    const itemClass = isAttack ? 'list-group-item-danger' : 'list-group-item-light';
                    const statusBadgeClass = req.status >= 500 ? 'bg-danger' : req.status >= 400 ? 'bg-warning text-dark' : 'bg-success';
                    const clfBadge = isAttack
                        ? `<span class="badge bg-danger ms-1">ATTACK ${((req.prob || 0) * 100).toFixed(0)}%</span>`
                        : `<span class="badge bg-success ms-1">BENIGN</span>`;

                    const reqTime = formatAdminTime(req.time);

                    requestList.innerHTML += `
                        <li class="list-group-item ${itemClass} py-2 border-bottom">
                            <div class="d-flex w-100 justify-content-between align-items-center mb-1">
                                <div>
                                    <span class="badge bg-secondary me-1">${req.method || 'GET'}</span>
                                    <span class="badge ${statusBadgeClass}">${req.status || 200}</span>
                                    ${clfBadge}
                                </div>
                                <small class="text-muted fw-bold">${reqTime}</small>
                            </div>
                            <div class="d-flex justify-content-between">
                                <small class="text-dark font-monospace text-truncate" title="${req.path}"><strong>${req.path}</strong></small>
                                <small class="text-muted">${req.ip || '127.0.0.1'}</small>
                            </div>
                            ${req.query ? `<code class="small d-block text-truncate mt-1 text-danger bg-white p-1 rounded border" title="${req.query}">${req.query}</code>` : ''}
                        </li>`;
                });
            } else {
                requestList.innerHTML = '<li class="list-group-item text-muted">Waiting for server requests...</li>';
            }
        }

    } catch (err) {
        console.error("Dashboard polling error:", err);
        const connBadge = document.getElementById('connection-status');
        if (connBadge) {
            connBadge.className = "badge bg-danger";
            connBadge.innerText = "Disconnected";
        }
    }
}

// --- Generator API Calls ---
async function startGenerator(mode) {
    const genBox = document.getElementById('gen-status-box');
    const genText = document.getElementById('gen-status-text');
    if (genText) genText.innerText = `STARTING (${mode.toUpperCase()})...`;
    if (genBox) genBox.className = "alert alert-warning py-1 text-center";

    try {
        const response = await fetch(`${ADMIN_API_BASE}/generator/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: mode })
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        await fetchMetrics(); // Force immediate refresh
    } catch (err) {
        console.error("Failed to start generator:", err);
        if (genText) genText.innerText = "ERROR STARTING";
        if (genBox) genBox.className = "alert alert-danger py-1 text-center";
    }
}

async function stopGenerator() {
    const genBox = document.getElementById('gen-status-box');
    const genText = document.getElementById('gen-status-text');
    if (genText) genText.innerText = "STOPPING...";
    if (genBox) genBox.className = "alert alert-warning py-1 text-center";

    try {
        const response = await fetch(`${ADMIN_API_BASE}/generator/stop`, {
            method: 'POST'
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        await fetchMetrics();
    } catch (err) {
        console.error("Failed to stop generator:", err);
        if (genText) genText.innerText = "ERROR STOPPING";
        if (genBox) genBox.className = "alert alert-danger py-1 text-center";
    }
}

// Attach globally for inline HTML onclick handlers
window.startGenerator = startGenerator;
window.stopGenerator = stopGenerator;
window.fetchMetrics = fetchMetrics;

// Start polling every 3 seconds
setInterval(fetchMetrics, 3000);
fetchMetrics(); // Initial fetch
