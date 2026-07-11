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
        "deprovisioning", "user accounts", "accounts", "provisioning",
    ],
    "network_security": [
        "vpn", "firewall", "network segmentation", "perimeter", "network",
    ],
    # ---- Problem-11 dataset topic vocabulary (bare, single-word topic
    # tokens from the generated sample policies, e.g. "All users must
    # <topic> as per company standards." / "<Topic> is prohibited for all
    # users."). Each of these is its own category rather than folded into
    # an existing one, since the dataset topics don't semantically overlap
    # with password/auth/encryption/retention/access/account/network.
    "api_security": ["api"],
    "asset_management": ["asset", "endpoint"],
    "backup_recovery": ["backup"],
    "change_management": ["change"],
    "cloud_security": ["cloud"],
    "vendor_management": ["vendor", "third-party"],
    "logging_monitoring": ["logging", "monitoring"],
    "mobile_device_management": ["mobile"],
    "patch_management": ["patch"],
    "physical_security": ["physical"],
    "data_privacy": ["privacy"],
    "personnel_security": ["hr"],
}
# NOTE: "change" as a bare keyword is intentionally broad -- it will also
# match unrelated sentences like "password change" or "change window".
# Category priority (config.py DEFAULT_CATEGORY_PRIORITY) resolves the
# overlap deterministically (password_management is checked first), but a
# curated multi-word phrase list would reduce false positives further if
# this table is extended for production use beyond this sample dataset.

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
