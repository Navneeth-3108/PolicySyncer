"""
§5.1 Modal lexicon (normalization table) and §5.2 split negation.

Critical ordering rule (§5.1): negated multi-word patterns must be matched
before single-word patterns, in ONE ordered list, first-match-wins. We do
NOT run independent regex passes, to avoid double-firing.
"""

import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ModalMatch:
    raw: str
    normalized: str  # OBLIGATION | PROHIBITION | RECOMMENDATION | PERMISSION
    strength: int
    polarity: str  # POSITIVE | NEGATIVE
    start: int
    end: int
    split_negation: bool = False


# Ordered, first-match-wins. Negated multi-word forms MUST precede their
# single-word counterparts.
_MODAL_LEXICON = [
    (r"\bmust\s+not\b", "PROHIBITION", 3, "NEGATIVE"),
    (r"\bshall\s+not\b", "PROHIBITION", 3, "NEGATIVE"),
    (r"\bmay\s+not\b", "PROHIBITION", 3, "NEGATIVE"),
    (r"\bis\s+prohibited\s+from\b", "PROHIBITION", 3, "NEGATIVE"),
    (r"\bis\s+not\s+(?:permitted|allowed)\s+to\b", "PROHIBITION", 3, "NEGATIVE"),
    (r"\bshould\s+not\b", "PROHIBITION", 2, "NEGATIVE"),
    (r"\bis\s+discouraged\s+from\b", "PROHIBITION", 2, "NEGATIVE"),
    (r"\bmust\b", "OBLIGATION", 3, "POSITIVE"),
    (r"\bshall\b", "OBLIGATION", 3, "POSITIVE"),
    (r"\bis\s+required\s+to\b", "OBLIGATION", 3, "POSITIVE"),
    (r"\bis\s+mandatory\b", "OBLIGATION", 3, "POSITIVE"),
    (r"\bis\s+to\s+be\b", "OBLIGATION", 3, "POSITIVE"),
    (r"\bshould\b", "RECOMMENDATION", 2, "POSITIVE"),
    (r"\bis\s+advised\s+to\b", "RECOMMENDATION", 2, "POSITIVE"),
    (r"\bis\s+recommended\s+(?:that|to)\b", "RECOMMENDATION", 2, "POSITIVE"),
    (r"\bis\s+encouraged\s+to\b", "RECOMMENDATION", 1, "POSITIVE"),
    (r"\bmay\s+optionally\b", "RECOMMENDATION", 1, "POSITIVE"),
    # "may" not followed by "not" within 3 tokens
    (r"\bmay\b(?!(?:\s+\w+){0,3}\s+not\b)", "PERMISSION", 1, "POSITIVE"),
]

_COMPILED_LEXICON = [
    (re.compile(pat, re.IGNORECASE), norm, strength, polarity)
    for pat, norm, strength, polarity in _MODAL_LEXICON
]

# §5.2 windowed negation check: modal ... (0-4 words) ... not
# Allows intervening commas/punctuation around the adverbial words (e.g.
# "must, under no circumstances, not be reused"), since real policy text
# often sets the interrupting phrase off with commas.
_SPLIT_NEG_RE = re.compile(
    r"\b(must|shall|should|may)\b(?:[\s,]+\w+){0,4}?[\s,]+not\b", re.IGNORECASE
)

# §10 stoplist: definitional (non-obligation) uses of modals, checked BEFORE
# the general OBLIGATION match.
DEFINITIONAL_PATTERNS = [
    re.compile(r"\bshall\s+be\s+known\s+as\b", re.IGNORECASE),
    re.compile(r"\bshall\s+mean\b", re.IGNORECASE),
]


def is_definitional(clause_text: str) -> bool:
    return any(p.search(clause_text) for p in DEFINITIONAL_PATTERNS)


def detect_modals(clause_text: str) -> List[ModalMatch]:
    """
    Find all non-overlapping modal matches in a clause, in left-to-right
    order, using first-match-wins per span per §5.1. Multiple *distinct*
    modal occurrences (§5.4) are all returned, in document order.
    """
    if is_definitional(clause_text):
        return []

    matches: List[ModalMatch] = []
    occupied: List[tuple] = []  # (start, end) already claimed

    # Scan token-by-token position: for each candidate start position, try
    # patterns in lexicon order (first-match-wins), but only accept the
    # match if it doesn't overlap an already-claimed span, and we advance
    # scanning left to right by looking for the next unclaimed modal cue.
    search_from = 0
    text = clause_text
    while search_from < len(text):
        best = None
        for pattern, norm, strength, polarity in _COMPILED_LEXICON:
            m = pattern.search(text, search_from)
            if m is None:
                continue
            if best is None or m.start() < best[0].start():
                best = (m, norm, strength, polarity)
        if best is None:
            break
        m, norm, strength, polarity = best

        # split negation check (§5.2): windowed pattern fires but tight
        # adjacent pattern (already encoded above) did not -> already
        # NEGATIVE forms are matched directly above; here we detect the
        # case where a POSITIVE-looking match actually has a distant "not".
        split_neg = False
        if polarity == "POSITIVE":
            window_m = _SPLIT_NEG_RE.match(text, m.start())
            if window_m and window_m.group(0).strip().split()[-1].lower() == "not":
                # only reinterpret if the matched modal word matches
                if window_m.start() == m.start():
                    split_neg = True
                    # flip to negated form of same modal family
                    norm = _negate(norm)
                    polarity = "NEGATIVE"

        matches.append(
            ModalMatch(
                raw=text[m.start():m.end()],
                normalized=norm,
                strength=strength,
                polarity=polarity,
                start=m.start(),
                end=m.end(),
                split_negation=split_neg,
            )
        )
        search_from = m.end()

    return matches


def _negate(normalized: str) -> str:
    return {
        "OBLIGATION": "PROHIBITION",
        "RECOMMENDATION": "PROHIBITION",
        "PERMISSION": "PROHIBITION",
    }.get(normalized, normalized)
