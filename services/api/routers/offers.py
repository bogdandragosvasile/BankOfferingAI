"""Offers router - serves ranked product offers for a customer."""

import logging
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from services.api.middleware.auth import get_current_customer_id
from services.api.models import CustomerProfile, Offer, OfferResponse

logger = logging.getLogger(__name__)

router = APIRouter()

WORKER_BASE_URL = "http://worker:8001"


async def _fetch_customer_profile(
    customer_id: str, request: Request
) -> CustomerProfile:
    """Retrieve customer profile from the database or cache."""
    redis = request.app.state.redis

    # Try cache first
    cached = await redis.get(f"profile:{customer_id}")
    if cached:
        return CustomerProfile.model_validate_json(cached)

    # Fall back to DB
    session_factory = request.app.state.db_session_factory
    async with session_factory() as session:
        from sqlalchemy import text

        result = await session.execute(
            text("SELECT data FROM customer_profiles WHERE customer_id = :cid"),
            {"cid": customer_id},
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Customer profile not found")

        profile = CustomerProfile.model_validate_json(row[0])

        # Warm cache (TTL 15 min)
        await redis.set(
            f"profile:{customer_id}",
            profile.model_dump_json(),
            ex=900,
        )
        return profile


async def _call_worker_scoring(profile: CustomerProfile) -> list[Offer]:
    """Call the worker service scorer/ranker pipeline and return ranked offers."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{WORKER_BASE_URL}/score-and-rank",
            json=profile.model_dump(mode="json"),
        )
        response.raise_for_status()
        data = response.json()
        return [Offer.model_validate(o) for o in data["offers"]]


@router.get(
    "/{customer_id}",
    response_model=OfferResponse,
    summary="Get ranked offers for a customer",
    description="Fetches the customer profile, runs AI scoring/ranking, and returns personalized offers.",
)
async def get_offers(
    customer_id: str,
    request: Request,
    top_n: int = Query(default=5, ge=1, le=20, description="Number of offers to return"),
    authenticated_customer: str = Depends(get_current_customer_id),
):
    """Return top-N ranked offers for the given customer."""
    # Authorization check: customers can only access their own offers
    if authenticated_customer != customer_id:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to access offers for this customer",
        )

    try:
        profile = await _fetch_customer_profile(customer_id, request)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to fetch profile for %s: %s", customer_id, e)
        raise HTTPException(status_code=500, detail="Failed to retrieve customer profile")

    try:
        ranked_offers = await _call_worker_scoring(profile)
    except httpx.HTTPStatusError as e:
        logger.error("Worker scoring failed for %s: %s", customer_id, e)
        raise HTTPException(status_code=502, detail="Scoring service unavailable")
    except httpx.RequestError as e:
        logger.error("Worker connection error for %s: %s", customer_id, e)
        raise HTTPException(status_code=503, detail="Scoring service unreachable")

    return OfferResponse(
        customer_id=customer_id,
        offers=ranked_offers[:top_n],
        generated_at=datetime.utcnow(),
        model_version="1.0.0",
    )
