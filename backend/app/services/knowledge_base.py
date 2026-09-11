from collections.abc import Sequence

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.embeddings import TextTooLongError, embed_document, embed_query
from app.core.tenancy import tenant_of
from app.models import KnowledgeBaseEntry
from app.schemas.knowledge_base import KnowledgeBaseCreate, RetrievedDoc

__all__ = ["TextTooLongError", "create_entry", "list_entries", "search"]


async def create_entry(session: AsyncSession, data: KnowledgeBaseCreate) -> KnowledgeBaseEntry:
    # Embedding is CPU-bound model inference: keep it off the event loop
    embedding = await run_in_threadpool(embed_document, data.title, data.content)
    # tenant_id comes from the session's tenant (column default)
    entry = KnowledgeBaseEntry(title=data.title, content=data.content, embedding=embedding)
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry


async def list_entries(session: AsyncSession) -> Sequence[KnowledgeBaseEntry]:
    stmt = select(KnowledgeBaseEntry).where(KnowledgeBaseEntry.tenant_id == tenant_of(session)).order_by(KnowledgeBaseEntry.title)
    return (await session.scalars(stmt)).all()


async def search(session: AsyncSession, query_text: str, k: int = 3) -> list[RetrievedDoc]:
    """The k entries of the session's tenant closest in meaning to `query_text` (cosine
    distance via pgvector). Retrieval never crosses tenants."""
    query = await run_in_threadpool(embed_query, query_text)
    distance = KnowledgeBaseEntry.embedding.cosine_distance(query)
    # With the tenant filter the HNSW index would stop after its first candidates, which
    # may all belong to other tenants; iterative scan keeps going until k rows match.
    await session.execute(text("SET LOCAL hnsw.iterative_scan = strict_order"))
    rows = await session.execute(
        select(KnowledgeBaseEntry, distance.label("distance"))
        .where(KnowledgeBaseEntry.tenant_id == tenant_of(session))
        .order_by(distance)
        .limit(k)
    )
    return [
        RetrievedDoc(id=str(entry.id), title=entry.title, content=entry.content, similarity=round(1 - dist, 4))
        for entry, dist in rows
    ]
