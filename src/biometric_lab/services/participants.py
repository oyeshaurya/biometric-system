"""Participant registry, consent and deletion (FR-01, FR-02, FR-04, FR-15)."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from biometric_lab.context import AppContext
from biometric_lab.core.privacy.aliases import make_alias
from biometric_lab.db.models import Consent, Participant, Template, Trial, utcnow
from biometric_lab.services.audit import AuditService


class ParticipantError(Exception):
    pass


class NotFound(Exception):
    pass


class ConsentInactive(Exception):
    pass


class ParticipantService:
    def __init__(self, session: Session, ctx: AppContext, audit: AuditService) -> None:
        self.session = session
        self.ctx = ctx
        self.audit = audit

    # --- queries -------------------------------------------------------------
    def get(self, participant_id: int) -> Participant:
        p = self.session.get(Participant, participant_id)
        if p is None:
            raise NotFound(f"participant {participant_id} not found")
        return p

    def get_by_label(self, label: str) -> Participant | None:
        return self.session.execute(
            select(Participant).where(
                or_(Participant.subject_code == label, Participant.alias == label)
            )
        ).scalar_one_or_none()

    def list(self, *, status: str | None = None, q: str | None = None) -> list[Participant]:
        stmt = select(Participant)
        if status:
            stmt = stmt.where(Participant.status == status)
        if q:
            stmt = stmt.where(Participant.subject_code.like(f"%{q}%"))
        return list(self.session.execute(stmt.order_by(Participant.subject_code)).scalars())

    def active_consent(self, participant_id: int) -> Consent | None:
        return self.session.execute(
            select(Consent)
            .where(
                Consent.participant_id == participant_id,
                Consent.accepted.is_(True),
                Consent.withdrawn_at.is_(None),
            )
            .order_by(Consent.id.desc())
            .limit(1)
        ).scalar_one_or_none()

    def require_active_consent(self, participant_id: int) -> None:
        if self.active_consent(participant_id) is None:
            raise ConsentInactive(f"participant {participant_id} has no active consent")

    # --- commands ------------------------------------------------------------
    def create(
        self, subject_code: str, *, display_name: str | None = None, actor_id: int | None = None
    ) -> Participant:
        if self.get_by_label(subject_code) is not None:
            raise ParticipantError(f"subject_code '{subject_code}' already exists")
        alias = make_alias(subject_code, self.ctx.alias_key)
        name_enc = self.ctx.cipher.encrypt_text(display_name) if display_name else None
        p = Participant(
            subject_code=subject_code, alias=alias, status="active", display_name_enc=name_enc
        )
        self.session.add(p)
        self.session.flush()
        self.audit.append(
            "participant.created",
            actor_id=actor_id,
            entity_type="participant",
            entity_id=p.id,
            summary={"subject_code": subject_code, "has_display_name": name_enc is not None},
        )
        return p

    def record_consent(
        self,
        participant_id: int,
        *,
        consent_version: str,
        consent_text_sha256: str,
        purposes: list[str],
        accepted: bool,
        actor_id: int | None = None,
    ) -> Consent:
        p = self.get(participant_id)
        consent = Consent(
            participant_id=p.id,
            consent_version=consent_version,
            consent_text_sha256=consent_text_sha256,
            purposes=purposes,
            accepted=accepted,
            recorded_by=actor_id,
        )
        self.session.add(consent)
        self.session.flush()
        self.audit.append(
            "consent.granted" if accepted else "consent.declined",
            actor_id=actor_id,
            entity_type="participant",
            entity_id=p.id,
            summary={"version": consent_version, "accepted": accepted},
        )
        return consent

    def withdraw_consent(
        self, participant_id: int, *, reason: str, actor_id: int | None = None
    ) -> dict:
        p = self.get(participant_id)
        now = utcnow()
        consents = self.session.execute(
            select(Consent).where(
                Consent.participant_id == p.id, Consent.withdrawn_at.is_(None)
            )
        ).scalars()
        for c in consents:
            c.withdrawn_at = now
        deleted = self._hard_delete_templates(p.id)
        p.status = "withdrawn"
        self.session.flush()
        self.audit.append(
            "consent.withdrawn",
            actor_id=actor_id,
            entity_type="participant",
            entity_id=p.id,
            summary={"reason": reason, "templates_deleted": deleted},
        )
        return {"withdrawn_at": now.isoformat(), "templates_deleted": deleted}

    def _hard_delete_templates(self, participant_id: int) -> int:
        rows = list(
            self.session.execute(
                select(Template).where(Template.participant_id == participant_id)
            ).scalars()
        )
        for t in rows:
            self.session.delete(t)
        return len(rows)

    def delete(self, participant_id: int, *, mode: str, actor_id: int | None = None) -> dict:
        if mode not in {"anonymise", "purge"}:
            raise ParticipantError("mode must be 'anonymise' or 'purge'")
        p = self.get(participant_id)
        self._hard_delete_templates(p.id)
        trials_affected = 0
        if mode == "anonymise":
            trials = self.session.execute(
                select(Trial).where(
                    or_(
                        Trial.probe_participant_id == p.id,
                        Trial.claimed_participant_id == p.id,
                    )
                )
            ).scalars()
            for t in trials:
                if t.probe_label == p.subject_code:
                    t.probe_label = p.alias
                if t.claimed_label == p.subject_code:
                    t.claimed_label = p.alias
                if t.probe_participant_id == p.id:
                    t.probe_participant_id = None
                if t.claimed_participant_id == p.id:
                    t.claimed_participant_id = None
                trials_affected += 1
            p.status = "anonymised"
            p.display_name_enc = None
        else:  # purge
            trials = list(
                self.session.execute(
                    select(Trial).where(
                        or_(
                            Trial.probe_participant_id == p.id,
                            Trial.claimed_participant_id == p.id,
                        )
                    )
                ).scalars()
            )
            for t in trials:
                self.session.delete(t)
                trials_affected += 1
            self.session.delete(p)
        self.session.flush()
        self.audit.append(
            "participant.deleted",
            actor_id=actor_id,
            entity_type="participant",
            entity_id=participant_id,
            summary={"mode": mode, "trials_affected": trials_affected},
        )
        return {"mode": mode, "trials_affected": trials_affected}
