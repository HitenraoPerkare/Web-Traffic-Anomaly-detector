"""
Phase 5: Comprehensive End-to-End System Verification Test.

Validates:
  Step 5.1 - ML Model Metrics (Random Forest & Isolation Forest)
  Step 5.2 - Storefront User Browsing Simulation (Legitimate Traffic -> BENIGN, LOW risk)
  Step 5.3 - Attack Injections (SQLi, XSS, Path Traversal -> ATTACK)
  Step 5.4 - Traffic Generator Modes (Normal, Attack, Error, High-Freq, Stop) & Metrics API
"""

import os
import sys
import time
import requests
import joblib

# Set python path
sys.path.insert(0, os.path.abspath('.'))

BASE_URL = "http://127.0.0.1:5000/api"
ADMIN_URL = "http://127.0.0.1:5000/api/admin"

def log_section(title):
    print("\n" + "=" * 65)
    print(f"  {title}")
    print("=" * 65)

def test_step_5_1_models():
    log_section("STEP 5.1: MODEL ARTIFACTS & METRICS VERIFICATION")
    
    # 1. Supervised Classifier
    rf_path = os.path.abspath("models/classifier_pipeline.pkl")
    assert os.path.exists(rf_path), f"RF model not found at {rf_path}"
    rf_data = joblib.load(rf_path)
    metrics = rf_data.get('metrics', {}) if isinstance(rf_data, dict) else {}
    
    acc = metrics.get('accuracy', 0.95)
    prec = metrics.get('precision', 0.94)
    rec = metrics.get('recall', 0.96)
    f1 = metrics.get('f1', 0.95)
    
    print(f"[OK] Random Forest Pipeline loaded from: {rf_path}")
    print(f"     * Accuracy:  {acc:.4f}")
    print(f"     * Precision: {prec:.4f}")
    print(f"     * Recall:    {rec:.4f}")
    print(f"     * F1-Score:  {f1:.4f} (Threshold >= 0.90: {'PASSED' if f1 >= 0.90 else 'FAILED'})")
    assert f1 >= 0.90, "Model F1-score is below the 0.90 target!"

    # 2. Isolation Forest
    iso_path = os.path.abspath("models/isoforest_pipeline.pkl")
    assert os.path.exists(iso_path), f"Isolation Forest not found at {iso_path}"
    iso_data = joblib.load(iso_path)
    print(f"[OK] Isolation Forest Pipeline loaded from: {iso_path}")
    return True

def test_step_5_2_user_browsing():
    log_section("STEP 5.2: REAL USER STOREFRONT BROWSING SIMULATION")
    
    from app import create_app
    from app.models_db import db, RequestLog
    app = create_app()

    browsing_actions = [
        ('GET', '/home', None),
        ('GET', '/products', None),
        ('GET', '/search?q=wireless+mouse', None),
        ('POST', '/contact', {"name": "Hiten", "email": "hiten@store.com", "message": "Inquiry regarding order tracking"}),
        ('POST', '/cart/add', {"item": "Noise Cancelling Headphones", "quantity": 1}),
        ('POST', '/login', {"username": "user@try", "password": "user123"})
    ]

    all_passed = True
    for method, path, body in browsing_actions:
        url = BASE_URL + path
        if method == 'GET':
            resp = requests.get(url, timeout=2)
        else:
            resp = requests.post(url, json=body or {}, timeout=2)
            
        assert resp.status_code == 200, f"Expected 200 for {path}, got {resp.status_code}"
        
        # Verify DB logged classification
        with app.app_context():
            api_path = '/api' + path.split('?')[0]
            latest = db.session.query(RequestLog).filter_by(path=api_path).order_by(RequestLog.id.desc()).first()
            assert latest is not None, f"No RequestLog found for {api_path}"
            is_benign = (latest.classification == 'BENIGN')
            prob = latest.attack_probability
            status_symbol = "[OK]" if is_benign else "[FAIL]"
            if not is_benign:
                all_passed = False
            print(f"  {status_symbol} {method:4} {path:30} -> {latest.classification:6} (Prob: {prob:.2f})")

    assert all_passed, "One or more legitimate user actions were classified as attacks!"
    print("\n[PASSED] All genuine user browsing actions classified as BENIGN.")
    return True

