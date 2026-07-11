"""
§6 Category Classification — rule-based keyword-to-category mapping.
Multi-label allowed; priority order (configurable, see config.py) picks
category_primary from among the matches.
"""

import re
from typing import List, Tuple

CATEGORY_KEYWORDS = {
    "password_management": [
        "password", "passwords", "rotate", "rotation", "reuse", "reused",
        "complexity", "passphrase",
    ],
    "authentication": [
        "mfa", "multi-factor", "multifactor", "authentication", "login",
        "sign-in", "credential", "credentials",
    ],
    "encryption": [
        "encrypt", "encryption", "tls", "cipher", "key management",
        "at rest", "in transit",
    ],
    "retention": [
        "retain", "retention", "delete", "deletion", "purge", "archive",
    ],
    "access_control": [
        "access", "authorize", "authorization", "permission", "role-based",
        "rbac", "least privilege",
    ],
    "account_management": [
        "api key", "service account", "service accounts", "account provisioning",
        "deprovisioning", "user accounts", "accounts",
    ],
    "network_security": [
        "vpn", "firewall", "network segmentation", "perimeter",
    ],
}

_COMPILED = {
    cat: [re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE) for kw in kws]
    for cat, kws in CATEGORY_KEYWORDS.items()
}


def classify_category(clause_text: str, priority: List[str]) -> Tuple[str, List[str], List[str]]:
    """
    Returns (category_primary, category_secondary, flags).
    """
    matched = []
    for cat, patterns in _COMPILED.items():
        if any(p.search(clause_text) for p in patterns):
            matched.append(cat)

    flags = []
    if not matched:
        return "other", [], ["category_unresolved"]

    matched_sorted = sorted(
        matched, key=lambda c: priority.index(c) if c in priority else len(priority)
    )
    primary = matched_sorted[0]
    secondary = matched_sorted[1:]
    return primary, secondary, flags
