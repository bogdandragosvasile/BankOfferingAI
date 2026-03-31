"""In-app notification adapter — publishes to Redis pub/sub."""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

_INAPP_CHANNEL_PREFIX = "inapp"
_INBOX_KEY = "notifications:inbox:{customer_id}"
_UNREAD_KEY = "notifications:unread:{customer_id}"
_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days


async def send_inapp(
    payload: Any,
    customer_id: str,
    redis_client: "aioredis.Redis",
) -> dict[str, Any]:
    """Publish a notification to the customer's Redis pub/sub channel and persist it.

    The message is published to ``inapp:{customer_id}`` so any connected
    WebSocket listener can forward it in real time. It is also stored in a
    Redis sorted set for REST polling fallback.

    Args:
        payload: NotificationPayload-compatible object with offer fields.
        customer_id: Target customer identifier.
        redis_client: An async Redis client instance.

    Returns:
        A delivery status dict with ``success`` (bool) and ``detail`` (str).
    """
    notification_id = str(uuid.uuid4())
    now = time.time()

    notification = {
        "id": notification_id,
        "offer_id": payload.offer_id,
        "product_name": payload.product_name,
        "personalization_reason": payload.personalization_reason,
        "cta_url": str(payload.cta_url),
        "customer_id": customer_id,
        "read": False,
        "timestamp": now,
    }

    channel = f"{_INAPP_CHANNEL_PREFIX}:{customer_id}"
    inbox_key = _INBOX_KEY.format(customer_id=customer_id)
    unread_key = _UNREAD_KEY.format(customer_id=customer_id)
    serialized = json.dumps(notification)

    try:
        async with redis_client.pipeline(transaction=True) as pipe:
            pipe.zadd(inbox_key, {serialized: now})
            pipe.incr(unread_key)
            pipe.expire(inbox_key, _TTL_SECONDS)
            pipe.expire(unread_key, _TTL_SECONDS)
            pipe.publish(channel, serialized)
            await pipe.execute()

        logger.info(
            "In-app notification %s published to channel %s for offer %s",
            notification_id,
            channel,
            payload.offer_id,
        )
        return {"success": True, "detail": f"Published to {channel} (id={notification_id})"}

    except Exception as exc:
        logger.exception(
            "Failed to publish in-app notification for offer %s to customer %s",
            payload.offer_id,
            customer_id,
        )
        return {"success": False, "detail": f"Redis error: {exc}"}
