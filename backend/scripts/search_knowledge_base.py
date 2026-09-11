"""Search the knowledge base with ticket text, the way the Knowledge Agent will.

Usage (from backend/):
    uv run python -m scripts.search_knowledge_base --tenant dev "my parcel is a week late, where is it?"
    uv run python -m scripts.search_knowledge_base --tenant dev -k 5 "I was charged twice"
"""

import argparse
import asyncio

from app.core.admin_db import UnknownTenant, admin_tenant_session
from app.services.knowledge_base import search


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("text")
    parser.add_argument("-k", type=int, default=3)
    parser.add_argument("--tenant", required=True, help="tenant slug: search only its knowledge base")
    args = parser.parse_args()
    try:
        async with admin_tenant_session(args.tenant) as session:
            docs = await search(session, args.text, k=args.k)
    except UnknownTenant as exc:
        raise SystemExit(f"Error: {exc}") from exc
    for rank, doc in enumerate(docs, 1):
        print(f"{rank}. [{doc.similarity:.3f}] {doc.title}\n   {doc.content[:160]}…")


if __name__ == "__main__":
    asyncio.run(main())
