"""Helpers to build fake-engine frames as base64 payloads for API tests."""

from __future__ import annotations

import base64

from biometric_lab.core.face.fake_engine import blank_image, encode_scene
from biometric_lab.imaging import encode_npy


def frame_b64(identity: int, *, noise: int = 0, **scene_kwargs) -> str:
    img = encode_scene(identity, noise=noise, **scene_kwargs)
    return base64.b64encode(encode_npy(img)).decode("ascii")


def blank_frame_b64() -> str:
    return base64.b64encode(encode_npy(blank_image())).decode("ascii")


SHA256_HEX = "a" * 64  # placeholder consent-text hash for tests
