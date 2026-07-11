"""
Layer 2: Semantic Conflict, Redundancy, Scope & Staleness Reasoning.

Consumes the Layer 1 -> Layer 2 contract (one JSON array of ObligationRecord
per policy, plus policy_metadata) and produces a Finding[] + Staleness[]
array per the Layer 2 design document (see /README.md in this package).

Public API:
    run_layer2(policy_records, config=None) -> Layer2Output
"""

from .pipeline import run_layer2
from .config import Config
from .schema import Finding, StalenessRecord, Layer2Output

__all__ = ["run_layer2", "Config", "Finding", "StalenessRecord", "Layer2Output"]
