"""Help documents: add (upload or paste), split into sections, embed, manage (Phase 9).

Adding a document stores its text with status `processing` and returns at once; the
sections are built and embedded in the background (`process_document`), since
embedding a long document takes a few seconds on CPU.
"""

import hashlib
import logging
import uuid
from collections.abc import Sequence

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.enums import DocumentSource, DocumentStatus
from app.core.tenancy import get_scoped, tenant_of, tenant_session
from app.knowledge.chunking import chunk
from app.ml.embeddings import document_text, embed_texts, token_count
from app.models import KnowledgeBaseEntry, KnowledgeDocument

logger = logging.getLogger(__name__)

MAX_SECTIONS = 400  # a larger document is probably not a help document; split it first
SECTION_TOKENS = 300


class DuplicateDocument(Exception):
    def __init__(self, existing: KnowledgeDocument):
        super().__init__(f"This document was already added as “{existing.title}”.")
        self.existing = existing


class DocumentNotFound(Exception):
    pass


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


async def add_document(
    session: AsyncSession, *, title: str, content: str, source: DocumentSource, filename: str | None, uploaded_by: str
) -> KnowledgeDocument:
    digest = content_hash(content)
    existing = await session.scalar(
        select(KnowledgeDocument).where(KnowledgeDocument.tenant_id == tenant_of(session), KnowledgeDocument.content_hash == digest)
    )
    if existing is not None:
        raise DuplicateDocument(existing)
    document = KnowledgeDocument(
        title=title.strip()[:200] or "Untitled",
        content=content,
        content_hash=digest,
        source=source,
        filename=filename,
        uploaded_by=uploaded_by,
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)
    return document


def _sections(document: KnowledgeDocument):
    return chunk(document.title, document.content, token_count, max_tokens=SECTION_TOKENS)


async def process_document(document_id: uuid.UUID, tenant_id: uuid.UUID, factory: async_sessionmaker[AsyncSession]) -> None:
    """Split, embed and store the sections; the document ends `ready` or `failed`."""
    async with tenant_session(factory, tenant_id) as session:
        document = await get_scoped(session, KnowledgeDocument, document_id)
        if document is None:
            return
        try:
            sections = await run_in_threadpool(_sections, document)
            if not sections:
                raise ValueError("No text to index.")
            if len(sections) > MAX_SECTIONS:
                raise ValueError(f"The document has {len(sections)} sections; split it into files of at most {MAX_SECTIONS}.")
            vectors = await run_in_threadpool(embed_texts, [document_text(s.title, s.content) for s in sections])
            # Reprocessing (after a restart) replaces any sections from the earlier attempt
            await session.execute(delete(KnowledgeBaseEntry).where(KnowledgeBaseEntry.document_id == document.id))
            session.add_all(
                KnowledgeBaseEntry(document_id=document.id, position=i, title=s.title[:200], content=s.content, embedding=v)
                for i, (s, v) in enumerate(zip(sections, vectors, strict=True))
            )
            document.status, document.error, document.section_count = DocumentStatus.READY, None, len(sections)
            await session.commit()
        except Exception as exc:
            logger.exception("Processing document %s failed", document_id)
            await session.rollback()
            document = await get_scoped(session, KnowledgeDocument, document_id)
            if document is not None:
                document.status, document.error = DocumentStatus.FAILED, str(exc)[:500]
                await session.commit()


async def resume_unfinished_documents(factory: async_sessionmaker[AsyncSession]) -> int:
    """Documents a restart left `processing` (see unfinished_kb_documents())."""
    async with factory() as session:
        rows = (await session.execute(text("SELECT document_id, tenant_id FROM unfinished_kb_documents()"))).all()
    for document_id, tenant_id in rows:
        await process_document(document_id, tenant_id, factory)
    return len(rows)


async def list_documents(session: AsyncSession) -> Sequence[KnowledgeDocument]:
    stmt = (
        select(KnowledgeDocument)
        .where(KnowledgeDocument.tenant_id == tenant_of(session))
        .order_by(KnowledgeDocument.created_at.desc())
    )
    return (await session.scalars(stmt)).all()


async def get_document(session: AsyncSession, document_id: uuid.UUID) -> tuple[KnowledgeDocument, Sequence[KnowledgeBaseEntry]]:
    document = await get_scoped(session, KnowledgeDocument, document_id)
    if document is None:
        raise DocumentNotFound
    sections = (
        await session.scalars(
            select(KnowledgeBaseEntry)
            .where(KnowledgeBaseEntry.tenant_id == tenant_of(session), KnowledgeBaseEntry.document_id == document_id)
            .order_by(KnowledgeBaseEntry.position)
        )
    ).all()
    return document, sections


async def delete_document(session: AsyncSession, document_id: uuid.UUID) -> None:
    document = await get_scoped(session, KnowledgeDocument, document_id)
    if document is None:
        raise DocumentNotFound
    await session.delete(document)  # its sections go with it (ON DELETE CASCADE)
    await session.commit()


async def refresh_section_count(session: AsyncSession, document_id: uuid.UUID) -> None:
    document = await get_scoped(session, KnowledgeDocument, document_id)
    if document is not None:
        document.section_count = await session.scalar(
            select(func.count()).select_from(KnowledgeBaseEntry).where(KnowledgeBaseEntry.document_id == document_id)
        )

