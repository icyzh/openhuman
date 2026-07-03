from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.gateway.models import SlackAppSlot
from app.gateway.schemas import SlotPoolResponse
from app.gateway.slack_app_provisioning import count_available_slots

router = APIRouter(prefix="/api/slack/slots", tags=["slack-slots"])


@router.get("/pool", response_model=SlotPoolResponse)
async def get_slot_pool_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SlotPoolResponse:
    """Return current Slack app slot pool capacity and health."""
    available = await count_available_slots(db)

    total_result = await db.execute(select(func.count(SlackAppSlot.id)))
    total = total_result.scalar() or 0

    threshold = settings.slack_slot_pool_threshold
    healthy = available >= threshold

    return SlotPoolResponse(
        available=available,
        total=total,
        threshold=threshold,
        healthy=healthy,
    )
