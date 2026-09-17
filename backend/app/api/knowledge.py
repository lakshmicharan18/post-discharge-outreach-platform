from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext, get_context
from app.core.database import get_session
from app.models.entities import Role
from app.schemas.knowledge import (
    KnowledgeDocumentCreate,
    KnowledgeDocumentResponse,
    KnowledgeDocumentUpdate,
    KnowledgeSearchRequest,
)
from app.services.knowledge import KnowledgeService

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])
Session = Annotated[AsyncSession, Depends(get_session)]
Context = Annotated[RequestContext, Depends(get_context)]


def readable(context: RequestContext) -> None:
    context.require_roles(Role.HOSPITAL_ADMIN, Role.CAMPAIGN_MANAGER, Role.CLINICAL_REVIEWER)


@router.get("", response_model=list[KnowledgeDocumentResponse])
async def list_documents(session: Session, context: Context):
    readable(context)
    return await KnowledgeService(session, context).list()


@router.post("", response_model=KnowledgeDocumentResponse, status_code=201)
async def create_document(payload: KnowledgeDocumentCreate, session: Session, context: Context):
    return await KnowledgeService(session, context).create(**payload.model_dump())


@router.get("/{document_id}", response_model=KnowledgeDocumentResponse)
async def get_document(document_id: UUID, session: Session, context: Context):
    readable(context)
    return await KnowledgeService(session, context).get(document_id)


@router.patch("/{document_id}", response_model=KnowledgeDocumentResponse)
async def update_document(
    document_id: UUID, payload: KnowledgeDocumentUpdate, session: Session, context: Context
):
    return await KnowledgeService(session, context).update(
        document_id, payload.model_dump(exclude_unset=True)
    )


@router.post("/{document_id}/reindex", response_model=KnowledgeDocumentResponse)
async def reindex_document(document_id: UUID, session: Session, context: Context):
    return await KnowledgeService(session, context).reindex_by_id(document_id)


@router.post("/search")
async def search_documents(payload: KnowledgeSearchRequest, session: Session, context: Context):
    readable(context)
    return {"references": await KnowledgeService(session, context).search(**payload.model_dump())}
