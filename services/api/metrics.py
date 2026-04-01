"""Custom Prometheus metrics for BankOffer AI business observability."""

from prometheus_client import Counter, Gauge, Histogram

# -- Offer scoring --
OFFERS_GENERATED = Counter(
    "bankoffer_offers_generated_total",
    "Total offers generated",
    ["product_type"],
)

OFFER_SCORING_DURATION = Histogram(
    "bankoffer_offer_scoring_seconds",
    "Time spent scoring offers for a customer",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)

OFFERS_PER_REQUEST = Histogram(
    "bankoffer_offers_per_request",
    "Number of offers returned per request",
    buckets=(0, 1, 2, 3, 5, 8, 10, 15, 20),
)

# -- Suitability --
SUITABILITY_CHECKS = Counter(
    "bankoffer_suitability_checks_total",
    "Suitability check outcomes",
    ["result"],  # passed, failed
)

# -- Consent --
CONSENT_BLOCKS = Counter(
    "bankoffer_consent_blocks_total",
    "Requests blocked due to missing consent",
    ["consent_type"],  # profiling, automated_decision
)

# -- Kill switch --
KILL_SWITCH_ACTIVE = Gauge(
    "bankoffer_kill_switch_active",
    "Whether the model kill-switch is engaged (1=active, 0=inactive)",
)

# -- Business gauges (updated periodically or on request) --
CUSTOMERS_TOTAL = Gauge(
    "bankoffer_customers_total",
    "Total customers in the database",
)

PRODUCTS_ACTIVE = Gauge(
    "bankoffer_products_active_total",
    "Number of active products",
)

# -- Profile --
PROFILE_BUILD_DURATION = Histogram(
    "bankoffer_profile_build_seconds",
    "Time to build a customer profile",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25),
)

# -- Auth --
DEMO_LOGINS = Counter(
    "bankoffer_demo_logins_total",
    "Demo login attempts",
    ["role"],
)
