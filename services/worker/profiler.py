from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ProfileResult:
    customer_id: str
    life_stage: str
    risk_score: float
    financial_health: str
    lifestyle_segment: str
    investor_readiness: str
    risk_bucket: str
    context_signals: list[str]
    family_context: bool
    housing_context: str | None


def _classify_life_stage(age: int, dependents_count: int, account_tenure_years: float) -> str:
    if age >= 67:
        return "retired"
    if age >= 55:
        return "pre_retirement"
    if 25 <= age <= 40 and dependents_count >= 1:
        return "young_family"
    if age < 25 and account_tenure_years <= 2:
        return "new_graduate"
    return "mid_career"


def _classify_financial_health(debt_to_income: float, monthly_savings: float) -> str:
    if debt_to_income >= 1.2:
        return "fragile"
    if 0.5 <= debt_to_income < 1.2:
        return "watchlist"
    return "healthy"


def _classify_lifestyle_segment(
    monthly_savings: float,
    savings_rate: float,
    avg_expenses: float,
    dominant_spend_category: str,
    monthly_savings_val: float,
) -> str:
    if monthly_savings > 800 and savings_rate > 0.15:
        return "disciplined_saver"
    if avg_expenses > 4000:
        return "high_spender"
    if dominant_spend_category == "travel":
        return "traveler"
    if dominant_spend_category == "subscriptions":
        return "digital_spender"
    if dominant_spend_category == "rent" and monthly_savings_val < 300:
        return "cost_pressured"
    return "balanced"


def _classify_investor_readiness(idle_cash: float, monthly_savings: float, events: list[dict[str, Any]]) -> str:
    has_event = any(e.get("event_type") in ("salary_increase", "bonus") for e in events)
    if idle_cash > 10000 and monthly_savings > 500 and has_event:
        return "high"
    if 5000 < idle_cash <= 10000:
        return "medium"
    return "low"


def _compute_risk_score(
    age: int,
    income: float,
    savings: float,
    debt_to_income: float,
    risk_profile: str,
) -> float:
    base: float
    if risk_profile == "high":
        base = 7.5
    elif risk_profile == "moderate":
        base = 5.0
    else:
        base = 2.5

    age_adj = max(-2.0, min(2.0, (40 - age) * 0.05))
    income_adj = min(1.5, income / 10000)
    savings_adj = min(1.0, savings / 20000)
    debt_adj = min(-2.0, -debt_to_income)

    raw = base + age_adj + income_adj + savings_adj + debt_adj
    return round(max(1.0, min(10.0, raw)), 2)


def _detect_context_signals(
    idle_cash: float,
    monthly_savings: float,
    investment_gap_flag: int,
    dominant_spend_category: str,
    events: list[dict[str, Any]],
    dependents_count: int,
    marital_status: str,
    income: float,
    homeowner_status: str,
) -> list[str]:
    signals: list[str] = []

    event_types = {e.get("event_type") for e in events}

    if idle_cash > 10000:
        signals.append("idle_cash_high")
    if "salary_increase" in event_types:
        signals.append("salary_increase")
    if investment_gap_flag == 1:
        signals.append("investment_gap")
    if monthly_savings > 500:
        signals.append("monthly_savings_consistent")
    if "travel_spike" in event_types:
        signals.append("travel_spike")
    if dominant_spend_category == "rent":
        signals.append("rent_pattern")
    if dependents_count > 0 or marital_status.lower() in ("married", "yes", "true", "1"):
        signals.append("family_context")
    if income > 7000:
        signals.append("high_income")
    if dominant_spend_category == "shopping":
        signals.append("shopping_pattern")
    if "bonus" in event_types:
        signals.append("bonus_event")

    return signals


def build_profile(customer_id: str, features: dict[str, Any]) -> ProfileResult:
    age = int(features.get("age", 30))
    income = float(features.get("income", 0))
    savings = float(features.get("savings", 0))
    monthly_savings = float(features.get("monthly_savings", 0))
    avg_expenses = float(features.get("avg_expenses", 0))
    idle_cash = float(features.get("idle_cash", 0))
    debt_to_income = float(features.get("debt_to_income", 0))
    savings_rate = float(features.get("savings_rate", 0))
    dominant_spend_category = str(features.get("dominant_spend_category", ""))
    investment_gap_flag = int(features.get("investment_gap_flag", 0))
    risk_profile = str(features.get("risk_profile", "low")).lower()
    marital_status = str(features.get("marital_status", ""))
    dependents_count = int(features.get("dependents_count", 0))
    homeowner_status = str(features.get("homeowner_status", "")).lower()
    account_tenure_years = float(features.get("account_tenure_years", 0))
    events: list[dict[str, Any]] = features.get("events", [])

    life_stage = _classify_life_stage(age, dependents_count, account_tenure_years)
    financial_health = _classify_financial_health(debt_to_income, monthly_savings)
    lifestyle_segment = _classify_lifestyle_segment(
        monthly_savings, savings_rate, avg_expenses, dominant_spend_category, monthly_savings
    )
    investor_readiness = _classify_investor_readiness(idle_cash, monthly_savings, events)

    risk_bucket_map = {"low": "low", "moderate": "moderate", "high": "high"}
    risk_bucket = risk_bucket_map.get(risk_profile, "low")

    risk_score = _compute_risk_score(age, income, savings, debt_to_income, risk_profile)

    is_married = marital_status.lower() in ("married", "yes", "true", "1")
    family_context = dependents_count > 0 or is_married

    housing_context: str | None = None
    if homeowner_status == "rent" and income > 7000:
        housing_context = "mortgage_opportunity"

    context_signals = _detect_context_signals(
        idle_cash,
        monthly_savings,
        investment_gap_flag,
        dominant_spend_category,
        events,
        dependents_count,
        marital_status,
        income,
        homeowner_status,
    )

    logger.info(
        "Profile built for %s: life_stage=%s financial_health=%s signals=%s",
        customer_id,
        life_stage,
        financial_health,
        context_signals,
    )

    return ProfileResult(
        customer_id=customer_id,
        life_stage=life_stage,
        risk_score=risk_score,
        financial_health=financial_health,
        lifestyle_segment=lifestyle_segment,
        investor_readiness=investor_readiness,
        risk_bucket=risk_bucket,
        context_signals=context_signals,
        family_context=family_context,
        housing_context=housing_context,
    )
