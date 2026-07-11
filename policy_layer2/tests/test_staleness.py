from policy_layer2.config import Config
from policy_layer2.nli import NLIEngine
from policy_layer2.normalize import build_deontic_proposition
from policy_layer2.staleness import evaluate_staleness


def _ob(**overrides):
    base = {
        "obligation_id": "X",
        "modal_normalized": "must",
        "polarity": "positive",
        "modal_strength": 3,
        "action": "use",
        "object": "TLS 1.0",
        "qualifiers": [],
        "category_primary": "encryption",
        "category_secondary": [],
        "scope": {"role": None, "system": None, "geography": None},
        "temporal_constraint": None,
        "exception": {},
        "confidence": 0.8,
        "raw_text": "must use TLS 1.0",
    }
    base.update(overrides)
    return build_deontic_proposition(base, policy_name="TestPolicy")


def test_recent_policy_with_no_deprecated_tech_is_not_stale():
    config = Config()
    nli = NLIEngine(config)
    obligations = [_ob(raw_text="must encrypt data at rest with AES-256")]
    meta = {"version": "1.0", "last_reviewed": "2026-06-01"}
    result = evaluate_staleness("Fresh Policy", meta, obligations, config, nli)
    assert result is None


def test_deprecated_tech_reference_flags_staleness_even_if_recently_reviewed():
    config = Config()
    nli = NLIEngine(config)
    obligations = [_ob(raw_text="all connections must use TLS 1.0 or higher")]
    meta = {"version": "1.0", "last_reviewed": "2026-06-01"}  # recently reviewed
    result = evaluate_staleness("Recently Reviewed But Stale Policy", meta, obligations, config, nli)
    assert result is not None
    signal_names = {s["name"] for s in result["staleness_signals"]}
    assert "deprecated_tech" in signal_names


def test_old_review_date_flags_staleness():
    config = Config()
    nli = NLIEngine(config)
    obligations = [_ob(raw_text="must encrypt data at rest")]
    meta = {"version": "1.0", "last_reviewed": "2020-01-01"}
    result = evaluate_staleness("Old Policy", meta, obligations, config, nli)
    assert result is not None
    assert result["severity"] in ("HIGH", "MEDIUM")
