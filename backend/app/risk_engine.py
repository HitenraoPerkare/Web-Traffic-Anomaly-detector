class RiskEngine:
    def __init__(self):
        pass
        
    def evaluate(self, window_metrics, anomaly_result):
        """
        Evaluate overall risk score (0-100) and severity level (LOW, MEDIUM, HIGH, CRITICAL).
        Based on metrics (like error rates, RF malicious hits) and Isolation Forest result.
        """
        score = 0.0
        
        # Base factors
        total_requests = window_metrics.get('total_requests', 0)
        if total_requests == 0:
            return 0.0, "LOW"
            
        error_rate = window_metrics.get('error_rate', 0.0)
        malicious_ratio = window_metrics.get('malicious_ratio', 0.0)
        unique_ips = window_metrics.get('unique_ips', 1)
        
        is_anomaly = anomaly_result.get('is_anomaly', False)
        
        # 1. Immediate RF Classifications (Highest weight)
        # If > 5% of traffic is classified as malicious, it's bad
        score += min(malicious_ratio * 100 * 2, 50) # Max 50 points from RF classifications
        
        # 2. Window Anomaly (Isolation forest)
        if is_anomaly:
            score += 30
            
        # 3. High error rates (Indicator of scanning/fuzzing)
        if error_rate > 10.0:
            score += min((error_rate - 10) * 1.5, 20) # Max 20 points
            
        # Bound score
        score = min(max(score, 0.0), 100.0)
        
        # Determine level
        if score >= 80:
            level = "CRITICAL"
        elif score >= 50:
            level = "HIGH"
        elif score >= 20:
            level = "MEDIUM"
        else:
            level = "LOW"
            
        return score, level

risk_engine = RiskEngine()
