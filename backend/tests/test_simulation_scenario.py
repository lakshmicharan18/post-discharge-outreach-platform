from datetime import datetime, timedelta

import pytest
from conftest import uid
from sqlalchemy import func, select

from app.core.context import RequestContext
from app.core.errors import APIError
from app.models.campaigns import OutreachTask, SimulationEvent
from app.models.entities import Role
from app.services.simulation import SimulationService
from app.services.simulation_scenario import SCENARIO_PATIENTS, SCENARIO_START_ISO, scenario_payload


def context(hospital: int) -> RequestContext:
    return RequestContext(uid(hospital * 10), uid(hospital), Role.HOSPITAL_ADMIN)


def test_fixed_scenario_has_required_logical_variation():
    payload = scenario_payload()
    outcomes = {outcome for patient in payload for outcome in patient["outcomes"]}
    assert len(payload) == len(SCENARIO_PATIENTS) == 25
    assert {patient["risk"] for patient in payload} == {"LOW", "MEDIUM", "HIGH"}
    assert {
        "COMPLETED",
        "NO_ANSWER",
        "BUSY",
        "VOICEMAIL",
        "DROPPED",
        "CALLBACK_REQUESTED",
        "TECHNICAL_FAILURE",
        "INVALID_NUMBER",
    } <= outcomes
    assert len({patient["deadline_offset_minutes"] for patient in payload}) > 1
    assert any(patient["outcomes"] == ["NO_ANSWER", "COMPLETED"] for patient in payload)
    assert any(patient["outcomes"] == ["BUSY", "NO_ANSWER", "VOICEMAIL"] for patient in payload)
    assert any(patient["callback_offset_minutes"] is not None for patient in payload)
    assert all(
        patient["dropped_partial_context"] is None
        or set(patient["dropped_partial_context"]) == {"completed_questions"}
        for patient in payload
    )


async def test_initialization_clock_reset_and_tenant_isolation(session):
    service_a = SimulationService(session, context(1))
    run_a = await service_a.initialize()
    expected_start = datetime.fromisoformat(SCENARIO_START_ISO)
    assert run_a.simulated_now == expected_start
    assert (
        await session.scalar(
            select(func.count()).select_from(OutreachTask).where(OutreachTask.hospital_id == uid(1))
        )
        == 25
    )

    event_a = await session.scalar(
        select(SimulationEvent).where(SimulationEvent.simulation_run_id == run_a.id)
    )
    first_definition = event_a.safe_payload["patients"]
    assert event_a.safe_payload["patient_count"] == 25
    assert {row["risk"] for row in first_definition} == {"LOW", "MEDIUM", "HIGH"}
    assert min(row["deadline_offset_minutes"] for row in first_definition) == 90

    advanced = await service_a.advance_clock(30)
    assert advanced.simulated_now == expected_start + timedelta(minutes=30)
    assert (await service_a.get_run()).simulated_now == expected_start + timedelta(minutes=30)

    reset = await service_a.reset()
    reset_event = await session.scalar(
        select(SimulationEvent).where(SimulationEvent.simulation_run_id == reset.id)
    )
    assert reset.simulated_now == expected_start
    assert reset_event.safe_payload["patients"] == first_definition

    service_b = SimulationService(session, context(2))
    with pytest.raises(APIError) as error:
        await service_b.get_run()
    assert error.value.status == 404
    await service_b.reset()
    assert (await service_a.get_run()).id == reset.id
    assert (
        await session.scalar(
            select(func.count()).select_from(OutreachTask).where(OutreachTask.hospital_id == uid(1))
        )
        == 25
    )
    assert (
        await session.scalar(
            select(func.count()).select_from(OutreachTask).where(OutreachTask.hospital_id == uid(2))
        )
        == 25
    )
