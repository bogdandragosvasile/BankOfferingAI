"""Compliance router - audit trail, human-in-the-loop feedback, and consent management."""

import logging
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import text

from services.api.middleware.auth import get_current_customer_id
from services.api.models import (
    AuditEntry,
    AuditListEntry,
    ConsentStatus,
    ConsentUpdate,
    FeedbackRequest,
    FeedbackResponse,
)

logger = logging.getLogger(__name__)

DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

router = APIRouter()


# ===== Requirement 3: Human-in-the-loop feedback =====

@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    summary="Submit feedback on a recommendation",
    description="Allows customers or employees to accept, reject, flag, or override a recommendation.",
)
async def submit_feedback(
    body: FeedbackRequest,
    request: Request,
    authenticated_customer: str = Depends(get_current_customer_id),
):
    """Record human feedback on a recommendation (GDPR art.22 + AI Act)."""
    session_factory = request.app.state.db_session_factory

    if body.action not in ("accepted", "rejected", "flagged", "overridden"):
        raise HTTPException(status_code=400, detail="Invalid action")
    if body.actor_type not in ("customer", "employee"):
        raise HTTPException(status_code=400, detail="Invalid actor_type")

    try:
        async with session_factory() as session:
            result = await session.execute(
                text("""INSERT INTO recommendation_feedback
                    (recommendation_id, offer_id, product_id, customer_id,
                     actor_type, actor_id, action, reason)
                    VALUES (:rid, :oid, :pid, :cid, :atype, :aid, :action, :reason)
                    RETURNING id, created_at"""),
                {
                    "rid": body.recommendation_id,
                    "oid": body.offer_id,
                    "pid": body.product_id,
                    "cid": body.customer_id,
                    "atype": body.actor_type,
                    "aid": body.actor_id,
                    "action": body.action,
                    "reason": body.reason,
                },
            )
            row = result.mappings().fetchone()
            await session.commit()

            return FeedbackResponse(
                id=row["id"],
                recommendation_id=body.recommendation_id,
                offer_id=body.offer_id,
                action=body.action,
                reason=body.reason,
                created_at=row["created_at"],
            )
    except Exception as e:
        logger.error("Failed to save feedback: %s", e)
        raise HTTPException(status_code=500, detail="Failed to save feedback")


@router.get(
    "/feedback/{customer_id}",
    response_model=list[FeedbackResponse],
    summary="Get feedback history for a customer",
)
async def get_feedback(
    customer_id: str,
    request: Request,
    authenticated_customer: str = Depends(get_current_customer_id),
):
    """Retrieve all feedback entries for a customer."""
    session_factory = request.app.state.db_session_factory
    try:
        async with session_factory() as session:
            result = await session.execute(
                text("""SELECT id, recommendation_id, offer_id, action, reason, created_at
                     FROM recommendation_feedback
                     WHERE customer_id = :cid
                     ORDER BY created_at DESC LIMIT 100"""),
                {"cid": customer_id},
            )
            rows = result.mappings().fetchall()
            return [FeedbackResponse(
                id=r["id"],
                recommendation_id=str(r["recommendation_id"]),
                offer_id=r["offer_id"],
                action=r["action"],
                reason=r["reason"],
                created_at=r["created_at"],
            ) for r in rows]
    except Exception as e:
        logger.error("Failed to fetch feedback: %s", e)
        raise HTTPException(status_code=500, detail="Failed to retrieve feedback")


# ===== Requirement 4: Audit trail =====

