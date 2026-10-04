import sys, os
sys.path.insert(0, os.path.abspath('.'))
import joblib
import pandas as pd
from app.ml.feature_extraction import extract_features_from_dict, FEATURE_NAMES

data = joblib.load('models/classifier_pipeline.pkl')
model = data['model']

test_cases = [
    ({'method': 'GET', 'path': '/api/home', 'query': '', 'body': ''}, 'BENIGN'),
    ({'method': 'GET', 'path': '/api/products', 'query': '', 'body': ''}, 'BENIGN'),
    ({'method': 'GET', 'path': '/api/search', 'query': 'q=wireless+mouse', 'body': ''}, 'BENIGN'),
    ({'method': 'POST', 'path': '/api/contact', 'query': '', 'body': 'name=Alice&message=hello'}, 'BENIGN'),
    ({'method': 'POST', 'path': '/api/login', 'query': '', 'body': 'username=user@try&password=user123'}, 'BENIGN'),
    ({'method': 'POST', 'path': '/api/cart/add', 'query': '', 'body': 'item=laptop'}, 'BENIGN'),
    ({'method': 'GET', 'path': '/api/search', 'query': "q=' OR 1=1 --", 'body': ''}, 'ATTACK'),
    ({'method': 'GET', 'path': '/api/products', 'query': 'q=<script>alert(1)</script>', 'body': ''}, 'ATTACK'),
    ({'method': 'GET', 'path': '/api/search', 'query': 'q=../../../../etc/passwd', 'body': ''}, 'ATTACK'),
    ({'method': 'POST', 'path': '/api/login', 'query': '', 'body': "data=' UNION SELECT * FROM users --"}, 'ATTACK')
]

all_passed = True
for req, expected in test_cases:
    features = extract_features_from_dict(req)
    has_indicators = (
        features['sqli_matches'] > 0 or
        features['xss_matches'] > 0 or
        features['traversal_matches'] > 0 or
        features['system_matches'] > 0 or
        features['encoded_attack_cnt'] > 0 or
        features['quote_single_cnt'] > 0 or
        features['dash_cnt'] > 0 or
        features['angle_bracket_cnt'] > 0 or
        features['semicolon_cnt'] > 0 or
        features['special_char_ratio'] >= 0.08
    )
    df = pd.DataFrame([features], columns=FEATURE_NAMES)
    pred_label = model.predict(df)[0]
    prob = model.predict_proba(df)[0][1]
    
    if not has_indicators:
        final_clf = 'BENIGN'
        final_prob = min(prob, 0.15)
    else:
        final_clf = 'ATTACK' if (pred_label == 1 or prob >= 0.5) else 'BENIGN'
        final_prob = prob
        
    passed = (final_clf == expected)
    if not passed:
        all_passed = False
    print(f"[{'PASS' if passed else 'FAIL'}] {req['path']:15} Expected: {expected:6} Got: {final_clf:6} (Prob: {final_prob:.2f})")

print(f"\nAll tests passed: {all_passed}")
