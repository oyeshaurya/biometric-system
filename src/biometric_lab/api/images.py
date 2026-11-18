"""Decode and validate base64 image payloads from API requests (SYSTEM_DESIGN 5.6)."""

from __future__ import annotations

import base64

import numpy as np

from biometric_lab.api.errors import ProblemError
from biometric_lab.context import AppContext
from biometric_lab.imaging import ImageDecodeError, decode_image


def decode_request_image(ctx: AppContext, image_b64: str) -> np.ndarray:
    try:
        raw = base64.b64decode(image_b64, validate=True)
    except Exception as exc:  # noqa: BLE001
        raise ProblemError(400, "IMAGE_DECODE_ERROR", "invalid base64 image") from exc
    if len(raw) > ctx.settings.max_image_bytes:
        raise ProblemError(413, "PAYLOAD_TOO_LARGE", "image exceeds size limit")
    try:
        img = decode_image(raw)
    except ImageDecodeError as exc:
        raise ProblemError(400, "IMAGE_DECODE_ERROR", str(exc)) from exc
    h, w = img.shape[:2]
    if max(h, w) > ctx.settings.max_image_dim:
        raise ProblemError(413, "PAYLOAD_TOO_LARGE", "image dimensions exceed limit")
    return img
