"""
§0 B4: compliance_impact is a lookup/classification sub-component, not a
generative task. category_primary (already assigned by Layer 1) is joined
against a maintained category -> framework-clause table.
"""

from typing import List, Optional

from .normalize import DeonticProposition


def lookup_compliance_impact(
    a: DeonticProposition, b: Optional[DeonticProposition], config
) -> List[str]:
    clauses = set(config.compliance_clause_table.get(a.category_primary or "", []))
    if b is not None:
        clauses |= set(config.compliance_clause_table.get(b.category_primary or "", []))
    return sorted(clauses)
