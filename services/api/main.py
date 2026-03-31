"""FastAPI application entry point for the Bank Offering AI API service."""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator

import asyncio

from services.api.routers import api_tokens, compliance, consent_registry, customer_auth, offers, products, profiles, staff_auth

logger = logging.getLogger(__name__)

ALLOWED_ORIGINS = [
    "https://bankoffer.lupulup.com",
    "https://bankofferingai.example.com",
    "http://localhost:3000",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown lifecycle events."""
    # Startup: initialize DB connection pool and Redis
    logger.info("Starting up API service...")
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    import redis.asyncio as aioredis
    import os

    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/bankofferingai",
    )
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    engine = create_async_engine(database_url, pool_size=20, max_overflow=10)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    redis_client = aioredis.from_url(redis_url, decode_responses=True)

    app.state.db_engine = engine
    app.state.db_session_factory = session_factory
    app.state.redis = redis_client

    logger.info("Database and Redis connections established.")

    # Start consent registry background sync
    sync_task = asyncio.create_task(
        consent_registry.start_background_sync(session_factory)
    )
    app.state.consent_sync_task = sync_task

    yield

    # Cancel background sync
    sync_task.cancel()

    # Shutdown: close connections
    logger.info("Shutting down API service...")
    await redis_client.aclose()
    await engine.dispose()
    logger.info("Connections closed.")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Bank Offering AI",
        description="Personalized bank product offering engine powered by AI",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # Prometheus metrics
    Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers=["/health", "/metrics"],
    ).instrument(app).expose(app, endpoint="/metrics")

    # Routers
    app.include_router(offers.router, prefix="/offers", tags=["offers"])
    app.include_router(profiles.router, prefix="/profiles", tags=["profiles"])
    app.include_router(compliance.router, prefix="/compliance", tags=["compliance"])
    app.include_router(customer_auth.router, prefix="/customer-auth", tags=["customer-auth"])
    app.include_router(staff_auth.router, prefix="/staff-auth", tags=["staff-auth"])
    app.include_router(api_tokens.router, prefix="/api-tokens", tags=["api-tokens"])
    app.include_router(products.router, prefix="/products-catalog", tags=["products"])
    app.include_router(consent_registry.router, prefix="/consent-registry", tags=["consent-registry"])

    if os.getenv("KAFKA_BOOTSTRAP_SERVERS"):
        from services.api.routers import webhooks
        app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])

    @app.get("/health", tags=["health"])
    async def health_check():
        """Liveness probe endpoint."""
        return {
            "status": "healthy",
            "service": "bank-offering-api",
            "demo_mode": os.getenv("DEMO_MODE", "false").lower() == "true",
            "keycloak_configured": bool(os.getenv("KEYCLOAK_URL")),
        }

    # Serve frontend portals
    static_dir = Path(__file__).parent / "static"
    if static_dir.is_dir():
        @app.get("/", include_in_schema=False)
        async def root():
            """Employee portal (bank staff dashboard)."""
            return FileResponse(static_dir / "index.html")

        @app.get("/portal", include_in_schema=False)
        async def customer_portal():
            """Customer portal (client-facing)."""
            return FileResponse(static_dir / "portal.html")

        @app.get("/admin", include_in_schema=False)
        async def admin_portal():
            """Admin portal (administrators only)."""
            return FileResponse(static_dir / "admin.html")

        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("services.api.main:app", host="0.0.0.0", port=8000, reload=True)
