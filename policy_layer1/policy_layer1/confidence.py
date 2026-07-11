"""
§7 Confidence Scoring — deterministic, explainable, rule-based.
Start at 1.0, apply penalties, floor at 0.3, cap at 1.0.
"""

from typing import List

from .config import Config

PENALTIES = {
    "implicit_actor": -0.20,
    "split_negation_detected": -0.15,
    "shared_subject_inferred": -0.10,
    "nonstandard_section_format": -0.05,
    "category_unresolved": -0.15,
    "temporal_unit_ambiguous": -0.10,
}

# metadata_incomplete affects metadata confidence only, not obligation
# confidence — intentionally excluded from PENALTIES (see §7 table note).


def score_confidence(flags: List[str], config: Config = None) -> float:
    config = config or Config()
    score = 1.0
    for flag in flags:
        score += PENALTIES.get(flag, 0.0)
    score = max(config.confidence_floor, min(config.confidence_cap, score))
    return score


def tier_for(score: float, config: Config = None) -> str:
    config = config or Config()
    if score >= config.high_threshold:
        return "HIGH"
    if score >= config.medium_threshold:
        return "MEDIUM"
    return "LOW"
