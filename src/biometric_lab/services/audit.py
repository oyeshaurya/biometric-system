"""Append-only, hash-chained audit log (FR-17, SYSTEM_DESIGN.md section 1.9).

Each event's ``row_hash`` is SHA-256 over a canonical JSON of its content fields plus the
previous event's ``row_hash``. Editing or reordering any event breaks the chain, which
:meth:`AuditService.verify` detects. Summaries are scrubbed of biometric content.

Note: the timestamp is stored for information but excluded from the hash, because SQLite
does not preserve timezone/precision reliably on round-trip. Integrity covers actor,
action, entity, summary, request id and chain order.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from biometric_lab.core.privacy.redaction import scrub_mapping
from biometric_lab.db.models import AuditEvent, utcnow


def _canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _row_payload(
    *,
    action: str,
    actor_id: int | None,
    entity_type: str | None,
    entity_id: str | None,
    summary: object,
    request_id: str | None,
    prev_hash: str | None,
) -> dict:
    return {
        "action": action,
        "actor_id": actor_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "summary": summary,
        "request_id": request_id,
        "prev_hash": prev_hash,
    }


@dataclass(frozen=True)
class ChainStatus:
    valid: bool
    events: int
    first_broken_id: int | None


class AuditService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _latest_hash(self) -> str | None:
        row = self.session.execute(
            select(AuditEvent).order_by(AuditEvent.id.desc()).limit(1)
        ).scalar_one_or_none()
        return row.row_hash if row else None

    def append(
        self,
        action: str,
        *,
        actor_id: int | None = None,
        entity_type: str | None = None,
        entity_id: str | int | None = None,
        summary: dict | None = None,
        request_id: str | None = None,
    ) -> AuditEvent:
        clean_summary = scrub_mapping(summary or {})
        prev_hash = self._latest_hash()
        payload = _row_payload(
            action=action,
            actor_id=actor_id,
            entity_type=entity_type,
            entity_id=None if entity_id is None else str(entity_id),
            summary=clean_summary,
            request_id=request_id,
            prev_hash=prev_hash,
        )
        row_hash = hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()
        event = AuditEvent(
            ts=utcnow(),
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=None if entity_id is None else str(entity_id),
            summary_json=clean_summary,
            request_id=request_id,
            prev_hash=prev_hash,
            row_hash=row_hash,
        )
        self.session.add(event)
        self.session.flush()
        return event

    def verify(self) -> ChainStatus:
        events = list(
            self.session.execute(select(AuditEvent).order_by(AuditEvent.id)).scalars()
        )
        prev_hash: str | None = None
        for event in events:
            payload = _row_payload(
                action=event.action,
                actor_id=event.actor_id,
                entity_type=event.entity_type,
                entity_id=event.entity_id,
                summary=event.summary_json,
                request_id=event.request_id,
                prev_hash=prev_hash,
            )
            expected = hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()
            if event.prev_hash != prev_hash or event.row_hash != expected:
                return ChainStatus(False, len(events), event.id)
            prev_hash = event.row_hash
        return ChainStatus(True, len(events), None)
