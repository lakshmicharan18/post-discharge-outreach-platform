import pytest
from pydantic import ValidationError

from app.ai.models import DeterministicFakeModel
from app.schemas.ai import ConversationStage, VoiceIntakeTurnOutput


async def test_fake_model_returns_validated_turn_output():
    model = DeterministicFakeModel(
        {
            "assistant_message": "How are you recovering?",
            "next_stage": "GENERAL_RECOVERY",
        }
    )
    output = await model.generate("ignored", VoiceIntakeTurnOutput)
    assert output.next_stage == ConversationStage.GENERAL_RECOVERY


def test_turn_contract_rejects_invalid_stage():
    with pytest.raises(ValidationError):
        VoiceIntakeTurnOutput(assistant_message="x", next_stage="TRIAGE")
