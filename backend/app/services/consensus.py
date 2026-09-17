from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.models import StructuredModel
from app.core.context import RequestContext
from app.core.errors import APIError
from app.models.triage import EscalationDecisionRecord
from app.schemas.ai import AgreementStatus, TriageClassification
from app.services.escalations import EscalationCaseService
from app.services.triage import ClinicalTriageService

SEVERITY = {
    TriageClassification.ROUTINE: 0,
    TriageClassification.INSUFFICIENT_INFORMATION: 1,
    TriageClassification.CONCERNING: 2,
    TriageClassification.URGENT: 3,
}


def conservative_consensus(classifications: list[TriageClassification]):
    """Deterministic application policy; never downgrade an urgent assessment."""
    if len(classifications) != 3:
        raise ValueError("Exactly three assessments are required")
    counts = Counter(classifications)
    final = max(classifications, key=lambda item: SEVERITY[item])
    if len(counts) == 1:
        return final, AgreementStatus.CONSENSUS, False, None
    majority = max(counts.values()) >= 2
    urgent = TriageClassification.URGENT in counts
    insufficient = TriageClassification.INSUFFICIENT_INFORMATION in counts
    review = urgent or insufficient or not majority
    reason = "assessments_disagree" if review else None
    return (
        final,
        AgreementStatus.MAJORITY if majority else AgreementStatus.DISAGREEMENT,
        review,
        reason,
    )


class ConsensusTriageService:
    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session, self.context = session, context
        self.hospital_id = context.require_clinical_tenant()

    async def assess_consensus(self, intake_session_id, models: list[StructuredModel], now):
        if len(models) != 3:
            raise APIError(422, "three_assessors_required", "Exactly three assessors are required")
        assessments = [
            await ClinicalTriageService(self.session, self.context, model).assess(
                intake_session_id, now
            )
            for model in models
        ]
        classifications = [TriageClassification(item.classification) for item in assessments]
        final, agreement, review, reason = conservative_consensus(classifications)
        decision = EscalationDecisionRecord(
            hospital_id=self.hospital_id,
            intake_session_id=intake_session_id,
            assessment_ids=[str(item.id) for item in assessments],
            final_classification=final.value,
            agreement_status=agreement.value,
            requires_human_review=review,
            disagreement_reason=reason,
            recommended_action="HUMAN_REVIEW" if review else "STANDARD_FOLLOW_UP",
            execution_metadata={"assessment_count": 3},
        )
        self.session.add(decision)
        await self.session.commit()
        await self.session.refresh(decision)
        await EscalationCaseService(self.session, self.context).create_for_decision(decision.id)
        return decision

    async def get(self, decision_id):
        decision = await self.session.scalar(
            select(EscalationDecisionRecord).where(
                EscalationDecisionRecord.id == decision_id,
                EscalationDecisionRecord.hospital_id == self.hospital_id,
            )
        )
        if decision is None:
            raise APIError(404, "not_found", "Escalation decision not found")
        return decision
