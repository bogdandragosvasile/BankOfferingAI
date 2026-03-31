"""Integration tests for the BankOffer AI REST API.

Uses httpx AsyncClient + pytest-asyncio to exercise the FastAPI application
with real routing but with DB/Redis/worker dependencies mocked out.

Tested endpoints:
  GET  /health                      -> 200 {"status": "healthy"}
  GET  /offers/{customer_id}        -> 401 without token, 200 with valid token
  POST /webhooks/transaction        -> 202 accepted
  GET  /profiles/{customer_id}      -> 200 with valid token
"""

import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from services.api.main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def async_client():
    """AsyncClient wired directly to the FastAPI app via ASGI transport."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.fixture
def valid_auth_headers():
    return {"Authorization": "Bearer test-valid-jwt-token-abc123"}


@pytest.fixture
def mock_ranked_offers():
    return [
        {
            "offer_id": "offer_001",
            "product_id": "prod_ins_001",
            "product_name": "Family Life Insurance",
            "product_type": "insurance",
            "relevance_score": 0.91,
            "rank": 1,
            "personalization_reason": (
                "As a parent with dependents, life insurance ensures "
                "your family's financial security."
            ),
            "confidence": 0.91,
            "cta_url": "https://bank.example.com/offers/offer_001",
        },
        {
            "offer_id": "offer_002",
            "product_id": "prod_etf_001",
            "product_name": "Global Equity ETF",
            "product_type": "ETF",
            "relevance_score": 0.82,
            "rank": 2,
            "personalization_reason": (
                "Your investment behavior and risk tolerance align well "
                "with diversified equity exposure."
            ),
            "confidence": 0.82,
            "cta_url": "https://bank.example.com/offers/offer_002",
        },
    ]


@pytest.fixture
def mock_customer_profile():
    return {
        "customer_id": "cust_001",
        "life_stage": "young_family",
        "financial_health": "healthy",
        "investor_readiness": "medium",
        "risk_bucket": "medium",
        "risk_score": 5.5,
        "lifestyle_segment": "urban_professional",
        "context_signals": ["idle_cash_high"],
        "family_context": True,
    }


@pytest.fixture
def mock_valid_token_payload():
    return {"sub": "cust_001", "role": "customer", "exp": 9999999999}


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestHealthCheck:
    async def test_health_check_returns_200(self, async_client):
        """GET /health must return HTTP 200."""
        response = await async_client.get("/health")
        assert response.status_code == 200

    async def test_health_check_returns_healthy_status(self, async_client):
        """GET /health body must contain {"status": "healthy"}."""
        response = await async_client.get("/health")
        data = response.json()
        assert data.get("status") == "healthy"

    async def test_health_check_no_auth_required(self, async_client):
        """GET /health must be accessible without an Authorization header."""
        response = await async_client.get("/health")
        assert response.status_code != 401

    async def test_health_check_content_type_json(self, async_client):
        """GET /health must return JSON content-type."""
        response = await async_client.get("/health")
        assert "application/json" in response.headers.get("content-type", "")


# ---------------------------------------------------------------------------
# /offers/{customer_id} - authentication
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestOffersRequiresAuth:
    async def test_offers_requires_auth_returns_401(self, async_client):
        """GET /offers/{id} without Authorization header returns 401."""
        response = await async_client.get("/offers/cust_001")
        assert response.status_code == 401

    async def test_offers_requires_auth_wrong_scheme_returns_401(self, async_client):
        """GET /offers/{id} with wrong auth scheme returns 401."""
        response = await async_client.get(
            "/offers/cust_001",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert response.status_code == 401

    async def test_offers_no_token_value_returns_401(self, async_client):
        """GET /offers/{id} with 'Bearer ' but no token value returns 401."""
        response = await async_client.get(
            "/offers/cust_001",
            headers={"Authorization": "Bearer "},
        )
        assert response.status_code == 401

    @patch("services.api.middleware.auth.verify_token")
    @patch("services.api.routers.offers.get_ranked_offers")
    async def test_offers_valid_token_returns_200(
        self,
        mock_get_offers,
        mock_verify,
        async_client,
        valid_auth_headers,
        mock_ranked_offers,
        mock_valid_token_payload,
    ):
        """GET /offers/{id} with valid token returns HTTP 200."""
        mock_verify.return_value = mock_valid_token_payload
        mock_get_offers.return_value = mock_ranked_offers

        response = await async_client.get("/offers/cust_001", headers=valid_auth_headers)
        assert response.status_code == 200

    @patch("services.api.middleware.auth.verify_token")
    @patch("services.api.routers.offers.get_ranked_offers")
    async def test_offers_response_contains_offers_list(
        self,
        mock_get_offers,
        mock_verify,
        async_client,
        valid_auth_headers,
        mock_ranked_offers,
        mock_valid_token_payload,
    ):
        """GET /offers/{id} response body must contain an 'offers' array."""
        mock_verify.return_value = mock_valid_token_payload
        mock_get_offers.return_value = mock_ranked_offers

        response = await async_client.get("/offers/cust_001", headers=valid_auth_headers)
        data = response.json()
        assert "offers" in data
        assert isinstance(data["offers"], list)

    @patch("services.api.middleware.auth.verify_token")
    async def test_offers_cross_customer_returns_403(
        self,
        mock_verify,
        async_client,
        valid_auth_headers,
        mock_valid_token_payload,
    ):
        """Token for cust_002 requesting cust_001's offers must return 403."""
        mock_verify.return_value = {**mock_valid_token_payload, "sub": "cust_002"}
        response = await async_client.get("/offers/cust_001", headers=valid_auth_headers)
        assert response.status_code == 403

    @patch("services.api.middleware.auth.verify_token")
    @patch("services.api.routers.offers.get_ranked_offers")
    async def test_offers_items_have_required_fields(
        self,
        mock_get_offers,
        mock_verify,
        async_client,
        valid_auth_headers,
        mock_ranked_offers,
        mock_valid_token_payload,
    ):
        """Each offer in the response must contain required fields."""
        mock_verify.return_value = mock_valid_token_payload
        mock_get_offers.return_value = mock_ranked_offers

        response = await async_client.get("/offers/cust_001", headers=valid_auth_headers)
        data = response.json()
        required_fields = {"offer_id", "product_id", "product_name", "product_type"}
        for offer in data.get("offers", []):
            for field in required_fields:
                assert field in offer, f"Missing field '{field}' in offer {offer}"


