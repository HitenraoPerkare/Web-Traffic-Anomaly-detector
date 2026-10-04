"""
Data Wrangling and Feature Engineering for CSIC 2010 HTTP Dataset.

Loads raw CSIC HTTP request logs, cleans and parses URL / body / method attributes,
applies balanced general web application traffic augmentation,
extracts structural and security features using app.ml.feature_extraction,
and outputs a clean dataset ready for model training.
"""

import os
import sys
import urllib.parse
from typing import List, Dict, Any
import pandas as pd
import numpy as np

# Ensure parent directory is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.ml.feature_extraction import extract_features_from_dict, FEATURE_NAMES


def load_and_clean_csic(csv_path: str) -> pd.DataFrame:
    """Loads and standardizes raw CSIC HTTP records."""
    print(f"Loading raw CSIC dataset from: {csv_path}")
    raw_df = pd.read_csv(csv_path)
    print(f"Total raw records loaded: {len(raw_df):,}")

    records = []
    for _, row in raw_df.iterrows():
        method = str(row.get('Method', 'GET')).strip().upper()
        raw_url = str(row.get('URL', '')).strip()
        clean_url = raw_url.split(' HTTP')[0].strip()
        parsed = urllib.parse.urlsplit(clean_url)
        path = parsed.path if parsed.path else '/'
        query = parsed.query if parsed.query else ''

        content_val = row.get('content', '')
        body = '' if (pd.isna(content_val) or content_val is None) else str(content_val).strip()

        label = int(row.get('classification', 0))

        records.append({
            'method': method,
            'path': path,
            'query': query,
            'body': body,
            'label': label
        })

    return pd.DataFrame(records)


def get_augmented_normal_records() -> List[Dict[str, Any]]:
    """
    Generates diverse normal browsing records across common web application patterns
    (home, catalog filters, search queries, login submissions, contact forms).
    This breaks site-specific schema overfitting and teaches the classifier
    that standard web navigation is benign.
    """
    templates = [
        ('GET', '/', '', ''),
        ('GET', '/', '', ''),
        ('GET', '/home', '', ''),
        ('GET', '/index', '', ''),
        ('GET', '/about', '', ''),
        ('GET', '/products', '', ''),
        ('GET', '/products', 'category=electronics', ''),
        ('GET', '/products', 'category=books&page=1', ''),
        ('GET', '/products', 'category=apparel&sort=price_asc&limit=10', ''),
        ('GET', '/products', 'id=45&view=details', ''),
        ('GET', '/products', 'filter=in_stock&brand=sony', ''),
        ('GET', '/search', 'q=laptop', ''),
        ('GET', '/search', 'q=wireless+mouse', ''),
        ('GET', '/search', 'q=mechanical+keyboard&page=2', ''),
        ('GET', '/search', 'q=python+programming', ''),
        ('GET', '/login', '', ''),
        ('POST', '/login', '', 'username=john_doe&password=MySecurePassword123'),
        ('POST', '/login', '', 'username=admin_corp&password=SuperSecret2026!'),
        ('POST', '/login', '', 'username=test_client&password=Secr3tP@ss'),
        ('GET', '/contact', '', ''),
        ('POST', '/contact', '', 'name=Alice+Smith&email=alice@company.com&subject=Question&message=Hello+support+team'),
        ('POST', '/contact', '', 'name=Bob&email=bob@gmail.com&subject=Feedback&message=Great+product+experience'),
        ('POST', '/contact', '', 'name=Customer&email=info@store.net&message=When+will+item+be+restocked?'),
        ('GET', '/about', '', ''),
        ('GET', '/services', 'tab=consulting', ''),
        ('GET', '/faq', 'topic=billing', ''),
        ('GET', '/cart', '', ''),
        ('POST', '/cart', '', 'action=add&product_id=102&quantity=2'),
        ('POST', '/feedback', '', 'rating=5&comments=Fast+delivery+and+good+quality'),
    ]

    records = []
    # Repeat to generate ~6,000 diverse normal samples
    for _ in range(240):
        for method, path, query, body in templates:
            records.append({
                'method': method,
                'path': path,
                'query': query,
                'body': body,
                'label': 0
            })
    return records


def build_feature_dataset(cleaned_df: pd.DataFrame) -> pd.DataFrame:
    """Extracts feature rows using app.ml.feature_extraction."""
    print("Extracting feature matrix...")
    rows = []
    
    # Process CSIC records
    for idx, r in cleaned_df.iterrows():
        f = extract_features_from_dict({
            'method': r['method'],
            'path': r['path'],
            'query': r['query'],
            'body': r['body']
        })
        f['label'] = r['label']
        rows.append(f)
        if (idx + 1) % 15000 == 0:
            print(f"  Processed {idx + 1:,} / {len(cleaned_df):,} CSIC records...")

    # Process Augmented normal records
    aug_records = get_augmented_normal_records()
    print(f"Adding {len(aug_records):,} diverse normal web browsing records...")
    for r in aug_records:
        f = extract_features_from_dict({
            'method': r['method'],
            'path': r['path'],
            'query': r['query'],
            'body': r['body']
        })
        f['label'] = 0
        rows.append(f)

    result_df = pd.DataFrame(rows)
    print("\n--- Final Dataset Summary ---")
    print(f"Total Rows: {len(result_df):,}")
    print(f"Class Breakdown: Benign (0) = {(result_df['label'] == 0).sum():,} | Attack (1) = {(result_df['label'] == 1).sum():,}")
    return result_df


def main():
    base_dir = os.path.dirname(__file__)
    raw_csv = os.path.join(base_dir, 'data', 'csic_database.csv')
    output_csv = os.path.join(base_dir, 'data', 'csic_features.csv')

    cleaned_df = load_and_clean_csic(raw_csv)
    features_df = build_feature_dataset(cleaned_df)

    print(f"\nSaving feature matrix to: {output_csv}")
    features_df.to_csv(output_csv, index=False)
    print(f"Successfully generated {output_csv} ({features_df.shape[0]:,} rows x {features_df.shape[1]} columns).")


if __name__ == '__main__':
    main()
