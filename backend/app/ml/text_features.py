"""Text preprocessing and hand-crafted tone features shared by training and inference.

Everything here is referenced by the saved sklearn pipelines, so it must stay importable
under the same module path (pickled pipelines store `app.ml.text_features.<name>`).
"""

import re
from functools import cache

import numpy as np
from scipy import sparse
from sklearn.base import BaseEstimator, TransformerMixin
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_DIGITS = re.compile(r"\d+")
_WORD = re.compile(r"[A-Za-z]{3,}")


def normalize_text(text: str) -> str:
    """TF-IDF preprocessor: lowercase and collapse numbers, so order ids and amounts
    don't become thousands of one-off features."""
    return _DIGITS.sub("0", text.lower())


@cache
def _vader() -> SentimentIntensityAnalyzer:
    return SentimentIntensityAnalyzer()


def sentiment(text: str) -> dict[str, float]:
    """VADER scores: `neg`/`neu`/`pos` proportions and `compound` in [-1, 1]."""
    return _vader().polarity_scores(text)


def caps_ratio(text: str) -> float:
    """Share of words (3+ letters) written in ALL CAPS."""
    words = _WORD.findall(text)
    return sum(w.isupper() for w in words) / len(words) if words else 0.0


class ToneFeatures(BaseEstimator, TransformerMixin):
    """Dense tone signals the TF-IDF features can't see (TF-IDF lowercases and drops
    punctuation): sentiment, shouting, exclamation/question density, length."""

    FEATURES = ("vader_compound", "vader_neg", "vader_pos", "caps_ratio", "exclamations", "questions", "log_length")

    def fit(self, X, y=None):
        return self

    def transform(self, X) -> sparse.csr_matrix:
        rows = []
        for text in X:
            scores = sentiment(text)
            rows.append(
                [
                    scores["compound"],
                    scores["neg"],
                    scores["pos"],
                    caps_ratio(text),
                    min(text.count("!"), 5),
                    min(text.count("?"), 5),
                    np.log1p(len(text)),
                ]
            )
        return sparse.csr_matrix(np.asarray(rows, dtype=np.float32).reshape(-1, len(self.FEATURES)))

    def get_feature_names_out(self, input_features=None) -> np.ndarray:
        return np.asarray(self.FEATURES, dtype=object)


@cache
def _sentence_model(model_name: str):
    # Imported lazily: torch is slow to import and only the urgency model needs it
    from sentence_transformers import SentenceTransformer

    # Prefer the local Hugging Face cache: skips a network check on every process start
    try:
        return SentenceTransformer(model_name, local_files_only=True)
    except OSError:
        return SentenceTransformer(model_name)  # first run: download the weights


_EMBED_CACHE: dict[tuple[str, str], np.ndarray] = {}
_EMBED_CACHE_MAX = 50_000  # ~75 MB of 384-d vectors; cleared when full


def embed(texts: list[str], model_name: str) -> np.ndarray:
    """Unit-length sentence embeddings, one row per text.

    Cached per text: training (cross-validation especially) embeds the same texts many times.
    """
    missing = list(dict.fromkeys(t for t in texts if (model_name, t) not in _EMBED_CACHE))
    if missing:
        if len(_EMBED_CACHE) + len(missing) > _EMBED_CACHE_MAX:
            _EMBED_CACHE.clear()
        vectors = _sentence_model(model_name).encode(
            missing, batch_size=64, normalize_embeddings=True, show_progress_bar=False
        )
        _EMBED_CACHE.update(((model_name, t), v) for t, v in zip(missing, vectors, strict=True))
    return np.stack([_EMBED_CACHE[(model_name, t)] for t in texts])


class SentenceEmbeddings(BaseEstimator, TransformerMixin):
    """Pretrained sentence-transformer embeddings as features: they capture meaning
    ("starting to wonder if it got lost") that keyword features can't. Only the model
    name is pickled; the weights load from the Hugging Face cache on first use."""

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name

    def fit(self, X, y=None):
        self.dim_ = _sentence_model(self.model_name).get_embedding_dimension()
        return self

    def transform(self, X) -> sparse.csr_matrix:
        return sparse.csr_matrix(embed(list(X), self.model_name))

    def get_feature_names_out(self, input_features=None) -> np.ndarray:
        return np.asarray([f"emb_{i}" for i in range(self.dim_)], dtype=object)
