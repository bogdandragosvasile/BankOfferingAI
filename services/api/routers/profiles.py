"""Profiles router - serves customer profile data."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from services.api.middleware.auth import get_current_customer_id
from services.api.models import CustomerProfile

logger = logging.getLogger(__name__)

router = APIRouter()


async def _compute_profile_from_features(customer_id: str, request: Request) -> CustomerProfile:
    """Attempt to build a CustomerProfile by pulling features from the feature store.

    Falls back to raising 404 if no feature data exists for this customer.
    """
    session_factory = request.app.state.db_session_factory
    async with session_factory() as session:
        from sqlalchemy import text

        result = await session.execute(
            text(
                "SELECT age, city, income, savings, debt, risk_profile, marital_status, "
                "dependents_count, homeowner_status, existing_products, life_stage, "
                "financial_health, lifestyle_segment, investor_readiness, risk_bucket "
                "FROM customer_features WHERE customer_id = :cid"
            ),
            {"cid": customer_id},
        )
        row = result.mappings().fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Customer profile not found")

        return CustomerProfile(
            customer_id=customer_id,
            age=row["age"],
            city=row["city"],
            income=float(row["income"]),
            savings=float(row["savings"]),
            debt=float(row["debt"]),
            risk_profile=row["risk_profile"],
            marital_status=row["marital_status"],
            dependents_count=row["dependents_count"] or 0,
            homeowner_status=row["homeowner_status"],
            existing_products=row["existing_products"] or [],
            life_stage=row["life_stage"],
            financial_health=row["financial_health"],
            lifestyle_segment=row["lifestyle_segment"],
            investor_readiness=float(row["investor_readiness"]),
            risk_bucket=row["risk_bucket"],
        )


@router.get(
    "/{customer_id}",
    response_model=CustomerProfile,
    summary="Get customer profile",
    description=(
        "Returns the customer profile. Checks Redis cache first, then the "
        "customer_profiles DB table. If no pre-computed profile exists, the "
        "profile is derived from the customer_features table."
    ),
)
async def get_profile(
    customer_id: str,
    request: Request,
    authenticated_customer: str = Depends(get_current_customer_id),
) -> CustomerProfile:
    if authenticated_customer != customer_id:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to access this customer profile",
        )

    redis = request.app.state.redis

    cached = await redis.get(f"profile:{customer_id}")
    if cached:
        return CustomerProfile.model_validate_json(cached)

    session_factory = request.app.state.db_session_factory
    async with session_factory() as session:
        from sqlalchemy import text

        result = await session.execute(
            text("SELECT data FROM customer_profiles WHERE customer_id = :cid"),
            {"cid": customer_id},
        )
        row = result.fetchone()

    if row:
        profile = CustomerProfile.model_validate_json(row[0])
    else:
        # Derive profile from raw feature columns
        logger.info("No pre-computed profile for %s; computing from features", customer_id)
        try:
            profile = await _compute_profile_from_features(customer_id, request)
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("Feature derivation failed for %s: %s", customer_id, exc)
            raise HTTPException(status_code=500, detail="Failed to compute customer profile")

    await redis.set(f"profile:{customer_id}", profile.model_dump_json(), ex=900)
    return profile
