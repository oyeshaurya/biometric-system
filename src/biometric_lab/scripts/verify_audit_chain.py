"""Verify the audit hash chain (FR-17)."""

from __future__ import annotations

from biometric_lab.config import get_settings
from biometric_lab.db.session import get_engine, session_scope
from biometric_lab.services.audit import AuditService


def main() -> int:
    get_engine(get_settings())
    with session_scope() as session:
        status = AuditService(session).verify()
    print(f"events: {status.events}")
    if status.valid:
        print("chain OK")
        return 0
    print(f"CHAIN BROKEN at event id {status.first_broken_id}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
