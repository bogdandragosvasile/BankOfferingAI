"""Pydantic v2 models for the Bank Offering AI API."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class RiskBucket(str, Enum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class LifeStage(str, Enum):
    NEW_GRADUATE = "new_graduate"
    YOUNG_FAMILY = "young_family"
    MID_CAREER = "mid_career"
    PRE_RETIREMENT = "pre_retirement"
    RETIRED = "retired"


class Channel(str, Enum):
    PUSH = "push"
    EMAIL = "email"
    IN_APP = "in_app"


class ProductType(str, Enum):
    CREDIT_CARD = "credit_card"
    PERSONAL_LOAN = "personal_loan"
    MORTGAGE = "mortgage"
    SAVINGS_ACCOUNT = "savings_account"
    INVESTMENT = "investment"
    INSURANCE = "insurance"
    OVERDRAFT = "overdraft"


class CustomerProfile(BaseModel):
    customer_id: str = Field(..., description="Unique customer identifier")
    age: int = Field(..., ge=18, le=120, description="Customer age in years")
    city: str = Field(..., description="Customer's city of residence")
    income: float = Field(..., ge=0, description="Annual income in USD")
    savings: float = Field(..., ge=0, description="Total savings balance in USD")
    debt: float = Field(..., ge=0, description="Total outstanding debt in USD")
    risk_profile: str = Field(..., description="Raw risk profile label from core banking")
    marital_status: str = Field(..., description="Marital status: single, married, divorced, widowed")
    dependents_count: int = Field(default=0, ge=0, description="Number of financial dependents")
    homeowner_status: str = Field(..., description="own, rent, or mortgage")
    existing_products: list[str] = Field(default_factory=list, description="List of product IDs already held")
    life_stage: LifeStage = Field(..., description="Classified life stage of the customer")
    financial_health: str = Field(..., description="Overall financial health score label")
    lifestyle_segment: str = Field(..., description="Behavioural lifestyle segment label")
    investor_readiness: float = Field(..., ge=0.0, le=1.0, description="Propensity score for investment products")
    risk_bucket: RiskBucket = Field(..., description="Discretised risk bucket")
    context_signals: dict[str, Any] = Field(
        default_factory=dict,
        description="Real-time contextual signals (location, device, session data)",
    )
    family_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Family composition and life-event signals",
    )


class Offer(BaseModel):
    offer_id: str = Field(..., description="Unique offer identifier")
    product_id: str = Field(..., description="Underlying product identifier")
    product_name: str = Field(..., description="Bank product display name")
    product_type: ProductType = Field(..., description="Product category")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="AI relevance score")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Model confidence")
    personalization_reason: str = Field(..., description="One-sentence explanation of why this offer fits")
    rank: int = Field(..., ge=1, description="Rank position in the ordered offer list")
    channel: Channel = Field(..., description="Recommended delivery channel")
    cta_url: str = Field(..., description="Call-to-action deep link URL")


class OfferResponse(BaseModel):
    customer_id: str = Field(..., description="Customer identifier")
    offers: list[Offer] = Field(..., description="Ranked list of offers")
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    model_version: str = Field(default="1.0.0", description="Scoring model version")


class NotificationPayload(BaseModel):
    offer_id: str = Field(..., description="Offer identifier")
    product_name: str = Field(..., description="Product name for the notification")
    personalization_reason: str = Field(..., description="Why this offer is relevant to the customer")
    cta_url: str = Field(..., description="Call-to-action deep link URL")
    channel: Channel = Field(..., description="Delivery channel for the notification")
    customer_id: str = Field(..., description="Target customer identifier")


class WebhookEvent(BaseModel):
    event_type: str = Field(..., description="Type of webhook event")
    customer_id: str = Field(..., description="Customer the event relates to")
    timestamp: datetime = Field(..., description="Event timestamp (UTC)")
    payload: dict[str, Any] = Field(..., description="Arbitrary event payload data")
