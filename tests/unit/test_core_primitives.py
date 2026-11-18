"""Unit tests for core primitives: crypto, quality, matching, redaction, aliases,
fake engine and the audit hash chain (SYSTEM_DESIGN.md section 9.1)."""

from __future__ import annotations

import numpy as np
import pytest

from biometric_lab.core.face.base import FaceDetection
from biometric_lab.core.face.fake_engine import FakeFaceEngine, blank_image, encode_scene
from biometric_lab.core.face.quality import check_quality
from biometric_lab.core.matching.base import MatchError
from biometric_lab.core.matching.cosine import CosineMatcher, cosine_similarity
from biometric_lab.core.privacy.aliases import make_alias
from biometric_lab.core.privacy.redaction import scrub_mapping, scrub_text
from biometric_lab.core.security.crypto import CryptoError, TemplateCipher, generate_key

QP = {"min_det_score": 0.6, "min_face_px": 80, "max_yaw_deg": 30.0}


# ---- crypto -----------------------------------------------------------------
def test_crypto_vector_round_trip():
    cipher = TemplateCipher.from_key_bytes(generate_key())
    vec = np.array([0.1, -0.2, 0.3], dtype=np.float32)
    back = cipher.decrypt_vector(cipher.encrypt_vector(vec))
    assert np.allclose(vec, back)


def test_crypto_text_round_trip():
    cipher = TemplateCipher.from_key_bytes(generate_key())
    assert cipher.decrypt_text(cipher.encrypt_text("P001")) == "P001"


def test_crypto_wrong_key_raises():
    c1 = TemplateCipher.from_key_bytes(generate_key())
    c2 = TemplateCipher.from_key_bytes(generate_key())
    token = c1.encrypt_vector(np.ones(4, dtype=np.float32))
    with pytest.raises(CryptoError):
        c2.decrypt_vector(token)


def test_crypto_tamper_raises():
    cipher = TemplateCipher.from_key_bytes(generate_key())
    token = bytearray(cipher.encrypt_vector(np.ones(4, dtype=np.float32)))
    token[-1] ^= 0x01
    with pytest.raises(CryptoError):
        cipher.decrypt_vector(bytes(token))


def test_crypto_key_rotation():
    k1, k2 = generate_key(), generate_key()
    old = TemplateCipher.from_key_bytes(k1)
    token = old.encrypt_vector(np.ones(4, dtype=np.float32))
    rotated = TemplateCipher.from_key_bytes(k2, k1)  # new key first, old still decrypts
    assert np.allclose(rotated.decrypt_vector(token), np.ones(4))


# ---- quality gate boundaries ------------------------------------------------
def _det(det=0.99, px=200, yaw=0.0):
    return FaceDetection(bbox=(0, 0, px, px), det_score=det, yaw_deg=yaw, embedding=np.ones(4))


def test_quality_ok():
    assert check_quality([_det()], **QP).ok


def test_quality_no_face():
    assert check_quality([], **QP).reason == "NO_FACE"


def test_quality_multiple_faces():
    assert check_quality([_det(), _det()], **QP).reason == "MULTIPLE_FACES"


def test_quality_det_score_boundary():
    assert check_quality([_det(det=0.60)], **QP).ok
    assert check_quality([_det(det=0.59)], **QP).reason == "LOW_DET_SCORE"


def test_quality_size_boundary():
    assert check_quality([_det(px=80)], **QP).ok
    assert check_quality([_det(px=79)], **QP).reason == "FACE_TOO_SMALL"


def test_quality_yaw_boundary():
    assert check_quality([_det(yaw=30.0)], **QP).ok
    assert check_quality([_det(yaw=30.1)], **QP).reason == "EXCESSIVE_YAW"


# ---- cosine matcher ---------------------------------------------------------
def test_cosine_values():
    assert cosine_similarity([1, 0], [1, 0]) == pytest.approx(1.0)
    assert cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)
    assert cosine_similarity([1, 0], [-1, 0]) == pytest.approx(-1.0)


def test_cosine_zero_raises():
    with pytest.raises(MatchError):
        cosine_similarity([0, 0], [1, 0])


def test_matcher_max_fusion_and_empty():
    m = CosineMatcher()
    probe = np.array([1.0, 0.0])
    templates = [np.array([0.0, 1.0]), np.array([1.0, 0.0])]
    assert m.score(probe, templates) == pytest.approx(1.0)
    with pytest.raises(MatchError):
        m.score(probe, [])


# ---- redaction --------------------------------------------------------------
def test_redaction_scrubs_base64_and_keys():
    long_b64 = "A" * 300
    assert "[REDACTED]" in scrub_text(f"payload {long_b64}")
    cleaned = scrub_mapping({"image_b64": long_b64, "score": 0.5, "nested": {"vector": [1, 2]}})
    assert cleaned["image_b64"] == "[REDACTED]"
    assert cleaned["score"] == 0.5
    assert cleaned["nested"]["vector"] == "[REDACTED]"


# ---- aliases ----------------------------------------------------------------
def test_alias_is_stable_and_distinct():
    key = b"secret-key"
    assert make_alias("P001", key) == make_alias("P001", key)
    assert make_alias("P001", key) != make_alias("P002", key)
    assert make_alias("P001", key).startswith("A")


# ---- fake engine ------------------------------------------------------------
def test_fake_engine_determinism_and_separation():
    eng = FakeFaceEngine()
    a = eng.analyse(encode_scene(1, noise=0))[0].embedding
    b = eng.analyse(encode_scene(1, noise=0))[0].embedding
    assert np.allclose(a, b)  # deterministic
    genuine = cosine_similarity(a, eng.analyse(encode_scene(1, noise=5))[0].embedding)
    impostor = cosine_similarity(a, eng.analyse(encode_scene(99, noise=5))[0].embedding)
    assert genuine > 0.6
    assert impostor < 0.3


def test_fake_engine_blank_and_multiple():
    eng = FakeFaceEngine()
    assert eng.analyse(blank_image()) == []
    assert len(eng.analyse(encode_scene(1, faces=2))) == 2


def test_fake_engine_yaw_passthrough():
    eng = FakeFaceEngine()
    assert eng.analyse(encode_scene(1, yaw_deg=45.0))[0].yaw_deg == pytest.approx(45.0)


# ---- audit chain ------------------------------------------------------------
@pytest.fixture
def audit_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from biometric_lab.db.init import create_schema

    engine = create_engine("sqlite:///:memory:")
    create_schema(engine, with_triggers=False)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def test_audit_chain_valid_then_broken(audit_session):
    from sqlalchemy import update

    from biometric_lab.db.models import AuditEvent
    from biometric_lab.services.audit import AuditService

    audit = AuditService(audit_session)
    audit.append("a.one", summary={"n": 1})
    audit.append("a.two", summary={"n": 2})
    audit_session.commit()
    assert audit.verify().valid is True

    first = audit_session.query(AuditEvent).order_by(AuditEvent.id).first()
    audit_session.execute(
        update(AuditEvent).where(AuditEvent.id == first.id).values(summary_json={"n": 999})
    )
    audit_session.commit()
    status = audit.verify()
    assert status.valid is False
    assert status.first_broken_id == first.id
