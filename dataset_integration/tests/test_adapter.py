import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "policy_layer1"))

from dataset_integration.adapter import parse_policy_md, build_dataset_document, file_to_name_map
from policy_layer1 import run_layer1

_SAMPLE_MD = """# Password Policy

**Author:** Ava Johnson

**Department:** Product

**Version:** v2.3

**Last Reviewed:** 2023-03-28

**Status:** active

- All users shall provisioning as per company standards.
- Access is prohibited for all users.
- All users required change as per company standards.
- All users recommended backup as per company standards.
"""


def test_parse_policy_md_extracts_front_matter():
    parsed = parse_policy_md(_SAMPLE_MD, "policy_01.md")
    assert parsed["title"] == "Password Policy"
    assert parsed["version"] == "2.3"
    assert parsed["last_reviewed"] == "2023-03-28"
    assert parsed["status"] == "active"


def test_parse_policy_md_extracts_all_bullets():
    parsed = parse_policy_md(_SAMPLE_MD, "policy_01.md")
    assert len(parsed["bullets"]) == 4
    assert parsed["bullets"][0] == "All users shall provisioning as per company standards."
    assert parsed["bullets"][1] == "Access is prohibited for all users."


def test_parse_policy_md_handles_missing_version_and_date():
    md = "# No Metadata Policy\n\n- All users must encrypt data.\n"
    parsed = parse_policy_md(md, "policy_99.md")
    assert parsed["title"] == "No Metadata Policy"
    assert parsed["version"] is None
    assert parsed["last_reviewed"] is None
    assert len(parsed["bullets"]) == 1


def test_build_dataset_document_produces_valid_native_blocks(tmp_path=None):
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        policies_dir = os.path.join(tmp, "policies")
        os.makedirs(policies_dir)
        with open(os.path.join(policies_dir, "policy_01.md"), "w") as f:
            f.write(_SAMPLE_MD)
        with open(os.path.join(policies_dir, "policy_02.md"), "w") as f:
            f.write("# Cloud Policy\n\n**Version:** v1.0\n\n**Last Reviewed:** 2024-01-01\n\n- All users must cloud as per company standards.\n")

        text, name_to_file = build_dataset_document(tmp)

        assert name_to_file["Password Policy"] == "policy_01.md"
        assert name_to_file["Cloud Policy"] == "policy_02.md"
        assert "--- Password Policy (v2.3, Last Reviewed: 2023-03-28) ---" in text
        assert "--- Cloud Policy (v1.0, Last Reviewed: 2024-01-01) ---" in text

        records = run_layer1(text)
        assert len(records) == 2
        names = {r.policy_metadata.policy_name for r in records}
        assert names == {"Password Policy", "Cloud Policy"}

        # All 4 obligation forms from the Password Policy sample should
        # extract (this is the modal-lexicon-fix regression check).
        pw_record = next(r for r in records if r.policy_metadata.policy_name == "Password Policy")
        assert len(pw_record.obligations) == 4


def test_file_to_name_map_is_inverse():
    name_to_file = {"Password Policy": "policy_01.md", "Cloud Policy": "policy_02.md"}
    inverse = file_to_name_map(name_to_file)
    assert inverse == {"policy_01.md": "Password Policy", "policy_02.md": "Cloud Policy"}
