"""
§2.1 Normalization & Enrichment, §3.2 deontic proposition construction.

Lifts a raw Layer 1 ObligationRecord dict into:
    <modality, action_canonical, scope_canonical, temporal, exception>

Layer 2 does NOT re-derive modality -- it consumes Layer 1's
`modal_normalized` + `polarity` and collapses to the four-way deontic type
{OBLIGATION, PROHIBITION, PERMISSION, RECOMMENDATION}.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .scope import Scope
from .temporal import TemporalConstraint

# INTEGRATION FIX (found while wiring Layer 3 end-to-end): Layer 1's
# `modal_normalized` field (policy_layer1/modals.py ModalMatch.normalized)
# is ALREADY the four-way deontic type -- OBLIGATION | PROHIBITION |
# RECOMMENDATION | PERMISSION -- not the raw modal word ("must"/"should"/
# "may") this table originally assumed. With the old lowercase-raw-word
# table, every real Layer 1 record missed every key (e.g. "obligation" never
# matches ("must", "positive")) and silently fell back to the RECOMMENDATION
# default below -- collapsing every OBLIGATION/PROHIBITION pair to the same
# modality and making direct-conflict detection (which keys off opposing
# modality) unreachable in practice. Layer 1 already resolves split-negation
# (§5.2) into `modal_normalized` directly (e.g. "must ... not" -> PROHIBITION),
# so Layer 2 should pass it straight through rather than re-deriving it from
# polarity; `polarity` is consulted only to sanity-check/normalize case, not
# to re-classify.
_VALID_MODALITIES = {"OBLIGATION", "PROHIBITION", "RECOMMENDATION", "PERMISSION"}

# Retained for legacy/raw-modal-word inputs (e.g. hand-built test fixtures
# that pass "must"/"should"/"may" directly) so this function stays backward
# compatible with either vocabulary.
_MODALITY_TABLE = {
    ("must", "positive"): "OBLIGATION",
    ("must", "negative"): "PROHIBITION",
    ("shall", "positive"): "OBLIGATION",
    ("shall", "negative"): "PROHIBITION",
    ("should", "positive"): "RECOMMENDATION",
    ("should", "negative"): "PROHIBITION",
    ("may", "positive"): "PERMISSION",
    ("may", "negative"): "PROHIBITION",  # "may not" collapses to prohibition-flavored
}


@dataclass
class DeonticProposition:
    obligation_id: str
    policy_name: str
    modality: str                      # OBLIGATION | PROHIBITION | PERMISSION | RECOMMENDATION
    modal_strength: int                # Layer 1's 1-3 strength tier, passed through
    action_canonical: str
    category_primary: Optional[str]
    category_secondary: List[str]
    scope: Scope
    temporal: Optional[TemporalConstraint]
    exception_scope_override: Optional[Scope]
    layer1_confidence: float
    raw_text: str
    metadata_incomplete: bool = False

    @property
    def action_text_for_embedding(self) -> str:
        # EMERGENCY FIX: action_canonical is unreliable for passive/fronted-
        # subject sentences (Layer 1's extractor drops the real topic, e.g.
        # "Password rotation shall not be required..." -> action="be",
        # object="required", losing "password rotation" entirely). raw_text
        # always retains the full sentence content, so blocking/NLI have a
        # real signal to work with even when action/object extraction fails.
        return self.raw_text or self.action_canonical


def build_deontic_proposition(obligation: Dict[str, Any], policy_name: str) -> DeonticProposition:
    modal_raw_field = (obligation.get("modal_normalized") or "").strip()
    polarity = (obligation.get("polarity") or "positive").strip().lower()

    if modal_raw_field.upper() in _VALID_MODALITIES:
        # Layer 1's real contract: already the four-way deontic type.
        modality = modal_raw_field.upper()
    else:
        # Backward-compat path for raw modal words ("must"/"should"/"may").
        modality = _MODALITY_TABLE.get((modal_raw_field.lower(), polarity), "RECOMMENDATION")

    action = obligation.get("action") or ""
    obj = obligation.get("object") or ""
    qualifiers = obligation.get("qualifiers") or []
    if isinstance(qualifiers, str):
        qualifiers = [qualifiers]
    action_canonical = " ".join(x for x in [action, obj, " ".join(qualifiers)] if x).strip()

    scope = Scope.from_layer1(obligation.get("scope"))

    exception = obligation.get("exception") or {}
    exc_override = exception.get("scope_override")
    exception_scope = Scope.from_layer1(exc_override) if exc_override else None

    return DeonticProposition(
        obligation_id=obligation.get("obligation_id", ""),
        policy_name=policy_name,
        modality=modality,
        modal_strength=int(obligation.get("modal_strength", 2) or 2),
        action_canonical=action_canonical or (obligation.get("raw_text") or ""),
        category_primary=obligation.get("category_primary"),
        category_secondary=obligation.get("category_secondary") or [],
        scope=scope,
        temporal=TemporalConstraint.from_layer1(obligation.get("temporal_constraint")),
        exception_scope_override=exception_scope,
        layer1_confidence=float(obligation.get("confidence", 0.5) or 0.5),
        raw_text=obligation.get("raw_text", ""),
        metadata_incomplete=bool(obligation.get("metadata_incomplete", False)),
    )
