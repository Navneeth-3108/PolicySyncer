"""
§3.4 Temporal conflict reasoning.

Layer 1 emits `temporal_constraint: {type, value, unit, value_days}` with
type in {recurring, duration, deadline, absolute_date} (per the Layer 1
README's field set). Layer 2 lifts these into a temporal relation per the
design doc's three cases:

  1. Two `recurring` constraints on the same action -> not an Allen-interval
     question at all; the conflict (if any) is in the *values* and is
     reclassified as a STRENGTH conflict by conflict.py, not handled here.
  2. A `duration`/retention constraint vs. a `deadline`/event-triggered
     constraint (e.g. "retain 7 years" vs "delete on request") -> not
     Allen-comparable (one is a fixed duration from creation, the other an
     event-triggered deadline with no fixed duration). Modeled here as
     TEMPORAL_TRIGGER_MISMATCH, per §3.4's explicit instruction NOT to force
     this into an Allen relation.
  3. Two fixed intervals (`absolute_date` with start/end, or two anchored
     deadlines) -> classified with Allen's 13-relation algebra (Allen, 1983).

This module deliberately does NOT decide precedence (§11.2 -- precedence
resolution is an explicit research gap / Layer 3+human concern).
"""

from dataclasses import dataclass
from typing import Optional, Tuple

ALLEN_RELATIONS = (
    "before", "after", "meets", "met_by", "overlaps", "overlapped_by",
    "starts", "started_by", "during", "contains", "finishes", "finished_by",
    "equals",
)


@dataclass
class TemporalConstraint:
    type: Optional[str] = None          # recurring | duration | deadline | absolute_date
    value: Optional[float] = None
    unit: Optional[str] = None
    value_days: Optional[float] = None
    trigger: Optional[str] = None       # e.g. "upon request", "upon termination"
    start_day: Optional[float] = None   # for absolute_date, days-from-epoch-ish anchor
    end_day: Optional[float] = None

    @classmethod
    def from_layer1(cls, d: Optional[dict]) -> Optional["TemporalConstraint"]:
        if not d:
            return None
        return cls(
            type=d.get("type"),
            value=d.get("value"),
            unit=d.get("unit"),
            value_days=d.get("value_days"),
            trigger=d.get("trigger") or d.get("event") or None,
            start_day=d.get("start_day"),
            end_day=d.get("end_day"),
        )


@dataclass
class TemporalRelationResult:
    kind: str  # "none" | "recurring_value_only" | "trigger_mismatch" | "allen"
    allen_relation: Optional[str] = None
    is_jointly_satisfiable: Optional[bool] = None
    description: str = ""


def classify_temporal_relation(
    ta: Optional[TemporalConstraint], tb: Optional[TemporalConstraint]
) -> TemporalRelationResult:
    if ta is None or tb is None:
        return TemporalRelationResult(kind="none", description="one or both obligations have no temporal constraint")

    types = {ta.type, tb.type}

    if ta.type == "recurring" and tb.type == "recurring":
        return TemporalRelationResult(
            kind="recurring_value_only",
            description=(
                "both constraints are recurring; any conflict is a value/strength "
                "disagreement (e.g. 90-day vs 365-day rotation), not a temporal-"
                "relation conflict -- handled as STRENGTH by the conflict reasoner"
            ),
        )

    duration_like = {"duration"}
    deadline_like = {"deadline"}
    if (ta.type in duration_like and tb.type in deadline_like) or (
        tb.type in duration_like and ta.type in deadline_like
    ):
        return TemporalRelationResult(
            kind="trigger_mismatch",
            is_jointly_satisfiable=False,
            description=(
                "a fixed-duration constraint and an event-triggered deadline "
                "constraint are not Allen-comparable; flagged as a triggering-"
                "condition mismatch per design doc §3.4, precedence left unresolved"
            ),
        )

    if ta.type == "absolute_date" and tb.type == "absolute_date":
        relation = _allen_relation(ta, tb)
        return TemporalRelationResult(
            kind="allen",
            allen_relation=relation,
            is_jointly_satisfiable=relation not in ("before", "after"),
            description=f"Allen interval relation: {relation}",
        )

    # Mixed/underspecified cases not covered above: conservatively report
    # "none" rather than fabricate a relation from incomplete data.
    return TemporalRelationResult(
        kind="none",
        description=f"temporal types {types} not comparable under the current rule set",
    )


def _allen_relation(a: TemporalConstraint, b: TemporalConstraint) -> str:
    """
    Classic 13-relation Allen algebra over two closed intervals [start, end].
    Falls back to 'equals' only on exact match; missing endpoints degrade to
    'before'/'after' using value_days as a point estimate when start/end are
    unavailable (best-effort, flagged via caller's evidence notes upstream).
    """
    a_start, a_end = _bounds(a)
    b_start, b_end = _bounds(b)
    if a_start is None or b_start is None:
        return "unknown"

    if a_end < b_start:
        return "before"
    if b_end < a_start:
        return "after"
    if a_end == b_start:
        return "meets"
    if b_end == a_start:
        return "met_by"
    if a_start == b_start and a_end == b_end:
        return "equals"
    if a_start == b_start and a_end < b_end:
        return "starts"
    if a_start == b_start and a_end > b_end:
        return "started_by"
    if a_end == b_end and a_start > b_start:
        return "finishes"
    if a_end == b_end and a_start < b_start:
        return "finished_by"
    if b_start < a_start < b_end < a_end:
        return "overlaps"
    if a_start < b_start < a_end < b_end:
        return "overlapped_by"
    if b_start < a_start and a_end < b_end:
        return "during"
    if a_start < b_start and b_end < a_end:
        return "contains"
    return "unknown"


def _bounds(t: TemporalConstraint) -> Tuple[Optional[float], Optional[float]]:
    if t.start_day is not None and t.end_day is not None:
        return t.start_day, t.end_day
    if t.value_days is not None:
        # single point-like value (e.g. a deadline N days out): treat as a
        # zero-width interval anchored at that point.
        return t.value_days, t.value_days
    return None, None
