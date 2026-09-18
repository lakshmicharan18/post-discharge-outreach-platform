import asyncio
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Protocol, TypeVar
from uuid import UUID

from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.core.errors import APIError
from app.models.ai import AIExecution

T = TypeVar("T", bound=BaseModel)


class StructuredModel(Protocol):
    provider: str
    model: str

    async def generate(self, prompt: str, response_model: type[T]) -> T: ...


class DeterministicFakeModel:
    """Test-only provider that validates supplied deterministic response data."""

    provider = "fake"
    model = "deterministic"

    def __init__(self, response: dict) -> None:
        self.response = response

    async def generate(self, prompt: str, response_model: type[T]) -> T:
        del prompt
        return response_model.model_validate(self.response)


class ModelExecutionError(APIError):
    def __init__(self, message: str = "Structured model execution failed") -> None:
        super().__init__(503, "model_execution_failed", message)


class OpenAICompatibleStructuredModel:
    provider = "openai_compatible"

    def __init__(
        self,
        settings: Settings | None = None,
        session=None,
        hospital_id: UUID | None = None,
        purpose: str = "structured",
        prompt_version: str = "structured-v1",
    ) -> None:
        self.settings = settings or get_settings()
        self.model = self.settings.llm_model
        self.session, self.hospital_id, self.purpose, self.prompt_version = (
            session,
            hospital_id,
            purpose,
            prompt_version,
        )

    async def generate(self, prompt: str, response_model: type[T]) -> T:
        if not self.settings.llm_api_key or not self.settings.llm_base_url:
            raise ModelExecutionError("OpenAI-compatible provider is not configured")
        started = perf_counter()
        attempts = self.settings.llm_max_retries + 1
        for attempt in range(attempts):
            repair = " Return only valid JSON matching the requested schema." if attempt else ""
            try:
                raw, usage = await self._request(prompt + repair, response_model)
                result = response_model.model_validate_json(raw)
                await self._telemetry(True, int((perf_counter() - started) * 1000), None, usage)
                return result
            except (json.JSONDecodeError, ValueError) as exc:
                if attempt + 1 == attempts:
                    await self._telemetry(
                        False,
                        int((perf_counter() - started) * 1000),
                        "invalid_structured_output",
                        None,
                    )
                    raise ModelExecutionError(
                        "Provider returned invalid structured output"
                    ) from exc
            except urllib.error.HTTPError as exc:
                if attempt + 1 == attempts:
                    error_type = (
                        f"provider_http_{exc.code}"
                        if isinstance(exc.code, int)
                        else "provider_http_error"
                    )
                    await self._telemetry(
                        False, int((perf_counter() - started) * 1000), error_type, None
                    )
                    raise ModelExecutionError("Provider request failed") from exc
            except urllib.error.URLError as exc:
                if attempt + 1 == attempts:
                    await self._telemetry(
                        False, int((perf_counter() - started) * 1000), "provider_error", None
                    )
                    raise ModelExecutionError("Provider request failed") from exc
        raise ModelExecutionError()

    async def _telemetry(
        self, success: bool, latency_ms: int, error_type: str | None, usage: dict | None
    ) -> None:
        if self.session is None or self.hospital_id is None:
            return
        self.session.add(
            AIExecution(
                hospital_id=self.hospital_id,
                purpose=self.purpose,
                provider=self.provider,
                model=self.model,
                prompt_version=self.prompt_version,
                latency_ms=latency_ms,
                success=success,
                input_tokens=(usage or {}).get("prompt_tokens"),
                output_tokens=(usage or {}).get("completion_tokens"),
                estimated_cost=None,
                error_type=error_type,
                created_at=datetime.now(timezone.utc),
            )
        )
        await self.session.commit()

    async def _request(self, prompt: str, response_model: type[T]) -> tuple[str, dict | None]:
        schema = json.dumps(response_model.model_json_schema(), separators=(",", ":"))
        structured_instruction = (
            "Return ONLY valid JSON with no markdown or explanation. "
            "Conform exactly to this JSON Schema:\n"
            f"{schema}"
        )
        payload = json.dumps(
            {
                "model": self.model,
                "messages": [{"role": "user", "content": f"{prompt}\n\n{structured_instruction}"}],
                "response_format": {"type": "json_object"},
            }
        ).encode()
        request = urllib.request.Request(
            self.settings.llm_base_url.rstrip("/") + "/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {self.settings.llm_api_key.get_secret_value()}",
                "Content-Type": "application/json",
            },
        )

        def call() -> str:
            with urllib.request.urlopen(
                request, timeout=self.settings.llm_timeout_seconds
            ) as response:
                body = json.loads(response.read())
                return body["choices"][0]["message"]["content"], body.get("usage")

        return await asyncio.to_thread(call)


def configured_model(
    response: dict[str, Any], settings: Settings | None = None, **metadata
) -> StructuredModel:
    selected = settings or get_settings()
    if selected.llm_provider == "openai_compatible":
        return OpenAICompatibleStructuredModel(selected, **metadata)
    return DeterministicFakeModel(response)
