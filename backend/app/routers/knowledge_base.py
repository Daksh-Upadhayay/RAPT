"""The tenant's knowledge base: entries, uploaded help documents, and a search preview.

Reading is open to every signed-in user (reviewers see what drafts are based on);
adding, editing and deleting is for tenant admins.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile, status

from app.core.db import SessionFactoryDep
from app.core.deps import AdminDep, SessionDep
from app.core.enums import DocumentSource
from app.knowledge.extract import ExtractionError, extract, from_paste
from app.schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdate,
    KnowledgeDocumentDetail,
    KnowledgeDocumentResponse,
    KnowledgePasteRequest,
    KnowledgeSearchRequest,
    KnowledgeUploadResult,
    RetrievedDoc,
)
from app.services import knowledge_base as kb_service
from app.services import knowledge_documents as doc_service

router = APIRouter(prefix="/knowledge-base", tags=["knowledge-base"])

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_FILES = 20


@router.get("")
async def list_entries(session: SessionDep) -> list[KnowledgeBaseResponse]:
    return [KnowledgeBaseResponse.model_validate(e) for e in await kb_service.list_entries(session)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_entry(data: KnowledgeBaseCreate, admin: AdminDep, session: SessionDep) -> KnowledgeBaseResponse:
    """Add one entry; its embedding is generated before it is stored."""
    try:
        entry = await kb_service.create_entry(session, data)
    except kb_service.TextTooLongError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return KnowledgeBaseResponse.model_validate(entry)


@router.patch("/{entry_id}")
async def update_entry(entry_id: UUID, data: KnowledgeBaseUpdate, admin: AdminDep, session: SessionDep) -> KnowledgeBaseResponse:
    """Edit an entry or a document's section; it is re-embedded."""
    try:
        entry = await kb_service.update_entry(session, entry_id, data.title.strip(), data.content.strip())
    except kb_service.EntryNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found") from exc
    except kb_service.TextTooLongError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return KnowledgeBaseResponse.model_validate(entry)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(entry_id: UUID, admin: AdminDep, session: SessionDep) -> None:
    try:
        await kb_service.delete_entry(session, entry_id)
    except kb_service.EntryNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found") from exc


@router.post("/search")
async def search(data: KnowledgeSearchRequest, session: SessionDep) -> list[RetrievedDoc]:
    """What the Knowledge Agent would retrieve for this text: a preview for admins."""
    return await kb_service.search(session, data.query, k=data.k)


# --- documents ------------------------------------------------------------------------


@router.get("/documents")
async def list_documents(session: SessionDep) -> list[KnowledgeDocumentResponse]:
    return [KnowledgeDocumentResponse.model_validate(d) for d in await doc_service.list_documents(session)]


@router.get("/documents/{document_id}")
async def get_document(document_id: UUID, session: SessionDep) -> KnowledgeDocumentDetail:
    try:
        document, sections = await doc_service.get_document(session, document_id)
    except doc_service.DocumentNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found") from exc
    return KnowledgeDocumentDetail.model_validate(
        {**KnowledgeDocumentResponse.model_validate(document).model_dump(), "sections": [KnowledgeBaseResponse.model_validate(s) for s in sections]}
    )


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: UUID, admin: AdminDep, session: SessionDep) -> None:
    """Delete a document and all its sections."""
    try:
        await doc_service.delete_document(session, document_id)
    except doc_service.DocumentNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found") from exc


@router.post("/documents/upload")
async def upload_documents(
    files: Annotated[list[UploadFile], File(description="Markdown, text, HTML or PDF; 5 MB each, 20 at a time")],
    admin: AdminDep,
    session: SessionDep,
    background: BackgroundTasks,
    factory: SessionFactoryDep,
) -> list[KnowledgeUploadResult]:
    """Add help documents. Each file is reported separately: one bad file doesn't stop
    the others. Accepted files are split and embedded in the background."""
    if not files:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Choose at least one file.")
    if len(files) > MAX_FILES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Upload at most {MAX_FILES} files at a time.")

    results = []
    for upload in files:
        name = upload.filename or "file"
        data = await upload.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            results.append(KnowledgeUploadResult(filename=name, document=None, error="The file is over 5 MB."))
            continue
        try:
            title, text = extract(name, data)
            document = await doc_service.add_document(
                session, title=title, content=text, source=DocumentSource.UPLOAD, filename=name, uploaded_by=admin.email
            )
        except (ExtractionError, doc_service.DuplicateDocument) as exc:
            results.append(KnowledgeUploadResult(filename=name, document=None, error=str(exc)))
            continue
        background.add_task(doc_service.process_document, document.id, admin.tenant_id, factory)
        results.append(KnowledgeUploadResult(filename=name, document=KnowledgeDocumentResponse.model_validate(document), error=None))
    return results


@router.post("/documents/paste", status_code=status.HTTP_201_CREATED)
async def paste_document(
    data: KnowledgePasteRequest, admin: AdminDep, session: SessionDep, background: BackgroundTasks, factory: SessionFactoryDep
) -> KnowledgeDocumentResponse:
    """Add a document from pasted text (Markdown headings are understood)."""
    try:
        text = from_paste(data.text)
        document = await doc_service.add_document(
            session, title=data.title, content=text, source=DocumentSource.PASTE, filename=None, uploaded_by=admin.email
        )
    except ExtractionError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    except doc_service.DuplicateDocument as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    background.add_task(doc_service.process_document, document.id, admin.tenant_id, factory)
    return KnowledgeDocumentResponse.model_validate(document)