# ---------------------------------------------------------------------------
# POST /webhooks/transaction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestWebhookReceive:
    @patch("services.api.routers.webhooks.verify_webhook_signature")
    @patch("services.api.routers.webhooks.publish_to_kafka")
    async def test_webhook_receive_returns_202(
        self, mock_publish, mock_verify_sig, async_client
    ):
        """POST /webhooks/transaction with valid payload returns 202 Accepted."""
        mock_verify_sig.return_value = True
        mock_publish.return_value = None

        payload = {
            "event_type": "transaction.created",
            "customer_id": "cust_001",
            "transaction": {
                "id": "txn_abc123",
                "amount": 250.0,
                "category": "groceries",
                "merchant": "SuperStore",
                "timestamp": "2026-03-31T10:00:00Z",
                "currency": "USD",
            },
        }
        response = await async_client.post(
            "/webhooks/transaction",
            json=payload,
            headers={"X-Webhook-Signature": "sha256=valid-hmac-signature"},
        )
        assert response.status_code == 202

    @patch("services.api.routers.webhooks.verify_webhook_signature")
    @patch("services.api.routers.webhooks.publish_to_kafka")
    async def test_webhook_receive_publishes_to_kafka(
        self, mock_publish, mock_verify_sig, async_client
    ):
        """A valid webhook POST must trigger a Kafka publish call."""
        mock_verify_sig.return_value = True
        mock_publish.return_value = None

        payload = {
            "event_type": "transaction.created",
            "customer_id": "cust_002",
            "transaction": {
                "id": "txn_xyz789",
                "amount": 1500.0,
                "category": "travel",
                "merchant": "AirlineX",
                "timestamp": "2026-03-31T14:00:00Z",
                "currency": "USD",
            },
        }
        await async_client.post(
            "/webhooks/transaction",
            json=payload,
            headers={"X-Webhook-Signature": "sha256=valid-hmac-signature"},
        )
        mock_publish.assert_called_once()

    @patch("services.api.routers.webhooks.verify_webhook_signature")
    async def test_webhook_invalid_signature_returns_401(
        self, mock_verify_sig, async_client
    ):
        """A webhook POST with bad signature must return 401."""
        mock_verify_sig.return_value = False

        response = await async_client.post(
            "/webhooks/transaction",
            json={"event_type": "transaction.created", "customer_id": "cust_001"},
            headers={"X-Webhook-Signature": "sha256=bad-signature"},
        )
        assert response.status_code == 401

    @patch("services.api.routers.webhooks.verify_webhook_signature")
    @patch("services.api.routers.webhooks.publish_to_kafka")
    async def test_webhook_missing_signature_header_returns_401(
        self, mock_publish, mock_verify_sig, async_client
    ):
        """Webhook POST without signature header must return 401."""
        mock_verify_sig.return_value = False

        response = await async_client.post(
            "/webhooks/transaction",
            json={"event_type": "transaction.created", "customer_id": "cust_001"},
        )
        assert response.status_code == 401

    @patch("services.api.routers.webhooks.verify_webhook_signature")
    @patch("services.api.routers.webhooks.publish_to_kafka")
    async def test_webhook_response_has_accepted_message(
        self, mock_publish, mock_verify_sig, async_client
    ):
        """202 response body should acknowledge the event was received."""
        mock_verify_sig.return_value = True
        mock_publish.return_value = None

        payload = {
            "event_type": "transaction.created",
            "customer_id": "cust_003",
            "transaction": {
                "id": "txn_test_001",
                "amount": 80.0,
                "category": "dining",
                "merchant": "RestaurantY",
                "timestamp": "2026-03-31T19:00:00Z",
                "currency": "USD",
            },
        }
        response = await async_client.post(
            "/webhooks/transaction",
            json=payload,
            headers={"X-Webhook-Signature": "sha256=valid-hmac-signature"},
        )
        assert response.status_code == 202
        data = response.json()
        # Response should communicate acceptance
        assert any(
            key in data for key in ("status", "message", "accepted", "event_id")
        ), f"202 body missing acknowledgement field: {data}"


