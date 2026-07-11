"""
§4 Redundancy & Subsumption Reasoning.

Distinguishes:
  - exact/near-paraphrase redundancy (high embedding similarity, same
    scope/modality/temporal)
  - subsumption (one scope/strength strictly contains the other)
  - complementary reinforcement -- NOT auto-resolved (§4.1); flagged as
    PARTIAL_REDUNDANCY with evidence, judgment left to a human reviewer
    via Layer 3, per the design doc's explicit refusal to guess intent.
"""

from dataclasses import dataclass
from typing import Optional

from .normalize import DeonticProposition
from .scope import ScopeLattice, compare_scopes


@dataclass
class RedundancyCandidate:
    a: DeonticProposition
    b: DeonticProposition
    finding_type: str  # REDUNDANCY | SUBSUMPTION
    relation_detail: str  # EXACT | SUBSUMES_A_BY_B | SUBSUMES_B_BY_A | PARTIAL_REDUNDANCY
    embedding_similarity: float
    scope_result: object


def evaluate_redundancy(
    a: DeonticProposition,
    b: DeonticProposition,
    action_similarity: float,
    lattice: ScopeLattice,
    config,
) -> Optional[RedundancyCandidate]:
    if a.modality != b.modality:
        return None  # redundancy/subsumption requires same deontic direction

    scope_result = compare_scopes(lattice, a.scope, b.scope)
    if scope_result.combined == "DISJOINT":
        return None

    same_temporal = _temporal_equivalent(a, b)

    if (
        action_similarity >= config.action_similarity_high_threshold
        and scope_result.combined == "EQUAL"
        and same_temporal
    ):
        return RedundancyCandidate(
            a=a, b=b, finding_type="REDUNDANCY", relation_detail="EXACT",
            embedding_similarity=action_similarity, scope_result=scope_result,
        )

    if scope_result.combined in ("SUPERSET", "SUBSET") and action_similarity >= config.blocking_similarity_threshold:
        stronger, weaker, detail = (
            (a, b, "SUBSUMES_A_BY_B") if scope_result.combined == "SUBSET" else (b, a, "SUBSUMES_B_BY_A")
        )
        if stronger.modal_strength >= weaker.modal_strength:
            return RedundancyCandidate(
                a=a, b=b, finding_type="SUBSUMPTION", relation_detail=detail,
                embedding_similarity=action_similarity, scope_result=scope_result,
            )

    # Complementary-reinforcement zone: same category, similar action, scope
    # overlaps but doesn't cleanly nest, or strengths disagree in a way that
    # doesn't fit clean subsumption. Flag as PARTIAL_REDUNDANCY, don't guess.
    if action_similarity >= config.action_similarity_high_threshold and scope_result.combined != "DISJOINT":
        return RedundancyCandidate(
            a=a, b=b, finding_type="REDUNDANCY", relation_detail="PARTIAL_REDUNDANCY",
            embedding_similarity=action_similarity, scope_result=scope_result,
        )

    return None


def _temporal_equivalent(a: DeonticProposition, b: DeonticProposition) -> bool:
    ta, tb = a.temporal, b.temporal
    if ta is None and tb is None:
        return True
    if ta is None or tb is None:
        return False
    return ta.type == tb.type and ta.value_days == tb.value_days
