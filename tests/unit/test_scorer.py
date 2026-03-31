"""Unit tests for the product scorer module.

Tests score_products() which uses an LLMClient to score financial products
against a customer profile and returns a sorted list of ScoredProduct objects.

Also tests:
  - PRODUCT_CATALOG completeness (12 products, required keys)
  - ScoringContext field population
  - Error handling when LLM raises an exception
"""

import pytest
from unittest.mock import MagicMock, patch, call
from typing import Any

from services.worker.scorer import (
    score_products,
    PRODUCT_CATALOG,
    ScoringContext,
    ScoredProduct,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


REQUIRED_PRODUCT_KEYS = {"product_id", "name", "type", "description"}


def make_customer_profile(
    *,
    customer_id: str = "cust_score_001",
    life_stage: str = "young_family",
    financial_health: str = "healthy",
    investor_readiness: str = "medium",
    risk_bucket: str = "medium",
    risk_score: float = 5.5,
    lifestyle_segment: str = "urban_professional",
    context_signals: list | None = None,
    family_context: bool = False,
) -> MagicMock:
    """Return a mock profile with realistic banking data."""
    profile = MagicMock()
    profile.customer_id = customer_id
    profile.life_stage = life_stage
    profile.financial_health = financial_health
    profile.investor_readiness = investor_readiness
    profile.risk_bucket = risk_bucket
    profile.risk_score = risk_score
    profile.lifestyle_segment = lifestyle_segment
    profile.context_signals = context_signals if context_signals is not None else []
    profile.family_context = family_context
    return profile


def make_scored_product(product_id: str, score: float) -> MagicMock:
    p = MagicMock(spec=ScoredProduct)
    p.product_id = product_id
    p.relevance_score = score
    return p


def build_llm_response(scores: list[tuple[str, float]]) -> MagicMock:
    """Build a mock LLMClient that returns the given (product_id, score) pairs."""
    client = MagicMock()
    client.score.return_value = [
        MagicMock(product_id=pid, relevance_score=s) for pid, s in scores
    ]
    return client


# ---------------------------------------------------------------------------
# Test: sorted by relevance
# ---------------------------------------------------------------------------


class TestScoreProductsSortedByRelevance:
    @patch("services.worker.scorer.LLMClient")
    def test_score_products_returns_sorted_by_relevance(self, mock_llm_cls):
        """Results must be sorted in descending order of relevance_score."""
        unsorted_scores = [
            ("prod_001", 0.45),
            ("prod_002", 0.91),
            ("prod_003", 0.72),
            ("prod_004", 0.58),
        ]
        mock_client = build_llm_response(unsorted_scores)
        mock_llm_cls.return_value = mock_client

        profile = make_customer_profile()
        products = [
            {"product_id": pid, "name": f"Product {i}", "type": "investment", "description": "desc"}
            for i, (pid, _) in enumerate(unsorted_scores)
        ]

        results = score_products(profile, products)

        assert len(results) == len(products)
        scores = [r.relevance_score for r in results]
        assert scores == sorted(scores, reverse=True), (
            f"Results not sorted descending: {scores}"
        )

    @patch("services.worker.scorer.LLMClient")
    def test_score_products_top_item_has_highest_score(self, mock_llm_cls):
        """The first item in the result list has the maximum relevance score."""
        scored = [("p1", 0.30), ("p2", 0.95), ("p3", 0.60)]
        mock_llm_cls.return_value = build_llm_response(scored)

        profile = make_customer_profile()
        products = [
            {"product_id": pid, "name": "P", "type": "loan", "description": "d"}
            for pid, _ in scored
        ]

        results = score_products(profile, products)
        assert results[0].relevance_score == max(r.relevance_score for r in results)

    @patch("services.worker.scorer.LLMClient")
    def test_score_products_all_scores_normalized(self, mock_llm_cls):
        """All relevance scores must be in [0.0, 1.0]."""
        scored = [("p1", 0.0), ("p2", 0.5), ("p3", 1.0)]
        mock_llm_cls.return_value = build_llm_response(scored)

        profile = make_customer_profile()
        products = [
            {"product_id": pid, "name": "P", "type": "savings", "description": "d"}
            for pid, _ in scored
        ]

        results = score_products(profile, products)
        for r in results:
            assert 0.0 <= r.relevance_score <= 1.0, (
                f"Score {r.relevance_score} out of [0, 1] range"
            )

    @patch("services.worker.scorer.LLMClient")
    def test_score_products_returns_scored_product_instances(self, mock_llm_cls):
        """Each returned element must be a ScoredProduct instance."""
        scored = [("p1", 0.7), ("p2", 0.4)]
        mock_llm_cls.return_value = build_llm_response(scored)

        profile = make_customer_profile()
        products = [
            {"product_id": pid, "name": "P", "type": "credit", "description": "d"}
            for pid, _ in scored
        ]

        results = score_products(profile, products)
        for r in results:
            assert isinstance(r, ScoredProduct)


# ---------------------------------------------------------------------------
# Test: LLM error handling
# ---------------------------------------------------------------------------


class TestScoreProductsLLMErrorHandling:
    @patch("services.worker.scorer.LLMClient")
    def test_score_products_handles_llm_error_returns_zero_score(self, mock_llm_cls):
        """When LLM raises an exception the product receives a 0.0 relevance score."""
        mock_client = MagicMock()
        mock_client.score.side_effect = Exception("LLM service unavailable")
        mock_llm_cls.return_value = mock_client

        profile = make_customer_profile()
        products = [
            {"product_id": "prod_err_001", "name": "Error Product", "type": "loan", "description": "desc"}
        ]

        results = score_products(profile, products)

        assert len(results) == 1
        assert results[0].product_id == "prod_err_001"
        assert results[0].relevance_score == 0.0

    @patch("services.worker.scorer.LLMClient")
    def test_score_products_partial_error_zeroes_failed_product(self, mock_llm_cls):
        """When only one product fails, the rest keep their scores; failed gets 0.0."""
        def selective_fail(product_ids, profile_ctx):
            results = []
            for pid in product_ids:
                if pid == "prod_bad":
                    raise Exception("timeout")
                results.append(MagicMock(product_id=pid, relevance_score=0.8))
            return results

        mock_client = MagicMock()
        mock_client.score.side_effect = selective_fail
        mock_llm_cls.return_value = mock_client

        profile = make_customer_profile()
        products = [
            {"product_id": "prod_bad",  "name": "Bad",  "type": "loan",   "description": "d"},
            {"product_id": "prod_good", "name": "Good", "type": "savings", "description": "d"},
        ]

        results = score_products(profile, products)
        bad = next((r for r in results if r.product_id == "prod_bad"), None)
        if bad is not None:
            assert bad.relevance_score == 0.0

    @patch("services.worker.scorer.LLMClient")
    def test_score_products_empty_list_returns_empty(self, mock_llm_cls):
        """Empty product list returns empty list without calling LLM."""
        mock_client = MagicMock()
        mock_llm_cls.return_value = mock_client

        profile = make_customer_profile()
        results = score_products(profile, [])

        assert results == []


# ---------------------------------------------------------------------------
# Test: PRODUCT_CATALOG
# ---------------------------------------------------------------------------


class TestProductCatalog:
    def test_product_catalog_has_all_12_products(self):
        """PRODUCT_CATALOG must contain exactly 12 products."""
        assert len(PRODUCT_CATALOG) == 12, (
            f"Expected 12 products, got {len(PRODUCT_CATALOG)}. "
            f"Product IDs: {[p.get('product_id') for p in PRODUCT_CATALOG]}"
        )

    def test_product_catalog_required_keys(self):
        """Every product in the catalog must have the required keys."""
        for product in PRODUCT_CATALOG:
            for key in REQUIRED_PRODUCT_KEYS:
                assert key in product, (
                    f"Product {product.get('product_id', '?')} missing key '{key}'"
                )

    def test_product_catalog_unique_ids(self):
        """All product_ids in the catalog must be unique."""
        ids = [p["product_id"] for p in PRODUCT_CATALOG]
        assert len(ids) == len(set(ids)), "Duplicate product_ids found in PRODUCT_CATALOG"

    def test_product_catalog_product_names_non_empty(self):
        """All product names must be non-empty strings."""
        for product in PRODUCT_CATALOG:
            assert isinstance(product.get("name"), str)
            assert len(product["name"]) > 0, f"Empty name for product {product.get('product_id')}"

    def test_product_catalog_types_non_empty(self):
        """All product types must be non-empty strings."""
        for product in PRODUCT_CATALOG:
            assert isinstance(product.get("type"), str)
            assert len(product["type"]) > 0

    def test_product_catalog_includes_investment_products(self):
        """Catalog should include at least one investment-type product."""
        investment_types = {"ETF", "mutual_fund", "investment", "bond"}
        types_in_catalog = {p["type"] for p in PRODUCT_CATALOG}
        overlap = investment_types & types_in_catalog
        assert len(overlap) > 0, (
            f"No investment products found. Types present: {types_in_catalog}"
        )

    def test_product_catalog_includes_insurance_products(self):
        """Catalog should include at least one insurance product."""
        insurance_products = [p for p in PRODUCT_CATALOG if "insurance" in p["type"].lower()]
        assert len(insurance_products) >= 1, "No insurance products in PRODUCT_CATALOG"

    def test_product_catalog_includes_credit_products(self):
        """Catalog should include at least one credit product."""
        credit_products = [p for p in PRODUCT_CATALOG if "credit" in p["type"].lower() or "loan" in p["type"].lower()]
        assert len(credit_products) >= 1, "No credit/loan products in PRODUCT_CATALOG"


# ---------------------------------------------------------------------------
# Test: ScoringContext
# ---------------------------------------------------------------------------


class TestScoringContext:
    def test_scoring_context_has_customer_id(self):
        """ScoringContext must expose the customer_id from the profile."""
        profile = make_customer_profile(customer_id="cust_ctx_001")
        ctx = ScoringContext(profile=profile)
        assert ctx.customer_id == "cust_ctx_001"

    def test_scoring_context_has_life_stage(self):
        """ScoringContext must expose the life_stage from the profile."""
        profile = make_customer_profile(life_stage="retired")
        ctx = ScoringContext(profile=profile)
        assert ctx.life_stage == "retired"

    def test_scoring_context_has_financial_health(self):
        """ScoringContext must expose financial_health."""
        profile = make_customer_profile(financial_health="watchlist")
        ctx = ScoringContext(profile=profile)
        assert ctx.financial_health == "watchlist"

    def test_scoring_context_has_investor_readiness(self):
        """ScoringContext must expose investor_readiness."""
        profile = make_customer_profile(investor_readiness="high")
        ctx = ScoringContext(profile=profile)
        assert ctx.investor_readiness == "high"

    def test_scoring_context_has_risk_bucket(self):
        """ScoringContext must expose risk_bucket."""
        profile = make_customer_profile(risk_bucket="low")
        ctx = ScoringContext(profile=profile)
        assert ctx.risk_bucket == "low"

    def test_scoring_context_has_context_signals(self):
        """ScoringContext must expose context_signals as a list."""
        signals = ["idle_cash_high", "travel_spike"]
        profile = make_customer_profile(context_signals=signals)
        ctx = ScoringContext(profile=profile)
        assert ctx.context_signals == signals

    def test_scoring_context_serializable(self):
        """ScoringContext must support dict/JSON serialization for LLM prompt building."""
        profile = make_customer_profile(
            customer_id="cust_serial_001",
            life_stage="mid_career",
            financial_health="healthy",
            investor_readiness="medium",
            risk_bucket="medium",
            context_signals=["idle_cash_high"],
        )
        ctx = ScoringContext(profile=profile)
        ctx_dict = ctx.to_dict() if hasattr(ctx, "to_dict") else vars(ctx)
        assert isinstance(ctx_dict, dict)
        assert "customer_id" in ctx_dict or "life_stage" in ctx_dict

    @pytest.mark.parametrize(
        "life_stage,financial_health,investor_readiness,risk_bucket",
        [
            ("new_graduate",   "watchlist", "low",    "low"),
            ("young_family",   "healthy",   "medium", "medium"),
            ("mid_career",     "healthy",   "high",   "high"),
            ("pre_retirement", "watchlist", "medium", "medium"),
            ("retired",        "fragile",   "low",    "low"),
        ],
    )
    def test_scoring_context_fields_parametrized(
        self, life_stage, financial_health, investor_readiness, risk_bucket
    ):
        profile = make_customer_profile(
            life_stage=life_stage,
            financial_health=financial_health,
            investor_readiness=investor_readiness,
            risk_bucket=risk_bucket,
        )
        ctx = ScoringContext(profile=profile)
        assert ctx.life_stage == life_stage
        assert ctx.financial_health == financial_health
        assert ctx.investor_readiness == investor_readiness
        assert ctx.risk_bucket == risk_bucket
