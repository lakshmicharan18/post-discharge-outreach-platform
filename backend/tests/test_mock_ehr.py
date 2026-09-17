from uuid import UUID, uuid4

import pytest

from app.core.context import CurrentUserContext
from app.core.errors import APIError
from app.models.entities import Role
from app.services.mock_ehr import LocalMockEHRClient


def context(tenant: int, role: Role = Role.HOSPITAL_ADMIN):
    return CurrentUserContext(UUID(int=tenant * 10), UUID(int=tenant), role)


async def test_failed_operation_retries_with_same_key_and_no_duplicate(session):
    task_id, reference_id = None, uuid4()
    failed = await LocalMockEHRClient(session, context(1), fail_writes=True).write_outreach_note(
        task_id, reference_id, {"safe": "payload"}
    )
    assert failed.status == "FAILED"
    assert failed.error == "deterministic mock EHR failure"
    retried = await LocalMockEHRClient(session, context(1)).retry(failed.id)
    assert retried.status == "SUCCEEDED"
    assert retried.idempotency_key == failed.idempotency_key
    assert (await LocalMockEHRClient(session, context(1)).retry(failed.id)).id == failed.id


async def test_tenant_and_platform_access_fail_closed(session):
    operation = await LocalMockEHRClient(session, context(1)).write_outreach_note(
        None, uuid4(), {"safe": "payload"}
    )
    with pytest.raises(APIError):
        await LocalMockEHRClient(session, context(2)).get(operation.id)
    with pytest.raises(APIError):
        LocalMockEHRClient(session, context(1, Role.PLATFORM_ADMIN))
