"""
§8 Confidence Propagation.

Two explicit stages, kept separate in the output schema:

1. Extraction-confidence gate: source_layer1_confidence = MIN (not product)
   of the contributing obligations' Layer 1 confidence scores (§8.2.1).
2. Reasoning-confidence combination: weighted LINEAR combination (not
   product) of modality_certainty, scope_certainty, nli_score,
   embedding_similarity (§8.2.2).

Final confidence = source_layer1_confidence (hard cap) x reasoning_confidence
(graded signal within that cap) (§8.2.3) -- retains a multiplicative *cap*
relationship while avoiding multiplicative *collapse* within the reasoning
combination itself (§8.1's rejection of naive score-multiplication).
"""

from dataclasses import dataclass

_SCOPE_CERTAINTY_BY_RELATION = {
    "EQUAL": 1.0,
    "SUPERSET": 0.85,
    "SUBSET": 0.85,
    "OVERLAP": 0.55,
    "DISJOINT": 0.0,  # should never reach here -- disjoint is gated upstream
}


@dataclass
class ConfidenceResult:
    source_layer1_confidence: float
    reasoning_confidence: float
    final_confidence: float


def compute_confidence(
    layer1_confidence_a: float,
    layer1_confidence_b: float,
    modality_certainty: float,
    scope_relation: str,
    nli_score: float,
    embedding_similarity: float,
    config,
) -> ConfidenceResult:
    source_conf = min(layer1_confidence_a, layer1_confidence_b)

    scope_certainty = _SCOPE_CERTAINTY_BY_RELATION.get(scope_relation, 0.5)
    w = config.reasoning_weights
    reasoning_conf = (
        w["modality_certainty"] * modality_certainty
        + w["scope_certainty"] * scope_certainty
        + w["nli_score"] * nli_score
        + w["embedding_similarity"] * embedding_similarity
    )
    reasoning_conf = max(0.0, min(1.0, reasoning_conf))

    final = source_conf * reasoning_conf
    return ConfidenceResult(
        source_layer1_confidence=round(source_conf, 3),
        reasoning_confidence=round(reasoning_conf, 3),
        final_confidence=round(final, 3),
    )
