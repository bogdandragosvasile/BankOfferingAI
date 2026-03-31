"""SendGrid email notification adapter using httpx."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"


async def send_email(payload: Any, email: str) -> dict[str, Any]:
    """Send a personalised offer email via the SendGrid v3 Mail Send API.

    Args:
        payload: NotificationPayload-compatible object with offer fields.
        email: Recipient email address.

    Returns:
        A delivery status dict with ``success`` (bool) and ``detail`` (str).
    """
    api_key = os.environ.get("SENDGRID_API_KEY")
    if not api_key:
        logger.error("SENDGRID_API_KEY not set — cannot send email")
        return {"success": False, "detail": "SENDGRID_API_KEY not configured"}

    from_email = os.environ.get("SENDGRID_FROM_EMAIL", "offers@bank.com")
    from_name = os.environ.get("SENDGRID_FROM_NAME", "Bank Offers")
    unsubscribe_base = os.environ.get("UNSUBSCRIBE_BASE_URL", "https://bank.com/unsubscribe")
    unsubscribe_url = f"{unsubscribe_base}?customer_id={payload.customer_id}"

    html_body = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{payload.product_name}</title>
  <style>
    body {{ margin:0; padding:0; font-family: Arial, Helvetica, sans-serif; background:#f4f4f7; }}
    .container {{ max-width:600px; margin:0 auto; background:#fff; border-radius:8px; overflow:hidden; }}
    .header {{ background:#003366; color:#fff; padding:24px 32px; }}
    .header h1 {{ margin:0; font-size:22px; }}
    .body-content {{ padding:32px; color:#333; line-height:1.6; }}
    .body-content h2 {{ color:#003366; margin-top:0; }}
    .cta-btn {{ display:inline-block; margin-top:24px; padding:14px 28px; background:#0066cc;
                color:#fff; text-decoration:none; border-radius:6px; font-weight:bold; }}
    .footer {{ padding:16px 32px; font-size:12px; color:#999; text-align:center; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header"><h1>A new offer just for you</h1></div>
    <div class="body-content">
      <h2>{payload.product_name}</h2>
      <p>{payload.personalization_reason}</p>
      <a href="{payload.cta_url}" class="cta-btn">View Offer</a>
    </div>
    <div class="footer">
      <p>You received this email because you are a valued customer.
         <a href="{unsubscribe_url}">Unsubscribe</a></p>
      <p>Offer ID: {payload.offer_id}</p>
    </div>
  </div>
</body>
</html>"""

    body = {
        "personalizations": [
            {
                "to": [{"email": email}],
                "subject": f"Exclusive offer: {payload.product_name}",
            }
        ],
        "from": {"email": from_email, "name": from_name},
        "content": [{"type": "text/html", "value": html_body}],
        "categories": ["bank_offer"],
        "tracking_settings": {
            "click_tracking": {"enable": True},
            "open_tracking": {"enable": True},
        },
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(SENDGRID_API_URL, headers=headers, json=body)

        if 200 <= response.status_code < 300:
            logger.info(
                "Email accepted by SendGrid for offer %s to %s (HTTP %d)",
                payload.offer_id,
                email,
                response.status_code,
            )
            return {"success": True, "detail": f"SendGrid HTTP {response.status_code}"}

        logger.warning(
            "SendGrid returned HTTP %d for offer %s: %s",
            response.status_code,
            payload.offer_id,
            response.text[:200],
        )
        return {"success": False, "detail": f"SendGrid HTTP {response.status_code}"}

    except httpx.RequestError as exc:
        logger.exception("SendGrid request error for offer %s", payload.offer_id)
        return {"success": False, "detail": f"Request error: {exc}"}
