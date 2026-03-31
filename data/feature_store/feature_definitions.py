"""Feast feature store definitions for the BankOfferingAI platform."""

from __future__ import annotations

from datetime import timedelta

from feast import Entity, FeatureService, FeatureView, Field, FileSource
from feast.types import Bool, Float32, Float64, Int64, String

# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------

customer = Entity(
    name="customer",
    join_keys=["customer_id"],
    description="A bank customer uniquely identified by customer_id.",
)

# ---------------------------------------------------------------------------
# Data sources
# ---------------------------------------------------------------------------

transaction_features_source = FileSource(
    path="data/feature_store/data/customer_transaction_features.parquet",
    timestamp_field="feature_timestamp",
    created_timestamp_column="created_at",
    description="Daily-aggregated transaction features produced by the Airflow DAG.",
)

demographic_features_source = FileSource(
    path="data/feature_store/data/customer_demographic_features.parquet",
    timestamp_field="feature_timestamp",
    created_timestamp_column="created_at",
    description="Customer demographic data refreshed weekly from the core banking system.",
)

# ---------------------------------------------------------------------------
# Feature view: customer_features (behavioural / financial aggregates)
# ---------------------------------------------------------------------------

customer_features = FeatureView(
    name="customer_features",
    entities=[customer],
    ttl=timedelta(days=7),
    schema=[
        Field(name="monthly_savings", dtype=Float64,
              description="Average monthly net savings over the last 3 months"),
        Field(name="avg_expenses", dtype=Float64,
              description="Average monthly total expenditure over the last 3 months"),
        Field(name="idle_cash", dtype=Float64,
              description="Estimated cash sitting in low-yield current accounts"),
        Field(name="balance_trend", dtype=Float32,
              description="Month-over-month balance change rate (positive = growing)"),
        Field(name="debt_to_income", dtype=Float32,
              description="Total outstanding debt divided by annual income"),
        Field(name="savings_rate", dtype=Float32,
              description="Monthly savings as a fraction of monthly income"),
        Field(name="dominant_spend_category", dtype=String,
              description="Top spending category by volume in the last 30 days"),
        Field(name="investment_gap_flag", dtype=Bool,
              description="True when idle_cash exceeds the customer's investment threshold"),
    ],
    source=transaction_features_source,
    online=True,
    description="Behavioural and financial aggregate features derived from transaction history.",
)

# ---------------------------------------------------------------------------
# Feature view: customer_demographics (slowly-changing profile data)
# ---------------------------------------------------------------------------

customer_demographics = FeatureView(
    name="customer_demographics",
    entities=[customer],
    ttl=timedelta(days=30),
    schema=[
        Field(name="age", dtype=Int64,
              description="Customer age in years"),
        Field(name="income", dtype=Float64,
              description="Annual income in USD"),
        Field(name="savings", dtype=Float64,
              description="Total savings balance in USD"),
        Field(name="debt", dtype=Float64,
              description="Total outstanding debt in USD"),
        Field(name="risk_profile", dtype=String,
              description="Raw risk profile label from core banking"),
        Field(name="marital_status", dtype=String,
              description="Marital status: single, married, divorced, widowed"),
        Field(name="dependents_count", dtype=Int64,
              description="Number of financial dependents"),
        Field(name="homeowner_status", dtype=String,
              description="own, rent, or mortgage"),
    ],
    source=demographic_features_source,
    online=True,
    description="Slowly-changing demographic features sourced from the core banking system.",
)

# ---------------------------------------------------------------------------
# Feature service: customer_full_profile
# ---------------------------------------------------------------------------

customer_full_profile = FeatureService(
    name="customer_full_profile",
    features=[
        customer_features,
        customer_demographics,
    ],
    description=(
        "Combined feature service used by the offer-recommendation model "
        "at inference time. Bundles behavioural aggregates with demographic "
        "data to construct a complete customer representation."
    ),
)
