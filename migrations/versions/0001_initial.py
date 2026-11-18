"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-18
"""

from __future__ import annotations

from alembic import op

from biometric_lab.db import models  # noqa: F401 - register models on metadata
from biometric_lab.db.base import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

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


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind)
    if bind.dialect.name == "sqlite":
        for stmt in _AUDIT_TRIGGERS:
            op.execute(stmt)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS audit_no_update")
        op.execute("DROP TRIGGER IF EXISTS audit_no_delete")
    Base.metadata.drop_all(bind)
