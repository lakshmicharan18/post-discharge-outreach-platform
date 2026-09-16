from datetime import datetime

from app.models.campaigns import Campaign
from app.schemas.eligibility import EligibilityResult

RISK_SCORES = {"LOW": 0, "UNKNOWN": 5, "MEDIUM": 20, "HIGH": 40}


def score_outreach_task(
    campaign: Campaign,
    result: EligibilityResult,
    *,
    now: datetime,
    eligible_at: datetime,
    attempt_count: int = 0,
    callback_at: datetime | None = None,
) -> dict[str, int]:
    """Higher values are more urgent. `now` is explicit for reproducible scoring."""
    remaining_hours = (result.follow_up_deadline - now).total_seconds() / 3600
    deadline = (
        50
        if remaining_hours <= 1
        else 35
        if remaining_hours <= 6
        else 20
        if remaining_hours <= 24
        else 10
        if remaining_hours <= 72
        else 0
    )
    waiting_hours = max(0, (now - eligible_at).total_seconds() / 3600)
    components = {
        "risk": RISK_SCORES.get(result.risk_level, RISK_SCORES["UNKNOWN"]),
        "deadline_urgency": deadline,
        "campaign_priority": (campaign.campaign_priority or 0) // 5,
        "waiting_age": min(20, int(waiting_hours // 12)),
        "retry": -5 * attempt_count,
        "callback": 25 if callback_at is not None and callback_at <= now else 0,
    }
    components["total"] = sum(components.values())
    return components
