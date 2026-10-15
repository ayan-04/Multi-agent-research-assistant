"""Character windows with overlap. Overlap keeps a quote from being split in half."""

from __future__ import annotations


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    cleaned = text.strip()
    if not cleaned:
        return []
    if size < 1:
        raise ValueError("chunk size must be positive")
    if len(cleaned) <= size:
        return [cleaned]
    # Overlap must be smaller than the window or the cursor never moves.
    if overlap < 0:
        overlap = 0
    if overlap >= size:
        overlap = size // 4
    step = size - overlap
    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        piece = cleaned[start : start + size].strip()
        if piece:
            chunks.append(piece)
        if start + size >= len(cleaned):
            break
        start += step
    return chunks
