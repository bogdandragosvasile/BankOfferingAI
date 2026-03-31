"""FastAPI notification service — HTTP entry point on port 8002."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from services.notification.adapters.email import send_email
from services.notification.adapters.inapp import send_inapp
from services.notification.adapters.push import send_push
from services.notification.preference_service import get_customer_preference

logger = logging.getLogger(__name__)


class NotificationPayload(BaseModel):
    offer_id: str = Field(..., description="Unique offer identifier")
    product_name: str = Field(..., description="Name of the banking product")
    personalization_reason: str = Field(..., description="Why this offer is relevant for the customer")
    cta_url: str = Field(..., description="Call-to-action deep link")
    channel: str = Field(..., description="Preferred delivery channel: push | email | in_app")
    customer_id: str = Field(..., description="Target customer identifier")


class DeliveryStatus(BaseModel):
    customer_id: str
    channel: str
    success: bool
    detail: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    app.state.redis = aioredis.from_url(redis_url, decode_responses=True)
    logger.info("Notification service started")
    yield
    await app.state.redis.aclose()
    logger.info("Notification service shut down")


app = FastAPI(
    title="BankOffer Notification Service",
    description="Routes personalised offer notifications to push, email, or in-app channels.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "healthy", "service": "notification"}


@app.post(
    "/notify",
    response_model=DeliveryStatus,
    status_code=status.HTTP_200_OK,
    summary="Send a notification to a customer",
    description=(
        "Looks up the customer's channel preference from Redis, routes the "
        "NotificationPayload to the appropriate adapter (push / email / in_app), "
        "and returns a delivery status."
    ),
)
async def notify(payload: NotificationPayload) -> DeliveryStatus:
    from fastapi import Request  # local import to avoid circular at module load

    redis_client = app.state.redis

    preference = await get_customer_preference(payload.customer_id, redis_client)
    effective_channel = preference.get("channel", "in_app")

    result: dict[str, Any]

    try:
        if effective_channel == "push":
            device_token = preference.get("device_token")
            if not device_token:
                logger.warning(
                    "No device token for customer %s — falling back to in_app",
                    payload.customer_id,
                )
                effective_channel = "in_app"
                result = await send_inapp(payload, payload.customer_id, redis_client)
            else:
                result = await send_push(payload, device_token)

        elif effective_channel == "email":
            email = preference.get("email")
            if not email:
                logger.warning(
                    "No email for customer %s — falling back to in_app",
                    payload.customer_id,
                )
                effective_channel = "in_app"
                result = await send_inapp(payload, payload.customer_id, redis_client)
            else:
                result = await send_email(payload, email)

        else:
            effective_channel = "in_app"
            result = await send_inapp(payload, payload.customer_id, redis_client)

    except Exception as exc:
        logger.exception(
            "Notification delivery failed for customer %s via %s",
            payload.customer_id,
            effective_channel,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Delivery failed: {exc}",
        )

    return DeliveryStatus(
        customer_id=payload.customer_id,
        channel=effective_channel,
        success=result.get("success", False),
        detail=result.get("detail", ""),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("services.notification.router:app", host="0.0.0.0", port=8002, reload=False)
