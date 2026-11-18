"""Template encryption at rest (NFR-06, SYSTEM_DESIGN.md section 5.3).

Embeddings and optional display names are encrypted with Fernet (AES-128-CBC + HMAC).
Multiple keys are supported for rotation via MultiFernet: the first key encrypts, any
key may decrypt. The key file lives outside ``data/`` and must be readable only by the
current user (checked on POSIX; best-effort on Windows).
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from cryptography.fernet import Fernet, InvalidToken, MultiFernet


class CryptoError(Exception):
    """Raised for key problems or failed decryption."""


def generate_key() -> bytes:
    """Return a new urlsafe-base64 Fernet key (44 bytes)."""
    return Fernet.generate_key()


def check_key_file_permissions(path: str | os.PathLike[str]) -> None:
    """Raise :class:`CryptoError` if the key file is readable by other users (POSIX).

    On Windows, NTFS ACLs are not represented in ``st_mode``; we do a best-effort check
    and otherwise trust the documented setup step (``icacls``). See README.
    """
    p = Path(path)
    if not p.exists():
        raise CryptoError(f"key file not found: {p}")
    if os.name == "posix":
        mode = p.stat().st_mode
        if mode & 0o077:
            raise CryptoError(
                f"key file {p} is accessible by group/other (mode {oct(mode & 0o777)}); "
                "restrict it to the current user"
            )


def load_cipher(path: str | os.PathLike[str], *, check_permissions: bool = True) -> MultiFernet:
    """Load one or more keys (newline-separated) from ``path`` into a MultiFernet."""
    p = Path(path)
    if not p.exists():
        raise CryptoError(f"key file not found: {p}")
    if check_permissions:
        check_key_file_permissions(p)
    lines = [ln.strip() for ln in p.read_bytes().splitlines() if ln.strip()]
    if not lines:
        raise CryptoError(f"key file {p} is empty")
    try:
        return MultiFernet([Fernet(ln) for ln in lines])
    except Exception as exc:  # noqa: BLE001 - surface as CryptoError
        raise CryptoError(f"invalid key material in {p}") from exc


class TemplateCipher:
    """Encrypt and decrypt embedding vectors and short text fields."""

    def __init__(self, fernet: MultiFernet) -> None:
        self._f = fernet

    @classmethod
    def from_key_file(cls, path: str | os.PathLike[str], **kwargs: object) -> TemplateCipher:
        return cls(load_cipher(path, **kwargs))  # type: ignore[arg-type]

    @classmethod
    def from_key_bytes(cls, *keys: bytes) -> TemplateCipher:
        return cls(MultiFernet([Fernet(k) for k in keys]))

    def encrypt_vector(self, vector: np.ndarray) -> bytes:
        arr = np.asarray(vector, dtype=np.float32).ravel()
        return self._f.encrypt(arr.tobytes())

    def decrypt_vector(self, token: bytes) -> np.ndarray:
        try:
            raw = self._f.decrypt(token)
        except InvalidToken as exc:
            raise CryptoError("failed to decrypt vector (wrong key or tampered data)") from exc
        return np.frombuffer(raw, dtype=np.float32).copy()

    def encrypt_text(self, text: str) -> bytes:
        return self._f.encrypt(text.encode("utf-8"))

    def decrypt_text(self, token: bytes) -> str:
        try:
            return self._f.decrypt(token).decode("utf-8")
        except InvalidToken as exc:
            raise CryptoError("failed to decrypt text") from exc
