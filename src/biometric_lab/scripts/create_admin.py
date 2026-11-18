"""Create the first admin operator (FR-18).

Usage:
    python -m biometric_lab.scripts.create_admin --username admin [--password ...]

If no password is given, a strong one is generated and printed once.
"""

from __future__ import annotations

import argparse
import secrets

from biometric_lab.config import get_settings
from biometric_lab.db.init import create_schema
from biometric_lab.db.session import get_engine, session_scope
from biometric_lab.services.audit import AuditService
from biometric_lab.services.auth import AuthError, AuthService
from biometric_lab.services.settings import SettingsService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create the first admin operator.")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", default=None)
    parser.add_argument("--role", default="admin", choices=["admin", "operator"])
    args = parser.parse_args(argv)

    settings = get_settings()
    create_schema(get_engine(settings))  # idempotent

    password = args.password or secrets.token_urlsafe(12)
    with session_scope() as session:
        audit = AuditService(session)
        SettingsService(session, audit).seed_defaults(settings)
        try:
            op = AuthService(session, audit).create_operator(
                args.username, password, role=args.role
            )
        except AuthError as exc:
            print(f"error: {exc}")
            return 1
        print(f"created {op.role} '{op.username}' (id={op.id})")

    if not args.password:
        print(f"generated password: {password}")
        print("Store it now; it is not shown again.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
