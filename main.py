"""
main.py
-------
FastAPI application factory.
Everything is wired here: middleware, routers, exception handlers, lifespan.
`app` is the ASGI object passed to Uvicorn.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestLoggingMiddleware
from app.routers import auth, tasks, users

# ── Bootstrap logging before anything else ───────────────────────────────────
configure_logging()
logger = logging.getLogger("taskflow.main")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Code before `yield` runs at startup; code after runs at shutdown.
    Use this for: DB pool warm-up, cache connections, background workers.
    """
    logger.info("🚀 TaskFlow API starting up  env=%s", settings.APP_ENV)
    yield
    logger.info("🛑 TaskFlow API shutting down")


# ── Application factory ───────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="1.0.0",
        description=(
            "Multi-user task management SaaS API.\n\n"
            "All protected routes require a Bearer JWT in the `Authorization` header."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Adjust `allow_origins` to the exact frontend domain(s) in production.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Custom middleware (added last = runs first in ASGI chain) ─────────────
    app.add_middleware(RequestLoggingMiddleware)

    # ── Global exception handlers ─────────────────────────────────────────────
    register_exception_handlers(app)

    # ── Routers ───────────────────────────────────────────────────────────────
    API_PREFIX = "/api/v1"
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(tasks.router, prefix=API_PREFIX)
    app.include_router(users.router, prefix=API_PREFIX)

    # ── Health check (no auth — used by load balancers, k8s liveness probes) ──
    @app.get("/health", tags=["Health"], summary="Liveness probe")
    def health_check():
        return {"status": "ok", "version": "1.0.0"}

    return app


app = create_app()
