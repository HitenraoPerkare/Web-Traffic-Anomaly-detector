import re
import math
import urllib.parse
from typing import Dict, Any, Union
import pandas as pd
import numpy as np

# Pre-compiled regex patterns for performance
SQL_KEYWORDS = re.compile(
    r'\b(select|union|insert|update|delete|drop|from|where|or\s+[\'"]?\d+[\'"]?\s*=\s*[\'"]?\d+|table|information_schema|waitfor\s+delay|sleep|benchmark|load_file|into\s+outfile)\b|--|\/\*|\*\/',
    re.IGNORECASE
)

XSS_KEYWORDS = re.compile(
    r'(<\s*script|javascript\s*:|<\s*img[^>]+onerror|<\s*svg[^>]+onload|alert\s*\(|prompt\s*\(|confirm\s*\(|document\.cookie|<iframe|<embed|<object)',
    re.IGNORECASE
)

TRAVERSAL_KEYWORDS = re.compile(
    r'(\.\./|\.\.\\|/etc/passwd|win\.ini|boot\.ini|windows/system32)',
    re.IGNORECASE
)

SYSTEM_KEYWORDS = re.compile(
    r'\b(cmd\.exe|/bin/sh|/bin/bash|powershell|wget|curl|chmod|chown)\b|(\|\s*\w+)|(`.+`)',
    re.IGNORECASE
)


def calculate_entropy(text: str) -> float:
    """Calculate Shannon entropy of a string."""
    if not text:
        return 0.0
    prob_dist = [text.count(c) / len(text) for c in set(text)]
    return -sum(p * math.log2(p) for p in prob_dist)


def extract_features_from_dict(req: Dict[str, Any]) -> Dict[str, float]:
    """
    Extract features from a normalized request dictionary.
    
    Expected keys:
      - method: str ('GET', 'POST', etc.)
      - path: str (e.g. '/search' or '/tienda1/index.jsp')
      - query: str (query string without leading '?', e.g. 'id=1&q=test')
      - body: str (request body content, e.g. 'user=admin&pass=123')
    """
    method = str(req.get('method', 'GET')).upper()
    path = str(req.get('path', ''))
    query = str(req.get('query', ''))
    body = str(req.get('body', ''))

    # Decoded variants
    try:
        decoded_query = urllib.parse.unquote_plus(query)
    except Exception:
        decoded_query = query
        
    try:
        decoded_body = urllib.parse.unquote_plus(body)
    except Exception:
        decoded_body = body

    full_payload = f"{path} {query} {body}"
    decoded_payload = f"{path} {decoded_query} {decoded_body}"

    path_len = len(path)
    query_len = len(query)
    body_len = len(body)
    total_len = len(full_payload)

    # Entropy
    query_entropy = calculate_entropy(decoded_query)
    payload_entropy = calculate_entropy(decoded_payload)

    # Character counts & frequencies on decoded payload
    quote_single_cnt = decoded_payload.count("'")
    quote_double_cnt = decoded_payload.count('"')
    semicolon_cnt = decoded_payload.count(';')
    dash_cnt = decoded_payload.count('-')
    angle_bracket_cnt = decoded_payload.count('<') + decoded_payload.count('>')
    parenthesis_cnt = decoded_payload.count('(') + decoded_payload.count(')')
    slash_cnt = decoded_payload.count('/') + decoded_payload.count('\\')
    percent_cnt = full_payload.count('%')
    equal_cnt = decoded_payload.count('=')
    ampersand_cnt = decoded_payload.count('&')
    dot_cnt = decoded_payload.count('.')

    digits_cnt = sum(c.isdigit() for c in decoded_payload)
    letters_cnt = sum(c.isalpha() for c in decoded_payload)
    special_cnt = total_len - digits_cnt - letters_cnt

    special_char_ratio = (special_cnt / total_len) if total_len > 0 else 0.0
    digit_ratio = (digits_cnt / total_len) if total_len > 0 else 0.0

    # Signature counts
    sqli_matches = len(SQL_KEYWORDS.findall(decoded_payload))
    xss_matches = len(XSS_KEYWORDS.findall(decoded_payload))
    traversal_matches = len(TRAVERSAL_KEYWORDS.findall(decoded_payload))
    system_matches = len(SYSTEM_KEYWORDS.findall(decoded_payload))

    # Parameter counts
    param_count = ampersand_cnt + 1 if (query_len > 0 or body_len > 0) else 0

    return {
        'path_length': float(path_len),
        'query_length': float(query_len),
        'body_length': float(body_len),
        'total_length': float(total_len),
        'payload_entropy': float(payload_entropy),
        'query_entropy': float(query_entropy),
        'quote_single_cnt': float(quote_single_cnt),
        'quote_double_cnt': float(quote_double_cnt),
        'semicolon_cnt': float(semicolon_cnt),
        'dash_cnt': float(dash_cnt),
        'angle_bracket_cnt': float(angle_bracket_cnt),
        'parenthesis_cnt': float(parenthesis_cnt),
        'slash_cnt': float(slash_cnt),
        'percent_cnt': float(percent_cnt),
        'equal_cnt': float(equal_cnt),
        'ampersand_cnt': float(ampersand_cnt),
        'dot_cnt': float(dot_cnt),
        'special_char_ratio': float(special_char_ratio),
        'digit_ratio': float(digit_ratio),
        'param_count': float(param_count),
        'sqli_matches': float(sqli_matches),
        'xss_matches': float(xss_matches),
        'traversal_matches': float(traversal_matches),
        'system_matches': float(system_matches),
        'is_get': 1.0 if method == 'GET' else 0.0,
        'is_post': 1.0 if method == 'POST' else 0.0,
        'is_other_method': 1.0 if method not in ('GET', 'POST') else 0.0
    }


FEATURE_NAMES = [
    'path_length', 'query_length', 'body_length', 'total_length',
    'payload_entropy', 'query_entropy',
    'quote_single_cnt', 'quote_double_cnt', 'semicolon_cnt', 'dash_cnt',
    'angle_bracket_cnt', 'parenthesis_cnt', 'slash_cnt', 'percent_cnt',
    'equal_cnt', 'ampersand_cnt', 'dot_cnt',
    'special_char_ratio', 'digit_ratio', 'param_count',
    'sqli_matches', 'xss_matches', 'traversal_matches', 'system_matches',
    'is_get', 'is_post', 'is_other_method'
]


def extract_features_from_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Vectorized/batched feature extraction for a Pandas dataframe of requests.
    Expects df with columns: 'method', 'path', 'query', 'body'
    """
    records = []
    for _, row in df.iterrows():
        req_dict = {
            'method': row.get('method', 'GET'),
            'path': row.get('path', ''),
            'query': row.get('query', ''),
            'body': row.get('body', '')
        }
        records.append(extract_features_from_dict(req_dict))
    
    return pd.DataFrame(records, columns=FEATURE_NAMES)
