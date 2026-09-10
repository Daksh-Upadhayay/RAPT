from collections.abc import Sequence

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.embeddings import TextTooLongError, embed_document, embed_query
from app.models import KnowledgeBaseEntry
from app.schemas.knowledge_base import KnowledgeBaseCreate, RetrievedDoc

__all__ = ["TextTooLongError", "create_entry", "list_entries", "search"]


async def create_entry(session: AsyncSession, data: KnowledgeBaseCreate) -> KnowledgeBaseEntry:
    # Embedding is CPU-bound model inference: keep it off the event loop
    embedding = await run_in_threadpool(embed_document, data.title, data.content)
    entry = KnowledgeBaseEntry(title=data.title, content=data.content, embedding=embedding)
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry


async def list_entries(session: AsyncSession) -> Sequence[KnowledgeBaseEntry]:
    return (await session.scalars(select(KnowledgeBaseEntry).order_by(KnowledgeBaseEntry.title))).all()


async def search(session: AsyncSession, text: str, k: int = 3) -> list[RetrievedDoc]:
    """The k entries closest in meaning to `text` (cosine distance via pgvector)."""
    query = await run_in_threadpool(embed_query, text)
    distance = KnowledgeBaseEntry.embedding.cosine_distance(query)
    rows = await session.execute(select(KnowledgeBaseEntry, distance.label("distance")).order_by(distance).limit(k))
    return [
        RetrievedDoc(id=str(entry.id), title=entry.title, content=entry.content, similarity=round(1 - dist, 4))
        for entry, dist in rows
    ]
