import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "policy_layer1"))

from policy_layer3.citations import CitationIndex, slugify


def _l1_records():
    return [
        {
            "policy_metadata": {
                "policy_name": "Password Policy",
                "version": "2.1",
                "last_reviewed": "2021-08-15",
            },
            "obligations": [
                {
                    "obligation_id": "password_policy_v2.1_3.1_001",
                    "section_ref": "3.1",
                    "source_section": "3.1",
                    "raw_text": "All employees must rotate their passwords every 90 days.",
                    "modal_normalized": "OBLIGATION",
                    "polarity": "POSITIVE",
                    "modal_strength": 3,
                    "category_primary": "password_management",
                    "scope": {"role": "employees", "system": None, "geography": None},
                }
            ],
        }
    ]


def test_obligation_citation_uses_section_ref():
    index = CitationIndex.build(_l1_records())
    assert index.obligation_citation("password_policy_v2.1_3.1_001") == "Password Policy §3.1"


def test_policy_citation_uses_version():
    index = CitationIndex.build(_l1_records())
    assert index.policy_citation_by_name("Password Policy") == "Password Policy v2.1"


def test_unresolvable_obligation_id_falls_back_to_raw_id():
    index = CitationIndex.build(_l1_records())
    assert index.obligation_citation("nonexistent_id") == "nonexistent_id"


def test_slugify_matches_layer1_convention():
    assert slugify("Password Policy") == "password_policy"
    assert slugify("Cloud Security Policy") == "cloud_security_policy"


def test_categories_for_policy_aggregates_across_obligations():
    index = CitationIndex.build(_l1_records())
    assert index.categories_for_policy("Password Policy") == {"password_management"}
