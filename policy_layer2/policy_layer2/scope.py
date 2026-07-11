"""
§5 Scope-Overlap Reasoning.

Organizes each of Layer 1's three flat scope dimensions (role, system,
geography) into a partial-order lattice so comparison is a
lattice-membership query rather than a string-equality check (§5.1).

Per-dimension relation in {EQUAL, SUPERSET, SUBSET, OVERLAP, DISJOINT}.
Combined relation across dimensions = conjunction, using "weakest dimension
wins": any DISJOINT dimension forces overall DISJOINT (§5.1).

§5.2: a `null` Layer 1 scope field is treated as "unscoped" => universal on
that dimension (conservative, recall-favoring default), not "unknown".
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

UNIVERSAL = "__universal__"

RELATION_STRENGTH_ORDER = ["DISJOINT", "OVERLAP", "SUPERSET", "SUBSET", "EQUAL"]


@dataclass
class Scope:
    role: Optional[str] = None
    system: Optional[str] = None
    geography: Optional[str] = None

    @classmethod
    def from_layer1(cls, d: Optional[dict]) -> "Scope":
        d = d or {}
        return cls(role=_norm(d.get("role")), system=_norm(d.get("system")), geography=_norm(d.get("geography")))


def _norm(v: Optional[str]) -> Optional[str]:
    return v.strip().lower() if isinstance(v, str) and v.strip() else None


class ScopeLattice:
    """
    Builds a transitive-closure partial order per dimension from
    Config.role_lattice_edges (extend similarly for system/geography if the
    corpus needs it -- role is the only dimension the design doc gives a
    worked lattice for; system/geography default to flat EQUAL/DISJOINT-only
    comparison unless a lattice table is supplied).
    """

    def __init__(self, config):
        self.config = config
        self._role_superset_of: Dict[str, Set[str]] = self._close(config.role_lattice_edges)
        self._role_incomparable: Set[frozenset] = {
            frozenset(pair) for pair in config.role_incomparable_pairs
        }

    @staticmethod
    def _close(edges: Dict[str, List[str]]) -> Dict[str, Set[str]]:
        closure: Dict[str, Set[str]] = {k: set(v) for k, v in edges.items()}
        changed = True
        while changed:
            changed = False
            for parent, children in list(closure.items()):
                for child in list(children):
                    grandchildren = closure.get(child, set())
                    new = grandchildren - closure[parent]
                    if new:
                        closure[parent] |= new
                        changed = True
        return closure

    def role_relation(self, a: Optional[str], b: Optional[str]) -> str:
        return self._dimension_relation(a, b, self._role_superset_of, self._role_incomparable)

    def system_relation(self, a: Optional[str], b: Optional[str]) -> str:
        return self._flat_relation(a, b)

    def geography_relation(self, a: Optional[str], b: Optional[str]) -> str:
        return self._flat_relation(a, b)

    def _flat_relation(self, a: Optional[str], b: Optional[str]) -> str:
        a_univ, b_univ = a is None, b is None
        if a_univ and b_univ:
            return "EQUAL"
        if a_univ and not b_univ:
            return "SUPERSET"
        if b_univ and not a_univ:
            return "SUBSET"
        if a == b:
            return "EQUAL"
        return "DISJOINT"

    def _dimension_relation(
        self, a: Optional[str], b: Optional[str], superset_of: Dict[str, Set[str]], incomparable: Set[frozenset]
    ) -> str:
        a_univ, b_univ = a is None, b is None
        if a_univ and b_univ:
            return "EQUAL"
        if a_univ and not b_univ:
            return "SUPERSET"
        if b_univ and not a_univ:
            return "SUBSET"
        if a == b:
            return "EQUAL"
        if frozenset({a, b}) in incomparable:
            return "DISJOINT"
        if b in superset_of.get(a, set()):
            return "SUPERSET"
        if a in superset_of.get(b, set()):
            return "SUBSET"
        # related-but-neither-nested dimensions (e.g. two different named
        # departments) default to OVERLAP-vs-DISJOINT via simple equality
        # already handled above; anything else with no lattice edge is
        # treated as DISJOINT (conservative: don't invent a relation the
        # lattice table doesn't encode).
        return "DISJOINT"


@dataclass
class ScopeOverlapResult:
    role: str
    system: str
    geography: str
    combined: str

    def as_dict(self) -> Dict[str, str]:
        return {"role": self.role, "system": self.system, "geography": self.geography, "combined": self.combined}


def compare_scopes(lattice: ScopeLattice, a: Scope, b: Scope) -> ScopeOverlapResult:
    role_rel = lattice.role_relation(a.role, b.role)
    system_rel = lattice.system_relation(a.system, b.system)
    geo_rel = lattice.geography_relation(a.geography, b.geography)
    combined = _combine([role_rel, system_rel, geo_rel])
    return ScopeOverlapResult(role=role_rel, system=system_rel, geography=geo_rel, combined=combined)


def _combine(relations: List[str]) -> str:
    """
    Conjunction across dimensions: overall relation is only as strong as its
    weakest dimension (§5.1). DISJOINT on any dimension => overall DISJOINT.
    Otherwise: all EQUAL => EQUAL; consistent SUPERSET (or EQUAL) on every
    dimension => SUPERSET; consistent SUBSET (or EQUAL) => SUBSET; anything
    else (a mix of SUPERSET/SUBSET/OVERLAP across dimensions) => OVERLAP,
    since the populations intersect without either side fully containing
    the other (the "EU data" x "cloud-hosted systems" case, §5.1).
    """
    if "DISJOINT" in relations:
        return "DISJOINT"
    if all(r == "EQUAL" for r in relations):
        return "EQUAL"
    if all(r in ("EQUAL", "SUPERSET") for r in relations):
        return "SUPERSET"
    if all(r in ("EQUAL", "SUBSET") for r in relations):
        return "SUBSET"
    return "OVERLAP"


def scope_breadth_rank(scope: Scope, lattice: ScopeLattice) -> int:
    """
    Ordinal breadth proxy for §9 impact scoring (wider scope = higher rank),
    using the lattice's partial order rather than a fabricated headcount
    (§5.3). 0 = fully unscoped (broadest), higher = narrower.
    """
    rank = 0
    for v in (scope.role, scope.system, scope.geography):
        if v is not None:
            rank += 1
    return rank
