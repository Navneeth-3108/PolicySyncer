"""
Configuration for the Layer 1 pipeline.

Resolves §12 open items:
  - category priority ordering is configurable (default = spec order, §6)
  - spaCy usage is opt-in / auto-detected, never a hard requirement
  - low-confidence records are never blocked, only flagged (§7)
"""

from dataclasses import dataclass, field
from typing import List


DEFAULT_CATEGORY_PRIORITY: List[str] = [
    "password_management",
    "authentication",
    "encryption",
    "retention",
    "access_control",
    "account_management",
    "network_security",
    "other",
]


@dataclass
class Config:
    # §6 — configurable category priority order (first match by this order
    # becomes category_primary).
    category_priority: List[str] = field(
        default_factory=lambda: list(DEFAULT_CATEGORY_PRIORITY)
    )

    # §5.5 open item — try spaCy for slot extraction if it (and a model) are
    # importable at runtime; otherwise silently use the regex extractor.
    # Setting this False forces regex-only regardless of what's installed.
    use_spacy_if_available: bool = True
    spacy_model_name: str = "en_core_web_sm"

    # §7 — confidence tier thresholds
    high_threshold: float = 0.80
    medium_threshold: float = 0.50
    confidence_floor: float = 0.30
    confidence_cap: float = 1.0
