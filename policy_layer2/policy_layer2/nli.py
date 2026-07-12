"""
§3.3 Stage B: semantic confirmation via sentence-pair NLI.

Same optionality pattern as similarity.py. If `transformers` is importable
and a local/cached NLI checkpoint can be loaded, it is used to produce a
proper entailment/neutral/contradiction distribution (the ContractNLI-style
task the design doc cites, Koreeda & Manning 2021). Because this reference
implementation cannot assume network access to download a checkpoint, the
default path is a **heuristic stand-in**, documented as exactly that: it is
NOT a claim that heuristic negation-cue matching is an adequate substitute
for a trained NLI model in production. It exists so Stage B has a
deterministic, testable contract to run against, and so the fusion/scoring
stage (confidence.py) can be developed and evaluated independently of which
NLI backend is plugged in later -- swapping in a real model means replacing
only `_heuristic_contradiction_score`.
"""

from typing import Optional

_HF_PIPELINE = None
_HF_AVAILABLE = False

# Candidate MNLI checkpoints, tried in order. The original hardcoded id
# "microsoft/deberta-v3-base-mnli" was REMOVED from the HuggingFace Hub (its
# config.json now 404s), so Stage B could never load and the pipeline silently
# ran on the heuristic stand-in forever. These are current, publicly available
# MNLI models that expose the same entailment/neutral/contradiction labels the
# _hf_score reader expects; the first that loads wins.
_DEFAULT_NLI_MODELS = [
    "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
    "roberta-large-mnli",
    "facebook/bart-large-mnli",
]


def _try_load_hf_nli(model_candidates=None):
    global _HF_PIPELINE, _HF_AVAILABLE
    if _HF_PIPELINE is not None or _HF_AVAILABLE:
        return
    try:
        from transformers import pipeline  # type: ignore
    except Exception:
        _HF_PIPELINE, _HF_AVAILABLE = None, False
        return
    for model_name in (model_candidates or _DEFAULT_NLI_MODELS):
        try:
            _HF_PIPELINE = pipeline("text-classification", model=model_name)
            _HF_AVAILABLE = True
            return
        except Exception:
            continue
    _HF_PIPELINE, _HF_AVAILABLE = None, False


class NLIEngine:
    def __init__(self, config):
        self.config = config
        _try_load_hf_nli(getattr(config, "nli_model_candidates", None))
        self.backend = "transformers-nli" if _HF_AVAILABLE else "heuristic-fallback"

    def contradiction_score(
        self,
        premise: str,
        hypothesis: str,
        modality_a: Optional[str] = None,
        modality_b: Optional[str] = None,
        action_similarity: float = 0.0,
    ) -> float:
        """Returns P(contradiction) in [0, 1]."""
        if _HF_AVAILABLE:
            return self._hf_score(premise, hypothesis)
        return self._heuristic_contradiction_score(
            premise, hypothesis, modality_a, modality_b, action_similarity
        )

    def _hf_score(self, premise: str, hypothesis: str) -> float:
        try:
            result = _HF_PIPELINE({"text": premise, "text_pair": hypothesis})
            for r in (result if isinstance(result, list) else [result]):
                if str(r.get("label", "")).lower().startswith("contra"):
                    return float(r.get("score", 0.0))
            return 0.0
        except Exception:
            return 0.5  # backend failed at call time; treat as maximally uncertain

    def _heuristic_contradiction_score(
        self,
        premise: str,
        hypothesis: str,
        modality_a: Optional[str],
        modality_b: Optional[str],
        action_similarity: float,
    ) -> float:
        score = 0.0

        # Deontic opposition is the dominant signal for this heuristic --
        # consistent with Design Principle 4 (symbolic structure constrains
        # statistical scoring, not the reverse). But modality alone is not
        # independent evidence: Layer 1 already assigns PROHIBITION using
        # the same negation lexicon this module used to re-check, so gating
        # on negation cues again was circular. Instead, corroborate with
        # action similarity -- a signal derived from the *actions* being
        # compared, not from the modality classification itself.
        opposing_pairs = {
            frozenset({"OBLIGATION", "PROHIBITION"}),
            frozenset({"PERMISSION", "PROHIBITION"}),
        }
        modal_pair = frozenset({modality_a, modality_b}) if modality_a and modality_b else frozenset()
        if modal_pair in opposing_pairs:
            if action_similarity >= self.config.action_similarity_high_threshold:
                score += 0.55  # same action, opposing modality = real contradiction
            else:
                score += 0.15  # opposing modality alone, weak/no action overlap

        return max(0.0, min(1.0, score))
