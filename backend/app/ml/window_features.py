"""
Shared Window-Level Behavioral Feature Extraction.

Aggregates a list of HTTP request logs (over a 10-second window)
into numerical behavioral metrics used by the Isolation Forest anomaly detector
and persisted to the TrafficWindow database table.
"""

import math
from typing import List, Dict, Any
import numpy as np


WINDOW_FEATURE_NAMES = [
    'requests_per_window',
    'requests_per_second',
    'unique_client_count',
    'requests_per_client_avg',
    'repeated_request_ratio',
    'endpoint_diversity',
    'avg_inter_request_time',
    'traffic_bytes',
    'avg_request_size',
    'avg_response_time',
    'error_4xx_ratio',
    'error_5xx_ratio'
]


def calculate_entropy(items: List[str]) -> float:
    """Computes Shannon entropy of categorical items (e.g. paths, endpoints)."""
    if not items:
        return 0.0
    total = len(items)
    counts = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    probs = [c / total for c in counts.values()]
    return -sum(p * math.log2(p) for p in probs)


def extract_window_features(requests: List[Dict[str, Any]], window_seconds: float = 10.0) -> Dict[str, float]:
    """
    Computes window-level behavioral features from a list of request dictionaries.
    
    Each request dict is expected to contain:
      - timestamp (float/datetime: arrival time)
      - path (str: URL path)
      - client_id (str: IP or client identifier)
      - status_code (int: HTTP response status)
      - response_time_ms (float: latency in ms)
      - request_size (int: payload size in bytes)
    """
    total_requests = len(requests)
    
    if total_requests == 0:
        # Default baseline empty window
        return {
            'requests_per_window': 0.0,
            'requests_per_second': 0.0,
            'unique_client_count': 0.0,
            'requests_per_client_avg': 0.0,
            'repeated_request_ratio': 0.0,
            'endpoint_diversity': 0.0,
            'avg_inter_request_time': float(window_seconds),
            'traffic_bytes': 0.0,
            'avg_request_size': 0.0,
            'avg_response_time': 0.0,
            'error_4xx_ratio': 0.0,
            'error_5xx_ratio': 0.0
        }

    # Rates
    req_per_sec = total_requests / max(window_seconds, 1.0)

    # Clients
    clients = [r.get('client_id', 'unknown') for r in requests]
    unique_clients = len(set(clients))
    req_per_client_avg = total_requests / max(unique_clients, 1)

    # Paths and diversity
    paths = [r.get('path', '/') for r in requests]
    endpoint_diversity = calculate_entropy(paths)
    
    path_counts = {}
    for p in paths:
        path_counts[p] = path_counts.get(p, 0) + 1
    max_single_path_count = max(path_counts.values()) if path_counts else 0
    repeated_request_ratio = max_single_path_count / total_requests

    # Inter-request time
    timestamps = [r.get('timestamp') for r in requests if r.get('timestamp') is not None]
    if len(timestamps) > 1:
        # Sort and calculate differences in seconds
        ts_sorted = sorted([
            t.timestamp() if hasattr(t, 'timestamp') else float(t)
            for t in timestamps
        ])
        diffs = [ts_sorted[i] - ts_sorted[i - 1] for i in range(1, len(ts_sorted))]
        avg_inter_time = float(np.mean(diffs)) if diffs else (window_seconds / total_requests)
    else:
        avg_inter_time = window_seconds / total_requests

    # Byte traffic & latency
    sizes = [float(r.get('request_size', 0)) for r in requests]
    total_bytes = sum(sizes)
    avg_req_size = total_bytes / total_requests

    latencies = [float(r.get('response_time_ms', 0.0)) for r in requests]
    avg_latency = float(np.mean(latencies)) if latencies else 0.0

    # Error code ratios
    status_codes = [int(r.get('status_code', 200)) for r in requests]
    c_4xx = sum(1 for s in status_codes if 400 <= s < 500)
    c_5xx = sum(1 for s in status_codes if 500 <= s < 600)
    error_4xx_ratio = c_4xx / total_requests
    error_5xx_ratio = c_5xx / total_requests

    return {
        'requests_per_window': float(total_requests),
        'requests_per_second': float(round(req_per_sec, 2)),
        'unique_client_count': float(unique_clients),
        'requests_per_client_avg': float(round(req_per_client_avg, 2)),
        'repeated_request_ratio': float(round(repeated_request_ratio, 4)),
        'endpoint_diversity': float(round(endpoint_diversity, 4)),
        'avg_inter_request_time': float(round(avg_inter_time, 4)),
        'traffic_bytes': float(round(total_bytes, 1)),
        'avg_request_size': float(round(avg_req_size, 2)),
        'avg_response_time': float(round(avg_latency, 2)),
        'error_4xx_ratio': float(round(error_4xx_ratio, 4)),
        'error_5xx_ratio': float(round(error_5xx_ratio, 4))
    }
