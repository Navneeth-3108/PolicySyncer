"""
§5 Prose generation -- template-based (§5.4's recommended default: fully
deterministic, auditable, zero hallucination risk; no LLM call).

Every function here is grounded strictly in the Finding/StalenessRecord
fields and the cited obligations' raw_text -- never anything invented.
Where §5 permits a quantitative scope_analysis only if a real population
source is wired in, and none is here, the qualitative path is used and no
number is ever fabricated (see config.py's population_source docstring).
"""

import re
from typing import Any, Dict, List, Optional

from .citations import CitationIndex, ObligationInfo


def _modal_phrase(ob: ObligationInfo) -> str:
    """Render one obligation's requirement in plain language, grounded in
    its own modal_normalized + raw_text -- never inventing content."""
    text = (ob.raw_text or "").strip().rstrip(".")
    verb = {
        "OBLIGATION": "requires",
        "PROHIBITION": "prohibits",
        "RECOMMENDATION": "recommends",
        "PERMISSION": "permits",
    }.get(ob.modal_normalized, "states")
    return f"{ob.policy_name} {verb}: \"{text}\""


def _scope_phrase(scope: Dict[str, Optional[str]]) -> Optional[str]:
    parts = []
    if scope.get("role"):
        parts.append(scope["role"])
    if scope.get("system"):
        parts.append(f"{scope['system']}-hosted systems" if scope["system"] not in (None, "") else None)
    if scope.get("geography"):
        parts.append(scope["geography"])
    parts = [p for p in parts if p]
    if not parts:
        return None
    return " / ".join(parts)


# ---------------------------------------------------------------------------
# CONFLICT
# ---------------------------------------------------------------------------

_SUBTYPE_FRAMING = {
    "DIRECT": "one requires what the other prohibits, so both cannot be satisfied at once",
    "STRENGTH": "both take the same obligation/recommendation direction but disagree on its strength or parameters",
    "TEMPORAL_TRIGGER_MISMATCH": "one is a fixed-duration requirement while the other is an event-triggered deadline, so they resolve differently over time",
    "PARTIAL_OVERLAP": "one policy is broader than the other and they disagree within the scope where they overlap",
}


def describe_conflict(finding: Any, obl_a: ObligationInfo, obl_b: ObligationInfo) -> str:
    subtype = finding.conflict_subtype or "DIRECT"
    framing = _SUBTYPE_FRAMING.get(subtype, _SUBTYPE_FRAMING["DIRECT"])
    sentence = f"{_modal_phrase(obl_a)}, while {_modal_phrase(obl_b)} -- {framing}."
    if subtype == "TEMPORAL_TRIGGER_MISMATCH" and getattr(finding.evidence, "trigger_mismatch_description", None):
        sentence += f" {finding.evidence.trigger_mismatch_description}."
    return sentence


def recommend_conflict(finding: Any, obl_a: ObligationInfo, obl_b: ObligationInfo, config) -> str:
    verb = config.conflict_recommendation_verb
    option_a = f"update {obl_a.policy_name} to explicitly exempt or accommodate the case covered by {obl_b.policy_name} §{obl_b.section_ref or '?'}"
    option_b = f"update {obl_b.policy_name} to explicitly exempt or accommodate the case covered by {obl_a.policy_name} §{obl_a.section_ref or '?'}"
    # Per §11.2: Layer 3 does not resolve precedence -- offer both directions
    # as options, phrased neutrally.
    return f"{verb} the two policies: either {option_a}, or {option_b}."


def scope_analysis_for_conflict(finding: Any, obl_a: ObligationInfo, obl_b: ObligationInfo, config) -> Optional[str]:
    """
    §5.2: only produced for CONFLICT findings, and only when there's
    something non-trivial to say about population overlap. Quantitative
    estimates require a real population_source (config) -- absent one,
    this stays qualitative and never invents a number.
    """
    if finding.scope_relation not in ("OVERLAP", "SUPERSET", "SUBSET"):
        return None

    phrase_a = _scope_phrase(obl_a.scope)
    phrase_b = _scope_phrase(obl_b.scope)
    if not phrase_a and not phrase_b:
        return None  # both scopes are universal/unspecified -- nothing non-trivial to say

    if config.population_source is not None:
        estimate = config.population_source(obl_a.scope, obl_b.scope, finding.scope_relation)
        if estimate:
            return estimate  # caller-supplied, real estimate -- not fabricated here

    if finding.scope_relation == "OVERLAP":
        combined = " who also fall under " .join(p for p in (phrase_a, phrase_b) if p)
        return f"Conflict applies to {combined or 'the overlapping population'} -- no workforce population source is configured, so no percentage is estimated."
    # SUPERSET/SUBSET: narrower obligation's scope is the affected population
    narrower = phrase_b if finding.scope_relation == "SUPERSET" else phrase_a
    if narrower:
        return f"Conflict applies specifically to {narrower}; no workforce population source is configured, so no percentage is estimated."
    return None


