from fastapi import APIRouter, Depends, HTTPException, status

from app.deps import get_current_user_id
from app.schemas import SubscriptionStatusOut
from app.services.subscription import (
    ClerkSubscriptionUnavailable,
    SUBSCRIPTION_VERIFY_UNAVAILABLE_DETAIL,
    user_has_premium_plan,
)

router = APIRouter(prefix="/api", tags=["subscription"])


@router.get("/subscription", response_model=SubscriptionStatusOut)
async def get_subscription_status(user_id: str = Depends(get_current_user_id)):
    try:
        has = await user_has_premium_plan(user_id)
    except ClerkSubscriptionUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            SUBSCRIPTION_VERIFY_UNAVAILABLE_DETAIL,
        ) from exc
    return SubscriptionStatusOut(has_premium=has)
