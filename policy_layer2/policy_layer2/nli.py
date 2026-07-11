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

_NEGATION_CUES = {
    "not", "no", "never", "without", "prohibited", "forbidden", "must not",
    "shall not", "may not", "disallowed", "banned",
}


def _try_load_hf_nli():
    global _HF_PIPELINE, _HF_AVAILABLE
    if _HF_PIPELINE is not None or _HF_AVAILABLE:
        return
    try:
        from transformers import pipeline  # type: ignore
        _HF_PIPELINE = pipeline("text-classification", model="microsoft/deberta-v3-base-mnli")
        _HF_AVAILABLE = True
    except Exception:
        _HF_PIPELINE = None
        _HF_AVAILABLE = False


class NLIEngine:
    def __init__(self, config):
        self.config = config
        _try_load_hf_nli()
        self.backend = "transformers-nli" if _HF_AVAILABLE else "heuristic-fallback"

    def contradiction_score(
        self,
        premise: str,
        hypothesis: str,
        modality_a: Optional[str] = None,
        modality_b: Optional[str] = None,
    ) -> float:
        """Returns P(contradiction) in [0, 1]."""
        if _HF_AVAILABLE:
            return self._hf_score(premise, hypothesis)
        return self._heuristic_contradiction_score(premise, hypothesis, modality_a, modality_b)

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
        self, premise: str, hypothesis: str, modality_a: Optional[str], modality_b: Optional[str]
    ) -> float:
        p = (premise or "").lower()
        h = (hypothesis or "").lower()
        score = 0.0

        # Deontic opposition is the dominant signal for this heuristic --
        # consistent with Design Principle 4 (symbolic structure constrains
        # statistical scoring, not the reverse).
        opposing_pairs = {
            frozenset({"OBLIGATION", "PROHIBITION"}),
            frozenset({"PERMISSION", "PROHIBITION"}),
        }
        if modality_a and modality_b and frozenset({modality_a, modality_b}) in opposing_pairs:
            score += 0.55

        # Lexical negation asymmetry: one side carries an explicit negation
        # cue the other lacks, over otherwise-similar text.
        neg_p = any(cue in p for cue in _NEGATION_CUES)
        neg_h = any(cue in h for cue in _NEGATION_CUES)
        if neg_p != neg_h:
            score += 0.25

        return max(0.0, min(1.0, score))
