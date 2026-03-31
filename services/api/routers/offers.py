"""Offers router - serves ranked product offers for a customer."""

import logging
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import text

from services.api.middleware.auth import get_current_customer_id
from services.api.models import Offer, OfferResponse
from services.worker.profiler import build_profile
from services.worker.ranker import rank_offers

logger = logging.getLogger(__name__)

router = APIRouter()

DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

# Product catalog matching the Excel dataset
PRODUCTS = [
    {"id": "prod_etf_starter", "name": "ETF Starter", "type": "investment", "category": "Investment"},
    {"id": "prod_etf_growth", "name": "ETF Growth", "type": "investment", "category": "Investment"},
    {"id": "prod_mutual_funds", "name": "Mutual Funds", "type": "investment", "category": "Investment"},
    {"id": "prod_managed_portfolio", "name": "Managed Portfolio", "type": "investment", "category": "Investment"},
    {"id": "prod_state_bonds", "name": "State Bonds", "type": "bond", "category": "Investment"},
    {"id": "prod_savings_deposit", "name": "Savings Deposit", "type": "savings", "category": "Savings"},
    {"id": "prod_private_pension", "name": "Private Pension", "type": "retirement", "category": "Retirement"},
    {"id": "prod_personal_loan", "name": "Personal Loan", "type": "personal_loan", "category": "Lending"},
    {"id": "prod_mortgage", "name": "Mortgage", "type": "mortgage", "category": "Lending"},
    {"id": "prod_credit_card", "name": "Credit Card", "type": "credit_card", "category": "Credit"},
    {"id": "prod_life_insurance", "name": "Life Insurance", "type": "insurance", "category": "Insurance"},
    {"id": "prod_travel_insurance", "name": "Travel Insurance", "type": "insurance", "category": "Insurance"},
]

# Life stage -> base relevance for each product type
LIFE_STAGE_RELEVANCE = {
    "new_graduate": {
        "investment": 0.3, "bond": 0.1, "savings": 0.6, "retirement": 0.1,
        "personal_loan": 0.4, "mortgage": 0.1, "credit_card": 0.7, "insurance": 0.2,
    },
    "young_family": {
        "investment": 0.4, "bond": 0.2, "savings": 0.5, "retirement": 0.3,
        "personal_loan": 0.3, "mortgage": 0.7, "credit_card": 0.5, "insurance": 0.7,
    },
    "mid_career": {
        "investment": 0.7, "bond": 0.4, "savings": 0.4, "retirement": 0.5,
        "personal_loan": 0.2, "mortgage": 0.5, "credit_card": 0.4, "insurance": 0.5,
    },
    "pre_retirement": {
        "investment": 0.5, "bond": 0.7, "savings": 0.6, "retirement": 0.8,
        "personal_loan": 0.1, "mortgage": 0.2, "credit_card": 0.3, "insurance": 0.6,
    },
    "retired": {
        "investment": 0.3, "bond": 0.8, "savings": 0.7, "retirement": 0.4,
        "personal_loan": 0.1, "mortgage": 0.1, "credit_card": 0.2, "insurance": 0.5,
    },
}


