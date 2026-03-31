"""Customer notification preference service."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

_PREFERENCE_KEY = "preference:{customer_id}"
_DEFAULT_CHANNEL = "in_app"


async def get_customer_preference(
    customer_id: str,
    redis_client: "aioredis.Redis",
) -> dict[str, Any]:
    """Return the notification delivery preference for a customer.

    Checks Redis for a stored preference hash. If none is found, returns
    the default preference with channel ``'in_app'`` and no contact details.

    The stored value in Redis is expected to be a JSON string with the shape::

        {
            "channel": "push" | "email" | "in_app",
            "device_token": "<fcm-token>" | null,
            "email": "<address>" | null
        }

    Args:
        customer_id: The customer whose preference to look up.
        redis_client: An async Redis client instance.

    Returns:
        A dict with keys ``channel``, ``device_token``, and ``email``.
    """
    key = _PREFERENCE_KEY.format(customer_id=customer_id)

    try:
        raw = await redis_client.get(key)
        if raw:
            preference = json.loads(raw)
            preference.setdefault("channel", _DEFAULT_CHANNEL)
            preference.setdefault("device_token", None)
            preference.setdefault("email", None)
            return preference
    except Exception:
        logger.exception("Failed to fetch preference for customer %s", customer_id)

    return {"channel": _DEFAULT_CHANNEL, "device_token": None, "email": None}
