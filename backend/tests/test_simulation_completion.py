import pytest
from conftest import uid
from sqlalchemy import select

from app.core.context import RequestContext
from app.core.errors import APIError
from app.models.campaigns import SimulationEvent, SimulationRunStatus
from app.models.entities import Role
from app.services.simulation import SimulationService


def context(hospital: int) -> RequestContext:
    return RequestContext(uid(hospital * 10), uid(hospital), Role.HOSPITAL_ADMIN)


async def test_run_to_completion_produces_deterministic_terminal_summary(session):
    service = SimulationService(session, context(1))
    run = await service.initialize()
    result = await service.run_to_completion(run.id)
    summary = result["summary"]
    assert not result["guard_triggered"]
    assert summary["status"] == SimulationRunStatus.COMPLETED.value
    assert summary["total_tasks"] == 25
    assert summary["completed"] + summary["manual_follow_up"] == 25
    assert summary["total_attempts"] >= 25
    assert summary["capacity_exceeded"] is False
    assert summary["active"] == 0
    assert summary["outcome_counts"]["INVALID_NUMBER"] == 2

    events = list(
        await session.scalars(
            select(SimulationEvent)
            .where(SimulationEvent.simulation_run_id == run.id)
            .order_by(SimulationEvent.sequence_number)
        )
    )
    assert [event.sequence_number for event in events] == list(range(1, len(events) + 1))
    assert "CLOCK_ADVANCED" in {event.event_type for event in events}


async def test_run_cycle_guard_and_tenant_scope(session):
    service_a = SimulationService(session, context(1))
    run = await service_a.initialize()
    guarded = await service_a.run_to_completion(run.id, max_cycles=1)
    assert guarded["guard_triggered"]
    assert guarded["summary"]["status"] == SimulationRunStatus.FAILED.value

    service_b = SimulationService(session, context(2))
    with pytest.raises(APIError) as error:
        await service_b.summary(run.id)
    assert error.value.status == 404
