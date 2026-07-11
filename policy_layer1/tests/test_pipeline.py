import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from policy_layer1 import run_layer1
from policy_layer1.config import Config


def _doc(section_body: str) -> str:
    return (
        "--- Test Policy (v1.0, Last Reviewed: 2022-01-01) ---\n"
        f"Section 1.1: {section_body}\n"
    )


def test_single_obligation_end_to_end():
    records = run_layer1(_doc("All employees must rotate their passwords every 90 days."))
    obligations = records[0].obligations
    assert len(obligations) == 1
    o = obligations[0]
    assert o.modal_normalized == "OBLIGATION"
    assert o.temporal_constraint.value_days == 90
    assert o.category_primary == "password_management"
    assert o.confidence_tier == "HIGH"


def test_multi_clause_sentence_produces_two_records():
    text = (
        "Employees must rotate passwords every 90 days and must not reuse "
        "the last 5 passwords."
    )
    records = run_layer1(_doc(text))
    obligations = records[0].obligations
    assert len(obligations) == 2
    assert obligations[0].modal_normalized == "OBLIGATION"
    assert obligations[1].modal_normalized == "PROHIBITION"
    # second clause has no explicit subject -> shared subject inferred
    assert "shared_subject_inferred" in obligations[1].extraction_flags
    assert obligations[1].actor == obligations[0].actor


def test_comma_qualifier_list_is_one_record():
    text = (
        "Passwords must be at least 12 characters with uppercase, lowercase, "
        "numbers, and special characters."
    )
    cfg = Config(use_spacy_if_available=False)
    records = run_layer1(_doc(text), config=cfg)
    obligations = records[0].obligations
    assert len(obligations) == 1
    assert len(obligations[0].qualifiers) == 3


def test_semicolon_rationale_not_split_when_second_half_has_no_modal():
    text = (
        "Password rotation shall not be required for cloud systems; MFA "
        "replaces the need for periodic credential changes."
    )
    records = run_layer1(_doc(text))
    obligations = records[0].obligations
    assert len(obligations) == 1
    assert obligations[0].rationale_text == "MFA replaces the need for periodic credential changes."


def test_semicolon_splits_when_both_halves_have_modals():
    text = "Employees must rotate passwords; contractors must use MFA."
    records = run_layer1(_doc(text))
    obligations = records[0].obligations
    assert len(obligations) == 2


def test_implicit_actor_flagged_and_confidence_reduced():
    # No noun phrase precedes the modal at all -> actor cannot be resolved.
    records = run_layer1(_doc("Shall be encrypted within 24 hours of collection."))
    o = records[0].obligations[0]
    assert "implicit_actor" in o.extraction_flags
    assert o.actor == "UNSPECIFIED"
    assert o.confidence <= 0.80


def test_cross_reference_produces_no_obligation():
    records = run_layer1(_doc("See Section 5.1 for authentication requirements."))
    assert records[0].obligations == []
    assert len(records[0].cross_references) == 1
    assert records[0].cross_references[0]["referenced_section"] == "5.1"


def test_definitional_shall_produces_no_obligation():
    records = run_layer1(
        _doc("This policy shall be known as the Acceptable Use Policy.")
    )
    assert records[0].obligations == []
    assert len(records[0].definitional_statements) == 1


def test_exception_clause_attached_to_obligation():
    text = "All systems must use disk encryption except for cloud systems."
    records = run_layer1(_doc(text))
    o = records[0].obligations[0]
    assert o.exception is not None
    assert o.exception.scope_override.get("system") == "cloud"


def test_numbered_sublist_items_get_distinct_ids():
    text = "The following applies: (a) employees must rotate passwords, (b) contractors must use MFA."
    records = run_layer1(_doc(text))
    obligations = records[0].obligations
    assert len(obligations) == 2
    assert "_a_" in obligations[0].obligation_id
    assert "_b_" in obligations[1].obligation_id
    assert obligations[0].obligation_id != obligations[1].obligation_id


def test_contradictory_modal_forces_low_confidence():
    text = "Employees must, but are not required to, complete the training."
    records = run_layer1(_doc(text))
    obligations = records[0].obligations
    assert len(obligations) >= 1
    o = obligations[0]
    assert "contradictory_modal_in_clause" in o.extraction_flags
    assert o.confidence_tier == "LOW"


def test_configurable_category_priority():
    text = "All user accounts must use MFA."
    default_records = run_layer1(_doc(text))
    assert default_records[0].obligations[0].category_primary == "authentication"

    cfg = Config()
    cfg.category_priority = ["account_management", "authentication"] + [
        c for c in cfg.category_priority if c not in ("account_management", "authentication")
    ]
    reordered_records = run_layer1(_doc(text), config=cfg)
    assert reordered_records[0].obligations[0].category_primary == "account_management"


def test_output_is_json_serializable():
    import json

    records = run_layer1(_doc("All employees must rotate their passwords every 90 days."))
    json.dumps([r.to_dict() for r in records])  # should not raise
