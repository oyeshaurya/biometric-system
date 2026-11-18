"""Deterministic fake face engine for tests and UI development (SYSTEM_DESIGN.md 9.2).

A "scene" is encoded into the first pixels of an image so tests can control the number of
faces, the identity, a noise seed, detection score, yaw and face size. Embeddings are
deterministic: the same identity and noise seed always give the same vector. With the
default sigma, two samples of one identity score about 0.8 cosine, and different
identities score about 0.0 — enough to drive genuine/impostor tests without a real model.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

import numpy as np

from biometric_lab.core.face.base import FaceDetection, ModelInfo

_MAGIC = b"FKF1"
_FMT = "<BiiffH"  # faces, identity, noise, det_score, yaw_deg, face_px
_HEADER_LEN = len(_MAGIC) + struct.calcsize(_FMT)

FAKE_DIM = 128
# Chosen so two samples of one identity score ~0.8 cosine for dim=128:
# E[cos] ~= 1 / (1 + sigma^2 * dim). sigma=0.045 -> ~0.79.
_DEFAULT_SIGMA = 0.045


@dataclass
class Scene:
    faces: int
    identity: int
    noise: int
    det_score: float
    yaw_deg: float
    face_px: int


def encode_scene(
    identity: int,
    *,
    noise: int = 0,
    faces: int = 1,
    det_score: float = 0.99,
    yaw_deg: float = 0.0,
    face_px: int = 200,
    width: int = 320,
    height: int = 240,
) -> np.ndarray:
    """Build a synthetic BGR image carrying a scene header (uint8, HxWx3)."""
    payload = _MAGIC + struct.pack(
        _FMT, faces, identity, noise, float(det_score), float(yaw_deg), int(face_px)
    )
    img = np.zeros((height, width, 3), dtype=np.uint8)
    flat = img.reshape(-1)
    flat[: len(payload)] = np.frombuffer(payload, dtype=np.uint8)
    return img


def blank_image(width: int = 320, height: int = 240) -> np.ndarray:
    """An image with no scene header, decoded as 'no face'."""
    return np.zeros((height, width, 3), dtype=np.uint8)


def decode_scene(image: np.ndarray) -> Scene | None:
    flat = np.asarray(image).reshape(-1)
    if flat.size < _HEADER_LEN:
        return None
    head = bytes(flat[:_HEADER_LEN].astype(np.uint8))
    if head[: len(_MAGIC)] != _MAGIC:
        return None
    faces, identity, noise, det_score, yaw_deg, face_px = struct.unpack(
        _FMT, head[len(_MAGIC) :]
    )
    return Scene(faces, identity, noise, det_score, yaw_deg, face_px)


class FakeFaceEngine:
    """A deterministic engine driven by scene headers. No model download."""

    def __init__(self, dim: int = FAKE_DIM, sigma: float = _DEFAULT_SIGMA) -> None:
        self.dim = dim
        self.sigma = sigma
        self.info: ModelInfo = {
            "detector": "fake",
            "recogniser": "fake",
            "model_name": "fake",
            "model_version": "1",
            "dim": dim,
        }

    def _identity_vector(self, identity: int) -> np.ndarray:
        rng = np.random.default_rng(np.uint64(identity * 2654435761 % (2**32)))
        v = rng.normal(size=self.dim)
        return v / np.linalg.norm(v)

    def _embedding(self, identity: int, noise: int) -> np.ndarray:
        centre = self._identity_vector(identity)
        rng = np.random.default_rng(np.uint64((noise * 100003 + identity) % (2**32)))
        v = centre + self.sigma * rng.normal(size=self.dim)
        return (v / np.linalg.norm(v)).astype(np.float32)

    def analyse(self, image_bgr: np.ndarray) -> list[FaceDetection]:
        scene = decode_scene(image_bgr)
        if scene is None or scene.faces <= 0:
            return []
        detections: list[FaceDetection] = []
        for k in range(scene.faces):
            # Extra faces get distinct identities so the quality gate flags MULTIPLE_FACES.
            ident = scene.identity if k == 0 else scene.identity + 10_000 + k
            emb = self._embedding(ident, scene.noise)
            detections.append(
                FaceDetection(
                    bbox=(10.0, 10.0, float(scene.face_px), float(scene.face_px)),
                    det_score=float(scene.det_score),
                    yaw_deg=float(scene.yaw_deg),
                    embedding=emb,
                )
            )
        return detections