@router.get(
    "/audit",
    response_model=list[AuditListEntry],
    summary="List audit trail entries",
    description="Returns paginated list of all recommendation audit entries (EBA Guidelines + AI Act).",
)
async def list_audit(
    request: Request,
    customer_id: str = Query(default=None, description="Filter by customer ID"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    authenticated_customer: str = Depends(get_current_customer_id),
):
    """List audit trail entries. Employee access in production."""
    session_factory = request.app.state.db_session_factory
    try:
        async with session_factory() as session:
            if customer_id:
                result = await session.execute(
                    text("""SELECT id, recommendation_id, external_customer_id, customer_id,
                            final_offers, excluded_products, model_version, created_at
                         FROM audit_recommendations
                         WHERE customer_id = :cid
                         ORDER BY created_at DESC LIMIT :lim OFFSET :off"""),
                    {"cid": customer_id, "lim": limit, "off": offset},
                )
            else:
                result = await session.execute(
                    text("""SELECT id, recommendation_id, external_customer_id, customer_id,
                            final_offers, excluded_products, model_version, created_at
                         FROM audit_recommendations
                         ORDER BY created_at DESC LIMIT :lim OFFSET :off"""),
                    {"lim": limit, "off": offset},
                )
            rows = result.mappings().fetchall()
            return [AuditListEntry(
                id=r["id"],
                recommendation_id=str(r["recommendation_id"]),
                external_customer_id=str(r["external_customer_id"]),
                customer_id=r["customer_id"],
                num_offers=len(r["final_offers"]) if isinstance(r["final_offers"], list) else 0,
                num_excluded=len(r["excluded_products"]) if isinstance(r["excluded_products"], list) else 0,
                model_version=r["model_version"],
                created_at=r["created_at"],
            ) for r in rows]
    except Exception as e:
        logger.error("Failed to list audit: %s", e)
        raise HTTPException(status_code=500, detail="Failed to retrieve audit entries")


@router.get(
    "/audit/{recommendation_id}",
    response_model=AuditEntry,
    summary="Get full audit detail for a recommendation",
)
async def get_audit_detail(
    recommendation_id: str,
    request: Request,
    authenticated_customer: str = Depends(get_current_customer_id),
):
    """Retrieve full audit record for a specific recommendation."""
    session_factory = request.app.state.db_session_factory
    try:
        async with session_factory() as session:
            result = await session.execute(
                text("""SELECT * FROM audit_recommendations
                     WHERE recommendation_id = CAST(:rid AS uuid)"""),
                {"rid": recommendation_id},
            )
            row = result.mappings().fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Audit entry not found")
            return AuditEntry(
                id=row["id"],
                recommendation_id=str(row["recommendation_id"]),
                external_customer_id=str(row["external_customer_id"]),
                customer_id=row["customer_id"],
                input_features=row["input_features"],
                profile_result=row["profile_result"],
                suitability_checks=row["suitability_checks"],
                scored_products=row["scored_products"],
                final_offers=row["final_offers"],
                excluded_products=row["excluded_products"],
                model_version=row["model_version"],
                consent_snapshot=row["consent_snapshot"],
                created_at=row["created_at"],
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to fetch audit detail: %s", e)
        raise HTTPException(status_code=500, detail="Failed to retrieve audit entry")


# ===== Requirement 5: Consent management =====

@router.get(
    "/consent/{customer_id}",
    response_model=ConsentStatus,
    summary="Get consent status for a customer",
)
async def get_consent(
    customer_id: str,
    request: Request,
    authenticated_customer: str = Depends(get_current_customer_id),
):
    """Retrieve current consent flags for a customer."""
    session_factory = request.app.state.db_session_factory
    try:
        async with session_factory() as session:
            result = await session.execute(
                text("""SELECT customer_id, external_id, profiling_consent,
                        profiling_consent_ts, sensitive_data_consent,
                        sensitive_data_consent_ts
                     FROM customers WHERE customer_id = :cid"""),
                {"cid": customer_id},
            )
            row = result.mappings().fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Customer not found")
            return ConsentStatus(
                customer_id=row["customer_id"],
                external_id=str(row["external_id"]),
                profiling_consent=bool(row["profiling_consent"]),
                profiling_consent_ts=row["profiling_consent_ts"],
                sensitive_data_consent=bool(row["sensitive_data_consent"]),
                sensitive_data_consent_ts=row["sensitive_data_consent_ts"],
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to fetch consent: %s", e)
        raise HTTPException(status_code=500, detail="Failed to retrieve consent status")


@router.put(
    "/consent/{customer_id}",
    response_model=ConsentStatus,
    summary="Update consent flags for a customer",
)
async def update_consent(
    customer_id: str,
    body: ConsentUpdate,
    request: Request,
    authenticated_customer: str = Depends(get_current_customer_id),
):
    """Update profiling and/or sensitive data consent."""
    session_factory = request.app.state.db_session_factory
    try:
        async with session_factory() as session:
            updates = []
            params = {"cid": customer_id}

            if body.profiling_consent is not None:
                updates.append("profiling_consent = :pc")
                updates.append("profiling_consent_ts = NOW()")
                params["pc"] = body.profiling_consent

            if body.sensitive_data_consent is not None:
                updates.append("sensitive_data_consent = :sc")
                updates.append("sensitive_data_consent_ts = NOW()")
                params["sc"] = body.sensitive_data_consent

            if not updates:
                raise HTTPException(status_code=400, detail="No consent fields to update")

            await session.execute(
                text(f"UPDATE customers SET {', '.join(updates)} WHERE customer_id = :cid"),
                params,
            )
            await session.commit()

            # Return updated status
            result = await session.execute(
                text("""SELECT customer_id, external_id, profiling_consent,
                        profiling_consent_ts, sensitive_data_consent,
                        sensitive_data_consent_ts
                     FROM customers WHERE customer_id = :cid"""),
                {"cid": customer_id},
            )
            row = result.mappings().fetchone()
            return ConsentStatus(
                customer_id=row["customer_id"],
                external_id=str(row["external_id"]),
                profiling_consent=bool(row["profiling_consent"]),
                profiling_consent_ts=row["profiling_consent_ts"],
                sensitive_data_consent=bool(row["sensitive_data_consent"]),
                sensitive_data_consent_ts=row["sensitive_data_consent_ts"],
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update consent: %s", e)
        raise HTTPException(status_code=500, detail="Failed to update consent")


# ===== Customer data endpoint (for customer portal) =====

@router.get(
    "/customer/{customer_id}",
    summary="Get customer data for portal",
)
async def get_customer_data(
    customer_id: str,
    request: Request,
    authenticated_customer: str = Depends(get_current_customer_id),
):
    """Return customer info for the customer portal (pseudonymized)."""
    session_factory = request.app.state.db_session_factory
    try:
        async with session_factory() as session:
            result = await session.execute(
                text("""SELECT c.customer_id, c.external_id, c.age, c.income,
                        c.risk_profile, c.financial_health,
                        c.dependents_count, c.homeowner_status,
                        c.profiling_consent, c.sensitive_data_consent,
                        cf.annual_income, cf.idle_cash, cf.savings_rate,
                        cf.debt_to_income, cf.balance_trend,
                        cf.dominant_spend_category, cf.investment_gap_flag
                 FROM customers c
                 LEFT JOIN customer_features cf ON c.customer_id = cf.customer_id
                 WHERE c.customer_id = :cid"""),
                {"cid": customer_id},
            )
            row = result.mappings().fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Customer not found")

            return {
                "customer_id": row["customer_id"],
                "external_id": str(row["external_id"]),
                "age": row["age"],
                "income_monthly": float(row["income"]) if row["income"] else 0,
                "risk_profile": row["risk_profile"],
                "financial_health": row["financial_health"],
                "dependents": row["dependents_count"],
                "homeowner_status": row["homeowner_status"],
                "profiling_consent": bool(row["profiling_consent"]),
                "sensitive_data_consent": bool(row["sensitive_data_consent"]),
                "features": {
                    "annual_income": float(row["annual_income"]) if row["annual_income"] else 0,
                    "idle_cash": float(row["idle_cash"]) if row["idle_cash"] else 0,
                    "savings_rate": float(row["savings_rate"]) if row["savings_rate"] else 0,
                    "debt_to_income": float(row["debt_to_income"]) if row["debt_to_income"] else 0,
                    "balance_trend": row["balance_trend"],
                    "spend_category": row["dominant_spend_category"],
                    "investment_gap": bool(row["investment_gap_flag"]),
                },
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to fetch customer data: %s", e)
        raise HTTPException(status_code=500, detail="Failed to retrieve customer data")
