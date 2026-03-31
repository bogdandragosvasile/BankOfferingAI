"""Customer authentication router with GDPR-compliant data anonymization.

Implements:
- SHA-256 email hashing (irreversible pseudonymization, GDPR Art. 5(1)(c))
- PBKDF2-SHA256 password hashing (no external dependencies)
- JWT session tokens
- Automatic anonymization scheduling (GDPR Art. 5(1)(e) storage limitation)
"""

import binascii
import hashlib
import logging
import os
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Request
from jose import jwt
from sqlalchemy import text

from services.api.models import (
    CustomerLoginRequest,
    CustomerLoginResponse,
    CustomerRegisterRequest,
    CustomerRegisterResponse,
)

logger = logging.getLogger(__name__)

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

# GDPR Art. 5(1)(e): Storage limitation — auto-anonymize after 2 years
ANONYMIZATION_PERIOD_DAYS = 730

router = APIRouter()


def hash_email(email: str) -> str:
    """One-way SHA-256 hash of email for pseudonymization (GDPR Art. 5(1)(c))."""
    return hashlib.sha256(email.lower().strip().encode()).hexdigest()


def hash_password(password: str) -> str:
    """Hash password using PBKDF2-SHA256 with random salt (100k iterations)."""
    salt = os.urandom(32)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
    return binascii.hexlify(salt).decode() + ":" + binascii.hexlify(dk).decode()


def verify_password(password: str, stored: str) -> bool:
    """Verify password against stored PBKDF2-SHA256 hash."""
    try:
        salt_hex, dk_hex = stored.split(":")
        salt = binascii.unhexlify(salt_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
        return binascii.hexlify(dk).decode() == dk_hex
    except (ValueError, binascii.Error):
        return False


def create_customer_token(customer_id: str, external_id: str) -> str:
    """Create a signed JWT for customer session."""
    payload = {
        "customer_id": customer_id,
        "external_id": external_id,
        "type": "customer",
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


@router.post(
    "/register",
    response_model=CustomerRegisterResponse,
    summary="Register a new customer account",
    description="Creates an account with automatic data anonymization. "
    "Email is stored as irreversible SHA-256 hash only (GDPR Art. 5(1)(c)). "
    "An auto-anonymization date is set per Art. 5(1)(e).",
)
async def register_customer(body: CustomerRegisterRequest, request: Request):
    if not body.gdpr_consent:
        raise HTTPException(
            status_code=400,
            detail="You must accept the GDPR data processing terms to register.",
        )

    session_factory = request.app.state.db_session_factory
    email_h = hash_email(body.email)

    async with session_factory() as session:
        # Check if email already registered
        existing = await session.execute(
            text("SELECT id FROM customer_auth WHERE email_hash = :eh"),
            {"eh": email_h},
        )
        if existing.fetchone():
            raise HTTPException(
                status_code=409,
                detail="An account with this email already exists.",
            )

        # Assign a random customer profile from unassigned ones
        assigned = await session.execute(
            text(
                "SELECT c.customer_id, c.external_id FROM customers c "
                "WHERE c.customer_id NOT IN (SELECT ca.customer_id FROM customer_auth ca) "
                "ORDER BY random() LIMIT 1"
            )
        )
        row = assigned.fetchone()
        if not row:
            # All profiles taken — reuse a random one
            assigned = await session.execute(
                text(
                    "SELECT customer_id, external_id FROM customers "
                    "ORDER BY random() LIMIT 1"
                )
            )
            row = assigned.fetchone()

        customer_id = row[0]
        external_id = str(row[1])

        pwd_hash = hash_password(body.password)
        anon_date = datetime.utcnow() + timedelta(days=ANONYMIZATION_PERIOD_DAYS)
        display = body.display_name or "Customer"

        await session.execute(
            text(
                "INSERT INTO customer_auth "
                "(email_hash, password_hash, customer_id, display_name, anonymize_after) "
                "VALUES (:eh, :ph, :cid, :dn, :anon)"
            ),
            {
                "eh": email_h,
                "ph": pwd_hash,
                "cid": customer_id,
                "dn": display,
                "anon": anon_date,
            },
        )
        await session.commit()

        token = create_customer_token(customer_id, external_id)

        return CustomerRegisterResponse(
            token=token,
            customer_id=customer_id,
            external_id=external_id,
            display_name=display,
            anonymize_after=anon_date,
            message="Account created. Your email is stored as an irreversible hash only — automatic anonymization scheduled.",
        )


@router.post(
    "/login",
    response_model=CustomerLoginResponse,
    summary="Customer login",
    description="Authenticate with email and password. "
    "Returns a session token and pseudonymized identifiers.",
)
async def login_customer(body: CustomerLoginRequest, request: Request):
    session_factory = request.app.state.db_session_factory
    email_h = hash_email(body.email)

    async with session_factory() as session:
        result = await session.execute(
            text(
                "SELECT ca.id, ca.password_hash, ca.customer_id, ca.display_name, "
                "ca.anonymize_after, c.external_id "
                "FROM customer_auth ca "
                "JOIN customers c ON c.customer_id = ca.customer_id "
                "WHERE ca.email_hash = :eh"
            ),
            {"eh": email_h},
        )
        row = result.fetchone()

        if not row or not verify_password(body.password, row[1]):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        customer_id = row[2]
        external_id = str(row[5])

        # Update last_login
        await session.execute(
            text("UPDATE customer_auth SET last_login = NOW() WHERE id = :id"),
            {"id": row[0]},
        )
        await session.commit()

        token = create_customer_token(customer_id, external_id)

        return CustomerLoginResponse(
            token=token,
            customer_id=customer_id,
            external_id=external_id,
            display_name=row[3] or "Customer",
            anonymize_after=row[4],
        )