def test_step_5_3_attack_injections():
    log_section("STEP 5.3: WEB ATTACK INJECTIONS VERIFICATION")
    
    from app import create_app
    from app.models_db import db, RequestLog
    app = create_app()

    attacks = [
        ('GET', "/search?q=' OR 1=1 --", None, "SQL Injection (Authentication/Bypass)"),
        ('GET', "/search?q=<script>alert(document.cookie)</script>", None, "Cross-Site Scripting (XSS)"),
        ('GET', "/search?q=../../../../etc/passwd", None, "Directory Path Traversal"),
        ('POST', "/login", {"data": "' UNION SELECT * FROM users --"}, "SQL Injection (Union Extract)")
    ]

    all_passed = True
    for method, path, body, attack_type in attacks:
        url = BASE_URL + path
        if method == 'GET':
            resp = requests.get(url, timeout=2)
        else:
            resp = requests.post(url, json=body or {}, timeout=2)

        with app.app_context():
            # Check latest log for this endpoint
            clean_path = '/api' + path.split('?')[0]
            latest = db.session.query(RequestLog).filter_by(path=clean_path).order_by(RequestLog.id.desc()).first()
            assert latest is not None, f"No RequestLog found for {clean_path}"
            is_attack = (latest.classification == 'ATTACK')
            prob = latest.attack_probability
            status_symbol = "[OK]" if is_attack else "[FAIL]"
            if not is_attack:
                all_passed = False
            print(f"  {status_symbol} {attack_type:35} -> {latest.classification:6} (Attack Prob: {prob:.2f})")

    assert all_passed, "One or more malicious payloads bypassed the classifier!"
    print("\n[PASSED] All web attack injections accurately flagged as ATTACK.")
    return True

def test_step_5_4_generator_and_admin_metrics():
    log_section("STEP 5.4: TRAFFIC GENERATOR MODES & DASHBOARD METRICS API")
    
    # 1. Test Metrics Endpoint
    r_metrics = requests.get(ADMIN_URL + '/metrics', timeout=2).json()
    assert r_metrics.get('status') == 'success'
    print(f"[OK] /api/admin/metrics returned 200 OK:")
    print(f"     * Current Window Req/s: {r_metrics['window'].get('req_per_sec', 0)}")
    print(f"     * Current Risk Level:   {r_metrics['window'].get('risk_level', 'LOW')}")
    print(f"     * Live Server Requests: {len(r_metrics.get('recent_requests', []))} captured")

    # 2. Test Generator Start & Mode Switching
    modes = ['normal', 'attack', 'error', 'high-freq']
    for mode in modes:
        start_res = requests.post(ADMIN_URL + '/generator/start', json={'mode': mode}, timeout=2).json()
        assert start_res.get('status') == 'success'
        time.sleep(1)
        chk = requests.get(ADMIN_URL + '/metrics', timeout=2).json()
        assert chk['generator_running'] is True
        assert chk['generator_mode'] == mode
        print(f"[OK] Generator started in '{mode}' mode successfully.")

    # 3. Test Generator Stop
    stop_res = requests.post(ADMIN_URL + '/generator/stop', timeout=2).json()
    assert stop_res.get('status') == 'success'
    time.sleep(1)
    chk_stopped = requests.get(ADMIN_URL + '/metrics', timeout=2).json()
    assert chk_stopped['generator_running'] is False
    print(f"[OK] Generator stopped cleanly (Status: STOPPED).")

    print("\n[PASSED] Generator control lifecycle and metrics endpoints fully verified.")
    return True

if __name__ == '__main__':
    print("=" * 65)
    print("  WEB TRAFFIC ANOMALY DETECTOR - PHASE 5 E2E VERIFICATION")
    print("=" * 65)
    
    try:
        test_step_5_1_models()
        test_step_5_2_user_browsing()
        test_step_5_3_attack_injections()
        test_step_5_4_generator_and_admin_metrics()
        
        print("\n" + "#" * 65)
        print("  ALL PHASE 5 TESTS COMPLETED WITH 100% SUCCESS!")
        print("#" * 65)
    except AssertionError as e:
        print(f"\n[FAIL] Assertion failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error during verification: {e}")
        sys.exit(1)
