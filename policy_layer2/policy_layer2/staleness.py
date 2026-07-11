"""
§7 Staleness Reasoning.

Combines five independent signals (review-age, deprecated-tech reference,
superseded-standard reference, semantic drift vs current guidance, missing
version history/ownership) into a weighted staleness verdict rather than a
single 18-month date check (§7.1, §7.2).
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from .normalize import DeonticProposition
from .nli import NLIEngine


@dataclass
class StalenessSignal:
    name: str
    fired: bool
    weight: float
    confidence: float
    evidence: str


def _months_since(last_reviewed: Optional[str], today: Optional[date] = None) -> Optional[float]:
    if not last_reviewed:
        return None
    today = today or date.today()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            d = datetime.strptime(last_reviewed, fmt).date()
            days = (today - d).days
            return round(days / 30.44, 1)
        except ValueError:
            continue
    return None


def _review_age_signal(months: Optional[float], config) -> StalenessSignal:
    if months is None:
        return StalenessSignal("review_age", False, config.staleness_signal_weights["review_age"], 0.0,
                                "last_reviewed missing or unparseable")
    fired = months >= config.staleness_age_months_threshold
    # confidence scales smoothly past the threshold rather than a hard 0/1 step
    conf = min(1.0, max(0.0, (months - config.staleness_age_months_threshold) / config.staleness_age_months_threshold)) if fired else 0.0
    return StalenessSignal("review_age", fired, config.staleness_signal_weights["review_age"], conf,
                            f"{months} months since last review (threshold {config.staleness_age_months_threshold})")


def _deprecated_tech_signal(obligations: List[DeonticProposition], config) -> StalenessSignal:
    hits = []
    for ob in obligations:
        text = ob.raw_text.lower()
        for term in config.deprecated_technologies:
            if term in text:
                hits.append((ob.obligation_id, term))
    fired = bool(hits)
    conf = min(1.0, 0.6 + 0.1 * len(hits)) if fired else 0.0
    ev = "; ".join(f"{oid}: '{term}'" for oid, term in hits) or "no deprecated-technology references found"
    return StalenessSignal("deprecated_tech", fired, config.staleness_signal_weights["deprecated_tech"], conf, ev)


def _superseded_standard_signal(obligations: List[DeonticProposition], config) -> StalenessSignal:
    hits = []
    for ob in obligations:
        text = ob.raw_text.lower()
        for cited, note in config.superseded_standards.items():
            if cited in text:
                hits.append((ob.obligation_id, cited, note))
    fired = bool(hits)
    conf = 0.85 if fired else 0.0
    ev = "; ".join(f"{oid}: cites '{cited}' ({note})" for oid, cited, note in hits) or "no superseded-standard citations found"
    return StalenessSignal("superseded_standard", fired, config.staleness_signal_weights["superseded_standard"], conf, ev)


def _semantic_drift_signal(obligations: List[DeonticProposition], config, nli_engine: NLIEngine) -> StalenessSignal:
    best_score = 0.0
    best_ev = "no current-guidance corpus entries matched this policy's categories"
    for ob in obligations:
        corpus = config.current_guidance_corpus.get(ob.category_primary or "", [])
        for guidance in corpus:
            score = nli_engine.contradiction_score(ob.raw_text, guidance, ob.modality, "RECOMMENDATION")
            if score > best_score:
                best_score = score
                best_ev = f"{ob.obligation_id} vs current guidance: \"{guidance[:60]}...\" (score={score:.2f})"
    fired = best_score >= config.nli_contradiction_confirm_threshold
    return StalenessSignal("semantic_drift", fired, config.staleness_signal_weights["semantic_drift"],
                            best_score if fired else 0.0, best_ev)


def _missing_metadata_signal(obligations: List[DeonticProposition], policy_metadata: Dict[str, Any], config) -> StalenessSignal:
    incomplete = bool(policy_metadata.get("metadata_incomplete") or policy_metadata.get("staleness_undetermined"))
    any_ob_incomplete = any(ob.metadata_incomplete for ob in obligations)
    fired = incomplete or any_ob_incomplete
    conf = 0.5 if fired else 0.0  # pass-through discount signal, not a standalone claim (§7.1)
    ev = "policy_metadata flags metadata_incomplete/staleness_undetermined" if fired else "metadata complete"
    return StalenessSignal("missing_metadata", fired, config.staleness_signal_weights["missing_metadata"], conf, ev)


def evaluate_staleness(
    policy_name: str,
    policy_metadata: Dict[str, Any],
    obligations: List[DeonticProposition],
    config,
    nli_engine: NLIEngine,
) -> Optional[Dict[str, Any]]:
    months = _months_since(policy_metadata.get("last_reviewed"))

    signals = [
        _review_age_signal(months, config),
        _deprecated_tech_signal(obligations, config),
        _superseded_standard_signal(obligations, config),
        _semantic_drift_signal(obligations, config, nli_engine),
        _missing_metadata_signal(obligations, policy_metadata, config),
    ]

    fired_signals = [s for s in signals if s.fired]
    if not fired_signals:
        return None

    # weighted combination (§7.2) -- same fusion philosophy as §8, applied to
    # a different signal set. Weighted sum of (weight * confidence), normalized
    # by the sum of weights of *fired* signals so a policy that only trips one
    # low-weight signal doesn't get an inflated verdict.
    numerator = sum(s.weight * s.confidence for s in fired_signals)
    denominator = sum(s.weight for s in fired_signals) or 1.0
    staleness_confidence = round(numerator / denominator, 3)

    # missing-metadata discounts overall confidence rather than standing alone
    # (§7.1: "any staleness conclusion about it explicitly low-confidence,
    # not silently omitted").
    if any(s.name == "missing_metadata" and s.fired for s in fired_signals):
        staleness_confidence = round(staleness_confidence * 0.7, 3)

    if staleness_confidence < config.severity_min_emission_confidence:
        return None

    if staleness_confidence >= config.severity_high_confidence:
        severity = "HIGH"
    elif staleness_confidence >= config.severity_medium_confidence:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    return {
        "policy_name": policy_name,
        "version": policy_metadata.get("version", ""),
        "last_reviewed": policy_metadata.get("last_reviewed"),
        "months_since_review": months,
        "staleness_signals": [
            {"name": s.name, "weight": s.weight, "confidence": s.confidence, "evidence": s.evidence}
            for s in fired_signals
        ],
        "severity": severity,
        "confidence": staleness_confidence,
    }
