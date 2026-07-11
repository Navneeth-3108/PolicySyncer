import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "policy_layer2"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "policy_layer1"))

from policy_layer2.schema import Evidence, Finding, Layer2Output, StalenessRecord
from policy_layer3 import run_layer3, Layer3Config


def _layer1_records():
    return [
        {
            "policy_metadata": {"policy_name": "Password Policy", "version": "2.1", "last_reviewed": "2021-08-15"},
            "obligations": [
                {
                    "obligation_id": "pp_3_1", "section_ref": "3.1", "source_section": "3.1",
                    "raw_text": "All employees must rotate their passwords every 90 days.",
                    "modal_normalized": "OBLIGATION", "polarity": "POSITIVE", "modal_strength": 3,
                    "category_primary": "password_management",
                    "scope": {"role": "employees", "system": None, "geography": None},
                },
            ],
        },
        {
            "policy_metadata": {"policy_name": "Cloud Security Policy", "version": "1.0", "last_reviewed": "2024-11-20"},
            "obligations": [
                {
                    "obligation_id": "cs_5_2", "section_ref": "5.2", "source_section": "5.2",
                    "raw_text": "Password rotation shall not be required for cloud systems.",
                    "modal_normalized": "PROHIBITION", "polarity": "NEGATIVE", "modal_strength": 3,
                    "category_primary": "password_management",
                    "scope": {"role": None, "system": "cloud", "geography": None},
                },
            ],
        },
    ]


def _conflict_finding(scope_relation, compliance_impact):
    return Finding(
        finding_id="CONFLICT::pp_3_1::cs_5_2",
        finding_type="CONFLICT",
        conflict_subtype="DIRECT",
        obligation_refs=["pp_3_1", "cs_5_2"],
        evidence=Evidence(notes=[]),
        confidence=0.9,
        severity="HIGH",
        scope_relation=scope_relation,
        compliance_impact=compliance_impact,
        source_layer1_confidence=1.0,
    )


def test_compliance_impact_omitted_when_empty():
    finding = _conflict_finding("OVERLAP", [])
    output = Layer2Output(findings=[finding], staleness=[])
    report = run_layer3(output, _layer1_records(), config=Layer3Config())
    entry = report["findings"][0]
    assert "compliance_impact" not in entry


def test_compliance_impact_present_when_nonempty():
    finding = _conflict_finding("OVERLAP", ["ISO 27001 A.5.1", "NIST IA-5"])
    output = Layer2Output(findings=[finding], staleness=[])
    report = run_layer3(output, _layer1_records(), config=Layer3Config())
    entry = report["findings"][0]
    assert entry["compliance_impact"] == ["ISO 27001 A.5.1", "NIST IA-5"]


def test_scope_analysis_present_on_overlap_with_nontrivial_scope():
    finding = _conflict_finding("OVERLAP", [])
    output = Layer2Output(findings=[finding], staleness=[])
    report = run_layer3(output, _layer1_records(), config=Layer3Config())
    entry = report["findings"][0]
    assert "scope_analysis" in entry
    # qualitative-only: no population_source configured -> never a fabricated number
    assert "%" not in entry["scope_analysis"]


def test_scope_analysis_omitted_when_scope_relation_disjoint_like():
    finding = _conflict_finding("EQUAL", [])  # EQUAL is not in the OVERLAP/SUPERSET/SUBSET set
    output = Layer2Output(findings=[finding], staleness=[])
    report = run_layer3(output, _layer1_records(), config=Layer3Config())
    entry = report["findings"][0]
    assert "scope_analysis" not in entry


def test_stale_uses_policy_field_not_policy_a_b():
    record = StalenessRecord(
        policy_name="Password Policy", version="2.1", last_reviewed="2021-08-15",
        months_since_review=58.8,
        staleness_signals=[{"name": "review_age", "weight": 0.3, "confidence": 1.0, "evidence": "58.8 months"}],
        severity="HIGH", confidence=1.0,
    )
    output = Layer2Output(findings=[], staleness=[record])
    report = run_layer3(output, _layer1_records(), config=Layer3Config())
    entry = report["findings"][0]
    assert entry["finding_type"] == "STALE"
    assert entry["policy"] == "Password Policy v2.1"
    assert "policy_a" not in entry and "policy_b" not in entry
