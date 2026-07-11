import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from policy_layer1.parsing import parse_policy_blocks
from policy_layer1.preprocessing import preprocess


def test_basic_header_parsing():
    text = preprocess(
        "--- Password Policy (v2.1, Last Reviewed: 2021-08-15) ---\n"
        "Section 3.1: All employees must rotate passwords every 90 days.\n"
    )
    blocks = parse_policy_blocks(text)
    assert len(blocks) == 1
    assert blocks[0].name == "Password Policy"
    assert blocks[0].version == "2.1"
    assert blocks[0].last_reviewed == "2021-08-15"
    assert blocks[0].metadata_flags == []


def test_tolerant_version_format():
    text = preprocess(
        "--- Password Policy (Version 2.1, Last Reviewed: 2021-08-15) ---\n"
        "Section 3.1: All employees must rotate passwords every 90 days.\n"
    )
    blocks = parse_policy_blocks(text)
    assert blocks[0].version == "2.1"


def test_missing_last_reviewed_flags_staleness_undetermined():
    text = preprocess(
        "--- Password Policy (v2.1) ---\n"
        "Section 3.1: All employees must rotate passwords every 90 days.\n"
    )
    blocks = parse_policy_blocks(text)
    assert blocks[0].last_reviewed is None
    assert "staleness_undetermined" in blocks[0].metadata_flags


def test_nested_section_numbering():
    text = preprocess(
        "--- Policy (v1.0, Last Reviewed: 2022-01-01) ---\n"
        "Section 3.1.2: A nested rule that must be followed.\n"
    )
    blocks = parse_policy_blocks(text)
    assert blocks[0].sections[0].section_id == "3.1.2"


def test_section_without_colon_fallback():
    text = preprocess(
        "--- Policy (v1.0, Last Reviewed: 2022-01-01) ---\n"
        "Section 3.1 All employees must comply with this rule.\n"
    )
    blocks = parse_policy_blocks(text)
    assert blocks[0].sections[0].section_id == "3.1"
    assert "nonstandard_section_format" in blocks[0].sections[0].flags


def test_wrapped_section_body_is_joined():
    text = preprocess(
        "--- Policy (v1.0, Last Reviewed: 2022-01-01) ---\n"
        "Section 3.2: Passwords must be at least 12 characters with uppercase,\n"
        "lowercase, numbers, and special characters.\n"
    )
    blocks = parse_policy_blocks(text)
    body = blocks[0].sections[0].body
    assert "lowercase, numbers, and special characters" in body
    assert "\n" not in body


def test_multiple_policy_blocks():
    text = preprocess(
        "--- Policy A (v1.0, Last Reviewed: 2022-01-01) ---\n"
        "Section 1.1: Rule one must apply.\n"
        "--- Policy B (v2.0, Last Reviewed: 2023-01-01) ---\n"
        "Section 1.1: Rule two must apply.\n"
    )
    blocks = parse_policy_blocks(text)
    assert len(blocks) == 2
    assert blocks[0].name == "Policy A"
    assert blocks[1].name == "Policy B"
