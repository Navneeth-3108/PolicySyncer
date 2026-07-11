import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from policy_layer1.temporal import extract_temporal
from policy_layer1.exceptions import extract_exception
from policy_layer1.category import classify_category
from policy_layer1.confidence import score_confidence, tier_for
from policy_layer1.config import Config


def test_recurring_temporal():
    tc, flags = extract_temporal("rotate passwords every 90 days")
    assert tc.type == "recurring"
    assert tc.value == 90
    assert tc.value_days == 90


def test_duration_temporal():
    tc, flags = extract_temporal("retain logs for 2 years")
    assert tc.type == "duration"
    assert tc.value_days == 730


def test_deadline_temporal():
    tc, flags = extract_temporal("report incidents within 24 hours")
    assert tc.type == "deadline"
    assert tc.value == 24
    assert round(tc.value_days) == 1


def test_bare_count_is_not_temporal():
    # "10" here is a count of passwords, not a time unit -> no match
    tc, flags = extract_temporal("Previous 10 passwords may not be reused.")
    assert tc is None


def test_absolute_date():
    tc, flags = extract_temporal("effective as of 2024-01-01")
    assert tc.type == "absolute_date"
    assert tc.abs_date == "2024-01-01"


def test_exception_extraction_with_scope_override():
    exc = extract_exception(
        "All systems must use disk encryption except for cloud systems."
    )
    assert exc is not None
    assert "cloud systems" in exc.text
    assert exc.scope_override.get("system") == "cloud"


def test_no_exception_when_no_marker():
    exc = extract_exception("Employees must rotate passwords every 90 days.")
    assert exc is None


def test_category_single_match():
    primary, secondary, flags = classify_category(
        "Employees must rotate passwords every 90 days.", Config().category_priority
    )
    assert primary == "password_management"
    assert flags == []


def test_category_ambiguous_priority():
    # "MFA for all user accounts" matches authentication (MFA) AND
    # account_management (user accounts) -> priority order picks winner
    primary, secondary, flags = classify_category(
        "MFA for all user accounts.", Config().category_priority
    )
    assert primary == "authentication"
    assert "account_management" in secondary


def test_category_unresolved_fallback():
    primary, secondary, flags = classify_category(
        "Employees must wear photo identification badges.", Config().category_priority
    )
    assert primary == "other"
    assert "category_unresolved" in flags


def test_confidence_clean_match_stays_1_0():
    assert score_confidence([]) == 1.0
    assert tier_for(1.0) == "HIGH"


def test_confidence_implicit_actor_penalty():
    score = score_confidence(["implicit_actor"])
    assert abs(score - 0.80) < 1e-9
    assert tier_for(score) == "HIGH"  # exactly at threshold


def test_confidence_floor_at_0_3():
    flags = [
        "implicit_actor",
        "split_negation_detected",
        "shared_subject_inferred",
        "category_unresolved",
        "temporal_unit_ambiguous",
        "nonstandard_section_format",
    ]
    score = score_confidence(flags)
    assert score == Config().confidence_floor


def test_confidence_medium_tier():
    score = score_confidence(["implicit_actor", "category_unresolved"])  # 1 - .2 - .15 = .65
    assert tier_for(score) == "MEDIUM"
