"""Face engine factory (AD-7). Selects the engine by name, lazily importing heavy ones."""

from __future__ import annotations

from biometric_lab.core.face.base import FaceEngine, FaceEngineError
from biometric_lab.core.face.fake_engine import FakeFaceEngine


def build_engine(name: str) -> FaceEngine:
    """Return an engine instance for ``name`` ("fake" | "insightface" | "yunet_sface")."""
    key = name.lower().strip()
    if key == "fake":
        return FakeFaceEngine()
    if key == "insightface":
        from biometric_lab.core.face.insightface_engine import InsightFaceEngine

        return InsightFaceEngine()
    if key == "yunet_sface":
        from biometric_lab.core.face.insightface_engine import YuNetSFaceEngine

        return YuNetSFaceEngine()
    raise FaceEngineError(f"unknown engine '{name}'")
