"""Deterministic prototype simulation over existing scheduler and outcomes."""
from datetime import datetime, timedelta, timezone
from uuid import UUID
from sqlalchemy import func, select
from app.core.context import RequestContext
from app.core.errors import APIError
from app.models.campaigns import OutreachOutcome, OutreachTask, OutreachTaskState
from app.models.entities import Role
from app.models.healthcare import HospitalConfiguration
from app.schemas.outreach import OutcomeRequest
from app.services.outcomes import OutcomeService
from app.services.scheduler import ACTIVE_STATES, QueueSchedulerService

RUNS: dict[UUID, dict] = {}
PLANS = [["COMPLETED"], ["NO_ANSWER", "COMPLETED"], ["BUSY", "COMPLETED"], ["VOICEMAIL", "COMPLETED"], ["DROPPED", "COMPLETED"], ["CALLBACK_REQUESTED", "COMPLETED"], ["TECHNICAL_FAILURE", "COMPLETED"], ["INVALID_NUMBER"], ["BUSY", "NO_ANSWER", "VOICEMAIL"]]

class SimulationService:
    def __init__(self, session, context: RequestContext):
        self.session, self.context, self.hospital_id = session, context, context.require_clinical_tenant()
    def _run(self):
        if self.hospital_id not in RUNS: raise APIError(409, "simulation_required", "Initialize simulation first")
        return RUNS[self.hospital_id]
    async def setup(self):
        self.context.require_roles(Role.HOSPITAL_ADMIN, Role.CAMPAIGN_MANAGER)
        rows = list(await self.session.scalars(select(OutreachTask).where(OutreachTask.hospital_id == self.hospital_id).order_by(OutreachTask.id).limit(30)))
        if len(rows) < 20: raise APIError(409, "simulation_data_required", "Create at least 20 tenant outreach tasks for the deterministic simulation")
        config = await self.session.scalar(select(HospitalConfiguration).where(HospitalConfiguration.hospital_id == self.hospital_id))
        config.max_concurrent_calls = min(config.max_concurrent_calls, 3)
        now = datetime(2026, 1, 5, 10, tzinfo=timezone.utc)
        for i, task in enumerate(rows[:24]):
            task.state, task.attempt_count, task.next_eligible_at = OutreachTaskState.PENDING, 0, now
            task.max_attempts = 3
        await self.session.commit()
        RUNS[self.hospital_id] = {"now": now, "steps": 0, "plans": {str(t.id): PLANS[i % len(PLANS)] for i,t in enumerate(rows[:24])}, "events": [{"at":now.isoformat(),"type":"SCENARIO_INITIALIZED","details":{"tasks":24}}]}
        return await self.status()
    async def step(self):
        self.context.require_roles(Role.HOSPITAL_ADMIN, Role.CAMPAIGN_MANAGER); run=self._run(); now=run["now"]
        task=await QueueSchedulerService(self.session,self.context).reserve_next(now)
        if task is None: return await self.status()
        service=OutcomeService(self.session,self.context); await service.start(task.id,now,"simulation")
        name=run["plans"][str(task.id)][min(task.attempt_count,len(run["plans"][str(task.id)])-1)]
        outcome=OutreachOutcome(name); callback=now+timedelta(minutes=30) if outcome==OutreachOutcome.CALLBACK_REQUESTED else None
        result=await service.process(task.id,OutcomeRequest(outcome=outcome,idempotency_key=f"sim-{task.id}-{task.attempt_count+1}",callback_at=callback,partial_context={"completed_questions":["intake"]} if outcome==OutreachOutcome.DROPPED else None),now)
        run["steps"]+=1; run["events"].append({"at":now.isoformat(),"type":outcome.value,"details":{"task_id":str(task.id),"state":result.state.value}})
        return await self.status()
    async def advance(self, minutes:int):
        self.context.require_roles(Role.HOSPITAL_ADMIN, Role.CAMPAIGN_MANAGER); run=self._run(); run["now"]+=timedelta(minutes=minutes); run["events"].append({"at":run["now"].isoformat(),"type":"TIME_ADVANCED","details":{"minutes":minutes}}); return await self.status()
    async def status(self):
        run=self._run(); config=await self.session.scalar(select(HospitalConfiguration).where(HospitalConfiguration.hospital_id==self.hospital_id))
        states=list(await self.session.scalars(select(OutreachTask.state).where(OutreachTask.hospital_id==self.hospital_id)))
        active=sum(states.count(s) for s in ACTIVE_STATES)
        if active>config.max_concurrent_calls: raise APIError(409,"simulation_capacity_violation","Simulation capacity invariant failed")
        return {"simulated_now":run["now"],"steps_processed":run["steps"],"configured_capacity":config.max_concurrent_calls,"active_capacity":active,"state_counts":{s.value:states.count(s) for s in OutreachTaskState if states.count(s)},"events":run["events"]}
