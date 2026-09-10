"""Embed the knowledge-base entries in data/knowledge_base.json and insert them.

Each entry is embedded as "title. content" with the configured embedding model. Entries
longer than the model reads (256 tokens for MiniLM) are rejected rather than silently
truncated. The `categories` field in the JSON is not stored; scripts/evaluate_retrieval.py
uses it to check that search returns entries relevant to a ticket's category.

Usage (from backend/):
    uv run python -m scripts.seed_knowledge_base            # refuses if the table has rows
    uv run python -m scripts.seed_knowledge_base --reset    # wipe and re-embed everything
"""

import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import SessionLocal, engine
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
    if reset:
        await session.execute(text("TRUNCATE knowledge_base"))
    elif await session.scalar(select(func.count()).select_from(KnowledgeBaseEntry)):
        raise ExistingDataError("knowledge_base is not empty; rerun with --reset to wipe and re-embed")

    vectors = embed_texts([document_text(e["title"], e["content"]) for e in entries])
    session.add_all(
        KnowledgeBaseEntry(title=e["title"], content=e["content"], embedding=v)
        for e, v in zip(entries, vectors, strict=True)
    )
    await session.commit()
    return len(entries)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="truncate knowledge_base first")
    args = parser.parse_args()

    entries = load_entries()
    try:
        async with SessionLocal() as session:
            n = await seed(session, entries, reset=args.reset)
    except ExistingDataError as exc:
        raise SystemExit(f"Error: {exc}") from exc
    finally:
        await engine.dispose()
    print(f"Embedded and inserted {n} knowledge-base entries ({settings.embedding_model})")


if __name__ == "__main__":
    asyncio.run(main())
