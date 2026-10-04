from datetime import datetime, timedelta
from app.models_db import db, Alert
from flask import current_app

class AlertEngine:
    def __init__(self):
        # Dictionary to track last alert time per rule/type to implement cooldown
        self.last_alert_times = {}
        self.cooldown_seconds = 30 # Prevent spam

    def process_risk(self, risk_level, risk_score, window_id, window_metrics):
        """
        Check risk level and generate alert if threshold met
        """
        if risk_level not in ['HIGH', 'CRITICAL']:
            return None
            
        now = datetime.utcnow()
        alert_type = f"{risk_level}_RISK"
        
        # Check cooldown
        if alert_type in self.last_alert_times:
            if (now - self.last_alert_times[alert_type]) < timedelta(seconds=self.cooldown_seconds):
                # Cooldown active, skip alert
                return None
                
        # Generate alert
        req_sec = window_metrics.get('requests_per_second', window_metrics.get('req_per_sec', 0.0))
        description = f"High traffic risk detected (Score: {risk_score:.2f}). Metrics: Req/s: {req_sec:.2f}, Error Rate: {window_metrics.get('error_rate', 0):.2f}%"
        
        alert = Alert(
            alert_type=alert_type,
            risk_level=risk_level,
            description=description,
            timestamp=now,
            is_resolved=False
        )
        
        # Save to DB
        try:
            db.session.add(alert)
            db.session.commit()
            self.last_alert_times[alert_type] = now
            return alert
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to generate alert: {e}")
            return None

alert_engine = AlertEngine()
