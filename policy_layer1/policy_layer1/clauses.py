"""
§2.5 sentence segmentation (with abbreviation guard) and §4 clause
segmentation (semicolon splitting only when both halves independently
carry a modal).
"""

import re
from dataclasses import dataclass
from typing import List

from .modals import detect_modals

# §2.5 abbreviation exclusion list — checked before splitting on ". "
_ABBREVIATIONS = {"e.g.", "i.e.", "u.s.", "u.s.a.", "etc.", "vs.", "mr.", "mrs.", "dr."}

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


@dataclass
class Clause:
    text: str
    is_list_item: bool = False
    list_id_suffix: str = ""


def _protect_abbreviations(text: str) -> str:
    # Replace the periods in known abbreviations with a placeholder so the
    # sentence splitter doesn't treat them as boundaries.
    protected = text
    for abbr in _ABBREVIATIONS:
        pattern = re.compile(re.escape(abbr), re.IGNORECASE)

        def _sub(m, abbr=abbr):
            return m.group(0).replace(".", "\u0000")

        protected = pattern.sub(_sub, protected)
    return protected


def _restore_abbreviations(text: str) -> str:
    return text.replace("\u0000", ".")


def split_sentences(section_body: str) -> List[str]:
    """§2.5 — split into candidate sentences, guarding against abbreviations."""
    protected = _protect_abbreviations(section_body)
    parts = _SENTENCE_SPLIT_RE.split(protected)
    # also split on end-of-string implicitly handled since regex only splits
    # between sentences; trailing sentence is the last element.
    return [_restore_abbreviations(p).strip() for p in parts if p.strip()]


def _has_independent_modal(text: str) -> bool:
    return len(detect_modals(text)) > 0


def split_semicolon_clauses(sentence: str) -> List[str]:
    """
    §4 — split on semicolons ONLY when both halves independently contain a
    modal (subject + modal verb). Otherwise treat ';' as a list separator,
    not a clause boundary.
    """
    if ";" not in sentence:
        return [sentence]

    halves = [h.strip() for h in sentence.split(";")]
    if len(halves) < 2:
        return [sentence]

    # Only split if EVERY half independently matches a modal pattern.
    # (Spec example: only the first half has a modal -> do not split;
    # second half is instead captured as rationale via clauses.py caller.)
    if all(_has_independent_modal(h) for h in halves if h):
        return halves
    return [sentence]


def segment_clauses(section_body: str) -> List[Clause]:
    """
    Full §2.5 + §4 segmentation for a section body: sentence split, then
    semicolon split where applicable. Numbered/lettered sub-list items
    (§10) are detected here too.
    """
    clauses: List[Clause] = []
    sentences = split_sentences(section_body)

    for sent in sentences:
        list_items = _split_numbered_list(sent)
        if list_items:
            for suffix, item_text in list_items:
                for sub in split_semicolon_clauses(item_text):
                    clauses.append(Clause(text=sub, is_list_item=True, list_id_suffix=suffix))
        else:
            for sub in split_semicolon_clauses(sent):
                clauses.append(Clause(text=sub))

    return clauses


_LIST_ITEM_RE = re.compile(r"(?:^|\s)\(?([a-z]|\d+)\)\s+")


def _split_numbered_list(sentence: str) -> List[tuple]:
    """
    §10 — numbered/lettered sub-lists under a single section: split into
    items with distinct suffixes (a, b, c / 1, 2, 3) if the pattern is
    present; otherwise return [] (no sub-list detected).
    """
    matches = list(_LIST_ITEM_RE.finditer(sentence))
    if len(matches) < 2:
        return []

    items = []
    for idx, m in enumerate(matches):
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(sentence)
        suffix = m.group(1)
        text = sentence[start:end].strip()
        if text:
            items.append((suffix, text))
    return items
