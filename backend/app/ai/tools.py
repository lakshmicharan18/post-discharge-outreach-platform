"""Explicit, tenant-bound tools for future AI agents.

This module intentionally has no model or repository reflection and no SQL builder.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Awaitable, Callable

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.errors import APIError
from app.models.campaigns import OutreachOutcome, StructuredCallNote
from app.models.healthcare import CarePlan, Medication
from app.schemas.ai import (
    CallbackToolInput,
    KnowledgeSearchToolInput,
    PatientToolInput,
    SafeToolError,
    StructuredCallNoteInput,
    TaskToolInput,
    ToolRequest,
    ToolResult,
)
from app.services.audit import add_audit_event
from app.services.configuration import HospitalConfigurationService
from app.services.healthcare import HealthcareService, PatientContextService
from app.services.knowledge import KnowledgeService
from app.services.outcomes import OutcomeService
from app.services.outreach import OutreachWorkService

ToolHandler = Callable[[BaseModel], Awaitable[dict[str, Any]]]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, tuple[type[BaseModel], ToolHandler]] = {}

    def register(self, name: str, input_schema: type[BaseModel], handler: ToolHandler) -> None:
        self._tools[name] = (input_schema, handler)

    async def invoke(self, request: ToolRequest) -> ToolResult:
        tool = self._tools.get(request.name)
        if tool is None:
            return ToolResult(
                name=request.name,
                request_id=request.request_id,
                success=False,
                error=SafeToolError(code="tool_not_allowed", message="Tool is not allowlisted"),
            )
        schema, handler = tool
        try:
            return ToolResult(
                name=request.name,
                request_id=request.request_id,
                success=True,
                data=await handler(schema.model_validate(request.arguments)),
            )
        except APIError as exc:
            code = "forbidden" if exc.status_code == 403 else "not_found"
            return ToolResult(
                name=request.name,
                request_id=request.request_id,
                success=False,
                error=SafeToolError(code=code, message="Tool request was rejected"),
            )
        except ValueError:
            return ToolResult(
                name=request.name,
                request_id=request.request_id,
                success=False,
                error=SafeToolError(code="invalid_input", message="Tool input is invalid"),
            )


class ControlledAITools:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session, self.context = session, context
        self.hospital_id = context.require_clinical_tenant()
        self.registry = ToolRegistry()
        self._register_tools()

    async def invoke(self, request: ToolRequest) -> ToolResult:
        result = await self.registry.invoke(request)
        await add_audit_event(
            self.session,
            self.context,
            self.hospital_id,
            "AI_TOOL_EXECUTED",
            "AITool",
            None,
            {
                "tool": request.name,
                "request_id": str(request.request_id),
                "success": result.success,
            },
        )
        await self.session.commit()
        return result

    def _register_tools(self) -> None:
        self.registry.register("get_patient_context", PatientToolInput, self._patient_context)
        self.registry.register("get_recent_encounter", PatientToolInput, self._recent_encounter)
        self.registry.register("get_discharge_plan", PatientToolInput, self._discharge_plan)
        self.registry.register("get_medications", PatientToolInput, self._medications)
        self.registry.register("get_care_plan", PatientToolInput, self._care_plan)
        self.registry.register("get_hospital_configuration", BaseModel, self._configuration)
        self.registry.register("get_current_outreach_task", TaskToolInput, self._task)
        self.registry.register("record_structured_call_note", StructuredCallNoteInput, self._note)
        self.registry.register("request_callback", CallbackToolInput, self._callback)
        self.registry.register(
            "search_hospital_knowledge", KnowledgeSearchToolInput, self._knowledge_search
        )

    async def _patient_context(self, payload: PatientToolInput) -> dict[str, Any]:
        context = await PatientContextService(self.session, self.context).context(
            payload.patient_id
        )
        return {
            "patient_id": str(context.patient.id),
            "preferred_language": context.patient.preferred_language,
            "communication_preferences": context.patient.communication_preferences,
            "timeline": [event.model_dump(mode="json") for event in context.timeline],
        }

    async def _recent_encounter(self, payload: PatientToolInput) -> dict[str, Any]:
        encounters = (
            await PatientContextService(self.session, self.context).context(payload.patient_id)
        ).encounters
        encounter = max(encounters, key=lambda item: item.admit_at, default=None)
        return {"encounter": encounter.model_dump(mode="json") if encounter else None}

    async def _discharge_plan(self, payload: PatientToolInput) -> dict[str, Any]:
        discharges = (
            await PatientContextService(self.session, self.context).context(payload.patient_id)
        ).discharges
        discharge = max(discharges, key=lambda item: item.discharge_at, default=None)
        if discharge is None:
            return {"discharge": None}
        return {
            "discharge": {
                "id": str(discharge.id),
                "instructions": discharge.discharge_instructions,
                "deadline": discharge.follow_up_deadline.isoformat(),
            }
        }

    async def _medications(self, payload: PatientToolInput) -> dict[str, Any]:
        rows = await HealthcareService(self.session, self.context, Medication).list_for_patient(
            payload.patient_id
        )
        return {
            "medications": [
                {
                    "id": str(row.id),
                    "name": row.medication_name,
                    "dose": row.dose,
                    "frequency": row.frequency,
                    "instructions": row.instructions,
                    "status": row.status,
                }
                for row in rows
            ]
        }

    async def _care_plan(self, payload: PatientToolInput) -> dict[str, Any]:
        rows = await HealthcareService(self.session, self.context, CarePlan).list_for_patient(
            payload.patient_id
        )
        return {
            "care_plans": [
                {
                    "id": str(row.id),
                    "title": row.title,
                    "instructions": row.follow_up_instructions,
                    "status": row.status,
                }
                for row in rows
            ]
        }

    async def _configuration(self, _: BaseModel) -> dict[str, Any]:
        config = await HospitalConfigurationService(self.session, self.context).get_own()
        return {
            "timezone": config.timezone,
            "calling_window_start": config.calling_window_start.isoformat(),
            "calling_window_end": config.calling_window_end.isoformat(),
        }

    async def _task(self, payload: TaskToolInput) -> dict[str, Any]:
        task = await OutreachWorkService(self.session, self.context).get(payload.task_id)
        return {
            "task_id": str(task.id),
            "patient_id": str(task.patient_id),
            "state": task.state.value,
            "callback_at": task.callback_at.isoformat() if task.callback_at else None,
        }

    async def _note(self, payload: StructuredCallNoteInput) -> dict[str, Any]:
        task = await OutreachWorkService(self.session, self.context).get(payload.task_id)
        note = StructuredCallNote(
            hospital_id=self.hospital_id,
            outreach_task_id=task.id,
            patient_id=task.patient_id,
            note=payload.note.model_dump(mode="json"),
        )
        self.session.add(note)
        await self.session.flush()
        return {"note_id": str(note.id), "task_id": str(task.id)}

    async def _callback(self, payload: CallbackToolInput) -> dict[str, Any]:
        task = await OutcomeService(self.session, self.context).process(
            payload.task_id,
            SimpleNamespace(
                outcome=OutreachOutcome.CALLBACK_REQUESTED,
                idempotency_key=payload.idempotency_key,
                callback_at=payload.callback_at,
                outcome_reason="AI_REQUESTED_CALLBACK",
                technical_error_code=None,
                partial_context=None,
            ),
            datetime.now(timezone.utc),
        )
        return {
            "task_id": str(task.id),
            "state": task.state.value,
            "callback_at": task.callback_at.isoformat() if task.callback_at else None,
        }

    async def _knowledge_search(self, payload: KnowledgeSearchToolInput) -> dict[str, Any]:
        return {
            "references": await KnowledgeService(self.session, self.context).search(
                payload.query, payload.top_k
            )
        }
