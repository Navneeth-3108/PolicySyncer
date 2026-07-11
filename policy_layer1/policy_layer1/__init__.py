"""
Layer 1: Rule-Based Obligation Extraction
Policy Conflict & Staleness Detector

Public API:
    run_layer1(raw_text: str, config: Config | None = None) -> list[PolicyRecord]
"""

from .pipeline import run_layer1
from .schema import PolicyRecord, ObligationRecord, PolicyMetadata
from .config import Config

__all__ = [
    "run_layer1",
    "PolicyRecord",
    "ObligationRecord",
    "PolicyMetadata",
    "Config",
]
