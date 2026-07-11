"""
§2 Preprocessing.

- Normalize whitespace (collapse spaces/tabs, preserve newlines)
- Join wrapped lines (§2.2)
- Normalize unicode curly quotes/dashes to ASCII (§2.3)
- Sentence segmentation with abbreviation guard (§2.5) lives in clauses.py,
  since it operates per-section-body rather than on the whole document.
"""

import re

# §2.3 unicode normalization table
_UNICODE_MAP = {
    "\u2018": "'",  # left single quote
    "\u2019": "'",  # right single quote
    "\u201c": '"',  # left double quote
    "\u201d": '"',  # right double quote
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash
    "\u2026": "...",  # ellipsis
}

_WS_RE = re.compile(r"[ \t]+")


def normalize_unicode(text: str) -> str:
    for src, dst in _UNICODE_MAP.items():
        text = text.replace(src, dst)
    return text


def normalize_whitespace(text: str) -> str:
    """Collapse runs of spaces/tabs but preserve newlines."""
    lines = text.split("\n")
    lines = [_WS_RE.sub(" ", line).strip() for line in lines]
    return "\n".join(lines)


_TERMINAL_PUNCT = (".", ":", ";")


def _is_structural_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("---") or re.match(r"^Section\s+\d", stripped) is not None


def join_wrapped_lines_v2(text: str) -> str:
    """
    More faithful implementation of §2.2's rule, which explicitly depends on
    the *next* line's content ("the next line does not start with Section or
    ---"), not just the current line's punctuation. This version does a
    proper two-line lookahead.
    """
    raw_lines = text.split("\n")
    out: list[str] = []
    i = 0
    n = len(raw_lines)

    while i < n:
        line = raw_lines[i].rstrip()
        if line.strip() == "":
            out.append("")
            i += 1
            continue

        # Structural lines (headers) are never joined into.
        if _is_structural_line(line):
            out.append(line.strip())
            i += 1
            continue

        merged = line.strip()
        while True:
            ends_terminal = merged.endswith(_TERMINAL_PUNCT)
            next_idx = i + 1
            if next_idx >= n:
                break
            next_line = raw_lines[next_idx].rstrip()
            if next_line.strip() == "":
                break
            if _is_structural_line(next_line):
                break
            if ends_terminal:
                break
            # join
            merged = merged + " " + next_line.strip()
            i = next_idx
        out.append(merged)
        i += 1

    return "\n".join(out)


def preprocess(raw_text: str) -> str:
    text = normalize_unicode(raw_text)
    text = normalize_whitespace(text)
    text = join_wrapped_lines_v2(text)
    return text
