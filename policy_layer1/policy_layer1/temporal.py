"""
§5.6 Temporal constraint extraction.
"""

import re
from typing import Optional

from .schema import TemporalConstraint

_RECUR_RE = re.compile(r"\bevery\s+(\d+)\s+(day|days|month|months|year|years)\b", re.IGNORECASE)
_DURATION_RE = re.compile(r"\bfor\s+(\d+)\s+(day|days|month|months|year|years)\b", re.IGNORECASE)
_DEADLINE_RE = re.compile(r"\bwithin\s+(\d+)\s+(hour|hours|day|days)\b", re.IGNORECASE)
_ABS_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")

_UNIT_TO_DAYS = {
    "hour": 1 / 24,
    "hours": 1 / 24,
    "day": 1,
    "days": 1,
    "month": 30,
    "months": 30,
    "year": 365,
    "years": 365,
}


def _to_days(n: int, unit: str) -> int:
    days = n * _UNIT_TO_DAYS[unit.lower()]
    return int(round(days))


def extract_temporal(clause_text: str):
    """
    Returns (TemporalConstraint | None, flags: list[str]).
    Edge case (§5.6): bare counts like "previous 10 passwords" are NOT
    temporal — only fire when a time-unit noun immediately follows the
    number, which the regexes above already enforce structurally.
    """
    flags = []

    m = _RECUR_RE.search(clause_text)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        return TemporalConstraint(
            type="recurring", value=n, unit=unit, value_days=_to_days(n, unit)
        ), flags

    m = _DURATION_RE.search(clause_text)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        return TemporalConstraint(
            type="duration", value=n, unit=unit, value_days=_to_days(n, unit)
        ), flags

    m = _DEADLINE_RE.search(clause_text)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        return TemporalConstraint(
            type="deadline", value=n, unit=unit, value_days=_to_days(n, unit)
        ), flags

    m = _ABS_DATE_RE.search(clause_text)
    if m:
        return TemporalConstraint(type="absolute_date", abs_date=m.group(1)), flags

    return None, flags
