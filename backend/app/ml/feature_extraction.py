"""
Shared Request-Level HTTP Feature Extraction Module.

Extracts security and structural features from HTTP requests (both CSIC dataset records
and live Flask incoming requests) for the Random Forest attack classifier.
"""

import re
import math
import urllib.parse
from typing import Dict, Any, List

# Compiled attack signatures
SQL_KEYWORDS = re.compile(
    r'\b(select|union|insert|update|delete|drop|from|where|or\s+[\'\"(]?\d+[\'\")]?\s*=\s*[\'\"(]?\d+|table|information_schema|benchmark|sleep|into\s+outfile|load_file|waitfor\s+delay)\b|--|\/\*|\*\/',
    re.IGNORECASE
)

XSS_KEYWORDS = re.compile(
    r'<\s*script|javascript\s*:|<\s*img[^>]+onerror|<\s*svg[^>]+onload|alert\s*\(|prompt\s*\(|confirm\s*\(|document\.cookie|<iframe|<embed|<object',
    re.IGNORECASE
)

TRAVERSAL_KEYWORDS = re.compile(
    r'\.\./|\.\.\\|/etc/passwd|win\.ini|windows/system32|boot\.ini|cmd\.exe',
    re.IGNORECASE
)

SYSTEM_KEYWORDS = re.compile(
    r'\b(cmd\.exe|/bin/sh|/bin/bash|powershell|wget|curl)\b|(\|\s*\w+)|(`.+`)',
    re.IGNORECASE
)

ENCODED_ATTACK_REGEX = re.compile(
    r'%27|%22|%3c|%3e|%3b|%28|%29|%2f|%5c|%00',
    re.IGNORECASE
)

FEATURE_NAMES = [
    'sqli_matches',
    'xss_matches',
    'traversal_matches',
    'system_matches',
    'quote_single_cnt',
    'quote_double_cnt',
    'semicolon_cnt',
    'dash_cnt',
    'angle_bracket_cnt',
    'parenthesis_cnt',
    'encoded_attack_cnt',
    'payload_entropy',
    'max_param_len',
    'total_length',
    'special_char_ratio',
    'is_get',
    'is_post'
]


def calculate_entropy(text: str) -> float:
    """Computes Shannon entropy of a string."""
    if not text:
        return 0.0
    prob_dist = [text.count(c) / len(text) for c in set(text)]
    return -sum(p * math.log2(p) for p in prob_dist)


def extract_features_from_dict(req: Dict[str, Any]) -> Dict[str, float]:
    """
    Extracts security and structural features from a normalized request dictionary.
    
    Expected keys:
      - method: str ('GET', 'POST', etc.)
      - path: str ('/products', '/search', etc.)
      - query: str ('category=books&page=1', 'q=test', etc.)
      - body: str ('username=alice&password=123', etc.)
    """
    method = str(req.get('method', 'GET')).upper()
    path = str(req.get('path', '/'))
    query = str(req.get('query', ''))
    body = str(req.get('body', ''))

    full_payload = f"{path} {query} {body}"
    try:
        decoded_payload = urllib.parse.unquote_plus(full_payload)
    except Exception:
        decoded_payload = full_payload

    # Signature hits
    sqli_hits = len(SQL_KEYWORDS.findall(decoded_payload))
    xss_hits = len(XSS_KEYWORDS.findall(decoded_payload))
    trav_hits = len(TRAVERSAL_KEYWORDS.findall(decoded_payload))
    if '~' in path or '.bak' in path or '.old' in path:
        trav_hits += 1
    sys_hits = len(SYSTEM_KEYWORDS.findall(decoded_payload))
    encoded_hits = len(ENCODED_ATTACK_REGEX.findall(full_payload))

    # Punctuation & delimiter counts
    quote_single = decoded_payload.count("'")
    quote_double = decoded_payload.count('"')
    semicolons = decoded_payload.count(';')
    dashes = full_payload.count('--')
    angle_brackets = decoded_payload.count('<') + decoded_payload.count('>')
    parentheses = decoded_payload.count('(') + decoded_payload.count(')')

    # Parameter value lengths
    params = []
    if query:
        params.extend(query.split('&'))
    if body:
        params.extend(body.split('&'))
    val_lens = [len(p.split('=', 1)[1]) if '=' in p else len(p) for p in params]
    max_val_len = max(val_lens) if val_lens else 0

    tot_len = len(full_payload)
    entropy = calculate_entropy(decoded_payload)

    # Special characters ratio (excluding standard URL, form & JSON delimiters)
    allowed_standard = (' ', '/', '.', '-', '_', '=', '&', '@', '+', ':', '{', '}', '"', ',')
    special_cnt = sum(1 for c in decoded_payload if not c.isalnum() and c not in allowed_standard)
    special_ratio = special_cnt / tot_len if tot_len > 0 else 0.0

    return {
        'sqli_matches': float(sqli_hits),
        'xss_matches': float(xss_hits),
        'traversal_matches': float(trav_hits),
        'system_matches': float(sys_hits),
        'quote_single_cnt': float(quote_single),
        'quote_double_cnt': float(quote_double),
        'semicolon_cnt': float(semicolons),
        'dash_cnt': float(dashes),
        'angle_bracket_cnt': float(angle_brackets),
        'parenthesis_cnt': float(parentheses),
        'encoded_attack_cnt': float(encoded_hits),
        'payload_entropy': float(round(entropy, 4)),
        'max_param_len': float(max_val_len),
        'total_length': float(tot_len),
        'special_char_ratio': float(round(special_ratio, 4)),
        'is_get': 1.0 if method == 'GET' else 0.0,
        'is_post': 1.0 if method == 'POST' else 0.0
    }
