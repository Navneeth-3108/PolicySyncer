"""
Layer 3: Recommendation & Reporting Engine.

Consumes Layer 2's Layer2Output (Finding[] + StalenessRecord[]) plus the
originating Layer 1 PolicyRecord[], and produces the human-facing report:
citation resolution, prose (description/recommendation/scope_analysis),
policy_health_score, and final JSON assembly.

Public API:
    run_layer3(layer2_output, layer1_records, config=None, layer2_config=None) -> dict
"""

from .pipeline import run_layer3
from .config import Layer3Config

__all__ = ["run_layer3", "Layer3Config"]
