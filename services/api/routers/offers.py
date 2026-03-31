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
    {"id": "prod_etf_starter", "name": "ETF Starter", "type": "investment"},
    {"id": "prod_etf_growth", "name": "ETF Growth", "type": "investment"},
    {"id": "prod_mutual_funds", "name": "Mutual Funds", "type": "investment"},
    {"id": "prod_managed_portfolio", "name": "Managed Portfolio", "type": "investment"},
    {"id": "prod_state_bonds", "name": "State Bonds", "type": "bond"},
    {"id": "prod_savings_deposit", "name": "Savings Deposit", "type": "savings"},
    {"id": "prod_private_pension", "name": "Private Pension", "type": "retirement"},
    {"id": "prod_personal_loan", "name": "Personal Loan", "type": "personal_loan"},
    {"id": "prod_mortgage", "name": "Mortgage", "type": "mortgage"},
    {"id": "prod_credit_card", "name": "Credit Card", "type": "credit_card"},
    {"id": "prod_life_insurance", "name": "Life Insurance", "type": "insurance"},
    {"id": "prod_travel_insurance", "name": "Travel Insurance", "type": "insurance"},
]

# Life stage -> base relevance per product type
LIFE_STAGE_BASE = {
    "new_graduate": {
        "investment": 0.25, "bond": 0.08, "savings": 0.50, "retirement": 0.08,
        "personal_loan": 0.35, "mortgage": 0.05, "credit_card": 0.55, "insurance": 0.15,
    },
    "young_family": {
        "investment": 0.30, "bond": 0.15, "savings": 0.40, "retirement": 0.20,
        "personal_loan": 0.25, "mortgage": 0.50, "credit_card": 0.35, "insurance": 0.45,
    },
    "mid_career": {
        "investment": 0.45, "bond": 0.30, "savings": 0.30, "retirement": 0.40,
        "personal_loan": 0.15, "mortgage": 0.30, "credit_card": 0.25, "insurance": 0.30,
    },
    "pre_retirement": {
        "investment": 0.35, "bond": 0.55, "savings": 0.45, "retirement": 0.65,
        "personal_loan": 0.08, "mortgage": 0.10, "credit_card": 0.15, "insurance": 0.40,
    },
    "retired": {
        "investment": 0.20, "bond": 0.60, "savings": 0.55, "retirement": 0.25,
        "personal_loan": 0.05, "mortgage": 0.05, "credit_card": 0.10, "insurance": 0.35,
    },
}


