"""
FastAPI application.

Service-layer responsibilities (docs/fastapi.md section 1), and only these:
  1. Public read APIs with different caching characteristics than HTML.
  2. Availability computation as a service.
  3. The image-derivative endpoint.
  4. A typed, versioned, documented contract.

It does NOT render HTML, does NOT own the schema, and does NOT duplicate Django's write
paths — booking and contact delegate to the same service functions the HTML forms use.
"""

from __future__ import annotations

import logging
import os

import django
from django.apps import apps as django_apps
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api_service.db.session import check_connection
from api_service.routers import booking as booking_router
from api_service.routers import content as content_router
from api_service.routers import search as search_router
from api_service.routers import site as site_router
from api_service.settings import get_settings

logger = logging.getLogger("apps")

API_VERSION = "1.0.0"


def _setup_django() -> None:
    """
    Initialise Django before any ORM access.

    The API and the site share one schema and one set of business rules, so the API calls
    Django's ORM and service functions rather than maintaining a parallel implementation.

    The default settings module is ``config.settings.prod``: this module is imported by
    uvicorn in production, and a production process that boots with DEBUG=True because an
    environment variable was forgotten is precisely the failure this avoids. ``prod.py``
    refuses to start on a missing secret key or empty ALLOWED_HOSTS. Development sets
    DJANGO_SETTINGS_MODULE=config.settings.dev explicitly (see README).
    """
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")
    # `import django` alone does not expose the app registry; `django.apps` must be
    # imported explicitly before `apps.ready` can be consulted.
    if not django_apps.ready:
        django.setup()


def create_app() -> FastAPI:
    settings = get_settings()
    _setup_django()

    app = FastAPI(
        title="TattoWeb API",
        version=API_VERSION,
        description=(
            "Public JSON API for the TattoWeb portfolio, gallery, shop, booking and "
            "availability services. This is the service layer only: the site itself is "
            "rendered by Django, and the artist's CMS lives at /admin/."
        ),
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
        openapi_url="/api/v1/openapi.json",
    )

    # CORS: an explicit allow-list, never a wildcard. The frontend is same-origin in
    # production (one reverse proxy fronts both stacks), so this matters only in dev.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins or [],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        """
        Never leak a traceback to a client.

        The detail is logged; the response is a generic 500 with a stable shape so a
        consumer can handle it programmatically.
        """
        logger.exception("unhandled API error on %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "code": "internal_error"},
        )

    # --- Routes -----------------------------------------------------------------
    app.include_router(content_router.router, prefix="/api/v1", tags=["content"])
    app.include_router(site_router.router, prefix="/api/v1", tags=["site"])
    app.include_router(booking_router.router, prefix="/api/v1", tags=["booking"])
    app.include_router(search_router.router, prefix="/api/v1", tags=["search"])

    @app.get("/api/v1/healthz", tags=["meta"], summary="Liveness probe")
    def healthz():
        db_ok = check_connection()
        return {
            "status": "ok" if db_ok else "degraded",
            "database": "ok" if db_ok else "error",
            "version": API_VERSION,
        }

    @app.get("/api/v1/meta", tags=["meta"], summary="API metadata")
    def meta():
        return {
            "version": API_VERSION,
            "schema_contract": "django-owned",
            "docs": "/api/v1/docs",
        }

    return app


app = create_app()
