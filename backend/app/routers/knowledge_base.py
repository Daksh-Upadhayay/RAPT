from fastapi import APIRouter, HTTPException, status

from app.core.db import SessionDep
from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseResponse
from app.services import knowledge_base as kb_service

router = APIRouter(prefix="/knowledge-base", tags=["knowledge-base"])


@router.get("")
async def list_entries(session: SessionDep) -> list[KnowledgeBaseResponse]:
    return [KnowledgeBaseResponse.model_validate(e) for e in await kb_service.list_entries(session)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_entry(data: KnowledgeBaseCreate, session: SessionDep) -> KnowledgeBaseResponse:
    """Add an entry; its embedding is generated before it is stored."""
    try:
        entry = await kb_service.create_entry(session, data)
    except kb_service.TextTooLongError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return KnowledgeBaseResponse.model_validate(entry)
