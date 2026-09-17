from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.entities import Base, Identity, Tenant, Timestamps


class KnowledgeDocument(Identity, Tenant, Timestamps, Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (UniqueConstraint("hospital_id", "source_identifier", "version"),)

    title: Mapped[str] = mapped_column(String(250))
    source_type: Mapped[str] = mapped_column(String(100), index=True)
    source_identifier: Mapped[str] = mapped_column(String(150))
    content: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class KnowledgeChunk(Identity, Tenant, Timestamps, Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index"),
        Index("ix_knowledge_chunks_hospital_document", "hospital_id", "document_id"),
    )

    document_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_documents.id"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    chunk_text: Mapped[str] = mapped_column(Text)
    citation_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
