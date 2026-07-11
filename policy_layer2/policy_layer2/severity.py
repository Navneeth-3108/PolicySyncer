"""
§9 Severity / Decision Thresholds.

Severity is derived from two orthogonal axes: confidence (how sure) and
impact (how consequential if true) -- NOT confidence alone (§9's rejection
of a single-axis design).
"""

from dataclasses import dataclass
from typing import Optional

_HIGH_IMPACT_SUBTYPES = {"DIRECT", "TEMPORAL_TRIGGER_MISMATCH"}


@dataclass
class ImpactAssessment:
    tier: str  # "high" | "mid" | "low"
    factors: dict


def assess_impact(
    conflict_subtype: Optional[str],
    max_modal_strength: int,
    scope_breadth_rank: int,
    compliance_impact_nonempty: bool,
) -> ImpactAssessment:
    factors = {
        "subtype_high_impact": conflict_subtype in _HIGH_IMPACT_SUBTYPES,
        "mandatory_strength_involved": max_modal_strength >= 3,
        "broad_scope": scope_breadth_rank <= 1,  # 0-1 restricted dimensions = broad
        "compliance_mapped": compliance_impact_nonempty,
    }
    score = sum(1 for v in factors.values() if v)
    if score >= 3:
        tier = "high"
    elif score >= 1:
        tier = "mid"
    else:
        tier = "low"
    return ImpactAssessment(tier=tier, factors=factors)


def compute_severity(confidence: float, impact: ImpactAssessment, config) -> Optional[str]:
    if confidence < config.severity_min_emission_confidence:
        return None  # not emitted at all (§9's one deliberate discard point)

    if confidence >= config.severity_high_confidence and impact.tier == "high":
        return "HIGH"
    if confidence >= config.severity_medium_confidence and impact.tier in ("mid", "high"):
        return "MEDIUM"
    if confidence >= config.severity_high_confidence and impact.tier == "high":
        return "HIGH"
    return "LOW"
