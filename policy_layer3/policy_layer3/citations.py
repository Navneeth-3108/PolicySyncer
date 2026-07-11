"""
§3.1 Citation resolution.

Builds, from the originating Layer 1 records, the lookups Layer 3 needs to
turn Layer 2's obligation_id / policy_name references into human-readable
citation strings -- and nothing else. No scoring, no prose, no judgment.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


def slugify(name: str) -> str:
    """Same convention Layer 1 uses for policy_slug (pipeline.py _slugify)."""
    return re.sub(r"[^a-zA-Z0-9]+", "_", (name or "").strip().lower()).strip("_")


def _as_dict(record: Any) -> Dict[str, Any]:
    """Accept either a Layer1 PolicyRecord dataclass or its .to_dict() shape."""
    if isinstance(record, dict):
        return record
    if hasattr(record, "to_dict"):
        return record.to_dict()
    raise TypeError(f"layer1_records entries must be dicts or have .to_dict(); got {type(record)}")


@dataclass
class ObligationInfo:
    obligation_id: str
    policy_name: str
    section_ref: Optional[str]
    raw_text: str
    modal_normalized: str
    polarity: str
    modal_strength: int
    category_primary: Optional[str]
    scope: Dict[str, Optional[str]]


@dataclass
class PolicyInfo:
    policy_name: str
    slug: str
    version: Optional[str]
    last_reviewed: Optional[str]
    categories: Set[str] = field(default_factory=set)


class CitationIndex:
    """
    Built once per run_layer3() call from layer1_records. Read-only lookup
    surface for the rest of Layer 3 -- it does not compute anything Layer 2
    is responsible for.
    """

    def __init__(self) -> None:
        self.obligations: Dict[str, ObligationInfo] = {}
        self.policies: Dict[str, PolicyInfo] = {}

    @classmethod
    def build(cls, layer1_records: List[Any]) -> "CitationIndex":
        index = cls()
        for record in layer1_records:
            rd = _as_dict(record)
            meta = rd.get("policy_metadata", {}) or {}
            policy_name = meta.get("policy_name", "UNKNOWN_POLICY")
            slug = slugify(policy_name)
            policy_info = index.policies.setdefault(
                policy_name,
                PolicyInfo(
                    policy_name=policy_name,
                    slug=slug,
                    version=meta.get("version"),
                    last_reviewed=meta.get("last_reviewed"),
                ),
            )
            for ob in rd.get("obligations", []) or []:
                section_ref = ob.get("section_ref") or ob.get("source_section")
                category = ob.get("category_primary")
                if category:
                    policy_info.categories.add(category)
                index.obligations[ob.get("obligation_id", "")] = ObligationInfo(
                    obligation_id=ob.get("obligation_id", ""),
                    policy_name=policy_name,
                    section_ref=section_ref,
                    raw_text=ob.get("raw_text", ""),
                    modal_normalized=ob.get("modal_normalized", ""),
                    polarity=ob.get("polarity", ""),
                    modal_strength=int(ob.get("modal_strength", 2) or 2),
                    category_primary=category,
                    scope=ob.get("scope") or {},
                )
        return index

    def obligation_citation(self, obligation_id: str) -> str:
        """'<policy_name> §<section_ref>' -- falls back gracefully if unknown."""
        info = self.obligations.get(obligation_id)
        if info is None:
            return obligation_id  # unresolvable; surface the raw id rather than guessing
        if info.section_ref:
            return f"{info.policy_name} §{info.section_ref}"
        return info.policy_name

    def policy_citation_by_name(self, policy_name: str) -> str:
        """'<policy_name> v<version>' -- used for STALE records."""
        info = self.policies.get(policy_name)
        version = info.version if info else None
        if version:
            return f"{policy_name} v{version}"
        return policy_name

    def slug_for(self, policy_name: str) -> str:
        info = self.policies.get(policy_name)
        return info.slug if info else slugify(policy_name)

    def categories_for_policy(self, policy_name: str) -> Set[str]:
        info = self.policies.get(policy_name)
        return set(info.categories) if info else set()
