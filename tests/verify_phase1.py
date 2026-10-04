"""
Phase 1 Verification Test Suite.

Tests feature extraction, supervised Random Forest classification on realistic web requests,
window feature aggregation, and unsupervised Isolation Forest anomaly detection.
"""

import os
import sys
import time

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.ml.classifier_service import classifier_service
from app.ml.window_features import extract_window_features
from app.ml.anomaly_service import anomaly_service


def test_classifier():
    print("\n--- 1. Testing Supervised HTTP Attack Classifier ---")
    test_cases = [
        # Legitimate Web Browsing (Storefront)
        ("Benign Home View", {'method': 'GET', 'path': '/', 'query': '', 'body': ''}, 'BENIGN'),
        ("Benign Products Catalog", {'method': 'GET', 'path': '/products', 'query': '', 'body': ''}, 'BENIGN'),
        ("Benign Catalog Filter", {'method': 'GET', 'path': '/products', 'query': 'category=electronics&page=1', 'body': ''}, 'BENIGN'),
        ("Benign Search Query", {'method': 'GET', 'path': '/search', 'query': 'q=wireless+laptop', 'body': ''}, 'BENIGN'),
        ("Benign Login Submission", {'method': 'POST', 'path': '/login', 'query': '', 'body': 'username=john_doe&password=MySecurePassword123'}, 'BENIGN'),
        ("Benign Contact Form", {'method': 'POST', 'path': '/contact', 'query': '', 'body': 'name=Alice+Smith&email=alice@company.com&subject=Support&message=Hello+team'}, 'BENIGN'),

        # Real Attack Scenarios
        ("SQLi Authentication Bypass", {'method': 'GET', 'path': '/search', 'query': "q=' OR 1=1 --", 'body': ''}, 'ATTACK'),
        ("SQLi Union Exfiltration", {'method': 'GET', 'path': '/products', 'query': "id=1 UNION SELECT null, username, password FROM users--", 'body': ''}, 'ATTACK'),
        ("SQLi Piggybacked Statement", {'method': 'POST', 'path': '/products', 'query': '', 'body': "id=2'; DROP TABLE users; --"}, 'ATTACK'),
        ("XSS Stored Payload", {'method': 'POST', 'path': '/contact', 'query': '', 'body': 'name=test&message=<script>alert(document.cookie)</script>'}, 'ATTACK'),
        ("XSS Reflected Probe", {'method': 'GET', 'path': '/search', 'query': 'q=<img src=x onerror=alert(1)>', 'body': ''}, 'ATTACK'),
        ("Path Traversal / LFI Attack", {'method': 'GET', 'path': '/download', 'query': 'file=../../../../etc/passwd', 'body': ''}, 'ATTACK'),
        ("Backup File Probing", {'method': 'GET', 'path': '/admin.php~', 'query': '', 'body': ''}, 'ATTACK'),
    ]

    all_passed = True
    for name, req, expected in test_cases:
        res = classifier_service.predict(req)
        verdict = res['classification']
        prob = res['attack_probability'] * 100
        passed = (verdict == expected)
        mark = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        print(f"  [{mark}] {name:<28} -> Predicted: {verdict:<6} ({prob:5.1f}% atk prob) | Expected: {expected}")

    return all_passed


def test_anomaly_detector():
    print("\n--- 2. Testing Behavioral Anomaly Detector (Isolation Forest) ---")
    now = time.time()

    # Normal browsing window (12 requests over 10 seconds across multiple paths)
    normal_reqs = [
        {'timestamp': now + i * 0.8, 'path': f'/page{i % 4}', 'client_id': f'user_{i % 3}', 'status_code': 200, 'response_time_ms': 25.0, 'request_size': 400}
        for i in range(12)
    ]
    w_norm = extract_window_features(normal_reqs)
    res_norm = anomaly_service.predict(w_norm)

    # BURST attack window (120 rapid requests)
    burst_reqs = [
        {'timestamp': now + i * 0.05, 'path': '/api/search', 'client_id': 'bot_net', 'status_code': 200, 'response_time_ms': 130.0, 'request_size': 500}
        for i in range(120)
    ]
    w_burst = extract_window_features(burst_reqs)
    res_burst = anomaly_service.predict(w_burst)

    # REPETITIVE crawler window (60 requests on exact same path)
    rep_reqs = [
        {'timestamp': now + i * 0.15, 'path': '/products/item-99', 'client_id': 'crawler_1', 'status_code': 200, 'response_time_ms': 30.0, 'request_size': 450}
        for i in range(60)
    ]
    w_rep = extract_window_features(rep_reqs)
    res_rep = anomaly_service.predict(w_rep)

    # 404 Error fuzzing window (35 404s targeting admin pages)
    err_reqs = [
        {'timestamp': now + i * 0.2, 'path': f'/admin_{i}.php', 'client_id': 'scanner', 'status_code': 404, 'response_time_ms': 15.0, 'request_size': 200}
        for i in range(35)
    ]
    w_err = extract_window_features(err_reqs)
    res_err = anomaly_service.predict(w_err)

    test_windows = [
        ("Normal Multi-User Browsing", res_norm, 'NORMAL'),
        ("High-Rate BURST Probe", res_burst, 'ANOMALY'),
        ("REPETITIVE Endpoint Scraper", res_rep, 'ANOMALY'),
        ("High 404 Error Fuzzing Scan", res_err, 'ANOMALY'),
    ]

    all_passed = True
    for name, res, expected in test_windows:
        status = res['status']
        score = res['anomaly_score']
        passed = (status == expected)
        mark = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        print(f"  [{mark}] {name:<28} -> Status: {status:<7} (Anomaly Score: {score:.4f}) | Expected: {expected}")

    return all_passed


def main():
    print("=" * 65)
    print("           PHASE 1 INTEGRATION & VERIFICATION SUITE              ")
    print("=" * 65)

    c_ok = test_classifier()
    a_ok = test_anomaly_detector()

    print("\n" + "=" * 65)
    if c_ok and a_ok:
        print("  RESULT: ALL PHASE 1 CHECKS PASSED (100% OK)")
    else:
        print("  RESULT: ONE OR MORE CHECKS FAILED")
    print("=" * 65)


if __name__ == '__main__':
    main()
