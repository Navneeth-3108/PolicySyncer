"""
§2 Conceptual Architecture -- orchestrates the full Layer 2 pipeline:

  2.1 Normalization & Enrichment      -> normalize.py
  2.2 Candidate Pair Generation        -> blocking.py
      Conflict Reasoner                -> conflict.py
      Redundancy/Subsumption Reasoner  -> redundancy.py
      Scope-Overlap Reasoner            -> scope.py (shared, used by both above)
      Staleness Reasoner                -> staleness.py
  2.3 Fusion & Scoring                  -> confidence.py, severity.py, compliance.py
"""

from typing import Any, Dict, List

from .blocking import generate_candidate_pairs
from .compliance import lookup_compliance_impact
from .confidence import compute_confidence
from .conflict import evaluate_conflict
from .config import Config
from .nli import NLIEngine
from .normalize import DeonticProposition, build_deontic_proposition
from .redundancy import evaluate_redundancy
from .schema import Evidence, Finding, Layer2Output, StalenessRecord
from .scope import ScopeLattice, scope_breadth_rank
from .severity import assess_impact, compute_severity
from .similarity import SimilarityEngine
from .staleness import evaluate_staleness


def run_layer2(policy_records: List[Dict[str, Any]], config: Config = None) -> Layer2Output:
    """
    policy_records: list of Layer 1 PolicyRecord.to_dict()-shaped dicts, i.e.
        [{"policy_metadata": {...}, "obligations": [ObligationRecord dict, ...]}, ...]
    """
    config = config or Config()

    lattice = ScopeLattice(config)
    sim_engine = SimilarityEngine(config)
    nli_engine = NLIEngine(config)

    # ---- 2.1 Normalization & Enrichment ----
    all_props: List[DeonticProposition] = []
    policy_obligation_map: Dict[str, List[DeonticProposition]] = {}
    for policy in policy_records:
        meta = policy.get("policy_metadata", {})
        policy_name = meta.get("policy_name", "UNKNOWN_POLICY")
        props = [build_deontic_proposition(ob, policy_name) for ob in policy.get("obligations", [])]
        all_props.extend(props)
        policy_obligation_map[policy_name] = props

    findings: List[Finding] = []
    seen_pairs: Dict[frozenset, Finding] = {}

    if all_props:
        # ---- 2.2 Candidate Pair Generation & Blocking ----
        candidates = generate_candidate_pairs(all_props, sim_engine, config)

        for a, b, action_sim in candidates:
            pair_key = frozenset({a.obligation_id, b.obligation_id})

            conflict_candidate = evaluate_conflict(a, b, action_sim, lattice, nli_engine, config)
            if conflict_candidate is not None:
                finding = _build_conflict_finding(conflict_candidate, config)
                if finding is not None:
                    _register(seen_pairs, findings, pair_key, finding)
                continue  # a pair is either a conflict OR a redundancy relation, not both

            redundancy_candidate = evaluate_redundancy(a, b, action_sim, lattice, config)
            if redundancy_candidate is not None:
                finding = _build_redundancy_finding(redundancy_candidate, config)
                if finding is not None:
                    _register(seen_pairs, findings, pair_key, finding)

    # ---- Staleness (§7) -- independent of pairwise findings ----
    staleness_records: List[StalenessRecord] = []
    for policy in policy_records:
        meta = policy.get("policy_metadata", {})
        policy_name = meta.get("policy_name", "UNKNOWN_POLICY")
        obligations = policy_obligation_map.get(policy_name, [])
        result = evaluate_staleness(policy_name, meta, obligations, config, nli_engine)
        if result is not None:
            staleness_records.append(StalenessRecord(**result))

    return Layer2Output(findings=findings, staleness=staleness_records)


def _register(seen: Dict[frozenset, Finding], findings: List[Finding], key: frozenset, finding: Finding) -> None:
    existing = seen.get(key)
    if existing is None or finding.confidence > existing.confidence:
        if existing is not None:
            findings.remove(existing)
        seen[key] = finding
        findings.append(finding)


