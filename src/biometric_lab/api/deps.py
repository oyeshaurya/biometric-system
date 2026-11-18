"""Request dependencies: session, context, current operator, CSRF and role checks."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, Request
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from biometric_lab.context import AppContext
from biometric_lab.db.models import Operator
from biometric_lab.db.session import get_session_factory

COOKIE_NAME = "bl_session"
_SESSION_SALT = "biometric-lab-session"
SESSION_MAX_AGE = 1800  # 30-minute idle window


def session_serializer(secret: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret, salt=_SESSION_SALT)


def get_context(request: Request) -> AppContext:
    return request.app.state.context


def get_db() -> Iterator[Session]:
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _load_session(request: Request) -> dict | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    secret = request.app.state.context.settings.session_secret
    try:
        data = session_serializer(secret).loads(token, max_age=SESSION_MAX_AGE)
    except BadSignature:
        return None
    return data if isinstance(data, dict) else None


def current_operator(
    request: Request, db: Session = Depends(get_db)
) -> Operator:
    from biometric_lab.api.errors import ProblemError

    data = _load_session(request)
    if not data or "operator_id" not in data:
        raise ProblemError(401, "NOT_AUTHENTICATED", "login required")
    op = db.get(Operator, data["operator_id"])
    if op is None or op.disabled:
        raise ProblemError(401, "NOT_AUTHENTICATED", "session is no longer valid")
    request.state.session_id = data.get("sid", "")
    request.state.operator = op
    return op


def require_admin(op: Operator = Depends(current_operator)) -> Operator:
    from biometric_lab.api.errors import ProblemError

    if op.role != "admin":
        raise ProblemError(403, "FORBIDDEN", "admin role required")
    return op


def verify_csrf(request: Request, op: Operator = Depends(current_operator)) -> None:
    from biometric_lab.api.errors import ProblemError
    from biometric_lab.core.security.csrf import verify_token

    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    token = request.headers.get("X-CSRF-Token", "")
    sid = getattr(request.state, "session_id", "")
    secret = request.app.state.context.settings.session_secret
    if not token or not sid or not verify_token(secret, token, sid):
        raise ProblemError(403, "CSRF_MISSING", "missing or invalid CSRF token")
