"""Image decoding for API payloads.

The browser sends JPEG/PNG. The test client (with the fake engine) sends a NumPy ``.npy``
buffer so the full API path can be exercised with no image library installed. Decoding
order: NumPy buffer, then OpenCV, then Pillow.
"""

from __future__ import annotations

import io

import numpy as np

_NPY_MAGIC = b"\x93NUMPY"


class ImageDecodeError(Exception):
    """Raised when an image payload cannot be decoded."""


def decode_image(data: bytes) -> np.ndarray:
    """Decode raw image bytes to an HxWx3 uint8 BGR array."""
    if data[:6] == _NPY_MAGIC:
        arr = np.load(io.BytesIO(data), allow_pickle=False)
        return np.asarray(arr, dtype=np.uint8)

    try:
        import cv2

        buf = np.frombuffer(data, dtype=np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        if img is None:
            raise ImageDecodeError("OpenCV could not decode the image")
        return img
    except ImportError:
        pass

    try:
        from PIL import Image

        rgb = np.asarray(Image.open(io.BytesIO(data)).convert("RGB"), dtype=np.uint8)
        return rgb[:, :, ::-1].copy()  # RGB -> BGR
    except ImportError as exc:
        raise ImageDecodeError(
            "no image decoder available; install opencv-python-headless or Pillow"
        ) from exc


def encode_npy(arr: np.ndarray) -> bytes:
    """Serialise an array to a ``.npy`` buffer (used by tests to post fake frames)."""
    buf = io.BytesIO()
    np.save(buf, np.asarray(arr, dtype=np.uint8), allow_pickle=False)
    return buf.getvalue()
