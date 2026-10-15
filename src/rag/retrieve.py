"""Retrieval used when the writer and critic need evidence already stored."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


class RetrievedChunk(BaseModel):
    text: str
    source_url: str
    title: str = ""
    distance: float | None = None


class VectorStore(Protocol):
    def add(self, url: str, title: str, chunks: list[str]) -> int: ...

    def query(self, text: str, k: int) -> list[RetrievedChunk]: ...


def retrieve_for_report(store: VectorStore, topic: str, questions: list[str], k: int) -> list[RetrievedChunk]:
    """One query keeps embedding use inside the per-run cap."""
    parts = [topic, *questions]
    query = "\n".join(part for part in parts if part.strip())
    return store.query(query, k)
