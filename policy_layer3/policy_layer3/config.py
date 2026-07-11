"""
Config for Layer 3. Every tunable named in the Layer 3 prompt (§6, §5.2)
lives here so it can be swapped without touching pipeline logic -- same
philosophy as Layer 2's own Config (scoring/reporting policy is a
governance decision, not a hardcoded constant).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Layer3Config:
    # ---- §6 policy_health_score ----
    # NOTE: these are a starting point, not a validated constant -- the
    # Layer 2 design doc makes the identical caveat about its own severity
    # thresholds, and it applies with equal force here. Calibrate against
    # real reviewer judgments before treating any specific score as
    # meaningful.
    severity_weight: Dict[str, float] = field(default_factory=lambda: {
        "HIGH": 30.0,
        "MEDIUM": 20.0,
        "LOW": 8.0,
    })

    # §6 open governance choice: a pairwise finding (policy_a/policy_b)
    # penalizes both sides. "full" = both policies bear the full weight
    # (this is what the §6 pseudocode literally does -- no split). "half"
    # = each side bears half the weight instead. We default to "full"
    # because that's the documented formula; "half" is offered as the
    # alternative the prompt explicitly flags as a legitimate choice.
    two_sided_penalty_mode: str = "full"  # "full" | "half"

    # ---- §5.2 scope_analysis ----
    # This implementation does NOT wire in a real population/HR/asset-
    # inventory source. Per §5.2's explicit instruction ("never let an LLM
    # call fabricate a percentage from the text alone"), scope_analysis is
    # therefore QUALITATIVE-ONLY: it describes which scopes overlap, never
    # a fabricated percentage/headcount. Set `population_source` to a
    # callable(role, system, geography) -> Optional[str] returning a real
    # estimate string (e.g. "~80% of workforce") to switch to the
    # quantitative path; leave None (the default) for qualitative-only.
    population_source: Optional[object] = None  # Callable[[str, str, str], Optional[str]]

    # ---- §5.3 recommendation wording ----
    # Named here (not hardcoded in prose.py) so an org can restate its own
    # standard remediation phrasing without touching template logic.
    conflict_recommendation_verb: str = "Harmonize"

    # ---- compliance_impact for STALE (Layer 2's StalenessRecord carries no
    # compliance_impact field -- §0 B4 scopes that lookup to pairwise
    # Findings only). Layer 3 derives it deterministically (not
    # generatively) by unioning config.compliance_clause_table lookups
    # across every category_primary present among the stale policy's own
    # obligations. Prefer sourcing the table from the actual Layer 2 Config
    # used for the run (pass layer2_config= to run_layer3); this default is
    # only a fallback for when no Layer 2 Config is supplied.
    compliance_clause_table: Dict[str, List[str]] = field(default_factory=lambda: {
        "password_management": ["ISO 27001 A.5.1", "NIST IA-5"],
        "authentication": ["NIST IA-5"],
        "access_control": ["ISO 27001 A.9.4"],
        "account_management": ["ISO 27001 A.9.4"],
        "encryption": ["ISO 27001 A.8.24", "NIST SC-13"],
        "retention": ["GDPR Art. 5(1)(e)"],
        "network_security": ["ISO 27001 A.8.20"],
        "other": [],
    })
