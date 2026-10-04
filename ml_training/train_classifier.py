"""
Train Supervised HTTP Attack Classifier (Random Forest).

Trains on the extracted CSIC 2010 + Augmented feature matrix, evaluates test metrics
(Accuracy, Precision, Recall, F1, Confusion Matrix, Feature Importances),
and exports the serialized model pipeline to models/classifier_pipeline.pkl.
"""

import os
import sys
import joblib
import pandas as pd
import numpy as np

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report
)

# Ensure parent directory is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.ml.feature_extraction import FEATURE_NAMES


def train_and_evaluate(features_csv: str, output_model_path: str):
    print("=" * 60)
    print("  SUPERVISED HTTP ATTACK CLASSIFIER TRAINING (RANDOM FOREST)")
    print("=" * 60)

    print(f"\n1. Loading feature matrix from: {features_csv}")
    df = pd.read_csv(features_csv)
    print(f"   Loaded {len(df):,} records with {len(FEATURE_NAMES)} features.")

    X = df[FEATURE_NAMES]
    y = df['label']

    print(f"   Class balance: Benign (0) = {(y == 0).sum():,} | Attack (1) = {(y == 1).sum():,}")

    # Stratified 80/20 train/test split
    print("\n2. Splitting into Train (80%) and Test (20%) sets...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    print(f"   Training samples: {len(X_train):,}")
    print(f"   Testing samples:  {len(X_test):,}")

    # Initialize Random Forest with balanced class weights
    print("\n3. Training RandomForestClassifier (n_estimators=100, max_depth=16)...")
    clf = RandomForestClassifier(
        n_estimators=100,
        max_depth=16,
        random_state=42,
        class_weight='balanced',
        n_jobs=-1
    )
    clf.fit(X_train, y_train)
    print("   Model training complete.")

    # Predictions & Probabilities
    print("\n4. Evaluating on Test Set...")
    y_pred = clf.predict(X_test)
    y_proba = clf.predict_proba(X_test)[:, 1]

    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred)
    rec = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)
    cm = confusion_matrix(y_test, y_pred)

    print("\n" + "-" * 50)
    print("                EVALUATION METRICS                ")
    print("-" * 50)
    print(f"  Accuracy:  {acc * 100:.2f}%")
    print(f"  Precision: {prec * 100:.2f}% (Attack class)")
    print(f"  Recall:    {rec * 100:.2f}% (Attack class)")
    print(f"  F1-Score:  {f1 * 100:.2f}%")
    print("\nConfusion Matrix:")
    print(f"               Predicted Benign (0)  Predicted Attack (1)")
    print(f"Actual Benign (0):   {cm[0][0]:6d} (TN)            {cm[0][1]:6d} (FP)")
    print(f"Actual Attack (1):   {cm[1][0]:6d} (FN)            {cm[1][1]:6d} (TP)")

    print("\nDetailed Classification Report:")
    print(classification_report(y_test, y_pred, target_names=['Benign (0)', 'Attack (1)'], digits=4))

    # Feature Importances
    print("-" * 50)
    print("               TOP FEATURE IMPORTANCES            ")
    print("-" * 50)
    importances = clf.feature_importances_
    indices = np.argsort(importances)[::-1]
    for rank in range(min(12, len(FEATURE_NAMES))):
        idx = indices[rank]
        print(f"  {rank + 1:2d}. {FEATURE_NAMES[idx]:<22} : {importances[idx]:.4f}")

    # Packaging Model and Metadata
    model_payload = {
        'model': clf,
        'feature_names': FEATURE_NAMES,
        'metrics': {
            'accuracy': float(acc),
            'precision': float(prec),
            'recall': float(rec),
            'f1_score': float(f1),
            'confusion_matrix': cm.tolist()
        }
    }

    os.makedirs(os.path.dirname(output_model_path), exist_ok=True)
    print(f"\n5. Saving model artifact to: {output_model_path}")
    joblib.dump(model_payload, output_model_path)
    print("   Artifact saved successfully!")
    print("=" * 60)


def main():
    base_dir = os.path.dirname(__file__)
    features_csv = os.path.join(base_dir, 'data', 'csic_features.csv')
    output_model = os.path.abspath(os.path.join(base_dir, '..', 'models', 'classifier_pipeline.pkl'))

    if not os.path.exists(features_csv):
        print(f"Error: {features_csv} not found. Run data_wrangling.py first.")
        sys.exit(1)

    train_and_evaluate(features_csv, output_model)


if __name__ == '__main__':
    main()
