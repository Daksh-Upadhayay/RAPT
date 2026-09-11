"""Text embeddings for knowledge-base search (RAG).

Not a classifier (see 02-ml-models.md): this turns text into vectors so pgvector can find
knowledge-base entries close in meaning to a ticket. The model (bge-small) is separate
from the MiniLM model behind the urgency classifier's features; see DECISIONS.md.
"""

from functools import cache

import numpy as np

from app.core.config import EMBEDDING_DIM, settings
from app.ml.text_features import embed, sentence_model


class TextTooLongError(ValueError):
    """The text exceeds what the embedding model reads; the rest would be silently ignored."""


def document_text(title: str, content: str) -> str:
    """What gets embedded for a knowledge-base entry."""
    return f"{title}. {content}"


@cache
def _max_tokens() -> int:
    return sentence_model(settings.embedding_model).max_seq_length


def token_count(text: str) -> int:
    return len(sentence_model(settings.embedding_model).tokenizer(text)["input_ids"])


def embed_texts(texts: list[str]) -> np.ndarray:
    """Unit-length embeddings, one row per text (so cosine similarity = dot product)."""
    vectors = embed(texts, settings.embedding_model)
    if vectors.shape[1] != EMBEDDING_DIM:
        raise RuntimeError(
            f"{settings.embedding_model} produces {vectors.shape[1]}-d vectors but the knowledge_base "
            f"column is {EMBEDDING_DIM}-d; add a migration and re-embed before switching models"
        )
    return vectors


def embed_document(title: str, content: str) -> np.ndarray:
    """Embed a knowledge-base entry, refusing text the model would truncate."""
    text = document_text(title, content)
    if (n := token_count(text)) > _max_tokens():
        raise TextTooLongError(
            f"Entry is {n} tokens; the embedding model reads only {_max_tokens()}. Split it into smaller entries."
        )
    return embed_texts([text])[0]


def embed_query(text: str) -> np.ndarray:
    """Embed a search query (ticket text), with the model's query instruction in front.
    Long tickets are truncated, which is fine for retrieval: the opening of a ticket
    usually states the problem."""
    return embed_texts([settings.embedding_query_prefix + text])[0]
