"""Phase 9: help documents (upload/paste -> sections -> embeddings), search preview,
section editing, roles and tenant isolation. The documents exist only in these tests."""

import pytest
from sqlalchemy import func, select

from app.core.enums import UserRole
from app.core.tenancy import tenant_session
from app.knowledge.chunking import chunk
from app.knowledge.extract import ExtractionError, extract
from app.ml.embeddings import token_count
from app.models import KnowledgeBaseEntry, KnowledgeDocument
from app.services import knowledge_documents as doc_service
from tests.conftest import make_user

POLICY_MD = b"""# Returns policy

You can return unused items within 30 days of delivery.

## Refund timing

Refunds reach your bank 5-10 business days after we receive the return.

## Damaged items

Send photos of the damage within 14 days and we'll send a replacement.
"""


def tiny_pdf(*lines: str) -> bytes:
    """A minimal valid one-page PDF with the given lines of text."""
    ops = ["BT", "/F1 12 Tf", "72 720 Td"]
    for line in lines:
        ops += [f"({line}) Tj", "0 -16 Td"]
    stream = "\n".join([*ops, "ET"]).encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for i, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return out


# --- extraction and chunking -----------------------------------------------------------


def test_markdown_sections_follow_the_headings() -> None:
    title, text = extract("returns.md", POLICY_MD)
    sections = chunk(title, text, token_count)

    assert title == "Returns policy"
    assert [s.title for s in sections] == [
        "Returns policy",
        "Returns policy: Refund timing",
        "Returns policy: Damaged items",
    ]
    assert sections[1].content.startswith("Refunds reach your bank")


def test_html_keeps_headings_and_drops_page_chrome() -> None:
    html = b"""<html><head><title>Shipping help</title><style>p{}</style></head><body>
      <nav>Home | Shop | Cart</nav>
      <h2>Delivery times</h2><p>We ship in <b>1-2</b> business days.</p>
      <ul><li>Standard: 3-5 days</li><li>Express: next day</li></ul>
      <script>track()</script><footer>(c) Store</footer></body></html>"""
    title, text = extract("shipping.html", html)

    assert title == "Shipping help"
    assert "## Delivery times" in text and "Express: next day" in text
    assert "Home | Shop" not in text and "track()" not in text and "(c) Store" not in text


def test_pdf_text_is_extracted() -> None:
    title, text = extract("Warranty_Terms.pdf", tiny_pdf("All kettles have a 2 year warranty.", "Keep your receipt."))

    assert title == "Warranty Terms"
    assert "2 year warranty" in text


@pytest.mark.parametrize(
    ("name", "data", "match"),
    [
        ("image.png", b"\x89PNG", "Upload Markdown, text, HTML or PDF"),
        ("empty.md", b"   \n\n ", "No text found"),
        ("broken.pdf", b"%PDF-1.4 not really", "couldn't be read"),
    ],
)
def test_unusable_files_are_rejected(name: str, data: bytes, match: str) -> None:
    with pytest.raises(ExtractionError, match=match):
        extract(name, data)


def test_long_sections_are_split_within_the_token_limit() -> None:
    text = "## Policy\n\n" + " ".join(f"Sentence number {i} explains one detail of the policy." for i in range(200))
    sections = chunk("Doc", text, token_count, max_tokens=120)

    assert len(sections) > 1
    assert all(token_count(s.content) <= 120 for s in sections)
    assert sections[0].title == "Doc: Policy (part 1)"


# --- API ------------------------------------------------------------------------------


async def upload(client, *files):
    return await client.post("/knowledge-base/documents/upload", files=[("files", f) for f in files])


async def test_upload_builds_searchable_sections(client, session) -> None:
    resp = await upload(client, ("returns.md", POLICY_MD, "text/markdown"), ("warranty.pdf", tiny_pdf("All kettles have a 2 year warranty."), "application/pdf"))

    assert resp.status_code == 200
    results = resp.json()
    assert [r["error"] for r in results] == [None, None]
    # The background job has run by the time the request returns (ASGITransport waits)
    documents = (await client.get("/knowledge-base/documents")).json()
    assert {d["title"]: (d["status"], d["section_count"]) for d in documents} == {
        "Returns policy": ("ready", 3),
        "warranty": ("ready", 1),
    }
    detail = (await client.get(f"/knowledge-base/documents/{results[0]['document']['id']}")).json()
    assert [s["position"] for s in detail["sections"]] == [0, 1, 2]

    hits = (await client.post("/knowledge-base/search", json={"query": "how long until my money comes back?", "k": 1})).json()
    assert hits[0]["title"] == "Returns policy: Refund timing"


