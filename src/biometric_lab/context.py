"""Application context: the shared engine, matcher and cipher (ARCHITECTURE.md section 4).

Built once at startup and injected into services. Tests build a context directly with the
fake engine and an in-memory key.
"""

from __future__ import annotations

from dataclasses import dataclass

from biometric_lab.config import Settings, get_settings
from biometric_lab.core.face.base import FaceEngine
from biometric_lab.core.face.registry import build_engine
from biometric_lab.core.liveness.base import LivenessChecker
from biometric_lab.core.liveness.none import NoLiveness
from biometric_lab.core.matching.cosine import CosineMatcher
from biometric_lab.core.security.crypto import TemplateCipher, generate_key


@dataclass
class AppContext:
    settings: Settings
    engine: FaceEngine
    matcher: CosineMatcher
    cipher: TemplateCipher
    liveness: LivenessChecker

    @property
    def alias_key(self) -> bytes:
        return self.settings.session_secret.encode("utf-8")


def build_context(
    settings: Settings | None = None,
    *,
    engine: FaceEngine | None = None,
    cipher: TemplateCipher | None = None,
    liveness: LivenessChecker | None = None,
) -> AppContext:
    settings = settings or get_settings()
    engine = engine or build_engine(settings.engine)
    if cipher is None:
        cipher = TemplateCipher.from_key_file(settings.key_file)
    return AppContext(
        settings=settings,
        engine=engine,
        matcher=CosineMatcher(),
        cipher=cipher,
        liveness=liveness or NoLiveness(),
    )


def build_test_context(**overrides: object) -> AppContext:
    """A context with the fake engine and an ephemeral key, for tests."""
    from biometric_lab.core.face.fake_engine import FakeFaceEngine

    settings = overrides.get("settings") or get_settings()
    return AppContext(
        settings=settings,  # type: ignore[arg-type]
        engine=overrides.get("engine") or FakeFaceEngine(),  # type: ignore[arg-type]
        matcher=CosineMatcher(),
        cipher=overrides.get("cipher") or TemplateCipher.from_key_bytes(generate_key()),  # type: ignore[arg-type]
        liveness=overrides.get("liveness") or NoLiveness(),  # type: ignore[arg-type]
    )
