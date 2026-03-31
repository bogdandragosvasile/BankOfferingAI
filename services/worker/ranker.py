from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from services.worker.profiler import ProfileResult
from services.worker.scorer import ScoredProduct

logger = logging.getLogger(__name__)

MAX_OFFERS_PER_BATCH = 5
COOLDOWN_DAYS = 30
MAX_SAME_CATEGORY = 2
MIN_RELEVANCE_THRESHOLD = 0.10
MIN_CONFIDENCE_THRESHOLD = 0.10
SIGNAL_BOOST = 0.15

SIGNAL_TO_PRODUCTS: dict[str, list[str]] = {
    "idle_cash_high": ["etf_starter", "mutual_funds", "state_bonds", "savings_deposit"],
    "salary_increase": ["etf_starter", "mutual_funds", "private_pension"],
    "investment_gap": ["etf_starter", "mutual_funds", "managed_portfolio"],
    "monthly_savings_consistent": ["etf_starter", "private_pension", "mutual_funds"],
    "travel_spike": ["travel_insurance"],
    "rent_pattern": ["mortgage"],
    "family_context": ["life_insurance"],
    "high_income": ["mortgage", "managed_portfolio", "etf_growth"],
    "shopping_pattern": ["credit_card"],
    "bonus_event": ["mortgage", "etf_growth", "managed_portfolio"],
}


@dataclass
class RankedOffer:
    offer_id: str
    product_id: str
    product_name: str
    category: str
    relevance_score: float
    confidence_score: float
    personalization_reason: str
    recommended_channel: str
    rank: int
    boosted: bool


@dataclass
class CooldownRecord:
    product_id: str
    dismissed_at: datetime


@dataclass
class RankingConfig:
    max_offers: int = MAX_OFFERS_PER_BATCH
    cooldown_days: int = COOLDOWN_DAYS
    max_same_category: int = MAX_SAME_CATEGORY
    min_relevance: float = MIN_RELEVANCE_THRESHOLD
    min_confidence: float = MIN_CONFIDENCE_THRESHOLD
    signal_boost: float = SIGNAL_BOOST


def _is_on_cooldown(
    product_id: str,
    cooldowns: list[CooldownRecord],
    cooldown_days: int,
    now: datetime,
) -> bool:
    cutoff = now - timedelta(days=cooldown_days)
    return any(r.product_id == product_id and r.dismissed_at > cutoff for r in cooldowns)


def _compute_boosted_score(
    product_id: str,
    base_score: float,
    context_signals: list[str],
    signal_boost: float,
) -> tuple[float, bool]:
    triggered = any(
        product_id in SIGNAL_TO_PRODUCTS.get(sig, []) for sig in context_signals
    )
    if triggered:
        return min(1.0, base_score + signal_boost), True
    return base_score, False


def rank_offers(
    scored_products: list[ScoredProduct],
    profile: ProfileResult,
    cooldowns: list[CooldownRecord] | None = None,
    config: RankingConfig | None = None,
    now: datetime | None = None,
) -> list[RankedOffer]:
    if config is None:
        config = RankingConfig()
    if cooldowns is None:
        cooldowns = []
    if now is None:
        now = datetime.now(timezone.utc)

    candidates: list[dict[str, Any]] = []
    for sp in scored_products:
        if sp.relevance_score < config.min_relevance or sp.confidence_score < config.min_confidence:
            continue
        if _is_on_cooldown(sp.product_id, cooldowns, config.cooldown_days, now):
            continue

        boosted_score, boosted = _compute_boosted_score(
            sp.product_id,
            sp.relevance_score,
            profile.context_signals,
            config.signal_boost,
        )

        candidates.append(
            {
                "product_id": sp.product_id,
                "product_name": sp.product_name,
                "category": sp.category,
                "relevance_score": boosted_score,
                "confidence_score": sp.confidence_score,
                "personalization_reason": sp.personalization_reason,
                "recommended_channel": sp.recommended_channel,
                "boosted": boosted,
            }
        )

    candidates.sort(key=lambda c: c["relevance_score"], reverse=True)

    category_counts: dict[str, int] = {}
    diverse: list[dict[str, Any]] = []
    for c in candidates:
        cat = c["category"]
        if category_counts.get(cat, 0) < config.max_same_category:
            diverse.append(c)
            category_counts[cat] = category_counts.get(cat, 0) + 1

    final = diverse[: config.max_offers]

    ranked: list[RankedOffer] = []
    for idx, c in enumerate(final, start=1):
        ranked.append(
            RankedOffer(
                offer_id=str(uuid.uuid4()),
                product_id=c["product_id"],
                product_name=c["product_name"],
                category=c["category"],
                relevance_score=round(c["relevance_score"], 4),
                confidence_score=round(c["confidence_score"], 4),
                personalization_reason=c["personalization_reason"],
                recommended_channel=c["recommended_channel"],
                rank=idx,
                boosted=c["boosted"],
            )
        )

    logger.info(
        "Ranked %d offers for customer %s (signals=%s)",
        len(ranked),
        profile.customer_id,
        profile.context_signals,
    )
    return ranked
