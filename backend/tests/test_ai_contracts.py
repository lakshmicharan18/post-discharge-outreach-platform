from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.ai.models import DeterministicFakeModel
from app.ai.tools import ToolRegistry
from app.schemas.ai import ToolRequest, VoiceIntakeOutput


async def test_unknown_ai_tool_fails_closed():
    result = await ToolRegistry().invoke(
        ToolRequest(name="arbitrary_model_access", request_id=uuid4(), arguments={})
    )
    assert not result.success
    assert result.error and result.error.code == "tool_not_allowed"


def test_voice_intake_contract_rejects_malformed_output():
    with pytest.raises(ValidationError):
        VoiceIntakeOutput.model_validate({"call_disposition": "MAYBE"})


async def test_deterministic_fake_model_returns_validated_output():
    model = DeterministicFakeModel(
        {
            "call_disposition": "COMPLETED",
            "identity_status": "VERIFIED",
            "consent_status": "CONFIRMED",
        }
    )
    result = await model.generate("unused", VoiceIntakeOutput)
    assert result.call_disposition == "COMPLETED"
