"""
Output schema (spec §8): the Layer 1 -> Layer 2 contract.

These dataclasses serialize to exactly the JSON shape shown in §8 of the
spec via to_dict().
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any


@dataclass
class Scope:
    role: Optional[str] = None
    system: Optional[str] = None
    geography: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"role": self.role, "system": self.system, "geography": self.geography}


@dataclass
class TemporalConstraint:
    type: str  # "recurring" | "duration" | "deadline" | "absolute_date"
    value: Optional[int] = None
    unit: Optional[str] = None
    value_days: Optional[int] = None
    abs_date: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Exception_:
    text: str
    scope_override: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"text": self.text, "scope_override": self.scope_override}


@dataclass
class ObligationRecord:
    obligation_id: str
    source_section: str
    raw_text: str
    modal_raw: str
    modal_normalized: str  # OBLIGATION | PROHIBITION | RECOMMENDATION | PERMISSION
    modal_strength: int  # 1-3
    polarity: str  # POSITIVE | NEGATIVE
    actor: str
    action: str
    object: Optional[str]
    section_ref: Optional[str] = None  # e.g. "3.1" -- human-readable section label (Layer 3 citation)
    qualifiers: List[str] = field(default_factory=list)
    scope: Scope = field(default_factory=Scope)
    temporal_constraint: Optional[TemporalConstraint] = None
    exception: Optional[Exception_] = None
    rationale_text: Optional[str] = None  # §4 — attached non-modal clause text
    category_primary: str = "other"
    category_secondary: List[str] = field(default_factory=list)
    confidence: float = 1.0
    confidence_tier: str = "HIGH"
    extraction_flags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "obligation_id": self.obligation_id,
            "source_section": self.source_section,
            "raw_text": self.raw_text,
            "modal_raw": self.modal_raw,
            "modal_normalized": self.modal_normalized,
            "modal_strength": self.modal_strength,
            "polarity": self.polarity,
            "actor": self.actor,
            "action": self.action,
            "object": self.object,
            "section_ref": self.section_ref,
            "qualifiers": self.qualifiers,
            "scope": self.scope.to_dict(),
            "temporal_constraint": (
                self.temporal_constraint.to_dict() if self.temporal_constraint else None
            ),
            "exception": self.exception.to_dict() if self.exception else None,
            "rationale_text": self.rationale_text,
            "category_primary": self.category_primary,
            "category_secondary": self.category_secondary,
            "confidence": round(self.confidence, 3),
            "confidence_tier": self.confidence_tier,
            "extraction_flags": self.extraction_flags,
        }


@dataclass
class PolicyMetadata:
    policy_name: str
    version: Optional[str]
    last_reviewed: Optional[str]
    metadata_flags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PolicyRecord:
    policy_metadata: PolicyMetadata
    obligations: List[ObligationRecord] = field(default_factory=list)
    cross_references: List[Dict[str, str]] = field(default_factory=list)
    definitional_statements: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_metadata": self.policy_metadata.to_dict(),
            "obligations": [o.to_dict() for o in self.obligations],
            "cross_references": self.cross_references,
            "definitional_statements": self.definitional_statements,
        }
