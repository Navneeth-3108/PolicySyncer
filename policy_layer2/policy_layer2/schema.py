"""
§6 Layer 2 output schema -- Finding[] + StalenessRecord[].

Deliberately has NO `recommendation` free-text field (§0 B1) and NO
`policy_health_score` (§0 B2) -- those are Layer 3 / aggregation concerns.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class Evidence:
    modality_pair: Optional[List[str]] = None
    scope_relation_per_dimension: Optional[Dict[str, str]] = None
    temporal_relation: Optional[str] = None
    trigger_mismatch_description: Optional[str] = None
    nli_contradiction_score: Optional[float] = None
    embedding_similarity_score: Optional[float] = None
    exception_match: Optional[bool] = None
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class Finding:
    finding_id: str
    finding_type: str  # CONFLICT | REDUNDANCY | SUBSUMPTION
    obligation_refs: List[str]
    evidence: Evidence
    confidence: float
    severity: str  # HIGH | MEDIUM | LOW
    scope_relation: str  # EQUAL | SUPERSET | SUBSET | OVERLAP | DISJOINT
    compliance_impact: List[str]
    source_layer1_confidence: float
    conflict_subtype: Optional[str] = None  # DIRECT | STRENGTH | TEMPORAL_TRIGGER_MISMATCH | PARTIAL_OVERLAP

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["evidence"] = self.evidence.to_dict()
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class StalenessRecord:
    policy_name: str
    version: str
    last_reviewed: Optional[str]
    months_since_review: Optional[float]
    staleness_signals: List[Dict[str, Any]]
    severity: str
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Layer2Output:
    findings: List[Finding]
    staleness: List[StalenessRecord]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "findings": [f.to_dict() for f in self.findings],
            "staleness": [s.to_dict() for s in self.staleness],
        }
