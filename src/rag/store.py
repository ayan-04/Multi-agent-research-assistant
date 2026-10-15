"""Chroma storage. Every chunk carries the source URL and title."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from src.rag.embeddings import Embedder
from src.rag.retrieve import RetrievedChunk

os.environ.setdefault("ANONYMIZED_TELEMETRY", "FALSE")


class ChromaStore:
    def __init__(
        self,
        embedder: Embedder,
        persist_dir: str | None = None,
        collection_name: str = "sources",
    ) -> None:
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        chroma_settings = ChromaSettings(anonymized_telemetry=False)
        if persist_dir:
            path = Path(persist_dir)
            path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(path), settings=chroma_settings)
        else:
            self._client = chromadb.EphemeralClient(settings=chroma_settings)
        self._embedder = embedder
        self._name = collection_name
        self._collection = self._client.get_or_create_collection(name=collection_name)

    def add(self, url: str, title: str, chunks: list[str]) -> int:
        documents = [chunk.strip() for chunk in chunks if chunk and chunk.strip()]
        if not documents:
            return 0
        ids: list[str] = []
        metadatas: list[dict] = []
        for index, document in enumerate(documents):
            digest = hashlib.sha256(f"{url}\n{index}\n{document}".encode("utf-8")).hexdigest()
            ids.append(digest)
            metadatas.append(
                {
                    "source_url": url,
                    "title": title or "",
                    "chunk_index": index,
                }
            )
        embeddings = self._embedder.embed(documents)
        self._collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )
        return len(documents)

    def query(self, text: str, k: int) -> list[RetrievedChunk]:
        if not text.strip() or k < 1:
            return []
        count = self._collection.count()
        if count == 0:
            return []
        vector = self._embedder.embed([text])[0]
        raw = self._collection.query(
            query_embeddings=[vector],
            n_results=min(k, count),
            include=["documents", "metadatas", "distances"],
        )
        documents = (raw.get("documents") or [[]])[0]
        metadatas = (raw.get("metadatas") or [[]])[0]
        distances = (raw.get("distances") or [[]])[0]
        found: list[RetrievedChunk] = []
        for document, metadata, distance in zip(documents, metadatas, distances):
            meta = metadata or {}
            found.append(
                RetrievedChunk(
                    text=document or "",
                    source_url=str(meta.get("source_url", "")),
                    title=str(meta.get("title", "")),
                    distance=float(distance) if distance is not None else None,
                )
            )
        return found

    def count(self) -> int:
        return self._collection.count()
