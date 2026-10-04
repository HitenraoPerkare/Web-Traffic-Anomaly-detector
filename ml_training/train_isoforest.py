"""
Train Unsupervised Behavioral Anomaly Detector (Isolation Forest).

Trains an IsolationForest model on baseline normal traffic windows
using the shared window feature definitions from app.ml.window_features.
Saves the serialized model artifact into models/isoforest_pipeline.pkl.
"""

import os
import sys
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

# Ensure parent directory is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.ml.window_features import WINDOW_FEATURE_NAMES


def generate_baseline_normal_windows(n_windows: int = 5000, random_state: int = 42) -> pd.DataFrame:
    """
    Generates synthetic feature distributions representative of normal web browsing
    over 10-second windows.
    """
    rng = np.random.default_rng(random_state)
    
    # Normal browsing parameters (10-second window):
    # Requests: typically 4 to 25 requests across multiple endpoints
    requests_per_window = rng.integers(4, 26, size=n_windows)
    requests_per_second = np.round(requests_per_window / 10.0, 2)
    
    # Clients: 1 to 4 active users browsing simultaneously
    unique_client_count = rng.integers(1, 5, size=n_windows)
    unique_client_count = np.minimum(unique_client_count, requests_per_window)
    requests_per_client_avg = np.round(requests_per_window / unique_client_count, 2)
    
    # Diversity: normal users browse varied pages (diversity between 1.0 and 2.5)
    endpoint_diversity = rng.uniform(1.0, 2.8, size=n_windows)
    
    # Repetition: low to moderate repeated requests (0.1 to 0.45)
    repeated_request_ratio = rng.uniform(0.10, 0.45, size=n_windows)
    
    # Inter-request time: normal human reading & clicking intervals (0.4s to 2.5s)
    avg_inter_request_time = rng.uniform(0.40, 2.50, size=n_windows)
    
    # Sizes and bytes: average request size ~ 200 - 800 bytes
    avg_request_size = rng.uniform(200.0, 800.0, size=n_windows)
    traffic_bytes = np.round(requests_per_window * avg_request_size, 1)
    
    # Response times: typical local server response times (10ms to 60ms)
    avg_response_time = rng.uniform(10.0, 60.0, size=n_windows)
    
    # Error rates: rarely fail in normal browsing (0% to 5%)
    error_4xx_ratio = rng.choice([0.0, 0.0, 0.0, 0.02, 0.04], size=n_windows)
    error_5xx_ratio = np.zeros(n_windows)
    
    data = {
        'requests_per_window': requests_per_window.astype(float),
        'requests_per_second': requests_per_second,
        'unique_client_count': unique_client_count.astype(float),
        'requests_per_client_avg': requests_per_client_avg,
        'repeated_request_ratio': np.round(repeated_request_ratio, 4),
        'endpoint_diversity': np.round(endpoint_diversity, 4),
        'avg_inter_request_time': np.round(avg_inter_request_time, 4),
        'traffic_bytes': traffic_bytes,
        'avg_request_size': np.round(avg_request_size, 2),
        'avg_response_time': np.round(avg_response_time, 2),
        'error_4xx_ratio': np.round(error_4xx_ratio, 4),
        'error_5xx_ratio': np.round(error_5xx_ratio, 4)
    }
    
    return pd.DataFrame(data, columns=WINDOW_FEATURE_NAMES)


