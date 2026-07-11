"""
§10 Additional edge cases:
  - cross-references without new obligations
  - definitional (non-obligation) modal uses
  - contradictory modal in one clause
"""

import re

_CROSS_REF_RE = re.compile(r"\bsee\s+section\s+(?P<section_id>\d+(?:\.\d+)*)\b", re.IGNORECASE)

_DEFINITIONAL_RE = re.compile(
    r"^(?P<subject>.+?)\s+(?P<pattern>shall\s+be\s+known\s+as|shall\s+mean)\s+(?P<rest>.+)$",
    re.IGNORECASE,
)

# "Employees must, but are not required to, ..." — a positive obligation and
# an explicit negation of requirement in the same clause.
_CONTRADICTORY_RE = re.compile(
    r"\bmust\b.{0,40}\bnot\s+required\s+to\b|\brequired\s+to\b.{0,40}\bnot\s+required\b",
    re.IGNORECASE,
)


def find_cross_reference(clause_text: str):
    m = _CROSS_REF_RE.search(clause_text)
    if not m:
        return None
    return {"raw_text": clause_text, "referenced_section": m.group("section_id")}


def find_definitional_statement(clause_text: str):
    m = _DEFINITIONAL_RE.match(clause_text.strip())
    if not m:
        return None
    return {"raw_text": clause_text.strip()}


def has_contradictory_modal(clause_text: str) -> bool:
    return bool(_CONTRADICTORY_RE.search(clause_text))
