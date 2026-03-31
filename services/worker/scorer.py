from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Protocol

import anthropic

from services.worker.catalog import PRODUCT_CATALOG
from services.worker.profiler import ProfileResult

logger = logging.getLogger(__name__)

MODEL_ID = "claude-sonnet-4-20250514"
MAX_TOKENS = 1000

SCORING_SYSTEM_PROMPT = """\
You are an expert bank product recommendation engine. You will receive a customer's full financial profile and a list of products from the bank's catalog. For each product, output a JSON object with exactly these three fields:
  - relevance_score: float between 0.0 and 1.0 (how well this product fits the customer right now)
  - confidence_score: float between 0.0 and 1.0 (your confidence in the relevance assessment)
  - personalization_reason: string (one concise sentence explaining why this product is or is not a good fit)

Return a JSON array where each element corresponds to one product in the same order as provided. Output only valid JSON with no markdown fences and no additional text.\
"""


class LLMClient(Protocol):
    def create_message(self, prompt: str, system: str, max_tokens: int) -> str: ...


class AnthropicLLMClient:
    def __init__(self, api_key: str) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)

    def create_message(self, prompt: str, system: str, max_tokens: int) -> str:
        message = self._client.messages.create(
            model=MODEL_ID,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text


@dataclass
class ScoredProduct:
    product_id: str
    product_name: str
    category: str
    relevance_score: float
    confidence_score: float
    personalization_reason: str
    trigger_signals: list[str]
    recommended_channel: str


def _build_scoring_prompt(profile: ProfileResult, products: list[dict[str, Any]]) -> str:
    product_list = json.dumps(
        [
            {
                "product_id": p["product_id"],
                "product_name": p["product_name"],
                "category": p["category"],
                "description": p["description"],
                "eligibility_criteria": p["eligibility_criteria"],
                "suitability_criteria": p["suitability_criteria"],
                "trigger_signals": p["trigger_signals"],
                "risk_bucket": p["risk_bucket"],
            }
            for p in products
        ],
        indent=2,
    )

    customer_block = json.dumps(
        {
            "customer_id": profile.customer_id,
            "life_stage": profile.life_stage,
            "financial_health": profile.financial_health,
            "lifestyle_segment": profile.lifestyle_segment,
            "investor_readiness": profile.investor_readiness,
            "risk_bucket": profile.risk_bucket,
            "risk_score": profile.risk_score,
            "context_signals": profile.context_signals,
            "family_context": profile.family_context,
            "housing_context": profile.housing_context,
        },
        indent=2,
    )

    return (
        f"Customer Profile:\n{customer_block}\n\n"
        f"Product Catalog ({len(products)} products):\n{product_list}\n\n"
        "Score each product for this customer. Return a JSON array with one object per product in the same order."
    )


def _parse_llm_response(
    raw: str,
    products: list[dict[str, Any]],
) -> list[ScoredProduct]:
    text = raw.strip()
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        text = match.group()

    data = json.loads(text)

    scored: list[ScoredProduct] = []
    for product, item in zip(products, data):
        relevance = max(0.0, min(1.0, float(item.get("relevance_score", 0))))
        confidence = max(0.0, min(1.0, float(item.get("confidence_score", 0))))
        reason = str(item.get("personalization_reason", ""))
        scored.append(
            ScoredProduct(
                product_id=product["product_id"],
                product_name=product["product_name"],
                category=product["category"],
                relevance_score=round(relevance, 4),
                confidence_score=round(confidence, 4),
                personalization_reason=reason,
                trigger_signals=product.get("trigger_signals", []),
                recommended_channel=product.get("recommended_channel", "push"),
            )
        )
    return scored


def score_products(
    profile: ProfileResult,
    llm_client: LLMClient,
    products: list[dict[str, Any]] | None = None,
) -> list[ScoredProduct]:
    if products is None:
        products = PRODUCT_CATALOG

    prompt = _build_scoring_prompt(profile, products)

    try:
        raw_response = llm_client.create_message(
            prompt=prompt,
            system=SCORING_SYSTEM_PROMPT,
            max_tokens=MAX_TOKENS,
        )
        scored = _parse_llm_response(raw_response, products)
    except Exception:
        logger.exception("LLM scoring failed for customer %s, using zero scores", profile.customer_id)
        scored = [
            ScoredProduct(
                product_id=p["product_id"],
                product_name=p["product_name"],
                category=p["category"],
                relevance_score=0.0,
                confidence_score=0.0,
                personalization_reason="Scoring unavailable",
                trigger_signals=p.get("trigger_signals", []),
                recommended_channel=p.get("recommended_channel", "push"),
            )
            for p in products
        ]

    scored.sort(key=lambda s: s.relevance_score, reverse=True)
    logger.info("Scored %d products for customer %s", len(scored), profile.customer_id)
    return scored
