"""
§5.7 Exception clause extraction.
"""

import re
from typing import Optional

from .schema import Exception_
from .slots import SCOPE_KEYWORDS  # reuse the same scope tables

_EXCEPTION_RE = re.compile(
    r"\b(?:unless|except(?:ing)?|excluding|other than|with the exception of)\b(?P<text>.+)$",
    re.IGNORECASE,
)


def extract_exception(clause_text: str) -> Optional[Exception_]:
    m = _EXCEPTION_RE.search(clause_text)
    if not m:
        return None

    text = m.group("text").strip().rstrip(".").strip()
    exc = Exception_(text=text, scope_override={})

    lowered = text.lower()
    for dim, keywords in SCOPE_KEYWORDS.items():
        for kw_pattern, kw_value in keywords:
            if kw_pattern.search(lowered):
                exc.scope_override[dim] = kw_value
                break

    return exc


def strip_exception_clause(clause_text: str) -> str:
    """Return the clause text with the exception clause removed, so slot
    extraction on the main obligation isn't confused by the carve-out."""
    m = _EXCEPTION_RE.search(clause_text)
    if not m:
        return clause_text
    return clause_text[: m.start()].strip().rstrip(",").strip()
