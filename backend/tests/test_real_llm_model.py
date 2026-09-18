import json

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


async def test_provider_request_includes_json_only_schema_instruction(monkeypatch):
    captured: dict = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return b'{"choices":[{"message":{"content":"{\\"value\\":\\"ok\\"}"}}]}'

    def urlopen(request, timeout):
        captured["payload"] = json.loads(request.data)
        captured["timeout"] = timeout
        return Response()

    model = OpenAICompatibleStructuredModel(settings())
    monkeypatch.setattr("urllib.request.urlopen", urlopen)

    assert (await model._request("structured prompt", Output))[0] == '{"value":"ok"}'
    content = captured["payload"]["messages"][0]["content"]
    assert "Return ONLY valid JSON with no markdown or explanation." in content
    assert json.dumps(Output.model_json_schema(), separators=(",", ":")) in content
    assert captured["payload"]["response_format"] == {"type": "json_object"}


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
