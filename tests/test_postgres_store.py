import os
import uuid

import pytest

from src.rag.embeddings import HashingEmbedder
from src.rag.store import PostgresStore


pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL is not set",
)


def test_postgres_round_trip():
    store = PostgresStore(
        embedder=HashingEmbedder(),
        database_url=os.environ["DATABASE_URL"],
        collection_name=f"t_{uuid.uuid4().hex[:12]}",
    )
    stored = store.add(
        "https://example.com/ssb",
        "Battery notes",
        ["Solid-state batteries replace liquid electrolytes with solid ones."],
    )
    assert stored == 1
    assert store.count() == 1
    found = store.query("solid-state batteries", k=1)
    assert found[0].source_url == "https://example.com/ssb"
    assert found[0].title == "Battery notes"
    assert store.query("   ", k=1) == []
