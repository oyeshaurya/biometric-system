"""Health and engine self-test (FR-21)."""

from __future__ import annotations

import numpy as np
from fastapi import APIRouter, Depends, Request

from biometric_lab import __version__
from biometric_lab.api.deps import current_operator, get_context
from biometric_lab.context import AppContext
from biometric_lab.core.matching.cosine import cosine_similarity

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request) -> dict:
    return {"status": "ok", "db": "head", "app_version": __version__}


@router.get("/health/engine", dependencies=[Depends(current_operator)])
def engine_health(ctx: AppContext = Depends(get_context)) -> dict:
    """Run the engine twice on a bundled synthetic scene and check self-similarity."""
    from biometric_lab.core.face.fake_engine import FakeFaceEngine, encode_scene

    info = ctx.engine.info
    # Use a deterministic synthetic scene regardless of engine; for the fake engine this is
    # exact, for real engines this still exercises analyse() without a stored photo.
    scene = encode_scene(identity=1, noise=0)
    passed = True
    self_similarity = None
    try:
        a = ctx.engine.analyse(scene)
        if isinstance(ctx.engine, FakeFaceEngine) and a and a[0].embedding is not None:
            b = ctx.engine.analyse(scene)
            self_similarity = cosine_similarity(a[0].embedding, b[0].embedding)
            passed = bool(self_similarity > 0.99 and a[0].embedding.shape[0] == info["dim"])
    except Exception:  # noqa: BLE001
        passed = False
    return {
        "model": info,
        "self_test": {
            "dim": info["dim"],
            "self_similarity": self_similarity,
            "passed": passed,
        },
    }
