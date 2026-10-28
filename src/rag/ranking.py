"""Cosine distance shared by the in-memory store and PostgreSQL."""

from __future__ import annotations

import math


def cosine_distance(left: list[float], right: list[float]) -> float | None:
    """Return `1 - cosine similarity`. `None` when the vectors cannot be compared."""
    if not left or len(left) != len(right):
        return None
    dot = 0.0
    left_norm = 0.0
    right_norm = 0.0
    for a, b in zip(left, right):
        dot += a * b
        left_norm += a * a
        right_norm += b * b
    if left_norm == 0.0 or right_norm == 0.0:
        return None
    similarity = dot / (math.sqrt(left_norm) * math.sqrt(right_norm))
    return 1.0 - similarity
