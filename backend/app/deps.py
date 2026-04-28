import logging

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.config import settings
from app.services.subscription import (
    ClerkSubscriptionUnavailable,
    SUBSCRIPTION_VERIFY_UNAVAILABLE_DETAIL,
    user_has_premium_plan,
)

logger = logging.getLogger(__name__)
clerk_guard = HTTPBearer(auto_error=False)
_jwks_url = settings.clerk_jwks_url or "https://invalid.invalid"
_jwks_client = PyJWKClient(_jwks_url, timeout=15)


async def get_current_user_id(
    creds: HTTPAuthorizationCredentials | None = Depends(clerk_guard),
) -> str:
    if not creds or creds.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")

    token = creds.credentials
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        decoded = jwt.decode(
            token,
            key=signing_key.key,
            algorithms=["RS256"],
            options={
                "verify_exp": True,
                "verify_aud": False,
                "verify_iss": False,
                # Clerk SDKs can have small clock skew; be tolerant.
                "verify_iat": False,
            },
            leeway=60,
        )
    except Exception as exc:
        logger.warning("Failed Clerk JWT verification against %s: %s", _jwks_url, exc)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid auth token") from exc

    sub = decoded.get("sub")
    if not sub:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    return str(sub)


async def require_premium(
    user_id: str = Depends(get_current_user_id),
) -> str:
    if not settings.require_subscription:
        return user_id
    try:
        ok = await user_has_premium_plan(user_id)
    except ClerkSubscriptionUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            SUBSCRIPTION_VERIFY_UNAVAILABLE_DETAIL,
        ) from exc
    if not ok:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Active subscription required for Emet fact-checking.",
        )
    return user_id
