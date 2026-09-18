from datetime import datetime, timezone
from uuid import UUID, uuid4

from conftest import auth_headers
from test_escalation_notification_delivery import urgent_case_and_event

from app.models.ai import AIExecution
from app.models.notifications import Notification, NotificationSeverity, NotificationStatus
from app.models.workflow import WorkflowEvent, WorkflowEventStatus


def workflow_event(hospital_id: UUID, status: WorkflowEventStatus, suffix: str) -> WorkflowEvent:
    return WorkflowEvent(
        hospital_id=hospital_id,
        event_type="SEND_NOTIFICATION",
        payload={"transcript": "do not expose", "secret": "do not expose"},
        status=status,
        attempt_count=1,
        max_attempts=3,
        next_attempt_at=datetime.now(timezone.utc),
        idempotency_key=f"idempotency-secret-{suffix}",
        last_error_type="handler_failure" if status == WorkflowEventStatus.FAILED else None,
    )


def ai_execution(hospital_id: UUID, success: bool, latency_ms: int) -> AIExecution:
    return AIExecution(
        hospital_id=hospital_id,
        purpose="triage",
        provider="openai-compatible",
        model="test-model",
        prompt_version="triage-v1",
        latency_ms=latency_ms,
        success=success,
        input_tokens=12 if success else None,
        output_tokens=7 if success else None,
        estimated_cost=None,
        error_type=None if success else "provider_failure",
    )


async def test_operations_summary_is_aggregated_and_excludes_sensitive_fields(client, session):
    await urgent_case_and_event(client, session)
    session.add_all(
        [
            workflow_event(UUID(int=1), WorkflowEventStatus.PENDING, "one"),
            workflow_event(UUID(int=1), WorkflowEventStatus.PROCESSING, "two"),
            workflow_event(UUID(int=1), WorkflowEventStatus.FAILED, "three"),
            workflow_event(UUID(int=2), WorkflowEventStatus.PENDING, "foreign"),
            Notification(
                hospital_id=UUID(int=1),
                notification_type="URGENT_ESCALATION",
                title="Urgent review required",
                message="Internal safe message",
                severity=NotificationSeverity.URGENT,
                status=NotificationStatus.UNREAD,
            ),
            Notification(
                hospital_id=UUID(int=1),
                notification_type="INFO",
                title="Read notification",
                message="Internal safe message",
                severity=NotificationSeverity.INFO,
                status=NotificationStatus.READ,
            ),
            Notification(
                hospital_id=UUID(int=2),
                notification_type="INFO",
                title="Foreign notification",
                message="Internal safe message",
                severity=NotificationSeverity.INFO,
                status=NotificationStatus.UNREAD,
            ),
            ai_execution(UUID(int=1), True, 100),
            ai_execution(UUID(int=1), False, 300),
            ai_execution(UUID(int=2), True, 900),
        ]
    )
    await session.commit()

    response = await client.get("/api/v1/operations/summary", headers=auth_headers(10))

    assert response.status_code == 200
    body = response.json()
    assert body["workflows"] == {
        "pending": 2,
        "processing": 1,
        "retry_scheduled": 0,
        "succeeded": 0,
        "failed": 1,
    }
    assert body["escalations"] == {"open": 1, "in_review": 0, "resolved": 0, "urgent_open": 1}
    assert body["notifications"] == {"unread": 1, "urgent_unread": 1}
    assert body["ai_executions"] == {
        "total": 2,
        "successful": 1,
        "failed": 1,
        "average_latency_ms": 200.0,
    }
    assert {item["status"] for item in body["recent_workflows"]} == {
        "PENDING",
        "PROCESSING",
        "FAILED",
    }
    assert all(
        set(item)
        == {
            "id",
            "event_type",
            "status",
            "attempt_count",
            "max_attempts",
            "next_attempt_at",
            "processed_at",
            "last_error_type",
            "created_at",
        }
        for item in body["recent_workflows"]
    )
    assert all(
        set(item)
        == {
            "id",
            "purpose",
            "provider",
            "model",
            "prompt_version",
            "latency_ms",
            "success",
            "input_tokens",
            "output_tokens",
            "error_type",
            "created_at",
        }
        for item in body["recent_ai_executions"]
    )
    assert "do not expose" not in response.text
    assert "idempotency-secret" not in response.text
    assert "transcript" not in response.text


async def test_operations_summary_is_tenant_scoped(client, session):
    foreign_event = workflow_event(UUID(int=2), WorkflowEventStatus.SUCCEEDED, uuid4().hex)
    local_event = workflow_event(UUID(int=1), WorkflowEventStatus.FAILED, uuid4().hex)
    session.add_all((foreign_event, local_event, ai_execution(UUID(int=2), True, 40)))
    await session.commit()

    response = await client.get("/api/v1/operations/summary", headers=auth_headers(20))

    assert response.status_code == 200
    body = response.json()
    assert body["workflows"]["succeeded"] == 1
    assert body["workflows"]["failed"] == 0
    assert body["ai_executions"]["total"] == 1
    assert [item["id"] for item in body["recent_workflows"]] == [str(foreign_event.id)]
    assert str(local_event.id) not in response.text
