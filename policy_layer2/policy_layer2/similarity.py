"""
§3.2 / §4.2 sentence-embedding similarity.

Mirrors Layer 1's spaCy-optionality pattern: the core pipeline has zero hard
third-party dependencies. If `sentence-transformers` is importable and
Config.use_sentence_transformers_if_available is True, it is used (this is
the SBERT approach the design doc cites, Reimers & Gurevych 2019). Otherwise
this module falls back to a pure-stdlib TF-IDF-weighted cosine similarity
over token bags, which is a much weaker paraphrase detector (it will miss
"rotate passwords" vs "refresh credentials" style zero-lexical-overlap
paraphrases) but keeps the pipeline runnable with nothing installed and is
sufficient for Stage-A blocking (§3.3), whose bar is deliberately low.

This fallback boundary is the single largest source of recall loss for the
paraphrase-driven cases named in the design doc, and is flagged as such in
the module docstring rather than silently accepted -- upgrading to a real
sentence-embedding model (SBERT or later) should be treated as a required
step before Stage B (NLI confirmation) is trusted in production, not an
optional nicety.
"""

import math
import re
from collections import Counter
from typing import Dict, List, Optional

_SBERT_MODEL = None
_SBERT_AVAILABLE = False


def _try_load_sbert(model_name: str):
    global _SBERT_MODEL, _SBERT_AVAILABLE
    if _SBERT_MODEL is not None or _SBERT_AVAILABLE:
        return
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        _SBERT_MODEL = SentenceTransformer(model_name)
        _SBERT_AVAILABLE = True
    except Exception:
        _SBERT_MODEL = None
        _SBERT_AVAILABLE = False


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall((text or "").lower())


class SimilarityEngine:
    """
    Computes pairwise semantic similarity for action_canonical / raw_text.
    Caches per-string vectors within a single Layer 2 run so an N-document
    corpus only embeds each unique string once (relevant once blocking, §3.3,
    fans a single obligation out against many candidates).
    """

    def __init__(self, config):
        self.config = config
        self._cache: Dict[str, object] = {}
        self._idf_corpus: Optional[List[str]] = None
        self._idf: Optional[Dict[str, float]] = None
        if config.use_sentence_transformers_if_available:
            _try_load_sbert(config.embedding_model_name)
        self.backend = "sentence-transformers" if _SBERT_AVAILABLE else "tfidf-fallback"

    # ---- corpus-level IDF fit, only used by the fallback backend ----
    def fit_corpus(self, all_texts: List[str]) -> None:
        if _SBERT_AVAILABLE:
            return
        df: Counter = Counter()
        n = 0
        for t in all_texts:
            toks = set(_tokenize(t))
            if not toks:
                continue
            n += 1
            for tok in toks:
                df[tok] += 1
        n = max(n, 1)
        self._idf = {tok: math.log((n + 1) / (c + 1)) + 1.0 for tok, c in df.items()}

    def _embed(self, text: str):
        if text in self._cache:
            return self._cache[text]
        if _SBERT_AVAILABLE:
            vec = _SBERT_MODEL.encode([text])[0]
        else:
            vec = self._tfidf_vector(text)
        self._cache[text] = vec
        return vec

    def _tfidf_vector(self, text: str) -> Dict[str, float]:
        idf = self._idf or {}
        counts = Counter(_tokenize(text))
        total = sum(counts.values()) or 1
        return {tok: (c / total) * idf.get(tok, 1.0) for tok, c in counts.items()}

    def similarity(self, text_a: str, text_b: str) -> float:
        """Cosine similarity in [0, 1] (clamped)."""
        if not text_a or not text_b:
            return 0.0
        va = self._embed(text_a)
        vb = self._embed(text_b)
        if _SBERT_AVAILABLE:
            sim = self._cosine_dense(va, vb)
        else:
            sim = self._cosine_sparse(va, vb)
        return float(max(0.0, min(1.0, sim)))

    @staticmethod
    def _cosine_dense(va, vb) -> float:
        dot = sum(x * y for x, y in zip(va, vb))
        na = math.sqrt(sum(x * x for x in va))
        nb = math.sqrt(sum(y * y for y in vb))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    @staticmethod
    def _cosine_sparse(va: Dict[str, float], vb: Dict[str, float]) -> float:
        if not va or not vb:
            return 0.0
        keys = set(va) & set(vb)
        dot = sum(va[k] * vb[k] for k in keys)
        na = math.sqrt(sum(v * v for v in va.values()))
        nb = math.sqrt(sum(v * v for v in vb.values()))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)