def _score_product(product: dict, life_stage: str, risk_score: float,
                   income: float, features: dict) -> dict:
    """Rule-based scoring for a single product against customer profile + features."""
    ptype = product["type"]
    base = LIFE_STAGE_RELEVANCE.get(life_stage, LIFE_STAGE_RELEVANCE["mid_career"]).get(ptype, 0.3)

    boost = 0.0
    reasons = []

    # Risk-based adjustments
    if ptype in ("investment",) and risk_score >= 6:
        boost += 0.15
        reasons.append("high risk tolerance suits growth products")
    elif ptype in ("bond", "savings") and risk_score < 4:
        boost += 0.15
        reasons.append("conservative profile favours stable returns")

    # Income-based adjustments
    if product["id"] == "prod_managed_portfolio" and income >= 100000:
        boost += 0.2
        reasons.append("high income qualifies for managed portfolio")
    elif product["id"] == "prod_personal_loan" and income < 40000:
        boost += 0.15
        reasons.append("personal loan can help bridge income gaps")

    # Feature signal-based boosts (from features_enhanced columns)
    idle_cash = features.get("idle_cash", 0)
    savings_rate = features.get("savings_rate", 0)
    debt_to_income = features.get("debt_to_income", 0)
    investment_gap = features.get("investment_gap_flag", 0)
    dominant_category = features.get("dominant_spend_category", "")
    balance_trend = features.get("balance_trend", "")

    if idle_cash and float(idle_cash) > 5000 and ptype in ("investment", "bond", "savings"):
        boost += 0.15
        reasons.append("significant idle cash available for deployment")

    if investment_gap and int(investment_gap) == 1 and ptype == "investment":
        boost += 0.2
        reasons.append("investment gap detected in portfolio")

    if savings_rate and float(savings_rate) > 0.2 and ptype in ("retirement", "bond"):
        boost += 0.1
        reasons.append("strong savings habit supports long-term products")

    if debt_to_income and float(debt_to_income) > 0.4 and product["id"] == "prod_personal_loan":
        boost += 0.15
        reasons.append("debt consolidation could improve financial health")

    if str(dominant_category).lower() in ("travel", "entertainment") and product["id"] == "prod_travel_insurance":
        boost += 0.2
        reasons.append("frequent travel spending makes travel insurance valuable")

    if str(dominant_category).lower() in ("travel", "entertainment") and product["id"] == "prod_credit_card":
        boost += 0.1
        reasons.append("credit card rewards align with lifestyle spending")

    # Dependents boost for insurance
    dependents = features.get("dependents", 0)
    if dependents and int(dependents) >= 1 and product["id"] == "prod_life_insurance":
        boost += 0.2
        reasons.append("family dependents increase life insurance relevance")

    # Balance trend boost
    if str(balance_trend).lower() == "increasing" and ptype == "investment":
        boost += 0.1
        reasons.append("growing balance suggests capacity for investment")

    relevance = min(1.0, base + boost)
    confidence = min(1.0, 0.6 + boost)
    reason = "; ".join(reasons) if reasons else f"Recommended based on {life_stage} profile"

    return {
        "product_id": product["id"],
        "product_name": product["name"],
        "product_type": ptype,
        "relevance_score": round(relevance, 4),
        "confidence_score": round(confidence, 4),
        "personalization_reason": reason,
    }


def _score_all_products(life_stage: str, risk_score: float,
                        income: float, features: dict) -> list[dict]:
    """Score all products and return sorted list."""
    scored = [_score_product(p, life_stage, risk_score, income, features) for p in PRODUCTS]
    scored.sort(key=lambda x: x["relevance_score"], reverse=True)
    return scored


@router.get(
    "/{customer_id}",
    response_model=OfferResponse,
    summary="Get ranked offers for a customer",
    description="Fetches customer features, builds a profile, scores products with rules, and returns personalized offers.",
)
async def get_offers(
    customer_id: str,
    request: Request,
    top_n: int = Query(default=5, ge=1, le=20, description="Number of offers to return"),
    authenticated_customer: str = Depends(get_current_customer_id),
):
    """Return top-N ranked offers for the given customer."""
    if not DEMO_MODE and authenticated_customer != customer_id:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to access offers for this customer",
        )

    # Fetch customer features from DB
    session_factory = request.app.state.db_session_factory
    try:
        async with session_factory() as session:
            result = await session.execute(
                text("SELECT * FROM customer_features WHERE customer_id = :cid"),
                {"cid": customer_id},
            )
            row = result.mappings().fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Customer not found")
            features = dict(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to fetch features for %s: %s", customer_id, e)
        raise HTTPException(status_code=500, detail="Failed to retrieve customer data")

    # Build profile using worker profiler
    profiler_input = {
        "age": features.get("age", 30),
        "annual_income": features.get("annual_income", 50000),
        "dependents": features.get("dependents", 0),
        "account_tenure_years": features.get("account_tenure_years", 0),
        "investment_balance": features.get("investment_balance", 0),
        "savings_ratio": min(1.0, max(0.0, float(features.get("savings_rate", 0.1)))),
        "loan_to_income": min(1.0, max(0.0, float(features.get("debt_to_income", 0)))),
    }

    try:
        profile = build_profile(customer_id, profiler_input)
    except Exception as e:
        logger.error("Profiler failed for %s: %s", customer_id, e)
        raise HTTPException(status_code=500, detail="Profile generation failed")

    # Rule-based scoring
    scored = _score_all_products(
        profile.life_stage,
        profile.risk_score,
        float(features.get("annual_income", 50000)),
        features,
    )

    # Apply ranking business rules (cooldowns, diversity, thresholds)
    ranked = rank_offers(scored)

    # Convert to Offer response models
    offers = []
    for r in ranked[:top_n]:
        offers.append(Offer(
            offer_id=r.offer_id,
            product_name=r.product_name,
            product_type=r.product_type,
            relevance_score=r.relevance_score,
            confidence_score=r.confidence_score,
            personalization_reason=r.personalization_reason,
            cta_url=f"/products/{r.product_id}/apply?customer={customer_id}",
        ))

    return OfferResponse(
        customer_id=customer_id,
        offers=offers,
        generated_at=datetime.utcnow(),
        model_version="rules-1.0.0",
    )
