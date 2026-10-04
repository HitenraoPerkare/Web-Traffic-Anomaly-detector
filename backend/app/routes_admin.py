import threading
import time
import random
import requests
from flask import Blueprint, jsonify, request
from app.models_db import db, RequestLog, TrafficWindow, Alert

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

# --- Traffic Generator ---
class TrafficGenerator:
    def __init__(self):
        self.running = False
        self.thread = None
        self.mode = 'normal' # 'normal', 'attack', 'error', 'high-freq'

    def start(self, mode):
        self.mode = mode
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._generate_traffic, daemon=True)
            self.thread.start()

    def stop(self):
        self.running = False

    def _generate_traffic(self):
        base_url = "http://127.0.0.1:5000/api"
        
        normal_endpoints = [
            ('/home', 'GET', None),
            ('/products', 'GET', None),
            ('/search?q=laptop', 'GET', None),
            ('/search?q=wireless+mouse', 'GET', None),
            ('/contact', 'POST', {"name": "Alice", "email": "alice@test.com", "message": "Inquiring about warranty"}),
            ('/cart/add', 'POST', {"item": "Mechanical Keyboard", "quantity": 1}),
            ('/login', 'POST', {"username": "user@try", "password": "user123"})
        ]

        attack_payloads = [
            "' OR 1=1 --", "<script>alert(1)</script>", "../../../../etc/passwd",
            "UNION SELECT * FROM users", "WAITFOR DELAY '0:0:5'", "1; DROP TABLE users",
            "<img src=x onerror=alert(1)>", "' UNION SELECT null, username, password FROM users --"
        ]

        error_scenarios = [
            # 404 Not Found (Directory traversal / path fuzzing)
            ('/admin.php', 'GET', None),
            ('/wp-login.php', 'GET', None),
            ('/.env', 'GET', None),
            ('/backup.zip', 'GET', None),
            ('/nonexistent-page', 'GET', None),
            ('/v2/debug', 'GET', None),
            ('/config.json', 'GET', None),
            # 401 Unauthorized (Credential stuffing / failed login)
            ('/login', 'POST', {"username": "fuzzer_bot", "password": "invalid_password_123"}),
            ('/login', 'POST', {"username": "admin", "password": "wrong_password"}),
            # 405 Method Not Allowed (Invalid HTTP verb on GET-only routes)
            ('/home', 'POST', {"data": "invalid_post"}),
            ('/products', 'POST', {"data": "invalid_post"})
        ]

        while self.running:
            headers = {'X-Synthetic-Traffic': '1'}
            try:
                if self.mode == 'attack':
                    # 80% attack payloads, 20% normal background
                    if random.random() < 0.8:
                        payload = random.choice(attack_payloads)
                        endpoint, method = random.choice([
                            ('/search', 'GET'), ('/products', 'GET'), ('/login', 'POST'), ('/contact', 'POST')
                        ])
                        if method == 'GET':
                            requests.get(f"{base_url}{endpoint}?q={payload}", headers=headers, timeout=1)
                        else:
                            requests.post(f"{base_url}{endpoint}", json={"data": payload}, headers=headers, timeout=1)
                    else:
                        requests.get(f"{base_url}/home", headers=headers, timeout=1)
                    time.sleep(random.uniform(0.04, 0.15))

                elif self.mode == 'error':
                    # High error rate mode (4xx / 5xx error fuzzing)
                    path, method, body = random.choice(error_scenarios)
                    url = f"{base_url}{path}"
                    if method == 'GET':
                        requests.get(url, headers=headers, timeout=1)
                    else:
                        requests.post(url, json=body or {}, headers=headers, timeout=1)
                    time.sleep(random.uniform(0.08, 0.25))

                elif self.mode == 'high-freq':
                    # High-frequency flood / rate spike / DoS simulation
                    path, method, body = random.choice(normal_endpoints)
                    url = f"{base_url}{path}"
                    if method == 'GET':
                        requests.get(url, headers=headers, timeout=1)
                    else:
                        requests.post(url, json=body or {}, headers=headers, timeout=1)
                    time.sleep(random.uniform(0.005, 0.02))

                else:
                    # Normal human browsing mode
                    path, method, body = random.choice(normal_endpoints)
                    url = f"{base_url}{path}"
                    if method == 'GET':
                        requests.get(url, headers=headers, timeout=1)
                    else:
                        requests.post(url, json=body or {}, headers=headers, timeout=1)
                    time.sleep(random.uniform(0.6, 1.8))

            except Exception:
                pass

generator = TrafficGenerator()

# --- API Endpoints ---

@admin_bp.route('/metrics', methods=['GET'])
def get_metrics():
    from datetime import datetime
    now = datetime.utcnow()

    # 1. Latest Traffic Window
    latest_window = db.session.query(TrafficWindow).order_by(TrafficWindow.id.desc()).first()
    window_data = {}
    if latest_window:
        is_stale = False
        if latest_window.end_time and (now - latest_window.end_time).total_seconds() > 20:
            is_stale = True

        window_data = {
            "id": latest_window.id,
            "req_per_sec": 0.0 if is_stale else (latest_window.requests_per_second or 0.0),
            "error_rate": 0.0 if is_stale else ((latest_window.error_4xx_ratio or 0.0) + (latest_window.error_5xx_ratio or 0.0)),
            "status": "NORMAL" if is_stale else (latest_window.status or "NORMAL"),
            "risk_level": "LOW" if is_stale else (latest_window.risk_level or "LOW"),
            "anomaly_score": 0.0 if is_stale else (latest_window.anomaly_score or 0.0)
        }

    # 2. Recent Alerts
    recent_alerts = db.session.query(Alert).order_by(Alert.id.desc()).limit(5).all()
    alerts_data = [{"id": a.id, "time": a.timestamp.isoformat() + "Z", "type": a.alert_type, "level": a.risk_level, "msg": a.description} for a in recent_alerts]

    # 3. Recent Server Requests (all traffic, excluding internal admin endpoints)
    recent_requests = db.session.query(RequestLog).filter(
        ~RequestLog.path.startswith('/api/admin')
    ).order_by(RequestLog.id.desc()).limit(15).all()
    
    requests_data = [{
        "id": r.id,
        "ip": r.client_ip or "127.0.0.1",
        "method": r.method or "GET",
        "path": r.path,
        "query": r.query or "",
        "status": r.status_code or 200,
        "classification": r.classification or "BENIGN",
        "prob": r.attack_probability or 0.0,
        "time": r.timestamp.isoformat() + "Z" if r.timestamp else ""
    } for r in recent_requests]

    return jsonify({
        "status": "success",
        "window": window_data,
        "alerts": alerts_data,
        "recent_requests": requests_data,
        "recent_attacks": [r for r in requests_data if r['classification'] == 'ATTACK'],
        "generator_running": generator.running,
        "generator_mode": generator.mode
    })

@admin_bp.route('/generator/start', methods=['POST'])
def start_generator():
    data = request.json or {}
    mode = data.get('mode', 'normal')
    generator.start(mode)
    return jsonify({"status": "success", "message": f"Generator started in {mode} mode"})

@admin_bp.route('/generator/stop', methods=['POST'])
def stop_generator():
    generator.stop()
    return jsonify({"status": "success", "message": "Generator stopped"})