def _safe_float(val, default=0.0):
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_int(val, default=0):
    if val is None:
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def _score_product(product: dict, life_stage: str, risk_score: float,
                   income: float, f: dict) -> dict:
    """Rule-based scoring for a single product using all customer signals."""
    pid = product["id"]
    ptype = product["type"]
    base = LIFE_STAGE_BASE.get(life_stage, LIFE_STAGE_BASE["mid_career"]).get(ptype, 0.2)

    boost = 0.0
    penalty = 0.0
    reasons = []

    # --- Parse all features ---
    age = _safe_int(f.get("age"), 30)
    dependents = _safe_int(f.get("dependents"), 0)
    idle_cash = _safe_float(f.get("idle_cash"))
    savings_rate = _safe_float(f.get("savings_rate"))
    dti = _safe_float(f.get("debt_to_income"))
    investment_gap = _safe_int(f.get("investment_gap_flag"))
    category = str(f.get("dominant_spend_category") or "").lower()
    trend = str(f.get("balance_trend") or "").lower()
    risk_profile = str(f.get("risk_profile") or "").lower()
    homeowner = str(f.get("homeowner_status") or "").lower()
    existing = str(f.get("existing_products") or "").lower()

    # --- Existing-product penalties (don't recommend what they already have) ---
    if "mortgage" in existing and pid == "prod_mortgage":
        penalty += 0.5
        reasons.append("already has mortgage")
    if "credit_card" in existing and pid == "prod_credit_card":
        penalty += 0.4
        reasons.append("already has credit card")
    if "loan" in existing and pid == "prod_personal_loan":
        penalty += 0.4
        reasons.append("already has a loan")

    # --- Risk profile from Excel (high / moderate / low) ---
    if risk_profile == "high":
        if ptype == "investment":
            boost += 0.20
            reasons.append("high risk appetite favours equity products")
        elif ptype in ("bond", "savings"):
            penalty += 0.10
    elif risk_profile == "low":
        if ptype in ("bond", "savings"):
            boost += 0.20
            reasons.append("low risk profile suits capital-preservation products")
        elif ptype == "investment":
            penalty += 0.15
    elif risk_profile == "moderate":
        if pid in ("prod_mutual_funds", "prod_state_bonds", "prod_etf_starter"):
            boost += 0.10
            reasons.append("balanced risk appetite suits diversified options")

    # --- Idle cash signal (from context detection rules) ---
    if idle_cash > 10000:
        if ptype in ("investment", "bond", "savings"):
            boost += 0.25
            reasons.append(f"high idle cash ({idle_cash:,.0f}) ready for deployment")
    elif idle_cash > 5000:
        if ptype in ("investment", "savings"):
            boost += 0.12
            reasons.append("idle cash available for investment")

    # --- Investment gap signal ---
    if investment_gap == 1:
        if pid == "prod_etf_starter":
            boost += 0.25
            reasons.append("investment gap detected - ETF Starter is ideal entry point")
        elif pid == "prod_mutual_funds":
            boost += 0.20
            reasons.append("investment gap makes mutual funds a strong fit")
        elif ptype == "investment":
            boost += 0.10

    # --- Savings rate ---
    if savings_rate >= 0.5:
        if ptype == "retirement":
            boost += 0.20
            reasons.append("strong saver profile ideal for pension planning")
        elif ptype == "bond":
            boost += 0.10
            reasons.append("consistent savings enable long-term bond allocation")
    elif savings_rate <= 0.0:
        if pid == "prod_savings_deposit":
            boost += 0.15
            reasons.append("savings deposit can help build a savings habit")

    # --- Debt-to-income ratio ---
    if dti > 3.0:
        if pid == "prod_personal_loan":
            boost += 0.25
            reasons.append(f"high debt-to-income ({dti:.1f}x) - consolidation recommended")
        if ptype in ("investment", "bond"):
            penalty += 0.15
    elif dti < 0.5:
        if ptype in ("investment", "bond"):
            boost += 0.10
            reasons.append("low leverage enables investment capacity")

    # --- Dominant spend category ---
    if category == "travel":
        if pid == "prod_travel_insurance":
            boost += 0.30
            reasons.append("travel-heavy spending pattern makes insurance essential")
        elif pid == "prod_credit_card" and "credit_card" not in existing:
            boost += 0.15
            reasons.append("travel rewards card aligns with spending habits")
    elif category == "shopping":
        if pid == "prod_credit_card" and "credit_card" not in existing:
            boost += 0.12
            reasons.append("cashback card matches shopping-heavy lifestyle")
    elif category == "rent":
        if pid == "prod_mortgage" and "mortgage" not in existing and homeowner == "rent":
            boost += 0.20
            reasons.append("renter with rent as top expense - mortgage could reduce costs")

    # --- Homeowner status ---
    if homeowner == "rent" and pid == "prod_mortgage" and "mortgage" not in existing:
        boost += 0.15
        reasons.append("renter status suggests home ownership opportunity")
    elif homeowner == "owner" and pid == "prod_mortgage" and "mortgage" not in existing:
        boost += 0.05  # refinancing potential only

    # --- Dependents ---
    if dependents >= 2:
        if pid == "prod_life_insurance":
            boost += 0.30
            reasons.append(f"{dependents} dependents - life insurance is critical")
        elif pid == "prod_private_pension":
            boost += 0.10
            reasons.append("family responsibility supports pension planning")
    elif dependents == 1:
        if pid == "prod_life_insurance":
            boost += 0.15
            reasons.append("family dependent increases life insurance need")
    elif dependents == 0:
        if pid == "prod_life_insurance":
            penalty += 0.15  # much less relevant without dependents

    # --- Balance trend ---
    if trend == "growing":
        if ptype in ("investment", "bond"):
            boost += 0.08
            reasons.append("growing balance supports new investments")
    elif trend == "declining":
        if ptype in ("investment",):
            penalty += 0.10
        if pid == "prod_savings_deposit":
            boost += 0.10
            reasons.append("declining balance - savings buffer recommended")

    # --- Income-based product differentiation ---
    if income >= 120000:
        if pid == "prod_managed_portfolio":
            boost += 0.25
            reasons.append("premium income tier qualifies for managed portfolio")
        elif pid == "prod_etf_starter":
            penalty += 0.10  # too basic
    elif income >= 80000:
        if pid == "prod_etf_growth":
            boost += 0.15
            reasons.append("solid income supports growth-oriented ETF strategy")
        elif pid == "prod_managed_portfolio":
            boost += 0.08
    elif income < 45000:
        if pid == "prod_personal_loan" and dti < 2.0:
            boost += 0.12
            reasons.append("personal loan can supplement lower income")
        if pid == "prod_managed_portfolio":
            penalty += 0.20  # too premium

    # --- Age-specific ---
    if age <= 25:
        if pid == "prod_etf_starter":
            boost += 0.15
            reasons.append("young age makes time-in-market advantage huge")
        elif pid == "prod_credit_card" and "credit_card" not in existing:
            boost += 0.10
            reasons.append("first credit card builds credit history early")
    elif age >= 50:
        if pid == "prod_private_pension":
            boost += 0.20
            reasons.append("approaching retirement - pension planning is urgent")
        elif pid == "prod_state_bonds":
            boost += 0.12
            reasons.append("state bonds provide stable pre-retirement income")

    # --- Compute final scores ---
    relevance = max(0.0, min(1.0, base + boost - penalty))
    confidence = max(0.2, min(1.0, 0.50 + boost * 0.6 + (0.1 if len(reasons) >= 2 else 0)))
    reason = "; ".join(reasons[:3]) if reasons else f"Recommended for {life_stage.replace('_', ' ')} profile"

    return {
        "product_id": pid,
        "product_name": product["name"],
        "product_type": ptype,
        "relevance_score": round(relevance, 4),
        "confidence_score": round(confidence, 4),
        "personalization_reason": reason,
    }


