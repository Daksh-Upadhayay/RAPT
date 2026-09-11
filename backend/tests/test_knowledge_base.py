import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import EMBEDDING_DIM
from app.ml.embeddings import embed_texts
from app.models import KnowledgeBaseEntry
from app.schemas.knowledge_base import KnowledgeBaseCreate
from app.services import knowledge_base as kb_service
from scripts.seed_knowledge_base import ExistingDataError, load_entries, seed

ENTRIES = [
    ("Refund timelines", "Refunds reach your bank 5-10 business days after we receive the return."),
    ("Damaged items", "If an item arrives broken or cracked, send photos and we will replace it."),
    ("Cancelling an order", "Orders can be cancelled while they are still processing."),
]


@pytest.fixture
async def kb_entries(session: AsyncSession) -> None:
    for title, content in ENTRIES:
        await kb_service.create_entry(session, KnowledgeBaseCreate(title=title, content=content))


async def test_create_entry(client: AsyncClient, session: AsyncSession) -> None:
    resp = await client.post("/knowledge-base", json={"title": "Returns", "content": "30-day returns on most items."})

    assert resp.status_code == 201
    body = resp.json()
    assert set(body) == {"id", "document_id", "position", "title", "content", "created_at"}  # embedding stays internal
    stored = await session.get(KnowledgeBaseEntry, body["id"])
    assert len(stored.embedding) == EMBEDDING_DIM


async def test_list_entries_sorted_by_title(client: AsyncClient, kb_entries: None) -> None:
    resp = await client.get("/knowledge-base")

    assert resp.status_code == 200
    assert [e["title"] for e in resp.json()] == sorted(t for t, _ in ENTRIES)


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "", "content": "text"},
        {"title": "Too long", "content": "refund policy details " * 200},  # beyond the model's 512 tokens
    ],
)
async def test_create_entry_rejects_bad_input(client: AsyncClient, payload: dict) -> None:
    resp = await client.post("/knowledge-base", json=payload)

    assert resp.status_code == 422


async def test_search_returns_closest_entries_first(session: AsyncSession, kb_entries: None) -> None:
    docs = await kb_service.search(session, "the vase I got is smashed to pieces", k=2)

    assert len(docs) == 2
    assert docs[0].title == "Damaged items"
    assert docs[0].similarity > docs[1].similarity


def test_embedding_size_matches_the_database_column() -> None:
    assert embed_texts(["hello"]).shape == (1, EMBEDDING_DIM)
    assert KnowledgeBaseEntry.__table__.c.embedding.type.dim == EMBEDDING_DIM


async def test_late_order_ticket_retrieves_the_delay_policy(session: AsyncSession) -> None:
    # Regression: this ticket never says "late" or "delayed", and the delay policy used
    # to rank 7th, so the draft could not quote it (see DECISIONS.md, Phase 4).
    await seed(session, load_entries())
    ticket = (
        "Where is my desk lamp?\nHi, I ordered a desk lamp over a week ago and it still has not arrived. "
        "The tracking has not updated in days. Can you tell me when it will get here?"
    )

    docs = await kb_service.search(session, ticket, k=3)

    assert "Late or delayed orders that haven't arrived" in [d.title for d in docs]


async def test_seed_inserts_every_entry_and_refuses_to_rerun(session: AsyncSession) -> None:
    entries = load_entries()

    assert await seed(session, entries) == len(entries)
    assert await session.scalar(select(func.count()).select_from(KnowledgeBaseEntry)) == len(entries)
    with pytest.raises(ExistingDataError):
        await seed(session, entries)
