"""Local semantic engine.

Two interchangeable backends:
  sbert  - sentence-transformers embeddings (install requirements-semantic.txt)
  tfidf  - TF-IDF vectors with cosine similarity (scikit-learn, no download)

Both expose the same cosine-similarity interface. The active backend is always
reported so that results are interpreted correctly: TF-IDF measures weighted
term overlap, while sentence embeddings capture paraphrase and meaning.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from config.scoring import CALIBRATION
from config.settings import Settings, get_settings
from utils.cache import stable_hash

log = logging.getLogger("citation_analyser.semantic")
_ENGINES: dict[tuple[str, str], "SemanticEngine"] = {}


def cosine_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Cosine similarity between each row of a and each row of b."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.size == 0 or b.size == 0:
        return np.zeros((a.shape[0], b.shape[0]))
    an = np.linalg.norm(a, axis=1, keepdims=True)
    bn = np.linalg.norm(b, axis=1, keepdims=True)
    an[an == 0] = 1.0
    bn[bn == 0] = 1.0
    return (a / an) @ (b / bn).T


class SemanticEngine:
    def __init__(self, backend: str = "auto", model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        self.requested = backend
        self.model_name = model_name
        self.backend = "tfidf"
        self.note = ""
        self._model = None
        self._emb_cache: dict[str, np.ndarray] = {}
        if backend in ("auto", "sbert"):
            self._try_load_sbert(strict=(backend == "sbert"))
        else:
            self.note = "TF-IDF backend selected. Similarity reflects weighted term overlap, not deep meaning."

    # ---------------------------------------------------------------- setup
    def _try_load_sbert(self, strict: bool) -> None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            self._model = SentenceTransformer(self.model_name)
            self.backend = "sbert"
            self.note = f"Sentence embeddings ({self.model_name}) with cosine similarity."
        except Exception as exc:
            reason = type(exc).__name__
            self.backend = "tfidf"
            if strict:
                self.note = (f"Sentence-transformers could not be loaded ({reason}). "
                             "TF-IDF similarity was used instead.")
            else:
                self.note = ("Sentence-transformers is not installed or the model is unavailable. "
                             "TF-IDF similarity (weighted term overlap) was used. See README to enable embeddings.")
            log.info("sbert unavailable: %s", reason)

    # ---------------------------------------------------------------- core API
    def similarity(self, queries: list[str], texts: list[str]) -> np.ndarray:
        """Matrix of shape (len(queries), len(texts)) with cosine similarities in [0, 1]."""
        queries = [q or "" for q in queries]
        texts = [t or "" for t in texts]
        if not queries or not texts:
            return np.zeros((len(queries), len(texts)))
        if self.backend == "sbert" and self._model is not None:
            try:
                qe = self._embed(queries)
                te = self._embed(texts)
                return np.clip(cosine_matrix(qe, te), 0, 1)
            except Exception as exc:
                log.warning("Embedding failed, falling back to TF-IDF: %s", type(exc).__name__)
                self.backend = "tfidf"
                self.note = "Embedding computation failed. TF-IDF similarity was used instead."
        return self._tfidf_similarity(queries, texts)

    def _embed(self, texts: list[str]) -> np.ndarray:
        keys = [stable_hash(self.model_name, t) for t in texts]
        missing = [i for i, k in enumerate(keys) if k not in self._emb_cache]
        if missing:
            vecs = self._model.encode([texts[i] for i in missing], normalize_embeddings=True, show_progress_bar=False)
            for i, v in zip(missing, vecs):
                self._emb_cache[keys[i]] = np.asarray(v)
        return np.vstack([self._emb_cache[k] for k in keys])

    @staticmethod
    def _tfidf_similarity(queries: list[str], texts: list[str]) -> np.ndarray:
        from sklearn.feature_extraction.text import TfidfVectorizer

        corpus = texts + queries
        try:
            vec = TfidfVectorizer(stop_words="english", sublinear_tf=True, ngram_range=(1, 2), min_df=1)
            mat = vec.fit_transform(corpus).toarray()
        except ValueError:  # empty vocabulary
            return np.zeros((len(queries), len(texts)))
        t_mat, q_mat = mat[: len(texts)], mat[len(texts):]
        return np.clip(cosine_matrix(q_mat, t_mat), 0, 1)

    def pairwise(self, a: str, b: str) -> float:
        return float(self.similarity([a], [b])[0, 0])

    def cluster(self, texts: list[str], k: int = 4) -> list[int]:
        """Group passages into topical clusters. Returns a cluster label per text."""
        if len(texts) < 3:
            return [0] * len(texts)
        k = max(2, min(k, len(texts) // 2 or 2))
        try:
            from sklearn.cluster import KMeans

            if self.backend == "sbert" and self._model is not None:
                x = self._embed(texts)
            else:
                from sklearn.feature_extraction.text import TfidfVectorizer

                x = TfidfVectorizer(stop_words="english", sublinear_tf=True).fit_transform(texts).toarray()
            return [int(v) for v in KMeans(n_clusters=k, n_init=5, random_state=0).fit_predict(x)]
        except Exception:
            return [0] * len(texts)

    # ---------------------------------------------------------------- calibration helpers
    def sim_to_score(self, sim: float) -> float:
        lo, hi = CALIBRATION["sim_range"][self.backend]
        return float(max(0.0, min(100.0, (sim - lo) / (hi - lo) * 100)))

    @property
    def relevance_threshold(self) -> float:
        return CALIBRATION["relevance_threshold"][self.backend]

    @property
    def coverage_high(self) -> float:
        return CALIBRATION["coverage_high_sim"][self.backend]

    @property
    def coverage_low(self) -> float:
        return CALIBRATION["coverage_low_sim"][self.backend]


def get_engine(settings: Optional[Settings] = None) -> SemanticEngine:
    s = settings or get_settings()
    key = (s.semantic_backend, s.embedding_model)
    if key not in _ENGINES:
        _ENGINES[key] = SemanticEngine(s.semantic_backend, s.embedding_model)
    return _ENGINES[key]
