"""
Inference Service for Unsupervised Isolation Forest Anomaly Detector.

Loads models/isoforest_pipeline.pkl and provides window-level behavioral anomaly scores.
"""

import os
import joblib
import pandas as pd
from typing import Dict, Any
from app.ml.window_features import WINDOW_FEATURE_NAMES


class AnomalyService:
    def __init__(self, model_path: str = None):
        if model_path is None:
            base_dir = os.path.dirname(__file__)
            model_path = os.path.abspath(os.path.join(base_dir, '..', '..', 'models', 'isoforest_pipeline.pkl'))
            
        self.model_path = model_path
        self.pipeline = None
        self.load_model()

    def load_model(self):
        if not os.path.exists(self.model_path):
            print(f"[AnomalyService] Warning: Model artifact not found at {self.model_path}")
            return
            
        data = joblib.load(self.model_path)
        if isinstance(data, dict):
            self.pipeline = data.get('pipeline')
        else:
            self.pipeline = data
            
        print(f"[AnomalyService] Successfully loaded Isolation Forest from {self.model_path}")

    def predict(self, window_metrics: Dict[str, float]) -> Dict[str, Any]:
        """
        Evaluates a 10-second traffic window metrics dictionary.
        
        Returns:
            {
                'status': 'NORMAL' | 'ANOMALY',
                'is_anomaly': bool,
                'anomaly_score': float (calibrated 0.0 to 1.0)
            }
        """
        if self.pipeline is None:
            return {
                'status': 'NORMAL',
                'is_anomaly': False,
                'anomaly_score': 0.0
            }

        df_feats = pd.DataFrame([window_metrics], columns=WINDOW_FEATURE_NAMES)
        pred = self.pipeline.predict(df_feats)[0]
        
        # Calculate raw decision score
        model = self.pipeline.named_steps['model']
        scaler = self.pipeline.named_steps['scaler']
        scaled = scaler.transform(df_feats)
        raw_score = -float(model.score_samples(scaled)[0])
        
        is_anomaly = (pred == -1)
        
        return {
            'status': 'ANOMALY' if is_anomaly else 'NORMAL',
            'is_anomaly': is_anomaly,
            'anomaly_score': round(raw_score, 4)
        }


# Global singleton instance for efficient reuse across background aggregator
anomaly_service = AnomalyService()
