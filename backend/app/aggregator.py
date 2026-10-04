import time
import threading
from datetime import datetime, timedelta
from app.middleware import request_buffer, buffer_lock
from app.models_db import db, TrafficWindow
from app.ml.anomaly_service import anomaly_service
from app.risk_engine import risk_engine
from app.alert_engine import alert_engine

class TrafficAggregator:
    def __init__(self, app):
        self.app = app
        self.interval_seconds = app.config.get('WINDOW_DURATION', 10)
        self.running = False
        self.thread = None
        
    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._run_loop, daemon=True)
            self.thread.start()
            self.app.logger.info(f"Aggregator started (interval: {self.interval_seconds}s)")
            
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
            
    def _run_loop(self):
        while self.running:
            time.sleep(self.interval_seconds)
            self._process_window()
            
    def _process_window(self):
        with self.app.app_context():
            requests_to_process = []
            now = datetime.utcnow()
            
            # Extract current items from buffer
            with buffer_lock:
                while request_buffer:
                    requests_to_process.append(request_buffer.popleft())
                    
            if not requests_to_process:
                # No traffic in this window
                return
                
            # Calculate metrics matching the TrafficWindow DB model
            total_requests = len(requests_to_process)
            req_per_sec = total_requests / self.interval_seconds
            
            error_4xx_count = sum(1 for r in requests_to_process if 400 <= r['status_code'] < 500)
            error_4xx_ratio = (error_4xx_count / total_requests) if total_requests > 0 else 0
            
            error_5xx_count = sum(1 for r in requests_to_process if 500 <= r['status_code'] < 600)
            error_5xx_ratio = (error_5xx_count / total_requests) if total_requests > 0 else 0
            
            malicious_count = sum(1 for r in requests_to_process if r['classification'] != 'BENIGN')
            malicious_ratio = (malicious_count / total_requests) if total_requests > 0 else 0
            
            client_ips = [r['client_id'] for r in requests_to_process]
            unique_ips = len(set(client_ips))
            
            paths = set(r['path'] for r in requests_to_process)
            endpoint_diversity = len(paths) / total_requests if total_requests > 0 else 0
            
            avg_response_time = sum(r['response_time_ms'] for r in requests_to_process) / total_requests
            traffic_bytes = sum(r['request_size'] for r in requests_to_process)
            avg_request_size = traffic_bytes / total_requests if total_requests > 0 else 0
            
            # Prepare window features for isolation forest (matching window_features.py logic approx)
            window_features = {
                'requests_per_window': float(total_requests),
                'requests_per_second': float(req_per_sec),
                'unique_client_count': float(unique_ips),
                'requests_per_client_avg': float(total_requests / unique_ips) if unique_ips > 0 else 0.0,
                'repeated_request_ratio': float((total_requests - len(set(f"{r['client_id']}-{r['path']}" for r in requests_to_process))) / total_requests) if total_requests > 0 else 0.0,
                'endpoint_diversity': float(endpoint_diversity),
                'avg_inter_request_time': 0.0, # Approximate for now
                'traffic_bytes': float(traffic_bytes),
                'avg_request_size': float(avg_request_size),
                'avg_response_time': float(avg_response_time),
                'error_4xx_ratio': float(error_4xx_ratio),
                'error_5xx_ratio': float(error_5xx_ratio)
            }
            
            # Predict anomaly via Isolation Forest
            anomaly_result = anomaly_service.predict(window_features)
            
            # Evaluate overall risk (add missing fields for risk engine)
            risk_input_features = window_features.copy()
            risk_input_features['malicious_ratio'] = malicious_ratio
            risk_input_features['error_rate'] = (error_4xx_ratio + error_5xx_ratio) * 100
            risk_input_features['total_requests'] = total_requests
            
            risk_score, risk_level = risk_engine.evaluate(risk_input_features, anomaly_result)
            
            is_anomaly = anomaly_result.get('is_anomaly', False)
            
            # Save to database matching TrafficWindow schema
            window_record = TrafficWindow(
                start_time=now - timedelta(seconds=self.interval_seconds),
                end_time=now,
                requests_per_window=window_features['requests_per_window'],
                requests_per_second=window_features['requests_per_second'],
                unique_client_count=window_features['unique_client_count'],
                requests_per_client_avg=window_features['requests_per_client_avg'],
                repeated_request_ratio=window_features['repeated_request_ratio'],
                endpoint_diversity=window_features['endpoint_diversity'],
                avg_inter_request_time=window_features['avg_inter_request_time'],
                traffic_bytes=window_features['traffic_bytes'],
                avg_request_size=window_features['avg_request_size'],
                avg_response_time=window_features['avg_response_time'],
                error_4xx_ratio=window_features['error_4xx_ratio'],
                error_5xx_ratio=window_features['error_5xx_ratio'],
                status='ANOMALY' if is_anomaly else 'NORMAL',
                anomaly_score=float(anomaly_result.get('anomaly_score', 0.0)),
                risk_level=risk_level
            )
            
            try:
                db.session.add(window_record)
                db.session.commit()
                print(f"[Aggregator] Processed 10s Window #{window_record.id}: {total_requests} reqs ({req_per_sec:.2f} r/s) | Status: {window_record.status} | Risk: {window_record.risk_level}")
                
                # Check alerts
                alert_engine.process_risk(risk_level, risk_score, window_record.id, risk_input_features)
                
            except Exception as e:
                db.session.rollback()
                self.app.logger.error(f"Error saving traffic window: {e}")

_aggregator_instance = None

def start_aggregator(app):
    global _aggregator_instance
    if _aggregator_instance is None:
        _aggregator_instance = TrafficAggregator(app)
        _aggregator_instance.start()
