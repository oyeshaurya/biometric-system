"""Schema creation shared by Alembic and tests.

``create_schema`` creates all tables and, optionally, the append-only triggers on
``audit_events``. Tests create the schema without triggers so they can simulate tampering.
"""

from __future__ import annotations

from sqlalchemy.engine import Engine

from biometric_lab.db.base import Base
from biometric_lab.db import models  # noqa: F401 - register models on Base.metadata

_AUDIT_TRIGGERS = [
    (
        "CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_events "
        "BEGIN SELECT RAISE(ABORT, 'audit_events is append-only'); END;"
    ),
    (
        "CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_events "
        "BEGIN SELECT RAISE(ABORT, 'audit_events is append-only'); END;"
    ),
]


def create_schema(engine: Engine, *, with_triggers: bool = True) -> None:
    Base.metadata.create_all(engine)
    if with_triggers and engine.dialect.name == "sqlite":
        from sqlalchemy import text

        with engine.begin() as conn:
            for stmt in _AUDIT_TRIGGERS:
                conn.execute(text(stmt))
