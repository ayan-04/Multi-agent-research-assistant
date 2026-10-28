import uuid

from src.rag.embeddings import HashingEmbedder
from src.rag.retrieve import retrieve_for_report
from src.rag.store import MemoryStore


def _store(name: str) -> MemoryStore:
    return MemoryStore(HashingEmbedder(), collection_name=f"{name}_{uuid.uuid4().hex[:8]}")


def test_chunks_keep_source_metadata_and_can_be_retrieved():
    store = _store("meta")
    stored = store.add(
        "https://example.com/ssb",
        "Battery notes",
        [
            "Solid-state batteries replace liquid electrolytes with solid ones.",
            "A second chunk about solid-state batteries and energy density.",
        ],
    )
    assert stored == 2
    found = store.query("solid-state batteries", k=2)
    assert len(found) == 2
    assert {item.source_url for item in found} == {"https://example.com/ssb"}
    assert {item.title for item in found} == {"Battery notes"}
    assert all(item.text for item in found)


def test_empty_store_and_blank_query():
    store = _store("empty")
    assert store.query("solid-state batteries", k=3) == []
    store.add("https://example.com/a", "A", ["solid-state batteries store energy"])
    assert store.query("   ", k=3) == []
    assert store.add("https://example.com/a", "A", ["  ", ""]) == 0


def test_retrieve_for_report_uses_topic_words():
    store = _store("report")
    store.add(
        "https://example.com/ssb",
        "Battery notes",
        ["Solid-state batteries replace liquid electrolytes with solid ones."],
    )
    found = retrieve_for_report(
        store,
        "solid-state batteries",
        ["How do solid-state batteries replace liquid electrolytes?"],
        k=1,
    )
    assert found[0].source_url == "https://example.com/ssb"
    assert "electrolytes" in found[0].text
