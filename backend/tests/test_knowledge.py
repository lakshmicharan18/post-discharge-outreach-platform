from uuid import UUID, uuid4

import pytest

from app.ai.tools import ControlledAITools
from app.core.context import CurrentUserContext
from app.core.errors import APIError
from app.models.entities import Role
from app.schemas.ai import ToolRequest
from app.services.knowledge import KnowledgeService, chunk_text


def context(tenant: int, role: Role = Role.HOSPITAL_ADMIN):
    return CurrentUserContext(
        user_id=UUID(int=tenant * 10), hospital_id=UUID(int=tenant), role=role
    )


async def test_knowledge_is_tenant_scoped_and_reindexes(session):
    a = KnowledgeService(session, context(1))
    b = KnowledgeService(session, context(2))
    document = await a.create(
        "A protocol", "GUIDANCE", "a-protocol", "A-NURSE follow up in 48 hours."
    )
    other = await b.create("B protocol", "GUIDANCE", "b-protocol", "B-NURSE follow up in 72 hours.")
    assert [item.id for item in await a.list()] == [document.id]
    with pytest.raises(APIError):
        await a.get(other.id)
    assert [item["title"] for item in await a.search("NURSE")] == ["A protocol"]
    await a.update(document.id, {"content": "A-NEW contact"})
    assert not await a.search("48")
    assert len(await a.search("NEW")) == 1
    await a.reindex_by_id(document.id)
    assert len(await a.search("NEW")) == 1


def test_chunking_is_deterministic():
    assert chunk_text("one\n\ntwo") == chunk_text("one\n\ntwo")


async def test_knowledge_tool_is_allowlisted_and_platform_is_denied(session):
    tools = ControlledAITools(session, context(1))
    result = await tools.invoke(
        ToolRequest(
            name="search_hospital_knowledge", request_id=uuid4(), arguments={"query": "none"}
        )
    )
    assert result.success
    with pytest.raises(APIError):
        ControlledAITools(session, CurrentUserContext(uuid4(), None, Role.PLATFORM_ADMIN))
