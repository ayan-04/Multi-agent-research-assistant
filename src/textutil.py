"""Small text helpers shared by retrieval checks and the eval harness."""

from __future__ import annotations


def normalize_ws(text: str) -> str:
    """Case-fold and collapse whitespace so quote checks survive HTML spacing."""
    return " ".join(text.split()).casefold()


def quote_in_text(quote: str, text: str) -> bool:
    if not quote.strip() or not text.strip():
        return False
    return normalize_ws(quote) in normalize_ws(text)
