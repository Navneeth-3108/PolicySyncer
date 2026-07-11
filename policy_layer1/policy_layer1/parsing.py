"""
§3 Document & Metadata Parsing.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional

_BLOCK_HEADER_RE = re.compile(
    r"^-{2,}\s*(?P<policy_name>.+?)\s*\(\s*v(?P<version>[\d.]+)\s*,\s*Last Reviewed:\s*"
    r"(?P<last_reviewed>\d{4}-\d{2}-\d{2})\s*\)\s*-{2,}\s*$",
    re.IGNORECASE,
)

# Tolerant alternate version pattern (§3.1 disambiguation rule)
_ALT_VERSION_RE = re.compile(r"[vV](?:ersion)?\s*([\d.]+)")
_ALT_DATE_RE = re.compile(r"Last Reviewed:\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE)
_ALT_NAME_RE = re.compile(r"^-{2,}\s*(.+?)\s*(?:\(|-{2,}\s*$)")

_SECTION_RE = re.compile(
    r"^Section\s+(?P<section_id>\d+(?:\.\d+)*)\s*:\s*(?P<body>.+)$", re.IGNORECASE
)
# §3.2 fallback: sections without a colon
_SECTION_FALLBACK_RE = re.compile(
    r"^Section\s+(?P<section_id>\d+(?:\.\d+)*)\s+(?P<body>.+)$", re.IGNORECASE
)


@dataclass
class SectionBlock:
    section_id: str
    body: str
    flags: List[str] = field(default_factory=list)


@dataclass
class PolicyBlock:
    name: str
    version: Optional[str]
    last_reviewed: Optional[str]
    body: str
    metadata_flags: List[str] = field(default_factory=list)
    sections: List[SectionBlock] = field(default_factory=list)


def _find_header_lines(text: str) -> List[int]:
    lines = text.split("\n")
    return [i for i, line in enumerate(lines) if line.strip().startswith("---")]


def parse_policy_blocks(text: str) -> List[PolicyBlock]:
    """
    §3.1 — split the document into policy blocks at '--- ... ---' header
    lines, parsing policy_name / version / last_reviewed from each header.
    """
    lines = text.split("\n")
    header_idxs = _find_header_lines(text)
    blocks: List[PolicyBlock] = []

    for i, start_idx in enumerate(header_idxs):
        header_line = lines[start_idx].strip()
        end_idx = header_idxs[i + 1] if i + 1 < len(header_idxs) else len(lines)
        body_lines = lines[start_idx + 1 : end_idx]
        body = "\n".join(body_lines)

        name, version, last_reviewed, flags = _parse_header(header_line)
        block = PolicyBlock(
            name=name,
            version=version,
            last_reviewed=last_reviewed,
            body=body,
            metadata_flags=flags,
        )
        block.sections = parse_sections(body)
        blocks.append(block)

    return blocks


def _parse_header(header_line: str):
    flags: List[str] = []
    m = _BLOCK_HEADER_RE.match(header_line)
    if m:
        return m.group("policy_name"), m.group("version"), m.group("last_reviewed"), flags

    # Tolerant fallback parsing
    name_m = _ALT_NAME_RE.match(header_line)
    name = name_m.group(1).strip() if name_m else header_line.strip("- ").strip()

    version = None
    v_m = _ALT_VERSION_RE.search(header_line)
    if v_m:
        version = v_m.group(1)
    else:
        flags.append("metadata_incomplete")

    last_reviewed = None
    d_m = _ALT_DATE_RE.search(header_line)
    if d_m:
        last_reviewed = d_m.group(1)
    else:
        flags.append("staleness_undetermined")

    return name, version, last_reviewed, flags


def parse_sections(policy_body: str) -> List[SectionBlock]:
    """§3.2 — split a policy block body into Section N.N: ... blocks."""
    lines = policy_body.split("\n")
    header_positions = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if _SECTION_RE.match(stripped) or _SECTION_FALLBACK_RE.match(stripped):
            header_positions.append(i)

    sections: List[SectionBlock] = []
    for idx, start in enumerate(header_positions):
        end = header_positions[idx + 1] if idx + 1 < len(header_positions) else len(lines)
        block_lines = lines[start:end]
        block_text = "\n".join(block_lines).strip()

        flags = []
        m = _SECTION_RE.match(block_text.split("\n")[0].strip())
        if m:
            section_id = m.group("section_id")
            first_line_body = m.group("body")
        else:
            m2 = _SECTION_FALLBACK_RE.match(block_text.split("\n")[0].strip())
            if not m2:
                continue
            section_id = m2.group("section_id")
            first_line_body = m2.group("body")
            flags.append("nonstandard_section_format")

        remaining = "\n".join(block_lines[1:]).strip()
        body = (first_line_body + (" " + remaining if remaining else "")).strip()
        sections.append(SectionBlock(section_id=section_id, body=body, flags=flags))

    return sections
