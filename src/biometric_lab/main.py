"""FastAPI application factory (ARCHITECTURE.md section 3, NFR-01)."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.staticfiles import StaticFiles

from biometric_lab.api.errors import register_error_handlers
from biometric_lab.api.routes import (
    admin,
    analysis,
    auth,
    export,
    health,
    participants,
    runs,
    verify,
)
from biometric_lab.config import Settings, get_settings
from biometric_lab.context import AppContext, build_context
from biometric_lab.core.privacy.redaction import RedactionFilter
from biometric_lab.db.session import session_scope
from biometric_lab.services.audit import AuditService
from biometric_lab.services.settings import SettingsService

logger = logging.getLogger("biometric_lab")

_CSP = (
    "default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; "
    "style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; "
    "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
)


def _configure_logging() -> None:
    root = logging.getLogger()
    redaction = RedactionFilter()
    for handler in root.handlers:
        handler.addFilter(redaction)
    logging.getLogger("uvicorn.access").addFilter(redaction)


def _seed(context: AppContext) -> None:
    with session_scope() as session:
        settings_svc = SettingsService(session, AuditService(session))
        settings_svc.seed_defaults(context.settings)


def create_app(context: AppContext | None = None, settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Face-Recognition Performance Lab",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.state.context = context
    register_error_handlers(app)

    @app.middleware("http")
    async def _security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", _CSP)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(self), microphone=()")
        return response

    @app.on_event("startup")
    def _startup() -> None:
        _configure_logging()
        if app.state.context is None:
            app.state.context = build_context(settings)
        if not app.state.context.settings.is_loopback:
            logger.warning("server is bound to a non-loopback host (%s)", settings.host)
        try:
            _seed(app.state.context)
        except Exception:  # noqa: BLE001 - app can still serve if DB not migrated yet
            logger.warning("could not seed settings; run 'alembic upgrade head' first")

    api = APIRouter(prefix="/api")
    for module in (health, auth, participants, verify, runs, analysis, export, admin):
        api.include_router(module.router)
    app.include_router(api)

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app


app = create_app()