# ---------------------------------------------------------------------------
# GET /profiles/{customer_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestProfilesEndpoint:
    async def test_profiles_requires_auth_returns_401(self, async_client):
        """GET /profiles/{id} without token returns 401."""
        response = await async_client.get("/profiles/cust_001")
        assert response.status_code == 401

    @patch("services.api.middleware.auth.verify_token")
    @patch("services.api.routers.profiles.get_customer_profile")
    async def test_profiles_valid_token_returns_200(
        self,
        mock_get_profile,
        mock_verify,
        async_client,
        valid_auth_headers,
        mock_customer_profile,
        mock_valid_token_payload,
    ):
        """GET /profiles/{id} with valid token returns HTTP 200."""
        mock_verify.return_value = mock_valid_token_payload
        mock_get_profile.return_value = mock_customer_profile

        response = await async_client.get("/profiles/cust_001", headers=valid_auth_headers)
        assert response.status_code == 200

    @patch("services.api.middleware.auth.verify_token")
    @patch("services.api.routers.profiles.get_customer_profile")
    async def test_profiles_response_has_customer_id(
        self,
        mock_get_profile,
        mock_verify,
        async_client,
        valid_auth_headers,
        mock_customer_profile,
        mock_valid_token_payload,
    ):
        """Profile response must include customer_id."""
        mock_verify.return_value = mock_valid_token_payload
        mock_get_profile.return_value = mock_customer_profile

        response = await async_client.get("/profiles/cust_001", headers=valid_auth_headers)
        data = response.json()
        assert "customer_id" in data
        assert data["customer_id"] == "cust_001"