# ---------------------------------------------------------------------------
# STALE
# ---------------------------------------------------------------------------

_GUIDANCE_QUOTE_RE = re.compile(r'vs current guidance: "([^"]*)"')


def describe_stale(record: Any) -> str:
    months = record.months_since_review
    age_clause = (
        f"Last reviewed on {record.last_reviewed} -- over {months / 12:.0f} years ago."
        if months is not None and record.last_reviewed
        else "This policy's review date is missing or unparseable."
    )
    signal_clauses = []
    for sig in record.staleness_signals:
        name = sig["name"]
        if name == "review_age":
            continue  # already covered by age_clause
        if name == "deprecated_tech":
            signal_clauses.append("it references technologies or algorithms considered deprecated")
        elif name == "superseded_standard":
            signal_clauses.append("it cites a standard revision that has since been superseded")
        elif name == "semantic_drift":
            m = _GUIDANCE_QUOTE_RE.search(sig.get("evidence", ""))
            if m:
                signal_clauses.append(f"it may conflict with updated guidance (\"{m.group(1)}...\")")
            else:
                signal_clauses.append("it may conflict with updated current guidance")
        elif name == "missing_metadata":
            signal_clauses.append("its metadata is incomplete, so this assessment carries reduced confidence")

    if signal_clauses:
        return age_clause + " " + "; also, ".join(s[0].upper() + s[1:] for s in signal_clauses[:1]) + (
            (" " + "; ".join(signal_clauses[1:]) + ".") if len(signal_clauses) > 1 else "."
        )
    return age_clause


def recommend_stale(record: Any) -> str:
    base = "Schedule a policy review."
    for sig in record.staleness_signals:
        if sig["name"] == "semantic_drift":
            m = _GUIDANCE_QUOTE_RE.search(sig.get("evidence", ""))
            if m:
                return base + f" Consider aligning with current guidance (\"{m.group(1)}...\")."
    if any(s["name"] == "deprecated_tech" for s in record.staleness_signals):
        return base + " Replace or re-justify any deprecated technology references identified above."
    if any(s["name"] == "superseded_standard" for s in record.staleness_signals):
        return base + " Update citations to the current standard revision."
    return base + " Confirm the policy still reflects current practice and re-date it once reviewed."


# ---------------------------------------------------------------------------
# REDUNDANCY / PARTIAL_REDUNDANCY / SUBSUMPTION
# ---------------------------------------------------------------------------

def describe_redundancy(finding: Any, obl_a: ObligationInfo, obl_b: ObligationInfo, is_partial: bool) -> str:
    shared = obl_a.category_primary or obl_b.category_primary or "the same requirement"
    shared_label = shared.replace("_", " ")
    mech_a = (obl_a.raw_text or "").strip().rstrip(".")
    mech_b = (obl_b.raw_text or "").strip().rstrip(".")
    if is_partial:
        return (
            f"Both policies address {shared_label} but through different mechanisms "
            f"(\"{mech_a}\" vs \"{mech_b}\"). This is not a conflict, but the overlapping "
            f"governance creates ambiguity about which control is primary."
        )
    return (
        f"{obl_a.policy_name} and {obl_b.policy_name} impose the same {shared_label} requirement "
        f"in near-identical terms (\"{mech_a}\" / \"{mech_b}\"), which is redundant rather than "
        f"contradictory."
    )


def describe_subsumption(finding: Any, obl_a: ObligationInfo, obl_b: ObligationInfo) -> str:
    narrower, broader = (obl_a, obl_b) if finding.scope_relation == "SUBSET" else (obl_b, obl_a)
    return (
        f"{broader.policy_name}'s requirement (\"{(broader.raw_text or '').strip().rstrip('.')}\") "
        f"already covers the narrower case set out in {narrower.policy_name} "
        f"(\"{(narrower.raw_text or '').strip().rstrip('.')}\"). Not a conflict -- the narrower "
        f"obligation is a stricter instance of the broader one."
    )


def recommend_redundancy() -> str:
    return (
        "Cross-reference the two policies and clarify which control is authoritative where they "
        "overlap; reinforcement may be intentional, so consolidate documentation rather than "
        "deleting either requirement."
    )


def recommend_subsumption() -> str:
    return (
        "Add a cross-reference so readers of the broader policy are pointed to the narrower, "
        "stricter requirement; no deletion is needed since the two are compatible."
    )
