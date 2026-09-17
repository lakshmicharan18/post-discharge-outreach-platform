from datetime import datetime, timezone

import pytest
from conftest import uid
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.campaigns import SimulationEvent, SimulationRun, SimulationRunStatus


def simulation_run(**changes) -> SimulationRun:
    now = datetime(2026, 1, 5, 10, tzinfo=timezone.utc)
    values = {
        "hospital_id": uid(1),
        "status": SimulationRunStatus.RUNNING,
        "scenario_name": "deterministic-queue",
        "simulated_now": now,
        "step_count": 0,
        "configured_capacity": 3,
        "started_at": now,
        "created_by_user_id": uid(10),
    }
    return SimulationRun(**(values | changes))


async def test_simulation_run_and_events_persist_in_sequence_order(session):
    run = simulation_run()
    session.add(run)
    await session.flush()
    session.add_all(
        [
            SimulationEvent(
                hospital_id=run.hospital_id,
                simulation_run_id=run.id,
                sequence_number=2,
                event_type="TIME_ADVANCED",
                simulated_at=run.simulated_now,
                safe_payload={"minutes": 30},
            ),
            SimulationEvent(
                hospital_id=run.hospital_id,
                simulation_run_id=run.id,
                sequence_number=1,
                event_type="SCENARIO_INITIALIZED",
                simulated_at=run.simulated_now,
                safe_payload={"task_count": 24},
            ),
        ]
    )
    await session.flush()

    events = list(
        await session.scalars(
            select(SimulationEvent)
            .where(SimulationEvent.simulation_run_id == run.id)
            .order_by(SimulationEvent.sequence_number)
        )
    )
    assert [event.sequence_number for event in events] == [1, 2]
    assert events[0].safe_payload == {"task_count": 24}
    assert run.created_at.tzinfo is not None
    assert run.updated_at.tzinfo is not None
    assert events[0].created_at.tzinfo is not None


async def test_simulation_event_rejects_duplicate_sequence_and_wrong_tenant_run(session):
    run = simulation_run()
    session.add(run)
    await session.flush()
    event = SimulationEvent(
        hospital_id=run.hospital_id,
        simulation_run_id=run.id,
        sequence_number=1,
        event_type="SCENARIO_INITIALIZED",
        simulated_at=run.simulated_now,
        safe_payload={},
    )
    session.add(event)
    await session.flush()

    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(
                SimulationEvent(
                    hospital_id=run.hospital_id,
                    simulation_run_id=run.id,
                    sequence_number=1,
                    event_type="DUPLICATE",
                    simulated_at=run.simulated_now,
                    safe_payload={},
                )
            )
            await session.flush()

    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(
                SimulationEvent(
                    hospital_id=uid(2),
                    simulation_run_id=run.id,
                    sequence_number=2,
                    event_type="CROSS_TENANT",
                    simulated_at=run.simulated_now,
                    safe_payload={},
                )
            )
            await session.flush()
