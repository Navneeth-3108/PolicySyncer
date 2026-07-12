import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "policy_layer2"))

from policy_layer2.schema import Evidence, Finding, StalenessRecord
from policy_layer3.citations import CitationIndex
from policy_layer3.config import Layer3Config
from policy_layer3.health_score import compute_health_scores


def _index():
    return CitationIndex.build([
        {
            "policy_metadata": {"policy_name": "Password Policy", "version": "2.1", "last_reviewed": "2021-08-15"},
            "obligations": [
                {"obligation_id": "pp_1", "section_ref": "3.1", "raw_text": "x", "modal_normalized": "OBLIGATION",
                 "polarity": "POSITIVE", "modal_strength": 3, "category_primary": "password_management",
                 "scope": {}},
            ],
        },
        {
            "policy_metadata": {"policy_name": "Cloud Security Policy", "version": "1.0", "last_reviewed": "2024-11-20"},
            "obligations": [
                {"obligation_id": "cs_1", "section_ref": "5.2", "raw_text": "y", "modal_normalized": "PROHIBITION",
                 "polarity": "NEGATIVE", "modal_strength": 3, "category_primary": "password_management",
                 "scope": {}},
            ],
        },
    ])


def _finding(severity):
    return Finding(
        finding_id="f", finding_type="CONFLICT", conflict_subtype="DIRECT",
        obligation_refs=["pp_1", "cs_1"], evidence=Evidence(notes=[]),
        confidence=0.9, severity=severity, scope_relation="OVERLAP",
        compliance_impact=[], source_layer1_confidence=1.0,
    )


def test_no_findings_gives_perfect_scores():
    scores = compute_health_scores([], [], _index(), Layer3Config())
    assert scores == {"password_policy": 100, "cloud_security_policy": 100, "overall": 100}


def test_high_severity_conflict_penalizes_both_sides_full_weight():
    config = Layer3Config()  # default two_sided_penalty_mode = "full"
    scores = compute_health_scores([_finding("HIGH")], [], _index(), config)
    # HIGH weight = 30, both policies appear in the pairwise finding -> both
    # penalized 30: 100 - min(30, 100) = 70.
    assert scores["password_policy"] == 70
    assert scores["cloud_security_policy"] == 70
    assert scores["overall"] == 70


def test_half_penalty_mode_splits_weight_across_sides():
    config = Layer3Config(two_sided_penalty_mode="half")
    scores = compute_health_scores([_finding("HIGH")], [], _index(), config)
    # half weight = 15 each: 100 - min(15, 100) = 85.
    assert scores["password_policy"] == 85
    assert scores["cloud_security_policy"] == 85


def test_staleness_penalizes_only_its_own_policy():
    record = StalenessRecord(
        policy_name="Password Policy", version="2.1", last_reviewed="2021-08-15",
        months_since_review=58.8,
        staleness_signals=[{"name": "review_age", "weight": 0.3, "confidence": 1.0, "evidence": "e"}],
        severity="MEDIUM", confidence=1.0,
    )
    scores = compute_health_scores([], [record], _index(), Layer3Config())
    assert scores["password_policy"] == 80   # 100 - 20 (MEDIUM weight)
    assert scores["cloud_security_policy"] == 100


def test_scores_never_go_below_zero():
    config = Layer3Config()
    findings = [_finding("HIGH") for _ in range(10)]  # 10x HIGH = way past 100 penalty
    scores = compute_health_scores(findings, [], _index(), config)
    # penalty (300) is clamped to a 100-point deduction, so the score floors
    # at 0 -- the full CRITICAL band is reachable for a badly-conflicted policy.
    assert scores["password_policy"] == 0
    assert scores["cloud_security_policy"] == 0
