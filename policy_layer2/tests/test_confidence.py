from policy_layer2.config import Config
from policy_layer2.confidence import compute_confidence


def test_extraction_gate_is_minimum_not_product():
    config = Config()
    result = compute_confidence(
        layer1_confidence_a=0.9,
        layer1_confidence_b=0.4,
        modality_certainty=1.0,
        scope_relation="EQUAL",
        nli_score=1.0,
        embedding_similarity=1.0,
        config=config,
    )
    assert result.source_layer1_confidence == 0.4  # min, not 0.9*0.4=0.36


def test_reasoning_confidence_does_not_collapse_multiplicatively():
    config = Config()
    result = compute_confidence(
        layer1_confidence_a=0.9,
        layer1_confidence_b=0.9,
        modality_certainty=0.8,
        scope_relation="EQUAL",
        nli_score=0.8,
        embedding_similarity=0.8,
        config=config,
    )
    # naive product of four ~0.8 signals would collapse to ~0.41;
    # weighted linear combination should stay much closer to 0.8-1.0.
    assert result.reasoning_confidence > 0.75


def test_final_confidence_is_capped_by_extraction_confidence():
    config = Config()
    result = compute_confidence(
        layer1_confidence_a=0.2,
        layer1_confidence_b=0.95,
        modality_certainty=1.0,
        scope_relation="EQUAL",
        nli_score=1.0,
        embedding_similarity=1.0,
        config=config,
    )
    assert result.final_confidence <= 0.2
