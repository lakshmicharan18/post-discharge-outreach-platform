from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.errors import APIError
from app.models.campaigns import Campaign


class CampaignRepository:
    """Campaign access always derives tenant scope from authenticated context."""

    def __init__(self, session: AsyncSession, context: RequestContext) -> None:
        self.session = session
        self.hospital_id = context.require_clinical_tenant()

    async def get(self, campaign_id: UUID) -> Campaign:
        campaign = await self.session.scalar(
            select(Campaign).where(
                Campaign.id == campaign_id,
                Campaign.hospital_id == self.hospital_id,
            )
        )
        if campaign is None:
            raise APIError(404, "not_found", "Campaign not found")
        return campaign

    async def list(self, limit: int, offset: int) -> list[Campaign]:
        return list(
            await self.session.scalars(
                select(Campaign)
                .where(Campaign.hospital_id == self.hospital_id)
                .order_by(Campaign.created_at.desc(), Campaign.id)
                .limit(limit)
                .offset(offset)
            )
        )

    async def create(self, values: dict) -> Campaign:
        campaign = Campaign(hospital_id=self.hospital_id, **values)
        self.session.add(campaign)
        await self.session.flush()
        return campaign
