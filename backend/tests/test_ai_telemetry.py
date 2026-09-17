from uuid import UUID

import pytest
from pydantic import BaseModel
from sqlalchemy import select

from app.ai.models import ModelExecutionError, OpenAICompatibleStructuredModel
from app.core.config import Settings
from app.models.ai import AIExecution


class Output(BaseModel):
    value: str


def settings(retries=0):
    return Settings(
        database_url="postgresql+psycopg://u:p@localhost/db",
        jwt_secret="x" * 32,
        llm_provider="openai_compatible",
        llm_api_key="secret-key",
        llm_base_url="http://provider",
        llm_model="test-model",
        llm_max_retries=retries,
    )


async def test_success_telemetry_persists_safe_operational_metadata(session, monkeypatch):
    model = OpenAICompatibleStructuredModel(
        settings(), session, UUID(int=1), "escalation_assessment", "escalation-assessment-v1"
    )

    async def request(*_):
        return '{"value":"ok"}', {"prompt_tokens": 11, "completion_tokens": 7}

    monkeypatch.setattr(model, "_request", request)
    await model.generate("patient transcript secret-key Authorization: Bearer", Output)
    row = await session.scalar(select(AIExecution))
    assert (row.hospital_id, row.purpose, row.prompt_version) == (
        UUID(int=1),
        "escalation_assessment",
        "escalation-assessment-v1",
    )
    assert (row.provider, row.model, row.input_tokens, row.output_tokens, row.success) == (
        "openai_compatible",
        "test-model",
        11,
        7,
        True,
    )
    assert row.latency_ms >= 0
    assert {"prompt", "response", "transcript", "payload", "api_key", "authorization"}.isdisjoint(
        {column.name for column in AIExecution.__table__.columns}
    )


async def test_failure_telemetry_persists_null_usage(session, monkeypatch):
    model = OpenAICompatibleStructuredModel(settings(), session, UUID(int=2), "triage", "triage-v1")

    async def request(*_):
        return "not-json", None

    monkeypatch.setattr(model, "_request", request)
    with pytest.raises(ModelExecutionError):
        await model.generate("sensitive transcript", Output)
    row = await session.scalar(select(AIExecution))
    assert row.hospital_id == UUID(int=2) and not row.success
    assert row.error_type == "invalid_structured_output"
    assert row.input_tokens is None and row.output_tokens is None
