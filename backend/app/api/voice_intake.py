from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.intake import VoiceIntakeAgent
from app.ai.models import configured_model
from app.ai.tools import ControlledAITools
from app.core.context import RequestContext, get_context
from app.core.database import get_session
from app.models.entities import Role
from app.schemas.ai import (
    VoiceIntakeSessionCreate,
    VoiceIntakeSessionResponse,
    VoiceIntakeTurnRequest,
)
from app.services.voice_intake import VoiceIntakeSessionService

router = APIRouter(prefix="/api/v1/voice-intake", tags=["voice-intake"])
Session = Annotated[AsyncSession, Depends(get_session)]
Context = Annotated[RequestContext, Depends(get_context)]


def response(record) -> VoiceIntakeSessionResponse:
    return VoiceIntakeSessionResponse(
        id=record.id,
        outreach_task_id=record.outreach_task_id,
        current_stage=record.current_stage,
        status=record.status,
        conversation_state=record.conversation_state,
        completed_at=record.completed_at,
    )


@router.post("/sessions", response_model=VoiceIntakeSessionResponse, status_code=201)
async def create_session(payload: VoiceIntakeSessionCreate, session: Session, context: Context):
    return response(
        await VoiceIntakeSessionService(session, context).create(payload.outreach_task_id)
    )


@router.get("/sessions/{session_id}", response_model=VoiceIntakeSessionResponse)
async def get_session(session_id: UUID, session: Session, context: Context):
    context.require_roles(Role.HOSPITAL_ADMIN, Role.CAMPAIGN_MANAGER, Role.CLINICAL_REVIEWER)
    return response(await VoiceIntakeSessionService(session, context).get(session_id))


@router.post("/sessions/{session_id}/turn", response_model=VoiceIntakeSessionResponse)
async def turn(
    session_id: UUID, payload: VoiceIntakeTurnRequest, session: Session, context: Context
):
    service = VoiceIntakeSessionService(session, context)
    record = await service.get(session_id)
    if record.status == "COMPLETED":
        return response(record)
    agent = VoiceIntakeAgent(
        ControlledAITools(session, context),
        configured_model(
            {"assistant_message": "Thank you. Please continue.", "next_stage": "GENERAL_RECOVERY"},
            session=session,
            hospital_id=context.hospital_id,
            purpose="voice_intake",
            prompt_version="voice-intake-v1",
        ),
    )
    conversation, _ = await agent.process_turn(
        context,
        await service.conversation(record),
        payload.patient_message,
        datetime.now(timezone.utc),
    )
    return response(
        await service.save(
            record,
            conversation.model_dump(mode="json", exclude={"session_id", "outreach_task_id"}),
            conversation.stage.value,
            conversation.completed,
            datetime.now(timezone.utc),
        )
    )


@router.post("/sessions/{session_id}/complete", response_model=VoiceIntakeSessionResponse)
async def complete(session_id: UUID, session: Session, context: Context):
    service = VoiceIntakeSessionService(session, context)
    record = await service.get(session_id)

    # /complete has deterministic semantics regardless of what the model returns.
    if record.status == "COMPLETED":
        state = dict(record.conversation_state)
        state["stage"] = "COMPLETION"
        state["completed"] = True

        return response(
            await service.save(
                record,
                state,
                "COMPLETION",
                True,
                datetime.now(timezone.utc),
            )
        )

    agent = VoiceIntakeAgent(
        ControlledAITools(session, context),
        configured_model(
            {
                "assistant_message": "Thank you.",
                "next_stage": "COMPLETION",
                "conversation_complete": True,
            },
            session=session,
            hospital_id=context.hospital_id,
            purpose="voice_intake",
            prompt_version="voice-intake-v1",
        ),
    )

    conversation, _ = await agent.process_turn(
        context,
        await service.conversation(record),
        "Complete intake",
        datetime.now(timezone.utc),
    )

    state = conversation.model_dump(
        mode="json",
        exclude={"session_id", "outreach_task_id"},
    )

    # The explicit /complete endpoint always finishes the conversation.
    state["stage"] = "COMPLETION"
    state["completed"] = True

    return response(
        await service.save(
            record,
            state,
            "COMPLETION",
            True,
            datetime.now(timezone.utc),
        )
    )
