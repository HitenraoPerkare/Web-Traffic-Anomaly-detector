import time
from collections import deque
from flask import request, current_app
from app.models_db import db, RequestLog
from app.ml.classifier_service import classifier_service
import threading

# Thread-safe buffer for batching DB writes and providing data to aggregator
request_buffer = deque(maxlen=5000)
buffer_lock = threading.Lock()

def init_middleware(app):
    @app.before_request
    def start_timer():
        request.start_time = time.time()

    @app.after_request
    def log_request(response):
        # Skip logging for static files and favicon
        if request.path.startswith('/static') or request.path == '/favicon.ico':
            return response
            
        # Calculate response time
        response_time_ms = 0
        if hasattr(request, 'start_time'):
            response_time_ms = (time.time() - request.start_time) * 1000.0
            
        # Extract basic request info
        client_ip = request.remote_addr
        method = request.method
        path = request.path
        query = request.query_string.decode('utf-8') if request.query_string else ''
        
        # Read body if it exists, limited size to avoid massive memory usage
        body = ''
        if request.is_json:
            body = request.get_data(as_text=True)
        elif request.form:
            # Reconstruct form data as query string like format
            body = '&'.join([f"{k}={v}" for k, v in request.form.items()])
        
        request_size = request.content_length or 0
        status_code = response.status_code
        
        # Prepare dictionary for ML prediction
        req_dict = {
            'method': method,
            'path': path,
            'query': query,
            'body': body
        }
        
        # Run real-time classification
        pred_result = classifier_service.predict(req_dict)
        
        classification = pred_result.get('classification', 'BENIGN')
        attack_probability = pred_result.get('attack_probability', 0.0)
        
        # Check if synthetic (we'll pass a header 'X-Synthetic-Traffic' from our generator)
        is_synthetic = request.headers.get('X-Synthetic-Traffic') == '1'
        
        # Create log entry record
        log_entry = RequestLog(
            client_ip=client_ip,
            method=method,
            path=path,
            query=query,
            body=body,
            status_code=status_code,
            response_time_ms=response_time_ms,
            request_size=request_size,
            classification=classification,
            attack_probability=attack_probability,
            is_synthetic=is_synthetic
        )
        
        # Write to DB immediately (for simplicity in MVP, though batching is better for prod)
        try:
            db.session.add(log_entry)
            db.session.commit()
            
            # Also append to in-memory buffer for the aggregator
            with buffer_lock:
                # We store a dict representation for the aggregator
                request_buffer.append({
                    'timestamp': log_entry.timestamp,
                    'client_id': client_ip,
                    'method': method,
                    'path': path,
                    'status_code': status_code,
                    'response_time_ms': response_time_ms,
                    'request_size': request_size,
                    'classification': classification
                })
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to log request: {e}")
            
        return response
