"""Transaction normalizer — stateless transformation of raw bank transactions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def normalize_transaction(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalise a raw transaction dict consumed from ``bank.transactions``.

    Transformations applied:
    - ``amount`` is coerced to ``float``; missing/invalid values default to ``0.0``
    - ``timestamp`` is parsed and re-serialised as an ISO-8601 UTC string;
      falls back to current UTC time if missing or unparseable
    - ``currency`` is uppercased; defaults to ``"USD"``
    - ``status`` defaults to ``"unknown"`` if absent
    - ``channel`` defaults to ``"unknown"`` if absent
    - ``merchant_name`` defaults to ``""`` if absent
    - ``merchant_category_code`` defaults to ``"0000"`` if absent
    - ``transaction_type`` defaults to ``"unknown"`` if absent
    - Derived fields added:
        - ``is_debit`` (bool): True when ``amount < 0``
        - ``abs_amount`` (float): absolute value of ``amount``
        - ``month_year`` (str): ``"YYYY-MM"`` extracted from ``timestamp``

    Args:
        raw: Raw transaction dict as decoded from the Kafka message.

    Returns:
        Normalised transaction dict ready for downstream feature engineering.
    """
    amount: float
    try:
        amount = float(raw.get("amount", 0.0) or 0.0)
    except (TypeError, ValueError):
        amount = 0.0

    timestamp_str: str
    month_year: str
    raw_ts = raw.get("timestamp")
    if raw_ts:
        try:
            if isinstance(raw_ts, (int, float)):
                dt = datetime.fromtimestamp(raw_ts, tz=timezone.utc)
            elif isinstance(raw_ts, datetime):
                dt = raw_ts if raw_ts.tzinfo else raw_ts.replace(tzinfo=timezone.utc)
            else:
                dt = datetime.fromisoformat(str(raw_ts).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            timestamp_str = dt.isoformat()
            month_year = dt.strftime("%Y-%m")
        except (ValueError, TypeError, OSError):
            now = datetime.now(tz=timezone.utc)
            timestamp_str = now.isoformat()
            month_year = now.strftime("%Y-%m")
    else:
        now = datetime.now(tz=timezone.utc)
        timestamp_str = now.isoformat()
        month_year = now.strftime("%Y-%m")

    currency = str(raw.get("currency") or "USD").upper()

    return {
        "transaction_id": raw.get("transaction_id") or "",
        "customer_id": raw.get("customer_id") or "",
        "amount": amount,
        "currency": currency,
        "merchant_name": raw.get("merchant_name") or "",
        "merchant_category_code": raw.get("merchant_category_code") or "0000",
        "transaction_type": raw.get("transaction_type") or "unknown",
        "timestamp": timestamp_str,
        "channel": raw.get("channel") or "unknown",
        "status": raw.get("status") or "unknown",
        "is_debit": amount < 0,
        "abs_amount": abs(amount),
        "month_year": month_year,
    }
