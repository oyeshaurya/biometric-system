"""Login and logout (FR-18)."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from biometric_lab.api.deps import (
    COOKIE_NAME,
    SESSION_MAX_AGE,
    current_operator,
    get_db,
    session_serializer,
)
from biometric_lab.core.security.csrf import issue_token
from biometric_lab.db.models import Operator
from biometric_lab.schemas import LoginRequest
from biometric_lab.services.audit import AuditService
from biometric_lab.services.auth import AuthService

router = APIRouter(tags=["auth"])


@router.post("/auth/login")
def login(
    body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)
) -> dict:
    client_key = request.client.host if request.client else "local"
    auth = AuthService(db, AuditService(db))
    op = auth.authenticate(body.username, body.password, client_key=client_key)

    secret = request.app.state.context.settings.session_secret
    sid = secrets.token_urlsafe(16)
    token = session_serializer(secret).dumps({"operator_id": op.id, "sid": sid})
    # Local-only app served over http on loopback: a Secure cookie would never be sent.
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="strict",
        secure=False,
    )
    return {
        "user": {"id": op.id, "username": op.username, "role": op.role},
        "csrf_token": issue_token(secret, sid),
    }


@router.post("/auth/logout")
def logout(
    response: Response, op: Operator = Depends(current_operator), db: Session = Depends(get_db)
) -> Response:
    AuthService(db, AuditService(db)).logout(op.id)
    response.delete_cookie(COOKIE_NAME)
    response.status_code = 204
    return response
