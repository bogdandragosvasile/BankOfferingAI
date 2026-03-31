"""JWT authentication middleware for the Bank Offering AI API."""

import os
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "bank-offering-api")
JWT_ISSUER = os.getenv("JWT_ISSUER", "bank-auth-service")

bearer_scheme = HTTPBearer(auto_error=True)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token, returning the claims payload.

    Raises HTTPException with 401 status if the token is invalid, expired,
    or missing required claims.
    """
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    customer_id: Optional[str] = payload.get("customer_id")
    if not customer_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing required customer_id claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


async def get_current_customer_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    """FastAPI dependency that extracts and validates the customer_id from a JWT.

    Usage:
        @router.get("/resource")
        async def endpoint(customer_id: str = Depends(get_current_customer_id)):
            ...
    """
    payload = decode_token(credentials.credentials)
    return payload["customer_id"]
