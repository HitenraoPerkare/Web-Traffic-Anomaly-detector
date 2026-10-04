"""
Inference Service for Supervised Request-Level HTTP Classifier.

Loads the serialized Random Forest pipeline from models/classifier_pipeline.pkl
and provides real-time prediction for incoming HTTP requests.
"""

import os
import joblib
import pandas as pd
from typing import Dict, Any, Tuple
from app.ml.feature_extraction import extract_features_from_dict, FEATURE_NAMES


class ClassifierService:
    def __init__(self, model_path: str = None):
        if model_path is None:
            base_dir = os.path.dirname(__file__)
            model_path = os.path.abspath(os.path.join(base_dir, '..', '..', 'models', 'classifier_pipeline.pkl'))
        
        self.model_path = model_path
        self.model = None
        self.metrics = {}
        self.load_model()

    def load_model(self):
        if not os.path.exists(self.model_path):
            print(f"[ClassifierService] Warning: Model artifact not found at {self.model_path}")
            return
        
        data = joblib.load(self.model_path)
        if isinstance(data, dict):
            self.model = data.get('model')
            self.metrics = data.get('metrics', {})
        else:
            self.model = data
            
        print(f"[ClassifierService] Successfully loaded classifier from {self.model_path}")

    def predict(self, req_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classifies an incoming HTTP request dictionary.
        
        Returns:
            {
                'classification': 'BENIGN' | 'ATTACK',
                'attack_probability': float (0.0 - 1.0),
                'features': Dict[str, float]
            }
        """
        features = extract_features_from_dict(req_dict)
        
        if self.model is None:
            return {
                'classification': 'BENIGN',
                'attack_probability': 0.0,
                'features': features
            }
        
        df_feats = pd.DataFrame([features], columns=FEATURE_NAMES)
        pred_label = self.model.predict(df_feats)[0]
        
        proba = 0.0
        if hasattr(self.model, 'predict_proba'):
            probas = self.model.predict_proba(df_feats)[0]
            # Class 1 is attack
            proba = float(probas[1]) if len(probas) > 1 else float(pred_label)
            
        # Domain-guided calibration:
        # Check if the request contains any actual attack indicators, payload delimiters, or suspicious syntax
        has_attack_indicators = (
            features.get('sqli_matches', 0) > 0 or
            features.get('xss_matches', 0) > 0 or
            features.get('traversal_matches', 0) > 0 or
            features.get('system_matches', 0) > 0 or
            features.get('encoded_attack_cnt', 0) > 0 or
            features.get('quote_single_cnt', 0) > 0 or
            features.get('dash_cnt', 0) > 0 or
            features.get('angle_bracket_cnt', 0) > 0 or
            features.get('semicolon_cnt', 0) > 0 or
            features.get('special_char_ratio', 0) >= 0.08
        )

        if not has_attack_indicators:
            # Clean request with zero attack signatures or syntax anomalies
            final_classification = 'BENIGN'
            final_prob = min(proba, 0.15)
        else:
            final_classification = 'ATTACK' if (pred_label == 1 or proba >= 0.5) else 'BENIGN'
            final_prob = proba

        return {
            'classification': final_classification,
            'attack_probability': round(final_prob, 4),
            'features': features
        }


# Global singleton instance for efficient reuse across Flask threads
classifier_service = ClassifierService()
