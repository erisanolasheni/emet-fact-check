from fastapi import APIRouter, Depends

from app.deps import get_current_user_id
from app.schemas import SubscriptionStatusOut
from app.services.subscription import user_has_premium_plan

router = APIRouter(prefix="/api", tags=["subscription"])


@router.get("/subscription", response_model=SubscriptionStatusOut)
async def get_subscription_status(user_id: str = Depends(get_current_user_id)):
    """Return whether the signed-in user has the configured Clerk Billing plan (server-verified; same logic as `require_premium`)."""
    return SubscriptionStatusOut(has_premium=await user_has_premium_plan(user_id))