def train_isolation_forest(output_path: str):
    print("=" * 60)
    print("  TRAINING ISOLATION FOREST ANOMALY DETECTOR")
    print("=" * 60)
    
    print("\n1. Generating baseline normal traffic windows...")
    normal_df = generate_baseline_normal_windows(n_windows=5000, random_state=42)
    print(f"   Generated {len(normal_df):,} normal baseline windows across {len(WINDOW_FEATURE_NAMES)} features.")
    
    # Setup Isolation Forest pipeline
    print("\n2. Fitting IsolationForest (contamination=0.05, n_estimators=100)...")
    iso_forest = IsolationForest(
        n_estimators=100,
        contamination=0.05,
        random_state=42,
        n_jobs=-1
    )
    
    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('model', iso_forest)
    ])
    
    pipeline.fit(normal_df[WINDOW_FEATURE_NAMES])
    print("   Model fitting complete.")
    
    # Test on synthetic anomalies to verify sensitivity
    print("\n3. Testing detection sensitivity on synthetic anomaly profiles:")
    test_cases = [
        ("Normal Window (Low Rate, Varied Paths)", {
            'requests_per_window': 10.0, 'requests_per_second': 1.0,
            'unique_client_count': 2.0, 'requests_per_client_avg': 5.0,
            'repeated_request_ratio': 0.25, 'endpoint_diversity': 1.8,
            'avg_inter_request_time': 1.0, 'traffic_bytes': 4500.0,
            'avg_request_size': 450.0, 'avg_response_time': 25.0,
            'error_4xx_ratio': 0.0, 'error_5xx_ratio': 0.0
        }),
        ("BURST Attack (Spike: 150 req/s, tiny inter-arrival)", {
            'requests_per_window': 150.0, 'requests_per_second': 15.0,
            'unique_client_count': 1.0, 'requests_per_client_avg': 150.0,
            'repeated_request_ratio': 0.85, 'endpoint_diversity': 0.2,
            'avg_inter_request_time': 0.05, 'traffic_bytes': 75000.0,
            'avg_request_size': 500.0, 'avg_response_time': 140.0,
            'error_4xx_ratio': 0.05, 'error_5xx_ratio': 0.0
        }),
        ("REPETITIVE Scraper (High Repetition, Zero Diversity)", {
            'requests_per_window': 60.0, 'requests_per_second': 6.0,
            'unique_client_count': 1.0, 'requests_per_client_avg': 60.0,
            'repeated_request_ratio': 1.0, 'endpoint_diversity': 0.0,
            'avg_inter_request_time': 0.16, 'traffic_bytes': 30000.0,
            'avg_request_size': 500.0, 'avg_response_time': 35.0,
            'error_4xx_ratio': 0.0, 'error_5xx_ratio': 0.0
        }),
        ("ERROR Fuzzing / Probing (80% 404s)", {
            'requests_per_window': 40.0, 'requests_per_second': 4.0,
            'unique_client_count': 1.0, 'requests_per_client_avg': 40.0,
            'repeated_request_ratio': 0.1, 'endpoint_diversity': 2.5,
            'avg_inter_request_time': 0.25, 'traffic_bytes': 16000.0,
            'avg_request_size': 400.0, 'avg_response_time': 20.0,
            'error_4xx_ratio': 0.80, 'error_5xx_ratio': 0.0
        })
    ]
    
    for name, sample_dict in test_cases:
        sample_df = pd.DataFrame([sample_dict], columns=WINDOW_FEATURE_NAMES)
        pred = pipeline.predict(sample_df)[0]
        # In sklearn IsolationForest: 1 = normal, -1 = anomaly
        score = -float(pipeline.named_steps['model'].score_samples(
            pipeline.named_steps['scaler'].transform(sample_df)
        )[0])
        status = "ANOMALY" if pred == -1 else "NORMAL"
        print(f"   [{status:<7}] {name:<50} (Score: {score:.4f})")

    # Packaging
    payload = {
        'pipeline': pipeline,
        'feature_names': WINDOW_FEATURE_NAMES,
        'model_type': 'IsolationForest'
    }
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    print(f"\n4. Saving Isolation Forest artifact to: {output_path}")
    joblib.dump(payload, output_path)
    print("   Artifact saved successfully!")
    print("=" * 60)


def main():
    base_dir = os.path.dirname(__file__)
    output_model = os.path.abspath(os.path.join(base_dir, '..', 'models', 'isoforest_pipeline.pkl'))
    train_isolation_forest(output_model)


if __name__ == '__main__':
    main()
