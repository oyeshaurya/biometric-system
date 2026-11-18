"""Matcher protocol (ARCHITECTURE.md section 5)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

import numpy as np


class MatchError(Exception):
    """Raised for empty template sets or zero-length vectors."""


class Matcher(Protocol):
    name: str

    def score(self, probe: np.ndarray, templates: Sequence[np.ndarray]) -> float:
        ...