def _build_conflict_finding(candidate, config) -> "Finding | None":
    a, b = candidate.a, candidate.b
    conf = compute_confidence(
        layer1_confidence_a=a.layer1_confidence,
        layer1_confidence_b=b.layer1_confidence,
        modality_certainty=candidate.modality_certainty,
        scope_relation=candidate.scope_result.combined,
        nli_score=candidate.nli_score,
        embedding_similarity=candidate.embedding_similarity,
        config=config,
    )

    compliance = lookup_compliance_impact(a, b, config)
    breadth = min(scope_breadth_rank(a.scope, None), scope_breadth_rank(b.scope, None))
    impact = assess_impact(
        conflict_subtype=candidate.subtype,
        max_modal_strength=max(a.modal_strength, b.modal_strength),
        scope_breadth_rank=breadth,
        compliance_impact_nonempty=bool(compliance),
    )
    severity = compute_severity(conf.final_confidence, impact, config)
    if severity is None:
        return None

    # §8.2.1: extraction-confidence floor caps severity regardless of
    # reasoning strength.
    if conf.source_layer1_confidence < config.extraction_confidence_floor:
        severity = "LOW"

    evidence = Evidence(
        modality_pair=[a.modality, b.modality],
        scope_relation_per_dimension=candidate.scope_result.as_dict(),
        temporal_relation=candidate.temporal_relation,
        trigger_mismatch_description=candidate.trigger_mismatch_description,
        nli_contradiction_score=round(candidate.nli_score, 3),
        embedding_similarity_score=round(candidate.embedding_similarity, 3),
        exception_match=False,
        notes=(
            candidate.notes
            + ([f"source_layer1_confidence below extraction floor "
                f"({conf.source_layer1_confidence} < {config.extraction_confidence_floor}); "
                f"severity capped at LOW"] if conf.source_layer1_confidence < config.extraction_confidence_floor else [])
        ),
    )

    return Finding(
        finding_id=f"CONFLICT::{a.obligation_id}::{b.obligation_id}",
        finding_type="CONFLICT",
        conflict_subtype=candidate.subtype,
        obligation_refs=[a.obligation_id, b.obligation_id],
        evidence=evidence,
        confidence=conf.final_confidence,
        severity=severity,
        scope_relation=candidate.scope_result.combined,
        compliance_impact=compliance,
        source_layer1_confidence=conf.source_layer1_confidence,
    )


def _build_redundancy_finding(candidate, config) -> "Finding | None":
    a, b = candidate.a, candidate.b
    modality_certainty = 0.9 if candidate.relation_detail == "EXACT" else 0.7
    conf = compute_confidence(
        layer1_confidence_a=a.layer1_confidence,
        layer1_confidence_b=b.layer1_confidence,
        modality_certainty=modality_certainty,
        scope_relation=candidate.scope_result.combined,
        nli_score=0.0,  # redundancy doesn't use contradiction score
        embedding_similarity=candidate.embedding_similarity,
        config=config,
    )

    compliance = lookup_compliance_impact(a, b, config)
    breadth = min(scope_breadth_rank(a.scope, None), scope_breadth_rank(b.scope, None))
    impact = assess_impact(
        conflict_subtype=None,
        max_modal_strength=max(a.modal_strength, b.modal_strength),
        scope_breadth_rank=breadth,
        compliance_impact_nonempty=bool(compliance),
    )
    severity = compute_severity(conf.final_confidence, impact, config)
    if severity is None:
        return None
    if conf.source_layer1_confidence < config.extraction_confidence_floor:
        severity = "LOW"

    finding_type = "SUBSUMPTION" if candidate.finding_type == "SUBSUMPTION" else "REDUNDANCY"

    evidence = Evidence(
        modality_pair=[a.modality, b.modality],
        scope_relation_per_dimension=candidate.scope_result.as_dict(),
        embedding_similarity_score=round(candidate.embedding_similarity, 3),
        notes=[f"relation_detail={candidate.relation_detail}"],
    )

    return Finding(
        finding_id=f"{finding_type}::{a.obligation_id}::{b.obligation_id}",
        finding_type=finding_type,
        conflict_subtype=None,
        obligation_refs=[a.obligation_id, b.obligation_id],
        evidence=evidence,
        confidence=conf.final_confidence,
        severity=severity,
        scope_relation=candidate.scope_result.combined,
        compliance_impact=compliance,
        source_layer1_confidence=conf.source_layer1_confidence,
    )
