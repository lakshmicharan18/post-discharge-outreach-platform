from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.errors import APIError
from app.models.ehr import EHROperationRecord
from app.models.entities import Role
from app.services.audit import add_audit_event


class MockEHRClient(Protocol):
    async def write_outreach_note(self, task_id: UUID, reference_id: UUID, payload: dict): ...

    async def create_follow_up_task(self, task_id: UUID, reference_id: UUID, payload: dict): ...

    async def record_escalation_reference(
        self, task_id: UUID, reference_id: UUID, payload: dict
    ): ...


class LocalMockEHRClient:
    """Tenant-scoped local persistence; never calls an external EHR."""

    def __init__(
        self, session: AsyncSession, context: RequestContext, *, fail_writes: bool = False
    ) -> None:
        self.session, self.context = session, context
        self.hospital_id = context.require_clinical_tenant()
        self.fail_writes = fail_writes

    async def write_outreach_note(self, task_id: UUID, reference_id: UUID, payload: dict):
        return await self._write("OUTREACH_NOTE", task_id, reference_id, payload)

    async def create_follow_up_task(self, task_id: UUID, reference_id: UUID, payload: dict):
        return await self._write("FOLLOW_UP_TASK", task_id, reference_id, payload)

    async def record_escalation_reference(self, task_id: UUID, reference_id: UUID, payload: dict):
        return await self._write("ESCALATION_REFERENCE", task_id, reference_id, payload)

    async def _write(self, operation_type: str, task_id: UUID, reference_id: UUID, payload: dict):
        key = f"{operation_type}:{reference_id}"
        existing = await self.session.scalar(
            select(EHROperationRecord).where(
                EHROperationRecord.hospital_id == self.hospital_id,
                EHROperationRecord.idempotency_key == key,
            )
        )
        if existing is not None:
            return existing
        operation = EHROperationRecord(
            hospital_id=self.hospital_id,
            outreach_task_id=task_id,
            reference_id=reference_id,
            operation_type=operation_type,
            idempotency_key=key,
            safe_payload=payload,
            status="FAILED" if self.fail_writes else "SUCCEEDED",
            completed_at=None if self.fail_writes else datetime.now(timezone.utc),
            error="deterministic mock EHR failure" if self.fail_writes else None,
        )
        self.session.add(operation)
        await self.session.flush()
        await add_audit_event(
            self.session,
            self.context,
            self.hospital_id,
            "EHR_WRITE_FAILED" if self.fail_writes else "EHR_WRITE_SUCCEEDED",
            "EHROperationRecord",
            operation.id,
        )
        await self.session.commit()
        return operation

    async def retry(self, operation_id: UUID) -> EHROperationRecord:
        """Retry a local failed operation without changing its idempotency key."""
        operation = await self.get(operation_id)
        if operation.status == "SUCCEEDED":
            return operation
        if self.fail_writes:
            return operation
        operation.status = "SUCCEEDED"
        operation.error = None
        operation.completed_at = datetime.now(timezone.utc)
        await add_audit_event(
            self.session,
            self.context,
            self.hospital_id,
            "EHR_WRITE_RETRIED",
            "EHROperationRecord",
            operation.id,
        )
        await self.session.commit()
        await self.session.refresh(operation)
        return operation

    async def get(self, operation_id: UUID) -> EHROperationRecord:
        operation = await self.session.scalar(
            select(EHROperationRecord).where(
                EHROperationRecord.id == operation_id,
                EHROperationRecord.hospital_id == self.hospital_id,
            )
        )
        if operation is None:
            raise APIError(404, "not_found", "EHR operation not found")
        return operation

    async def list(self) -> list[EHROperationRecord]:
        self.context.require_roles(
            Role.HOSPITAL_ADMIN, Role.CAMPAIGN_MANAGER, Role.CLINICAL_REVIEWER
        )
        return list(
            await self.session.scalars(
                select(EHROperationRecord).where(EHROperationRecord.hospital_id == self.hospital_id)
            )
        )
