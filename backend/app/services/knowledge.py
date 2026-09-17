from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.errors import APIError
from app.models.entities import Role
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument

CHUNK_SIZE = 800
MAX_TOP_K = 10


def chunk_text(content: str, size: int = CHUNK_SIZE) -> list[str]:
    """Stable paragraph-aware chunking; no model or network dependency."""
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if current and len(current) + len(paragraph) + 2 > size:
            chunks.append(current)
            current = ""
        while len(paragraph) > size:
            chunks.append(paragraph[:size])
            paragraph = paragraph[size:]
        current = f"{current}\n\n{paragraph}" if current else paragraph
    if current:
        chunks.append(current)
    return chunks


class KnowledgeService:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session, self.context = session, context
        self.hospital_id = context.require_clinical_tenant()

    async def create(self, title: str, source_type: str, source_identifier: str, content: str):
        self.context.require_roles(Role.HOSPITAL_ADMIN)
        document = KnowledgeDocument(
            hospital_id=self.hospital_id,
            title=title,
            source_type=source_type,
            source_identifier=source_identifier,
            content=content,
        )
        self.session.add(document)
        await self.session.flush()
        await self.reindex(document)
        await self.session.commit()
        return document

    async def get(self, document_id: UUID) -> KnowledgeDocument:
        document = await self.session.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.id == document_id,
                KnowledgeDocument.hospital_id == self.hospital_id,
            )
        )
        if document is None:
            raise APIError(404, "not_found", "Knowledge document not found")
        return document

    async def list(self) -> list[KnowledgeDocument]:
        return list(
            await self.session.scalars(
                select(KnowledgeDocument)
                .where(KnowledgeDocument.hospital_id == self.hospital_id)
                .order_by(KnowledgeDocument.title, KnowledgeDocument.id)
            )
        )

    async def update(self, document_id: UUID, values: dict) -> KnowledgeDocument:
        self.context.require_roles(Role.HOSPITAL_ADMIN)
        document = await self.get(document_id)
        content_changed = "content" in values and values["content"] != document.content
        for field, value in values.items():
            setattr(document, field, value)
        if content_changed:
            document.version += 1
            await self.reindex(document)
        await self.session.commit()
        await self.session.refresh(document)
        return document

    async def reindex_by_id(self, document_id: UUID) -> KnowledgeDocument:
        self.context.require_roles(Role.HOSPITAL_ADMIN)
        document = await self.get(document_id)
        await self.reindex(document)
        await self.session.commit()
        return document

    async def reindex(self, document: KnowledgeDocument) -> None:
        await self.session.execute(
            delete(KnowledgeChunk).where(
                KnowledgeChunk.document_id == document.id,
                KnowledgeChunk.hospital_id == self.hospital_id,
            )
        )
        for index, text in enumerate(chunk_text(document.content)):
            self.session.add(
                KnowledgeChunk(
                    hospital_id=self.hospital_id,
                    document_id=document.id,
                    chunk_index=index,
                    chunk_text=text,
                    citation_metadata={
                        "title": document.title,
                        "source_type": document.source_type,
                        "source_identifier": document.source_identifier,
                    },
                )
            )
        await self.session.flush()

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        if not 1 <= top_k <= MAX_TOP_K:
            raise APIError(422, "invalid_top_k", "top_k must be between 1 and 10")
        terms = {term.lower() for term in re.findall(r"[a-zA-Z0-9]+", query)}
        rows = await self.session.execute(
            select(KnowledgeChunk, KnowledgeDocument)
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(
                KnowledgeChunk.hospital_id == self.hospital_id,
                KnowledgeDocument.hospital_id == self.hospital_id,
                KnowledgeDocument.active.is_(True),
            )
        )
        ranked = []
        for chunk, document in rows:
            score = sum(chunk.chunk_text.lower().count(term) for term in terms)
            if score:
                ranked.append((score, document, chunk))
        ranked.sort(
            key=lambda item: (-item[0], item[1].title, item[2].chunk_index, str(item[2].id))
        )
        return [
            {
                "document_id": str(document.id),
                "chunk_id": str(chunk.id),
                "title": document.title,
                "source_type": document.source_type,
                "source_identifier": document.source_identifier,
                "excerpt": chunk.chunk_text,
                "score": score,
                "untrusted_source_data": True,
            }
            for score, document, chunk in ranked[:top_k]
        ]
