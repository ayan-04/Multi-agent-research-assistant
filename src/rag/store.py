"""Chunk storage. PostgreSQL is the durable store. Tests use an in-memory one."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from src.rag.embeddings import Embedder
from src.rag.ranking import cosine_distance
from src.rag.retrieve import RetrievedChunk


@dataclass
class _Row:
    text: str
    source_url: str
    title: str
    embedding: list[float]


def _chunk_id(collection: str, url: str, index: int, document: str) -> str:
    return hashlib.sha256(f"{collection}\n{url}\n{index}\n{document}".encode("utf-8")).hexdigest()


def _prepare(chunks: list[str]) -> list[str]:
    return [chunk.strip() for chunk in chunks if chunk and chunk.strip()]


def _nearest(rows: list[_Row], vector: list[float], k: int) -> list[RetrievedChunk]:
    scored: list[tuple[float, _Row]] = []
    for row in rows:
        distance = cosine_distance(vector, row.embedding)
        if distance is None:
            continue
        scored.append((distance, row))
    scored.sort(key=lambda item: item[0])
    return [
        RetrievedChunk(
            text=row.text,
            source_url=row.source_url,
            title=row.title,
            distance=distance,
        )
        for distance, row in scored[:k]
    ]


class MemoryStore:
    """Process-local stand-in so unit tests do not need PostgreSQL."""

    def __init__(self, embedder: Embedder, collection_name: str = "sources") -> None:
        self._embedder = embedder
        self._name = collection_name
        self._rows: dict[str, _Row] = {}

    def add(self, url: str, title: str, chunks: list[str]) -> int:
        documents = _prepare(chunks)
        if not documents:
            return 0
        embeddings = self._embedder.embed(documents)
        for index, (document, embedding) in enumerate(zip(documents, embeddings)):
            self._rows[_chunk_id(self._name, url, index, document)] = _Row(
                text=document,
                source_url=url,
                title=title or "",
                embedding=list(embedding),
            )
        return len(documents)

    def query(self, text: str, k: int) -> list[RetrievedChunk]:
        if not text.strip() or k < 1 or not self._rows:
            return []
        vector = self._embedder.embed([text])[0]
        return _nearest(list(self._rows.values()), vector, k)

    def count(self) -> int:
        return len(self._rows)


class PostgresStore:
    """One collection per runtime, stored in the shared `chunks` table."""

    def __init__(self, embedder: Embedder, database_url: str, collection_name: str) -> None:
        if not database_url.strip():
            raise RuntimeError("DATABASE_URL is not set")
        self._embedder = embedder
        self._url = database_url
        self._name = collection_name
        from src.db import apply_schema

        apply_schema(database_url)

    def add(self, url: str, title: str, chunks: list[str]) -> int:
        documents = _prepare(chunks)
        if not documents:
            return 0
        embeddings = self._embedder.embed(documents)
        from src.db import connect

        with connect(self._url) as conn:
            for index, (document, embedding) in enumerate(zip(documents, embeddings)):
                conn.execute(
                    """
                    INSERT INTO chunks (
                        id, collection_name, source_url, title, chunk_index, document, embedding
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (id) DO UPDATE SET
                        source_url = EXCLUDED.source_url,
                        title = EXCLUDED.title,
                        chunk_index = EXCLUDED.chunk_index,
                        document = EXCLUDED.document,
                        embedding = EXCLUDED.embedding
                    """,
                    (
                        _chunk_id(self._name, url, index, document),
                        self._name,
                        url,
                        title or "",
                        index,
                        document,
                        json.dumps(list(embedding)),
                    ),
                )
            conn.commit()
        return len(documents)

    def query(self, text: str, k: int) -> list[RetrievedChunk]:
        if not text.strip() or k < 1:
            return []
        from src.db import connect

        with connect(self._url) as conn:
            raw_rows = conn.execute(
                """
                SELECT document, source_url, title, embedding
                FROM chunks
                WHERE collection_name = %s
                """,
                (self._name,),
            ).fetchall()
        rows = [
            _Row(
                text=row["document"],
                source_url=row["source_url"],
                title=row["title"] or "",
                embedding=[float(value) for value in row["embedding"]],
            )
            for row in raw_rows
        ]
        if not rows:
            return []
        vector = self._embedder.embed([text])[0]
        return _nearest(rows, vector, k)

    def count(self) -> int:
        from src.db import connect

        with connect(self._url) as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM chunks WHERE collection_name = %s",
                (self._name,),
            ).fetchone()
        return int(row["n"])
