"""
run_layer3() -- ties citation resolution (citations.py), prose generation
(prose.py), and health-score aggregation (health_score.py) together into
the exact §4 target JSON shape. Does not re-derive or override any Layer 2
scoring, severity, or evidence.
"""

from typing import Any, Dict, List, Optional

from .citations import CitationIndex
from .config import Layer3Config
from .health_score import compute_health_scores
from . import prose

_SEVERITY_RANK = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
_TYPE_RANK = {"CONFLICT": 0, "STALE": 1, "REDUNDANCY": 2, "PARTIAL_REDUNDANCY": 2, "SUBSUMPTION": 2}


def _stale_compliance_impact(policy_name: str, index: CitationIndex, table: Dict[str, List[str]]) -> List[str]:
    """
    Layer 2's StalenessRecord carries no compliance_impact (§0 B4 scopes
    that lookup to pairwise Findings only) -- Layer 3 derives it
    deterministically (a lookup, not a generative step) by unioning the
    same compliance_clause_table across every category_primary actually
    present among the stale policy's own obligations.
    """
    categories = index.categories_for_policy(policy_name)
    clauses = set()
    for cat in categories:
        clauses |= set(table.get(cat, []))
    return sorted(clauses)


def _build_conflict_entry(finding: Any, index: CitationIndex, config: Layer3Config) -> Dict[str, Any]:
    a_id, b_id = finding.obligation_refs[0], finding.obligation_refs[1]
    obl_a, obl_b = index.obligations.get(a_id), index.obligations.get(b_id)

    entry: Dict[str, Any] = {
        "finding_type": "CONFLICT",
        "severity": finding.severity,
        "policy_a": index.obligation_citation(a_id),
        "policy_b": index.obligation_citation(b_id),
        "description": (
            prose.describe_conflict(finding, obl_a, obl_b)
            if obl_a and obl_b
            else "Conflicting obligations detected (citation details unavailable)."
        ),
    }
    scope_text = (
        prose.scope_analysis_for_conflict(finding, obl_a, obl_b, config) if obl_a and obl_b else None
    )
    if scope_text:
        entry["scope_analysis"] = scope_text
    entry["recommendation"] = (
        prose.recommend_conflict(finding, obl_a, obl_b, config)
        if obl_a and obl_b
        else "Review both obligations and reconcile precedence."
    )
    if finding.compliance_impact:
        entry["compliance_impact"] = list(finding.compliance_impact)
    return entry


def _build_stale_entry(record: Any, index: CitationIndex, table: Dict[str, List[str]]) -> Dict[str, Any]:
    entry: Dict[str, Any] = {
        "finding_type": "STALE",
        "severity": record.severity,
        "policy": index.policy_citation_by_name(record.policy_name),
        "description": prose.describe_stale(record),
        "recommendation": prose.recommend_stale(record),
    }
    compliance = _stale_compliance_impact(record.policy_name, index, table)
    if compliance:
        entry["compliance_impact"] = compliance
    return entry


def _build_redundancy_entry(finding: Any, index: CitationIndex) -> Dict[str, Any]:
    a_id, b_id = finding.obligation_refs[0], finding.obligation_refs[1]
    obl_a, obl_b = index.obligations.get(a_id), index.obligations.get(b_id)
    is_partial = any("relation_detail=PARTIAL_REDUNDANCY" in n for n in (finding.evidence.notes or []))
    out_type = "PARTIAL_REDUNDANCY" if (finding.finding_type == "REDUNDANCY" and is_partial) else finding.finding_type

    entry: Dict[str, Any] = {
        "finding_type": out_type,
        "severity": finding.severity,
        "policy_a": index.obligation_citation(a_id),
        "policy_b": index.obligation_citation(b_id),
    }
    if not (obl_a and obl_b):
        entry["description"] = "Overlapping obligations detected (citation details unavailable)."
        entry["recommendation"] = "Cross-reference the two policies and clarify which control applies."
        if finding.compliance_impact:
            entry["compliance_impact"] = list(finding.compliance_impact)
        return entry

    if finding.finding_type == "SUBSUMPTION":
        entry["description"] = prose.describe_subsumption(finding, obl_a, obl_b)
        entry["recommendation"] = prose.recommend_subsumption()
    else:
        entry["description"] = prose.describe_redundancy(finding, obl_a, obl_b, is_partial=(out_type == "PARTIAL_REDUNDANCY"))
        entry["recommendation"] = prose.recommend_redundancy()

    if finding.compliance_impact:
        entry["compliance_impact"] = list(finding.compliance_impact)
    return entry


def run_layer3(
    layer2_output: Any,
    layer1_records: List[Any],
    config: Optional[Layer3Config] = None,
    layer2_config: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    layer2_output: policy_layer2.schema.Layer2Output (findings=[Finding,...],
        staleness=[StalenessRecord,...])
    layer1_records: list of policy_layer1.schema.PolicyRecord (or their
        .to_dict()-shaped dicts)
    config: Layer3Config -- weights/policy choices (§5, §6)
    layer2_config: optional policy_layer2.config.Config for the SAME run,
        used to source compliance_clause_table for STALE lookups (§2.2) so
        the table isn't duplicated/out of sync between layers. Falls back
        to config.compliance_clause_table if not supplied.
    """
    config = config or Layer3Config()
    index = CitationIndex.build(layer1_records)
    compliance_table = (
        getattr(layer2_config, "compliance_clause_table", None) or config.compliance_clause_table
    )

    entries: List[Dict[str, Any]] = []
    for finding in layer2_output.findings:
        if finding.finding_type == "CONFLICT":
            entries.append((finding.severity, "CONFLICT", finding.confidence, _build_conflict_entry(finding, index, config)))
        else:  # REDUNDANCY | SUBSUMPTION
            built = _build_redundancy_entry(finding, index)
            entries.append((finding.severity, built["finding_type"], finding.confidence, built))

    for record in layer2_output.staleness:
        built = _build_stale_entry(record, index, compliance_table)
        entries.append((record.severity, "STALE", record.confidence, built))

    # §4: CONFLICT first (desc severity), then STALE, then REDUNDANCY/SUBSUMPTION;
    # ties broken by descending Layer 2 confidence for stable, non-arbitrary ordering.
    entries.sort(
        key=lambda t: (_TYPE_RANK.get(t[1], 3), -_SEVERITY_RANK.get(t[0], 0), -t[2])
    )

    health = compute_health_scores(layer2_output.findings, layer2_output.staleness, index, config)

    return {
        "findings": [e[3] for e in entries],
        "policy_health_score": health,
    }
