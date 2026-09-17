import pytest
from pydantic import BaseModel

from app.ai.models import (
    DeterministicFakeModel,
    ModelExecutionError,
    OpenAICompatibleStructuredModel,
    configured_model,
)
from app.core.config import Settings


class Output(BaseModel):
    value: str


def settings(retries=1):
    return Settings(
        database_url="postgresql+psycopg://u:p@localhost/db",
        jwt_secret="x" * 32,
        llm_provider="openai_compatible",
        llm_api_key="key",
        llm_base_url="http://provider",
        llm_model="test",
        llm_max_retries=retries,
    )


async def test_provider_selection_and_valid_response(monkeypatch):
    assert isinstance(
        configured_model(
            {"value": "fake"},
            Settings(database_url="postgresql+psycopg://u:p@localhost/db", jwt_secret="x" * 32),
        ),
        DeterministicFakeModel,
    )
    model = OpenAICompatibleStructuredModel(settings())
    monkeypatch.setattr(
        model,
        "_request",
        lambda *_: __import__("asyncio").sleep(0, result=('{"value":"ok"}', None)),
    )
    assert (await model.generate("prompt", Output)).value == "ok"


async def test_malformed_and_schema_output_repair_is_bounded(monkeypatch):
    model = OpenAICompatibleStructuredModel(settings())
    values = iter([("nope", None), ('{"value":"repaired"}', None)])

    async def request(*_):
        return next(values)

    monkeypatch.setattr(model, "_request", request)
    assert (await model.generate("prompt", Output)).value == "repaired"


async def test_invalid_or_provider_failure_is_explicit(monkeypatch):
    model = OpenAICompatibleStructuredModel(settings(retries=0))

    async def invalid(*_):
        return '{"wrong":true}', None

    monkeypatch.setattr(model, "_request", invalid)
    with pytest.raises(ModelExecutionError):
        await model.generate("prompt", Output)
