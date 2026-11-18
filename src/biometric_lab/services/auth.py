"""Operator accounts and authentication (FR-18, SYSTEM_DESIGN.md section 5.6).

Passwords are argon2id-hashed. Login is rate-limited (5 attempts per minute per client
key). Session transport (signed cookie, CSRF) lives in the API layer.
"""

from __future__ import annotations

import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from biometric_lab.core.security.passwords import hash_password, verify_password
from biometric_lab.db.models import Operator
from biometric_lab.services.audit import AuditService

_RATE_WINDOW_SECONDS = 60
_RATE_MAX_ATTEMPTS = 5
# Module-level so the limit holds across requests within one process.
_attempts: dict[str, list[float]] = {}


class AuthError(Exception):
    pass


class RateLimited(Exception):
    pass


class AdminProtected(Exception):
    """Raised when an action would remove the last enabled admin."""


class AuthService:
    def __init__(self, session: Session, audit: AuditService) -> None:
        self.session = session
        self.audit = audit

    # --- login ---------------------------------------------------------------
    def _check_rate(self, client_key: str) -> None:
        now = time.monotonic()
        window = [t for t in _attempts.get(client_key, []) if now - t < _RATE_WINDOW_SECONDS]
        _attempts[client_key] = window
        if len(window) >= _RATE_MAX_ATTEMPTS:
            raise RateLimited("too many login attempts; wait a minute")

    def _record_fail(self, client_key: str) -> None:
        _attempts.setdefault(client_key, []).append(time.monotonic())

    def authenticate(self, username: str, password: str, *, client_key: str = "local") -> Operator:
        self._check_rate(client_key)
        op = self.session.execute(
            select(Operator).where(Operator.username == username, Operator.disabled.is_(False))
        ).scalar_one_or_none()
        if op is None or not verify_password(op.password_hash, password):
            self._record_fail(client_key)
            raise AuthError("invalid username or password")
        _attempts.pop(client_key, None)
        self.audit.append("auth.login", actor_id=op.id, entity_type="operator", entity_id=op.id)
        return op

    def logout(self, operator_id: int) -> None:
        self.audit.append(
            "auth.logout", actor_id=operator_id, entity_type="operator", entity_id=operator_id
        )

    # --- account management --------------------------------------------------
    def get(self, operator_id: int) -> Operator | None:
        return self.session.get(Operator, operator_id)

    def list_operators(self) -> list[Operator]:
        return list(self.session.execute(select(Operator).order_by(Operator.id)).scalars())

    def _enabled_admins(self) -> int:
        return len(
            list(
                self.session.execute(
                    select(Operator).where(
                        Operator.role == "admin", Operator.disabled.is_(False)
                    )
                ).scalars()
            )
        )

    def create_operator(
        self, username: str, password: str, *, role: str = "operator", actor_id: int | None = None
    ) -> Operator:
        if role not in {"operator", "admin"}:
            raise AuthError("role must be 'operator' or 'admin'")
        if self.session.execute(
            select(Operator).where(Operator.username == username)
        ).scalar_one_or_none():
            raise AuthError(f"username '{username}' already exists")
        op = Operator(username=username, password_hash=hash_password(password), role=role)
        self.session.add(op)
        self.session.flush()
        self.audit.append(
            "operator.created",
            actor_id=actor_id,
            entity_type="operator",
            entity_id=op.id,
            summary={"username": username, "role": role},
        )
        return op

    def set_disabled(
        self, operator_id: int, disabled: bool, *, actor_id: int | None = None
    ) -> Operator:
        op = self.session.get(Operator, operator_id)
        if op is None:
            raise AuthError("operator not found")
        if disabled and op.role == "admin" and not op.disabled and self._enabled_admins() <= 1:
            raise AdminProtected("cannot disable the last enabled admin")
        op.disabled = disabled
        self.session.flush()
        self.audit.append(
            "operator.disabled" if disabled else "operator.enabled",
            actor_id=actor_id,
            entity_type="operator",
            entity_id=operator_id,
        )
        return op

    def change_password(
        self, operator_id: int, new_password: str, *, actor_id: int | None = None
    ) -> None:
        op = self.session.get(Operator, operator_id)
        if op is None:
            raise AuthError("operator not found")
        op.password_hash = hash_password(new_password)
        self.session.flush()
        self.audit.append(
            "operator.password_changed",
            actor_id=actor_id,
            entity_type="operator",
            entity_id=operator_id,
        )
