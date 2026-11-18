"""Log and summary redaction (NFR-05, SYSTEM_DESIGN.md section 5.5).

No images, base64 payloads, embeddings or landmarks may appear in logs, errors or audit
summaries. This module provides a logging filter and a mapping scrubber used before any
dict is written to the audit log.
"""

from __future__ import annotations

import logging
import re
from typing import Any

BANNED_KEYS = {"image_b64", "embedding", "vector", "frames", "vector_enc", "landmarks"}
_B64_RUN = re.compile(r"[A-Za-z0-9+/]{200,}={0,2}")
REDACTED = "[REDACTED]"


def scrub_text(text: str) -> str:
    return _B64_RUN.sub(REDACTED, text)


def scrub_mapping(data: Any) -> Any:
    """Recursively remove banned keys and shorten long base64-like strings."""
    if isinstance(data, dict):
        out: dict[str, Any] = {}
        for key, value in data.items():
            if key in BANNED_KEYS:
                out[key] = REDACTED
            else:
                out[key] = scrub_mapping(value)
        return out
    if isinstance(data, list):
        return [scrub_mapping(v) for v in data]
    if isinstance(data, str):
        return scrub_text(data)
    return data


class RedactionFilter(logging.Filter):
    """Scrub the rendered message of every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 - never let logging raise
            message = str(record.msg)
        record.msg = scrub_text(message)
        record.args = ()
        return True
