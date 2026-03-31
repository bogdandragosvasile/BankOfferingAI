"""Product catalog management router.

Full CRUD for the product catalog. Changes here are reflected immediately
in the recommendation engine (offers endpoint reads from DB on each request).
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text

logger = logging.getLogger(__name__)

router = APIRouter()


# ===== Pydantic models =====

class ProductCreate(BaseModel):
    product_id: str = Field(..., min_length=1, max_length=100, description="Unique product ID (e.g. prod_savings_plus)")
    name: str = Field(..., min_length=1, max_length=200, description="Display name")
    type: str = Field(..., min_length=1, max_length=100, description="Product type (investment, savings, insurance, etc.)")
    risk_level: str = Field(default="moderate", description="Risk level: low, moderate, high")
    short_description: Optional[str] = Field(None, max_length=500)
    category: Optional[str] = Field(None, max_length=100)
    channel: Optional[str] = Field(None, max_length=100)
    priority: Optional[str] = Field(None, max_length=50)
    lifecycle_stage: Optional[str] = Field(None, max_length=100)
    when_to_recommend: Optional[str] = Field(None, max_length=500)
    is_credit_product: bool = Field(default=False, description="True for loans, mortgages, credit cards")
    active: bool = Field(default=True, description="Whether this product is offered")


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    type: Optional[str] = Field(None, max_length=100)
    risk_level: Optional[str] = None
    short_description: Optional[str] = None
    category: Optional[str] = None
    channel: Optional[str] = None
    priority: Optional[str] = None
    lifecycle_stage: Optional[str] = None
    when_to_recommend: Optional[str] = None
    is_credit_product: Optional[bool] = None
    active: Optional[bool] = None


class ProductResponse(BaseModel):
    product_id: str
    name: str
    type: str
    risk_level: str
    short_description: Optional[str]
    category: Optional[str]
    channel: Optional[str]
    priority: Optional[str]
    lifecycle_stage: Optional[str]
    when_to_recommend: Optional[str]
    is_credit_product: bool
    active: bool
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


async def _ensure_table(session):
    """Extend the products table with columns needed for CRUD management."""
    # Add new columns if they don't exist (safe for existing data)
    for col_def in [
        "product_id VARCHAR(100)",
        "type VARCHAR(100)",
        "risk_level VARCHAR(20) DEFAULT 'moderate'",
        "is_credit_product BOOLEAN DEFAULT FALSE",
        "active BOOLEAN DEFAULT TRUE",
        "updated_at TIMESTAMP DEFAULT NOW()",
    ]:
        col_name = col_def.split()[0]
        try:
            await session.execute(text(
                f"ALTER TABLE products ADD COLUMN IF NOT EXISTS {col_def}"
            ))
        except Exception:
            pass  # Column may already exist
    await session.commit()

    # Backfill product_id from product_name for existing rows
    await session.execute(text("""
        UPDATE products SET product_id = LOWER(REPLACE(REPLACE(product_name, ' ', '_'), '-', '_'))
        WHERE product_id IS NULL OR product_id = ''
    """))
    # Backfill type from category
    await session.execute(text("""
        UPDATE products SET type = LOWER(category)
        WHERE type IS NULL OR type = ''
    """))
    # Backfill risk_level
    await session.execute(text("""
        UPDATE products SET risk_level = 'moderate'
        WHERE risk_level IS NULL OR risk_level = ''
    """))
    await session.commit()


def _row_to_product(row) -> dict:
    """Convert a DB row mapping to a ProductResponse dict."""
    return {
        "product_id": row.get("product_id") or "",
        "name": row.get("product_name") or row.get("name") or "",
        "type": row.get("type") or row.get("category") or "",
        "risk_level": row.get("risk_level") or "moderate",
        "short_description": row.get("short_description"),
        "category": row.get("category"),
        "channel": row.get("channel"),
        "priority": row.get("priority"),
        "lifecycle_stage": row.get("lifecycle_stage"),
        "when_to_recommend": row.get("when_to_recommend"),
        "is_credit_product": bool(row.get("is_credit_product")),
        "active": row.get("active") if row.get("active") is not None else True,
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


@router.get(
    "",
    response_model=list[ProductResponse],
    summary="List all products in the catalog",
)
async def list_products(request: Request, active_only: bool = False):
    session_factory = request.app.state.db_session_factory
    async with session_factory() as session:
        await _ensure_table(session)
        query = "SELECT * FROM products"
        if active_only:
            query += " WHERE active = TRUE"
        query += " ORDER BY product_name"
        result = await session.execute(text(query))
        rows = result.mappings().fetchall()
        return [_row_to_product(r) for r in rows]


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Get a single product",
)
async def get_product(product_id: str, request: Request):
    session_factory = request.app.state.db_session_factory
    async with session_factory() as session:
        await _ensure_table(session)
        result = await session.execute(
            text("SELECT * FROM products WHERE product_id = :pid"),
            {"pid": product_id},
        )
        row = result.mappings().fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Product not found")
        return _row_to_product(row)


@router.post(
    "",
    response_model=ProductResponse,
    summary="Add a new product to the catalog",
    status_code=201,
)
async def create_product(body: ProductCreate, request: Request):
    session_factory = request.app.state.db_session_factory
    async with session_factory() as session:
        await _ensure_table(session)

        # Check for duplicate
        existing = await session.execute(
            text("SELECT product_name FROM products WHERE product_id = :pid OR product_name = :name"),
            {"pid": body.product_id, "name": body.name},
        )
        if existing.fetchone():
            raise HTTPException(status_code=409, detail="Product with this ID or name already exists")

        await session.execute(
            text("""
                INSERT INTO products (product_id, product_name, type, risk_level, short_description,
                    category, channel, priority, lifecycle_stage, when_to_recommend,
                    is_credit_product, active, updated_at)
                VALUES (:pid, :name, :type, :risk, :desc, :cat, :chan, :prio, :stage, :when,
                    :credit, :active, NOW())
            """),
            {
                "pid": body.product_id,
                "name": body.name,
                "type": body.type,
                "risk": body.risk_level,
                "desc": body.short_description,
                "cat": body.category or body.type,
                "chan": body.channel,
                "prio": body.priority,
                "stage": body.lifecycle_stage,
                "when": body.when_to_recommend,
                "credit": body.is_credit_product,
                "active": body.active,
            },
        )
        await session.commit()

        # Return the created product
        result = await session.execute(
            text("SELECT * FROM products WHERE product_id = :pid"),
            {"pid": body.product_id},
        )
        row = result.mappings().fetchone()
        return _row_to_product(row)


@router.put(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Update an existing product",
)
async def update_product(product_id: str, body: ProductUpdate, request: Request):
    session_factory = request.app.state.db_session_factory
    async with session_factory() as session:
        await _ensure_table(session)

        existing = await session.execute(
            text("SELECT product_name FROM products WHERE product_id = :pid"),
            {"pid": product_id},
        )
        if not existing.fetchone():
            raise HTTPException(status_code=404, detail="Product not found")

        # Build dynamic UPDATE
        updates = {}
        if body.name is not None:
            updates["product_name"] = body.name
        if body.type is not None:
            updates["type"] = body.type
        if body.risk_level is not None:
            updates["risk_level"] = body.risk_level
        if body.short_description is not None:
            updates["short_description"] = body.short_description
        if body.category is not None:
            updates["category"] = body.category
        if body.channel is not None:
            updates["channel"] = body.channel
        if body.priority is not None:
            updates["priority"] = body.priority
        if body.lifecycle_stage is not None:
            updates["lifecycle_stage"] = body.lifecycle_stage
        if body.when_to_recommend is not None:
            updates["when_to_recommend"] = body.when_to_recommend
        if body.is_credit_product is not None:
            updates["is_credit_product"] = body.is_credit_product
        if body.active is not None:
            updates["active"] = body.active

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        set_clauses = ", ".join(f"{k} = :{k}" for k in updates)
        updates["pid"] = product_id
        await session.execute(
            text(f"UPDATE products SET {set_clauses}, updated_at = NOW() WHERE product_id = :pid"),
            updates,
        )
        await session.commit()

        result = await session.execute(
            text("SELECT * FROM products WHERE product_id = :pid"),
            {"pid": product_id},
        )
        row = result.mappings().fetchone()
        return _row_to_product(row)


@router.delete(
    "/{product_id}",
    summary="Remove a product from the catalog",
)
async def delete_product(product_id: str, request: Request):
    session_factory = request.app.state.db_session_factory
    async with session_factory() as session:
        await _ensure_table(session)
        result = await session.execute(
            text("DELETE FROM products WHERE product_id = :pid RETURNING product_name"),
            {"pid": product_id},
        )
        row = result.fetchone()
        await session.commit()
        if not row:
            raise HTTPException(status_code=404, detail="Product not found")
        return {"status": "deleted", "product_id": product_id, "name": row[0]}
