"""Embed the knowledge-base entries in data/knowledge_base.json and insert them.

Each entry is embedded as "title. content" with the configured embedding model. Entries
longer than the model reads (512 tokens for bge-small) are rejected rather than silently
truncated. The `categories` field in the JSON is not stored; scripts/evaluate_retrieval.py
uses it to check that search returns entries relevant to a ticket's category.

Usage (from backend/):
    uv run python -m scripts.seed_knowledge_base --tenant dev            # refuses if the tenant has entries
    uv run python -m scripts.seed_knowledge_base --tenant dev --reset    # replace the tenant's entries
"""

import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.admin_db import UnknownTenant, admin_tenant_session
from app.core.tenancy import tenant_of
from app.ml.embeddings import document_text, embed_texts, token_count
from app.ml.text_features import sentence_model
from app.models import KnowledgeBaseEntry

KB_PATH = Path(__file__).resolve().parents[2] / "data" / "knowledge_base.json"


class ExistingDataError(Exception):
    """Refusing to seed on top of existing entries without --reset."""


def load_entries(path: Path = KB_PATH) -> list[dict]:
    entries = json.loads(path.read_text())
    max_tokens = sentence_model(settings.embedding_model).max_seq_length
    too_long = [(e["title"], n) for e in entries if (n := token_count(document_text(e["title"], e["content"]))) > max_tokens]
    if too_long:
        raise SystemExit(f"Entries longer than {max_tokens} tokens (split them): {too_long}")
    return entries


async def seed(session: AsyncSession, entries: list[dict], reset: bool = False) -> int:
    tenant_id = tenant_of(session)
    if reset:
        await session.execute(text("DELETE FROM knowledge_base WHERE tenant_id = :t"), {"t": tenant_id})
    elif await session.scalar(select(func.count()).select_from(KnowledgeBaseEntry).where(KnowledgeBaseEntry.tenant_id == tenant_id)):
        raise ExistingDataError("this tenant already has entries; rerun with --reset to replace and re-embed them")

    vectors = embed_texts([document_text(e["title"], e["content"]) for e in entries])
    session.add_all(
        KnowledgeBaseEntry(title=e["title"], content=e["content"], embedding=v)
        for e, v in zip(entries, vectors, strict=True)
    )
    await session.commit()
    return len(entries)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="delete this tenant's entries first")
    parser.add_argument("--tenant", required=True, help="tenant slug (data/knowledge_base.json is the dev tenant's demo policies)")
    args = parser.parse_args()

    entries = load_entries()
    try:
        async with admin_tenant_session(args.tenant) as session:
            n = await seed(session, entries, reset=args.reset)
    except (ExistingDataError, UnknownTenant) as exc:
        raise SystemExit(f"Error: {exc}") from exc
    print(f"Embedded and inserted {n} knowledge-base entries ({settings.embedding_model})")


if __name__ == "__main__":
    asyncio.run(main())