@router.get(
    "/{customer_id}",
    response_model=OfferResponse,
    summary="Get ranked offers for a customer",
)
async def get_offers(
    customer_id: str,
    request: Request,
    top_n: int = Query(default=5, ge=1, le=20, description="Number of offers to return"),
    authenticated_customer: str = Depends(get_current_customer_id),
):
    """Return top-N ranked offers for the given customer."""
    if not DEMO_MODE and authenticated_customer != customer_id:
        raise HTTPException(status_code=403, detail="Not authorized")

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

    profiler_input = {
        "age": features.get("age", 30),
        "annual_income": max(1.0, _safe_float(features.get("annual_income"), 50000)),
        "dependents": features.get("dependents", 0),
        "account_tenure_years": features.get("account_tenure_years", 0),
        "investment_balance": features.get("investment_balance", 0),
        "savings_ratio": min(1.0, max(0.0, _safe_float(features.get("savings_rate"), 0.1))),
        "loan_to_income": min(1.0, max(0.0, _safe_float(features.get("debt_to_income"), 0))),
    }

    try:
        profile = build_profile(customer_id, profiler_input)
    except Exception as e:
        logger.error("Profiler failed for %s: %s", customer_id, e)
        raise HTTPException(status_code=500, detail="Profile generation failed")

    income = _safe_float(features.get("annual_income"), 50000)
    scored = [_score_product(p, profile.life_stage, profile.risk_score, income, features) for p in PRODUCTS]
    scored.sort(key=lambda x: x["relevance_score"], reverse=True)

    ranked = rank_offers(scored)

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
