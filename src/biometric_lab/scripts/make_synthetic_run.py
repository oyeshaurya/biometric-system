"""Populate a synthetic run for UI development (no webcam, fake engine).

Usage: python -m biometric_lab.scripts.make_synthetic_run [--subjects 10] [--name demo]
"""

from __future__ import annotations

import argparse

from biometric_lab.config import get_settings
from biometric_lab.context import build_context
from biometric_lab.core.face.fake_engine import FakeFaceEngine, encode_scene
from biometric_lab.core.security.crypto import TemplateCipher, generate_key
from biometric_lab.db.init import create_schema
from biometric_lab.db.session import get_engine, session_scope
from biometric_lab.services.audit import AuditService
from biometric_lab.services.enrolment import EnrolmentService
from biometric_lab.services.participants import ParticipantService
from biometric_lab.services.settings import SettingsService
from biometric_lab.services.trials import TrialService
from biometric_lab.services.verification import VerificationService

SHA256 = "a" * 64


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a synthetic run with fake data.")
    parser.add_argument("--subjects", type=int, default=10)
    parser.add_argument("--name", default="demo")
    args = parser.parse_args(argv)

    settings = get_settings()
    create_schema(get_engine(settings))
    # Use the fake engine with an ephemeral in-memory key so no real key file is needed.
    ctx = build_context(
        settings, engine=FakeFaceEngine(), cipher=TemplateCipher.from_key_bytes(generate_key())
    )

    with session_scope() as session:
        audit = AuditService(session)
        settings_svc = SettingsService(session, audit)
        settings_svc.seed_defaults(settings)
        participants = ParticipantService(session, ctx, audit)
        enrol = EnrolmentService(session, ctx, audit, settings_svc)
        verification = VerificationService(session, ctx, settings_svc)
        trials = TrialService(session, ctx, participants, verification, audit, settings_svc)

        codes = []
        for i in range(1, args.subjects + 1):
            code = f"S{i:03d}"
            p = participants.create(code)
            participants.record_consent(
                p.id,
                consent_version="v1.0",
                consent_text_sha256=SHA256,
                purposes=["research_face_verification_eval"],
                accepted=True,
            )
            frames = [encode_scene(i, noise=n) for n in range(5)]
            enrol.enrol(p, frames, replace=False)
            codes.append((code, i))

        run = trials.create_run(args.name, description="synthetic demo run")
        for code, ident in codes:
            for noise in range(20, 25):  # genuine
                trials.record(
                    run.id,
                    probe_label=code,
                    claimed_label=code,
                    image=encode_scene(ident, noise=noise),
                    condition_tags=["lighting:normal"],
                )
            other = codes[(ident) % len(codes)]
            if other[0] != code:  # impostor
                for noise in range(30, 35):
                    trials.record(
                        run.id,
                        probe_label=other[0],
                        claimed_label=code,
                        image=encode_scene(other[1], noise=noise),
                        condition_tags=["lighting:dim"],
                    )
        print(f"created run '{run.name}' (id={run.id}) with {args.subjects} subjects")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
