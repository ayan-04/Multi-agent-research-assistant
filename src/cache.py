"""On-disk response cache so a rerun does not spend the free-tier quota again."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol


class Cache(Protocol):
    def get(self, namespace: str, material: str) -> str | None: ...

    def set(self, namespace: str, material: str, value: str) -> None: ...


class NullCache:
    """Used when a caller wants the client with caching turned off."""

    def get(self, namespace: str, material: str) -> str | None:
        return None

    def set(self, namespace: str, material: str, value: str) -> None:
        return None


class DiskCache:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _path(self, namespace: str, material: str) -> Path:
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
        safe_ns = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in namespace)
        return self.root / safe_ns / digest[:2] / digest[2:]

    def get(self, namespace: str, material: str) -> str | None:
        path = self._path(namespace, material)
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def set(self, namespace: str, material: str, value: str) -> None:
        path = self._path(namespace, material)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")
