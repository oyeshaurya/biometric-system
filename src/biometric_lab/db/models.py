"""ORM models (SYSTEM_DESIGN.md section 1).

Notes:
- Timestamps are timezone-aware UTC.
- ``templates.vector_enc`` and ``participants.display_name_enc`` hold Fernet ciphertext.
- ``audit_events`` is append-only; UPDATE/DELETE are blocked by triggers created in the
  initial migration and re-asserted at startup.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from biometric_lab.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Operator(Base):
    __tablename__ = "operators"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="operator")
    disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    display_name_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    alias: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    consents: Mapped[list[Consent]] = relationship(back_populates="participant")
    templates: Mapped[list[Template]] = relationship(back_populates="participant")


class Consent(Base):
    __tablename__ = "consents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_id: Mapped[int] = mapped_column(
        ForeignKey("participants.id"), nullable=False, index=True
    )
    consent_version: Mapped[str] = mapped_column(String(32), nullable=False)
    consent_text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    purposes: Mapped[list] = mapped_column(JSON, nullable=False)
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recorded_by: Mapped[int | None] = mapped_column(ForeignKey("operators.id"), nullable=True)

    participant: Mapped[Participant] = relationship(back_populates="consents")


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_id: Mapped[int] = mapped_column(
        ForeignKey("participants.id"), nullable=False, index=True
    )
    enrolment_batch_id: Mapped[str] = mapped_column(String(36), nullable=False)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    dim: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    vector_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    quality_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    participant: Mapped[Participant] = relationship(back_populates="templates")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    threshold_snapshot: Mapped[float] = mapped_column(Float, nullable=False)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    trials: Mapped[list[Trial]] = relationship(back_populates="run")


class Trial(Base):
    __tablename__ = "trials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    probe_label: Mapped[str] = mapped_column(String(64), nullable=False)
    claimed_label: Mapped[str] = mapped_column(String(64), nullable=False)
    probe_participant_id: Mapped[int | None] = mapped_column(
        ForeignKey("participants.id"), nullable=True, index=True
    )
    claimed_participant_id: Mapped[int | None] = mapped_column(
        ForeignKey("participants.id"), nullable=True, index=True
    )
    ground_truth: Mapped[str] = mapped_column(String(10), nullable=False)
    outcome: Mapped[str] = mapped_column(String(8), nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    fta_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    template_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    condition_tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    liveness_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    liveness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    liveness_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    run: Mapped[Run] = relationship(back_populates="trials")


class DebugFrame(Base):
    __tablename__ = "debug_frames"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trial_id: Mapped[int] = mapped_column(ForeignKey("trials.id"), nullable=False, index=True)
    path: Mapped[str] = mapped_column(String(260), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value_json: Mapped[object] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="initial")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("operators.id"), nullable=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (UniqueConstraint("id", name="uq_audit_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("operators.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(48), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    summary_json: Mapped[object] = mapped_column(JSON, nullable=False, default=dict)
    request_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    row_hash: Mapped[str] = mapped_column(String(64), nullable=False)
