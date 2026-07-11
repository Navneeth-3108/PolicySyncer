"""
§2.2 Candidate Pair Generation & Blocking, §3.3 Stage A.

Avoids O(n^2) full-NLI comparison across every obligation pair in a 30-policy
corpus. A pair is only promoted to Stage B (conflict.py / redundancy.py) when:
  (a) category_primary matches, or one is in the other's category_secondary, AND
  (b) action_canonical embedding cosine similarity >= blocking_similarity_threshold

This is a low, recall-favoring bar (§3.3) -- its only job is to avoid
comparing unrelated obligations, not to decide conflict/redundancy.
"""

from itertools import combinations
from typing import List, Tuple

from .normalize import DeonticProposition
from .similarity import SimilarityEngine


def category_compatible(a: DeonticProposition, b: DeonticProposition) -> bool:
    if a.category_primary and a.category_primary == b.category_primary:
        return True
    if a.category_primary and a.category_primary in (b.category_secondary or []):
        return True
    if b.category_primary and b.category_primary in (a.category_secondary or []):
        return True
    return False


def generate_candidate_pairs(
    propositions: List[DeonticProposition],
    sim_engine: SimilarityEngine,
    config,
) -> List[Tuple[DeonticProposition, DeonticProposition, float]]:
    """Returns (a, b, action_similarity) triples that survive Stage A blocking."""
    sim_engine.fit_corpus([p.action_text_for_embedding for p in propositions])

    candidates: List[Tuple[DeonticProposition, DeonticProposition, float]] = []
    for a, b in combinations(propositions, 2):
        if a.obligation_id == b.obligation_id:
            continue
        if not category_compatible(a, b):
            continue
        sim = sim_engine.similarity(a.action_text_for_embedding, b.action_text_for_embedding)
        if sim >= config.blocking_similarity_threshold:
            candidates.append((a, b, sim))
    return candidates
