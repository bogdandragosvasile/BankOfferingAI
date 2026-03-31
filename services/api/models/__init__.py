"""Pydantic models for the Bank Offering AI API."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class LifeStage(str, Enum):
    NEW_GRADUATE = "new_graduate"
    YOUNG_FAMILY = "young_family"
    MID_CAREER = "mid_career"
    PRE_RETIREMENT = "pre_retirement"
    RETIRED = "retired"


class IncomeBracket(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class Channel(str, Enum):
    PUSH = "push"
    EMAIL = "email"
    SMS = "sms"
    IN_APP = "in_app"


class SpendingPattern(BaseModel):
    category: str = Field(..., description="Spending category (e.g., groceries, travel)")
    monthly_average: float = Field(..., ge=0, description="Average monthly spend in this category")
    trend: str = Field(..., description="Trend direction: increasing, stable, decreasing")


class CustomerProfile(BaseModel):
    customer_id: str = Field(..., description="Unique customer identifier")
    life_stage: LifeStage = Field(..., description="Classified life stage of the customer")
    risk_score: float = Field(..., ge=1.0, le=10.0, description="Risk tolerance score 1-10")
    segments: list[str] = Field(default_factory=list, description="Customer segments")
    income_bracket: IncomeBracket = Field(..., description="Income bracket classification")
    spending_patterns: list[SpendingPattern] = Field(
        default_factory=list, description="Categorized spending patterns"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Transaction(BaseModel):
    transaction_id: str = Field(..., description="Unique transaction identifier")
    customer_id: str = Field(..., description="Customer who made the transaction")
    amount: float = Field(..., description="Transaction amount")
    currency: str = Field(default="USD", description="ISO 4217 currency code")
    category: str = Field(..., description="Transaction category")
    merchant: str = Field(..., description="Merchant name")
    timestamp: datetime = Field(..., description="When the transaction occurred")
    description: Optional[str] = Field(None, description="Transaction description")


class Offer(BaseModel):
    offer_id: str = Field(..., description="Unique offer identifier")
    product_name: str = Field(..., description="Bank product name")
    product_type: str = Field(..., description="Product type (e.g., credit_card, loan, savings)")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="AI relevance score")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Model confidence")
    personalization_reason: str = Field(
        ..., description="One-sentence explanation of why this offer fits"
    )
    terms_summary: Optional[str] = Field(None, description="Brief terms summary")
    cta_url: str = Field(..., description="Call-to-action URL")


class OfferResponse(BaseModel):
    customer_id: str = Field(..., description="Customer identifier")
    offers: list[Offer] = Field(..., description="Ranked list of offers")
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    model_version: str = Field(default="1.0.0", description="Scoring model version")


class WebhookPayload(BaseModel):
    event_type: str = Field(..., description="Type of webhook event")
    timestamp: datetime = Field(..., description="Event timestamp")
    transactions: list[Transaction] = Field(..., description="Batch of transactions")
    signature: str = Field(..., description="HMAC signature for verification")


class NotificationPayload(BaseModel):
    offer_id: str = Field(..., description="Offer identifier")
    product_name: str = Field(..., description="Product name for the notification")
    personalization_reason: str = Field(
        ..., description="Why this offer is relevant to the customer"
    )
    cta_url: str = Field(..., description="Call-to-action deep link URL")
    channel: Channel = Field(..., description="Delivery channel for the notification")
    customer_id: str = Field(..., description="Target customer identifier")
