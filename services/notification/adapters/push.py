"""FCM push notification adapter using httpx."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

FCM_API_URL = "https://fcm.googleapis.com/fcm/send"


async def send_push(payload: Any, device_token: str) -> dict[str, Any]:
    """Send a push notification via the FCM Legacy HTTP API.

    Args:
        payload: NotificationPayload-compatible object with offer fields.
        device_token: FCM registration token for the target device.

    Returns:
        A delivery status dict with ``success`` (bool) and ``detail`` (str).
    """
    server_key = os.environ.get("FCM_SERVER_KEY")
    if not server_key:
        logger.error("FCM_SERVER_KEY not set — cannot send push notification")
        return {"success": False, "detail": "FCM_SERVER_KEY not configured"}

    headers = {
        "Authorization": f"key={server_key}",
        "Content-Type": "application/json",
    }

    body = {
        "to": device_token,
        "notification": {
            "title": f"New offer: {payload.product_name}",
            "body": payload.personalization_reason,
            "click_action": "OPEN_OFFER_DETAIL",
        },
        "data": {
            "offer_id": payload.offer_id,
            "cta_url": str(payload.cta_url),
            "product_name": payload.product_name,
            "customer_id": payload.customer_id,
        },
        "priority": "high",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(FCM_API_URL, headers=headers, json=body)

        if response.status_code == 200:
            data = response.json()
            if data.get("failure", 1) == 0:
                logger.info(
                    "FCM push delivered for offer %s to customer %s",
                    payload.offer_id,
                    payload.customer_id,
                )
                return {"success": True, "detail": f"FCM message_id={data.get('results', [{}])[0].get('message_id', '')}"}

            error = data.get("results", [{}])[0].get("error", "unknown")
            logger.warning("FCM reported failure for offer %s: %s", payload.offer_id, error)
            return {"success": False, "detail": f"FCM error: {error}"}

        logger.warning("FCM HTTP %d for offer %s", response.status_code, payload.offer_id)
        return {"success": False, "detail": f"FCM HTTP {response.status_code}"}

    except httpx.RequestError as exc:
        logger.exception("FCM request error for offer %s", payload.offer_id)
        return {"success": False, "detail": f"Request error: {exc}"}
