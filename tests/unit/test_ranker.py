"""Unit tests for the offer ranker module.

rank_offers(scored_products, cooldowns, config, now) -> list[RankedOffer]

RankedOffer fields: offer_id, product_id, product_name, product_type,
                    relevance_score, rank

Business rules enforced:
  - min_relevance threshold filter
  - cooldown filter (recently dismissed products excluded)
  - diversity cap (max_same_type per product_type)
  - max_offers cap on result length
  - sequential 1-based ranks
  - empty input returns empty list
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from services.worker.ranker import rank_offers, RankedOffer


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def make_config(
    *,
    min_relevance: float = 0.5,
    max_offers: int = 5,
    max_same_type: int = 2,
    cooldown_hours: int = 24,
) -> MagicMock:
    cfg = MagicMock()
    cfg.min_relevance = min_relevance
    cfg.max_offers = max_offers
    cfg.max_same_type = max_same_type
    cfg.cooldown_hours = cooldown_hours
    return cfg


def make_product(
    product_id: str,
    *,
    product_name: str | None = None,
    product_type: str = "investment",
    relevance_score: float = 0.75,
) -> MagicMock:
    p = MagicMock()
    p.product_id = product_id
    p.product_name = product_name or f"Product {product_id}"
    p.product_type = product_type
    p.relevance_score = relevance_score
    return p


def _now() -> datetime:
    return datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Threshold filter
# ---------------------------------------------------------------------------


class TestRankOffersThresholdFilter:
    def test_rank_offers_threshold_filter_excludes_low_score(self):
        """Products below min_relevance must be excluded from results."""
        products = [
            make_product("p1", relevance_score=0.8),
            make_product("p2", relevance_score=0.3),   # below threshold
            make_product("p3", relevance_score=0.6),
        ]
        config = make_config(min_relevance=0.5)
        results = rank_offers(products, cooldowns={}, config=config, now=_now())

        result_ids = [r.product_id for r in results]
        assert "p2" not in result_ids

    def test_rank_offers_threshold_filter_keeps_at_boundary(self):
        """A product exactly at min_relevance should be included."""
        products = [
            make_product("p_exact", relevance_score=0.5),
            make_product("p_above", relevance_score=0.9),
        ]
        config = make_config(min_relevance=0.5)
        results = rank_offers(products, cooldowns={}, config=config, now=_now())
        result_ids = [r.product_id for r in results]
        assert "p_exact" in result_ids

    def test_rank_offers_threshold_filter_all_below_returns_empty(self):
        """All products below min_relevance -> empty list."""
        products = [
            make_product("p1", relevance_score=0.1),
            make_product("p2", relevance_score=0.2),
        ]
        config = make_config(min_relevance=0.5)
        results = rank_offers(products, cooldowns={}, config=config, now=_now())
        assert results == []

    @pytest.mark.parametrize("threshold,score,should_include", [
        (0.5, 0.6, True),
        (0.5, 0.5, True),
        (0.5, 0.4, False),
        (0.7, 0.9, True),
        (0.7, 0.6, False),
    ])
    def test_threshold_parametrized(self, threshold, score, should_include):
        products = [make_product("p_test", relevance_score=score)]
        config = make_config(min_relevance=threshold)
        results = rank_offers(products, cooldowns={}, config=config, now=_now())
        if should_include:
            assert len(results) == 1
        else:
            assert len(results) == 0


# ---------------------------------------------------------------------------
# Cooldown filter
# ---------------------------------------------------------------------------


class TestRankOffersCooldownFilter:
    def test_rank_offers_cooldown_filter_excludes_recent(self):
        """Products shown within cooldown_hours must be excluded."""
        now = _now()
        recent_time = now - timedelta(hours=6)  # within 24h cooldown
        cooldowns = {"p_recent": recent_time.isoformat()}

        products = [
            make_product("p_recent", relevance_score=0.9),
            make_product("p_fresh",  relevance_score=0.8),
        ]
        config = make_config(cooldown_hours=24)
        results = rank_offers(products, cooldowns=cooldowns, config=config, now=now)

        result_ids = [r.product_id for r in results]
        assert "p_recent" not in result_ids
        assert "p_fresh" in result_ids

    def test_rank_offers_cooldown_expired_product_included(self):
        """Products outside the cooldown window must be included."""
        now = _now()
        old_time = now - timedelta(hours=48)  # beyond 24h cooldown
        cooldowns = {"p_old": old_time.isoformat()}

        products = [make_product("p_old", relevance_score=0.8)]
        config = make_config(cooldown_hours=24)
        results = rank_offers(products, cooldowns=cooldowns, config=config, now=now)

        result_ids = [r.product_id for r in results]
        assert "p_old" in result_ids

    def test_rank_offers_no_cooldowns_includes_all_eligible(self):
        """With no cooldowns dict, all threshold-passing products are included."""
        products = [
            make_product("p1", relevance_score=0.9),
            make_product("p2", relevance_score=0.7),
            make_product("p3", relevance_score=0.6),
        ]
        config = make_config(min_relevance=0.5, max_offers=10)
        results = rank_offers(products, cooldowns={}, config=config, now=_now())
        assert len(results) == 3

    def test_rank_offers_cooldown_boundary_exactly_at_limit_excluded(self):
        """A product dismissed exactly at the cooldown boundary is excluded."""
        now = _now()
        # Exactly at the cooldown boundary (not expired yet)
        boundary_time = now - timedelta(hours=24)
        cooldowns = {"p_boundary": boundary_time.isoformat()}

        products = [make_product("p_boundary", relevance_score=0.9)]
        config = make_config(cooldown_hours=24)
        results = rank_offers(products, cooldowns=cooldowns, config=config, now=now)
        result_ids = [r.product_id for r in results]
        assert "p_boundary" not in result_ids


# ---------------------------------------------------------------------------
# Diversity cap
# ---------------------------------------------------------------------------


class TestRankOffersDiversity:
    def test_rank_offers_diversity_caps_same_type(self):
        """No more than max_same_type products of the same type in results."""
        products = [
            make_product("p1", product_type="ETF", relevance_score=0.95),
            make_product("p2", product_type="ETF", relevance_score=0.90),
            make_product("p3", product_type="ETF", relevance_score=0.85),  # should be dropped
            make_product("p4", product_type="insurance", relevance_score=0.80),
        ]
        config = make_config(max_same_type=2, max_offers=10)
        results = rank_offers(products, cooldowns={}, config=config, now=_now())

        etf_results = [r for r in results if r.product_type == "ETF"]
        assert len(etf_results) <= 2

    def test_rank_offers_diversity_allows_different_types(self):
        """Products of different types are each allowed up to max_same_type."""
        products = [
            make_product("p1", product_type="ETF",       relevance_score=0.9),
            make_product("p2", product_type="ETF",       relevance_score=0.8),
            make_product("p3", product_type="insurance", relevance_score=0.9),
            make_product("p4", product_type="insurance", relevance_score=0.8),
            make_product("p5", product_type="loan",      relevance_score=0.7),
        ]
        config = make_config(max_same_type=2, max_offers=10)
        results = rank_offers(products, cooldowns={}, config=config, now=_now())

        etf = [r for r in results if r.product_type == "ETF"]
        insurance = [r for r in results if r.product_type == "insurance"]
        loan = [r for r in results if r.product_type == "loan"]

        assert len(etf) <= 2
        assert len(insurance) <= 2
        assert len(loan) <= 2

    def test_rank_offers_diversity_prefers_higher_score_within_type(self):
        """When diversity cap triggers, higher-scored products within type are kept."""
        products = [
            make_product("p_high",  product_type="ETF", relevance_score=0.95),
            make_product("p_mid",   product_type="ETF", relevance_score=0.80),
            make_product("p_low",   product_type="ETF", relevance_score=0.60),  # dropped by diversity
        ]
        config = make_config(max_same_type=2, max_offers=10)
        results = rank_offers(products, cooldowns={}, config=config, now=_now())

        etf_results = [r for r in results if r.product_type == "ETF"]
        result_ids = [r.product_id for r in etf_results]
        assert "p_high" in result_ids
        assert "p_mid" in result_ids
        assert "p_low" not in result_ids


# ---------------------------------------------------------------------------
# Max offers cap
# ---------------------------------------------------------------------------


class TestRankOffersMaxOffers:
    def test_rank_offers_max_offers_cap(self):
        """Result length must not exceed config.max_offers."""
        products = [
            make_product(f"p{i}", product_type=f"type{i}", relevance_score=0.9 - i * 0.01)
            for i in range(20)
        ]
        config = make_config(max_offers=5, max_same_type=10)
        results = rank_offers(products, cooldowns={}, config=config, now=_now())
        assert len(results) <= 5

    def test_rank_offers_fewer_products_than_max(self):
        """When fewer products than max_offers pass filters, return all that passed."""
        products = [
            make_product("p1", product_type="t1", relevance_score=0.9),
            make_product("p2", product_type="t2", relevance_score=0.8),
        ]
        config = make_config(max_offers=5)
        results = rank_offers(products, cooldowns={}, config=config, now=_now())
        assert len(results) == 2

    @pytest.mark.parametrize("max_offers,num_products,expected_count", [
        (3, 10, 3),
        (5, 3,  3),
        (1, 5,  1),
        (0, 5,  0),
    ])
    def test_max_offers_parametrized(self, max_offers, num_products, expected_count):
        products = [
            make_product(f"p{i}", product_type=f"t{i}", relevance_score=0.9)
            for i in range(num_products)
        ]
        config = make_config(max_offers=max_offers, max_same_type=100)
        results = rank_offers(products, cooldowns={}, config=config, now=_now())
        assert len(results) <= max_offers
        assert len(results) == min(expected_count, num_products)


# ---------------------------------------------------------------------------
# Sequential ranks
# ---------------------------------------------------------------------------


class TestRankOffersSequentialRanks:
    def test_rank_offers_assigns_sequential_ranks(self):
        """Ranks must be consecutive integers starting at 1."""
        products = [
            make_product("p1", product_type="t1", relevance_score=0.9),
            make_product("p2", product_type="t2", relevance_score=0.8),
            make_product("p3", product_type="t3", relevance_score=0.7),
        ]
        config = make_config(max_offers=10)
        results = rank_offers(products, cooldowns={}, config=config, now=_now())

        ranks = [r.rank for r in results]
        expected = list(range(1, len(results) + 1))
        assert ranks == expected, f"Expected ranks {expected}, got {ranks}"

    def test_rank_1_is_highest_relevance(self):
        """The product with rank=1 must have the highest relevance_score."""
        products = [
            make_product("p_low",  product_type="t1", relevance_score=0.55),
            make_product("p_high", product_type="t2", relevance_score=0.95),
            make_product("p_mid",  product_type="t3", relevance_score=0.75),
        ]
        config = make_config(max_offers=10)
        results = rank_offers(products, cooldowns={}, config=config, now=_now())

        rank_1 = next(r for r in results if r.rank == 1)
        assert rank_1.product_id == "p_high"

    def test_ranked_offers_have_rank_attribute(self):
        """Every RankedOffer must have a rank attribute."""
        products = [make_product("p1", product_type="t1", relevance_score=0.8)]
        config = make_config()
        results = rank_offers(products, cooldowns={}, config=config, now=_now())
        for r in results:
            assert hasattr(r, "rank")


# ---------------------------------------------------------------------------
# Empty input
# ---------------------------------------------------------------------------


class TestRankOffersEmptyInput:
    def test_rank_empty_input_returns_empty_list(self):
        """Empty scored_products input returns an empty list."""
        config = make_config()
        results = rank_offers([], cooldowns={}, config=config, now=_now())
        assert results == []

    def test_rank_empty_input_type_is_list(self):
        """Return value is always a list even on empty input."""
        config = make_config()
        results = rank_offers([], cooldowns={}, config=config, now=_now())
        assert isinstance(results, list)


# ---------------------------------------------------------------------------
# RankedOffer structure
# ---------------------------------------------------------------------------


class TestRankedOfferStructure:
    def test_ranked_offer_has_required_fields(self):
        """Every RankedOffer must expose the documented fields."""
        products = [make_product("p1", product_type="ETF", relevance_score=0.85)]
        config = make_config()
        results = rank_offers(products, cooldowns={}, config=config, now=_now())

        assert len(results) == 1
        offer = results[0]
        assert isinstance(offer, RankedOffer)
        assert hasattr(offer, "offer_id")
        assert hasattr(offer, "product_id")
        assert hasattr(offer, "product_name")
        assert hasattr(offer, "product_type")
        assert hasattr(offer, "relevance_score")
        assert hasattr(offer, "rank")

    def test_ranked_offer_offer_id_is_unique(self):
        """Each RankedOffer must have a unique offer_id."""
        products = [
            make_product(f"p{i}", product_type=f"t{i}", relevance_score=0.9 - i * 0.05)
            for i in range(5)
        ]
        config = make_config(max_offers=10, max_same_type=10)
        results = rank_offers(products, cooldowns={}, config=config, now=_now())

        offer_ids = [r.offer_id for r in results]
        assert len(offer_ids) == len(set(offer_ids)), "Duplicate offer_ids detected"

    def test_ranked_offer_preserves_product_metadata(self):
        """product_name and product_type must be preserved from input."""
        products = [
            make_product(
                "prod_etf_001",
                product_name="Global Equity ETF",
                product_type="ETF",
                relevance_score=0.88,
            )
        ]
        config = make_config()
        results = rank_offers(products, cooldowns={}, config=config, now=_now())

        assert len(results) == 1
        assert results[0].product_id == "prod_etf_001"
        assert results[0].product_name == "Global Equity ETF"
        assert results[0].product_type == "ETF"
