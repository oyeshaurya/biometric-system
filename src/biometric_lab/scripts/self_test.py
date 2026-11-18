"""Engine self-test (FR-21, M0 exit criterion).

Runs the configured engine on a synthetic scene and reports model info and self-similarity.
"""

from __future__ import annotations

from biometric_lab.config import get_settings
from biometric_lab.core.face.fake_engine import encode_scene
from biometric_lab.core.face.registry import build_engine
from biometric_lab.core.matching.cosine import cosine_similarity


def main() -> int:
    settings = get_settings()
    engine = build_engine(settings.engine)
    print(f"engine: {settings.engine}")
    print(f"model info: {engine.info}")

    scene = encode_scene(identity=1, noise=0)
    a = engine.analyse(scene)
    b = engine.analyse(scene)
    if not a or a[0].embedding is None:
        print("no face detected on the synthetic scene (expected only for 'fake' engine)")
        return 0
    sim = cosine_similarity(a[0].embedding, b[0].embedding)
    print(f"embedding dim: {a[0].embedding.shape[0]}")
    print(f"self-similarity: {sim:.4f}")
    print("PASS" if sim > 0.99 else "WARN: self-similarity below 0.99")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
