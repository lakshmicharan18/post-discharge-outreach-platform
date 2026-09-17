from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class KnowledgeDocumentCreate(KnowledgeInput):
    title: str = Field(min_length=1, max_length=250)
    source_type: str = Field(min_length=1, max_length=100)
    source_identifier: str = Field(min_length=1, max_length=150)
    content: str = Field(min_length=1, max_length=100_000)


class KnowledgeDocumentUpdate(KnowledgeInput):
    title: str | None = Field(default=None, min_length=1, max_length=250)
    content: str | None = Field(default=None, min_length=1, max_length=100_000)
    active: bool | None = None


class KnowledgeDocumentResponse(KnowledgeDocumentCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    hospital_id: UUID
    active: bool
    version: int
    created_at: datetime
    updated_at: datetime


class KnowledgeSearchRequest(KnowledgeInput):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=10)
