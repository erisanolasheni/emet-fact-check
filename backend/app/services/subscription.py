import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

SUBSCRIPTION_VERIFY_UNAVAILABLE_DETAIL = (
    "Could not verify subscription with Clerk. Retry later or check outbound "
    "HTTPS to api.clerk.com."
)


class ClerkSubscriptionUnavailable(Exception):
    pass


_BILLING_SUB = "https://api.clerk.com/v1/users/{user_id}/billing/subscription"
_COMMERCE_LIST = "https://api.clerk.com/v1/commerce/subscriptions"

_ACTIVE = frozenset({"active", "trialing", "past_due"})


def _plan_identifiers(obj: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    plan = obj.get("plan")
    if isinstance(plan, dict):
        for k in ("key", "slug", "id"):
            v = plan.get(k)
            if isinstance(v, str) and v.strip():
                out.add(v.strip())
    elif isinstance(plan, str) and plan.strip():
        out.add(plan.strip())
    for k in ("plan_key", "planId", "plan_id"):
        v = obj.get(k)
        if isinstance(v, str) and v.strip():
            out.add(v.strip())
    return out


def _want_matches_identifiers(want: str, identifiers: set[str]) -> bool:
    if not want or not identifiers:
        return False
    if want in identifiers:
        return True
    wl = want.lower()
    return any(i.lower() == wl for i in identifiers)


def _iter_subscription_item_dicts(sub: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("subscriptionItems", "subscription_items", "items"):
        raw = sub.get(key)
        if isinstance(raw, list):
            return [x for x in raw if isinstance(x, dict)]
    return []


def _item_active(status: str | None) -> bool:
    return (status or "").lower() in _ACTIVE


def _commerce_subscription_has_plan(sub: dict[str, Any], want: str) -> bool:
    if not isinstance(sub, dict) or not sub:
        return False
    top_status = (sub.get("status") or "").lower()
    if top_status in ("canceled", "ended", "abandoned"):
        return False

    items = _iter_subscription_item_dicts(sub)
    if items:
        for it in items:
            ids = _plan_identifiers(it)
            st = (it.get("status") or sub.get("status") or "").lower()
            if _want_matches_identifiers(want, ids) and _item_active(st):
                return True
        return False

    if _want_matches_identifiers(want, _plan_identifiers(sub)) and _item_active(sub.get("status")):
        return True
    return False


def _legacy_list_has_plan(payload: Any, want: str) -> bool:
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = payload.get("data") or payload.get("subscriptions") or []
    else:
        return False
    for item in items:
        if not isinstance(item, dict):
            continue
        if _commerce_subscription_has_plan(item, want):
            return True
        plan = item.get("plan") or {}
        key = plan.get("key") or plan.get("slug") or item.get("plan_key")
        st = (item.get("status") or "").lower()
        if isinstance(key, str) and key and st in _ACTIVE and _want_matches_identifiers(want, {key}):
            return True
    return False


async def _fetch_legacy_commerce_list(client: httpx.AsyncClient, clerk_user_id: str) -> Any | None:
    try:
        r2 = await client.get(
            _COMMERCE_LIST,
            params={"user_id": clerk_user_id},
            headers={"Authorization": f"Bearer {settings.clerk_secret_key}"},
        )
    except httpx.RequestError as exc:
        logger.warning("Clerk commerce list unreachable: %s", exc)
        return None
    if r2.status_code >= 400:
        logger.warning(
            "Clerk commerce list -> %s: %s",
            r2.status_code,
            (r2.text or "")[:400],
        )
        return None
    try:
        return r2.json()
    except Exception:
        return None


async def user_has_premium_plan(clerk_user_id: str) -> bool:
    if not settings.require_subscription:
        return True
    if not settings.clerk_secret_key:
        logger.warning("REQUIRE_SUBSCRIPTION=true but CLERK_SECRET_KEY missing")
        return False

    plan_key = (settings.clerk_premium_plan_key or "").strip()
    if not plan_key:
        logger.warning("REQUIRE_SUBSCRIPTION=true but CLERK_PREMIUM_PLAN_KEY is empty")
        return False

    headers = {"Authorization": f"Bearer {settings.clerk_secret_key}"}

    async with httpx.AsyncClient(timeout=15.0) as client:
        billing_url = _BILLING_SUB.format(user_id=clerk_user_id)
        try:
            r = await client.get(billing_url, headers=headers)
        except httpx.RequestError as exc:
            logger.warning("Clerk billing unreachable (%s): %s", billing_url, exc)
            raise ClerkSubscriptionUnavailable from exc

        logger.debug(
            "Clerk billing GET %s -> %s %s",
            billing_url,
            r.status_code,
            (r.text or "")[:500],
        )

        if r.status_code == 200:
            try:
                sub = r.json()
            except Exception:
                sub = None
            if isinstance(sub, dict) and _commerce_subscription_has_plan(sub, plan_key):
                return True
            legacy = await _fetch_legacy_commerce_list(client, clerk_user_id)
            if legacy is not None and _legacy_list_has_plan(legacy, plan_key):
                return True
            return False

        if r.status_code == 404:
            legacy = await _fetch_legacy_commerce_list(client, clerk_user_id)
            if legacy is not None:
                return _legacy_list_has_plan(legacy, plan_key)
            return False

        logger.warning(
            "Clerk GET /users/.../billing/subscription -> %s: %s",
            r.status_code,
            (r.text or "")[:400],
        )
        if r.status_code >= 500:
            legacy = await _fetch_legacy_commerce_list(client, clerk_user_id)
            if legacy is not None:
                return _legacy_list_has_plan(legacy, plan_key)
        return False
