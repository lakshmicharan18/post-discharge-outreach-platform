from typing import Protocol, TypeVar

from pydantic import BaseModel

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
