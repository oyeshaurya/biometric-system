"""Keyed participant aliases (SYSTEM_DESIGN.md section 5, FR-15 anonymise mode).

An alias is a deterministic HMAC of the subject code under a secret key, so trials can be
analysed after a participant is anonymised without exposing the original subject code.
"""

from __future__ import annotations

import base64
import hashlib
import hmac


def make_alias(subject_code: str, key: bytes, *, length: int = 12) -> str:
    """Return a stable ``A...`` alias for ``subject_code`` under ``key``."""
    mac = hmac.new(key, subject_code.encode("utf-8"), hashlib.sha256).digest()
    body = base64.b32encode(mac).decode("ascii").rstrip("=")
    return "A" + body[:length]
