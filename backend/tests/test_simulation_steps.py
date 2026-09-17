import pytest
from conftest import uid
from sqlalchemy import select

from app.core.context import RequestContext
from app.core.errors import APIError
from app.models.campaigns import OutreachAttempt, OutreachTask, OutreachTaskState, SimulationEvent
from app.models.entities import Patient, Role
from app.services.simulation import SimulationService


def context(hospital: int) -> RequestContext:
    return RequestContext(uid(hospital * 10), uid(hospital), Role.HOSPITAL_ADMIN)


async def scenario_rows(session, hospital_id):
    return list(
        await session.execute(
            select(Patient.external_patient_id, OutreachTask, OutreachAttempt)
            .join(OutreachTask, OutreachTask.patient_id == Patient.id)
            .outerjoin(OutreachAttempt, OutreachAttempt.outreach_task_id == OutreachTask.id)
            .where(Patient.hospital_id == hospital_id)
            .order_by(Patient.external_patient_id, OutreachAttempt.attempt_number)
        )
    )


async def test_step_uses_scheduler_outcomes_clock_and_persists_events(session):
    service = SimulationService(session, context(1))
    run = await service.initialize()
    first = await service.step(run.id)
    assert first["reserved_count"] == first["calls_started"] == first["outcomes_recorded"] == 3
    assert first["active_count"] <= run.configured_capacity

    rows = await scenario_rows(session, uid(1))
    attempts = {key: attempt for key, _, attempt in rows if attempt is not None}
    assert attempts["SIM-25-S24"].outcome.value == "BUSY"
    assert attempts["SIM-25-S21"].outcome.value == "INVALID_NUMBER"
    task_s24 = next(task for key, task, _ in rows if key == "SIM-25-S24")
    assert task_s24.state == OutreachTaskState.RETRY_SCHEDULED
    retry_at = task_s24.next_eligible_at

    await service.advance_clock(30)
    before_due = await service.step(run.id)
    assert before_due["simulated_now"] < retry_at
    rows = await scenario_rows(session, uid(1))
    assert len([attempt for key, _, attempt in rows if key == "SIM-25-S24" and attempt]) == 1

    await service.advance_clock(30)
    await service.step(run.id)
    rows = await scenario_rows(session, uid(1))
    s24_attempts = [attempt for key, _, attempt in rows if key == "SIM-25-S24" and attempt]
    assert [attempt.outcome.value for attempt in s24_attempts] == ["BUSY", "COMPLETED"]

    events = list(
        await session.scalars(
            select(SimulationEvent)
            .where(SimulationEvent.simulation_run_id == run.id)
            .order_by(SimulationEvent.sequence_number)
        )
    )
    assert [event.sequence_number for event in events] == list(range(1, len(events) + 1))
    assert {"TASK_RESERVED", "CALL_STARTED", "OUTCOME_RECORDED", "RETRY_SCHEDULED"} <= {
        event.event_type for event in events
    }


async def test_step_is_tenant_scoped(session):
    service_a = SimulationService(session, context(1))
    run_a = await service_a.initialize()
    service_b = SimulationService(session, context(2))
    with pytest.raises(APIError) as error:
        await service_b.step(run_a.id)
    assert error.value.status == 404
