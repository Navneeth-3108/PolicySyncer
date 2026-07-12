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

    # SUBSUMPTION asserts the two obligations are the SAME requirement stated
    # at different scopes, so it needs near-paraphrase action overlap -- not
    # merely the low "avoid-unrelated" blocking bar, which would call two
    # different same-category rules (e.g. password length vs rotation) a
    # subsumption just because one scope nests inside the other.
    if scope_result.combined in ("SUPERSET", "SUBSET") and action_similarity >= config.action_similarity_high_threshold:
        # combined == "SUBSET" means a's scope ⊂ b's scope (b is broader);
        # "SUPERSET" means a ⊃ b (a is broader). Bind narrower/broader
        # explicitly so the strength test isn't accidentally inverted.
        narrower, broader, detail = (
            (a, b, "SUBSUMES_A_BY_B") if scope_result.combined == "SUBSET" else (b, a, "SUBSUMES_B_BY_A")
        )
        # The narrow obligation is truly redundant (subsumed) only when the
        # BROADER rule already imposes an at-least-as-strong duty on it. If the
        # narrower rule is the stronger one, it is NOT redundant -- it adds a
        # stricter requirement -- so fall through to PARTIAL_REDUNDANCY.
        if broader.modal_strength >= narrower.modal_strength:
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