async def test_each_file_is_reported_separately(client) -> None:
    resp = await upload(
        client,
        ("returns.md", POLICY_MD, "text/markdown"),
        ("photo.png", b"\x89PNG", "image/png"),
        ("again.md", POLICY_MD, "text/markdown"),  # same content under another name
        ("huge.txt", b"a" * (5 * 1024 * 1024 + 1), "text/plain"),
    )

    errors = [r["error"] for r in resp.json()]
    assert errors[0] is None
    assert "Upload Markdown" in errors[1]
    assert "already added" in errors[2]
    assert "over 5 MB" in errors[3]


async def test_paste_and_duplicate(client) -> None:
    body = {"title": "Store hours", "text": "We answer email Monday to Friday, 9am-5pm."}
    first = await client.post("/knowledge-base/documents/paste", json=body)
    again = await client.post("/knowledge-base/documents/paste", json=body)

    assert first.status_code == 201 and first.json()["source"] == "paste"
    assert again.status_code == 409


async def test_edit_and_delete_sections_and_documents(client, session) -> None:
    doc = (await upload(client, ("returns.md", POLICY_MD, "text/markdown"))).json()[0]["document"]
    sections = (await client.get(f"/knowledge-base/documents/{doc['id']}")).json()["sections"]

    edited = await client.patch(f"/knowledge-base/{sections[0]['id']}", json={"title": "Returns", "content": "Returns within 60 days."})
    assert edited.json()["content"] == "Returns within 60 days."
    assert (await client.delete(f"/knowledge-base/{sections[1]['id']}")).status_code == 204
    assert (await client.get("/knowledge-base/documents")).json()[0]["section_count"] == 2

    assert (await client.delete(f"/knowledge-base/documents/{doc['id']}")).status_code == 204
    assert await session.scalar(select(func.count()).select_from(KnowledgeBaseEntry)) == 0  # cascade


async def test_reviewers_can_read_but_not_change_the_knowledge_base(api, admin_factory, tenant, client) -> None:
    doc = (await upload(client, ("returns.md", POLICY_MD, "text/markdown"))).json()[0]["document"]
    reviewer = await make_user(admin_factory, tenant, "rev@acme.example", UserRole.REVIEWER)

    async with api(reviewer) as rc:
        assert (await rc.get("/knowledge-base/documents")).status_code == 200
        assert (await rc.post("/knowledge-base/search", json={"query": "refund"})).status_code == 200
        assert (await upload(rc, ("x.md", b"# X\n\ny", "text/markdown"))).status_code == 403
        assert (await rc.post("/knowledge-base/documents/paste", json={"title": "x", "text": "y"})).status_code == 403
        assert (await rc.delete(f"/knowledge-base/documents/{doc['id']}")).status_code == 403
        assert (await rc.post("/knowledge-base", json={"title": "x", "content": "y"})).status_code == 403


async def test_documents_stay_inside_their_tenant(api, admin_factory, other_tenant, client) -> None:
    doc = (await upload(client, ("returns.md", POLICY_MD, "text/markdown"))).json()[0]["document"]
    outsider = await make_user(admin_factory, other_tenant, "boss@globex.example", UserRole.ADMIN)

    async with api(outsider) as oc:
        assert (await oc.get("/knowledge-base/documents")).json() == []
        assert (await oc.get(f"/knowledge-base/documents/{doc['id']}")).status_code == 404
        assert (await oc.delete(f"/knowledge-base/documents/{doc['id']}")).status_code == 404
        assert (await oc.post("/knowledge-base/search", json={"query": "refund"})).json() == []
        # The same content is a new document in another tenant, not a duplicate
        assert (await upload(oc, ("returns.md", POLICY_MD, "text/markdown"))).json()[0]["error"] is None


async def test_a_document_stuck_processing_is_finished_on_restart(session_factory, session, tenant) -> None:
    title, text = extract("returns.md", POLICY_MD)
    document = await doc_service.add_document(session, title=title, content=text, source="upload", filename="returns.md", uploaded_by="ada@acme.example")

    assert await doc_service.resume_unfinished_documents(session_factory) == 1

    async with tenant_session(session_factory, tenant.id) as s:
        refreshed = await s.get(KnowledgeDocument, document.id)
        assert (refreshed.status, refreshed.section_count) == ("ready", 3)
