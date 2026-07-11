"""
§3 Conflict Detection Framework.

Implements the five mutually-distinguishable conflict subtypes from §3.1:
  DIRECT, STRENGTH, TEMPORAL_TRIGGER_MISMATCH, PARTIAL_OVERLAP,
  and EXCEPTION_MEDIATED_NON_CONFLICT (which suppresses the finding
  entirely rather than emitting a low-severity one, §6).

Scope acts as a *gate*, not just a feature (§3.5): a DISJOINT scope relation
reclassifies what would otherwise look like a direct conflict into "no
finding" (fully disjoint) before Stage B is even consulted for that pair.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

from .normalize import DeonticProposition
from .nli import NLIEngine
from .scope import ScopeLattice, compare_scopes
from .temporal import classify_temporal_relation
from .similarity import SimilarityEngine

_OPPOSING_MODAL_PAIRS = {
    frozenset({"OBLIGATION", "PROHIBITION"}),
    frozenset({"PERMISSION", "PROHIBITION"}),
}


@dataclass
class ConflictCandidate:
    a: DeonticProposition
    b: DeonticProposition
    subtype: str  # DIRECT | STRENGTH | TEMPORAL_TRIGGER_MISMATCH | PARTIAL_OVERLAP
    scope_result: object
    modality_certainty: float
    nli_score: float
    embedding_similarity: float
    temporal_relation: Optional[str]
    trigger_mismatch_description: Optional[str]
    exception_mediated: bool
    notes: List[str]


def evaluate_conflict(
    a: DeonticProposition,
    b: DeonticProposition,
    action_similarity: float,
    lattice: ScopeLattice,
    nli_engine: NLIEngine,
) -> Optional[ConflictCandidate]:
    """
    Returns a ConflictCandidate if this pair constitutes some form of
    conflict, or None if scope gating / exception-mediation rules it out.
    """
    scope_result = compare_scopes(lattice, a.scope, b.scope)
    notes: List[str] = []

    # §3.5: scope is a gate. Fully disjoint populations => no conflict finding
    # at all, regardless of modality opposition.
    if scope_result.combined == "DISJOINT":
        return None

    # §3.1 row 5 / exception-mediated non-conflict: one obligation's
    # exception.scope_override matches (subsumes) the other's scope.
    exception_mediated = _is_exception_mediated(a, b, lattice)
    if exception_mediated:
        return None  # logged at debug/audit level upstream, not surfaced (§6)

    modal_pair = frozenset({a.modality, b.modality})
    is_direct_opposition = modal_pair in _OPPOSING_MODAL_PAIRS
    same_polarity_diff_strength = (
        a.modality == b.modality and a.modality in ("OBLIGATION", "RECOMMENDATION")
        and a.modal_strength != b.modal_strength
    )

    # §3.4: two *recurring* constraints on the same action are not inherently
    # conflicting by Allen relation -- the conflict, if any, is in the
    # *values* (90-day vs 365-day rotation), which is a STRENGTH/precision
    # conflict even when modal_strength itself is equal (e.g. both "must").
    recurring_value_mismatch = (
        a.temporal is not None and b.temporal is not None
        and a.temporal.type == "recurring" and b.temporal.type == "recurring"
        and a.temporal.value_days != b.temporal.value_days
    )
    if not is_direct_opposition and not same_polarity_diff_strength and recurring_value_mismatch:
        same_polarity_diff_strength = True  # route into STRENGTH classification below

    if not is_direct_opposition and not same_polarity_diff_strength:
        # still check temporal-only conflicts (§3.1 row 3) even when modality
        # doesn't oppose -- e.g. both are OBLIGATIONs on the same action with
        # incompatible temporal requirements (7yr retention vs delete-on-request).
        temporal_rel = classify_temporal_relation(a.temporal, b.temporal)
        if temporal_rel.kind == "trigger_mismatch":
            return ConflictCandidate(
                a=a, b=b, subtype="TEMPORAL_TRIGGER_MISMATCH", scope_result=scope_result,
                modality_certainty=0.5, nli_score=0.0, embedding_similarity=action_similarity,
                temporal_relation=temporal_rel.kind, trigger_mismatch_description=temporal_rel.description,
                exception_mediated=False, notes=["modality did not oppose; flagged on temporal grounds alone"],
            )
        return None

    nli_score = nli_engine.contradiction_score(a.raw_text, b.raw_text, a.modality, b.modality)

    subtype, modality_certainty = _classify_subtype(a, b, scope_result, is_direct_opposition, same_polarity_diff_strength)

    temporal_rel = classify_temporal_relation(a.temporal, b.temporal)
    trigger_desc = None
    if temporal_rel.kind == "trigger_mismatch" and subtype == "DIRECT":
        # a direct modal conflict that is *also* a temporal trigger mismatch:
        # temporal is the more specific/informative subtype per §3.1.
        subtype = "TEMPORAL_TRIGGER_MISMATCH"
        trigger_desc = temporal_rel.description

    return ConflictCandidate(
        a=a, b=b, subtype=subtype, scope_result=scope_result,
        modality_certainty=modality_certainty, nli_score=nli_score,
        embedding_similarity=action_similarity, temporal_relation=temporal_rel.kind,
        trigger_mismatch_description=trigger_desc, exception_mediated=False, notes=notes,
    )


def _classify_subtype(
    a: DeonticProposition, b: DeonticProposition, scope_result, is_direct_opposition: bool, same_polarity_diff_strength: bool
) -> Tuple[str, float]:
    if scope_result.combined in ("SUPERSET", "SUBSET"):
        return "PARTIAL_OVERLAP", 0.75
    if is_direct_opposition:
        return "DIRECT", 0.90
    if same_polarity_diff_strength:
        return "STRENGTH", 0.60
    return "DIRECT", 0.50


def _is_exception_mediated(a: DeonticProposition, b: DeonticProposition, lattice: ScopeLattice) -> bool:
    for opposer, other in ((a, b), (b, a)):
        override = opposer.exception_scope_override
        if override is None:
            continue
        rel = compare_scopes(lattice, override, other.scope)
        if rel.combined in ("EQUAL", "SUPERSET"):
            return True
    return False
