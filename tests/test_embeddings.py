from src.config import Settings
from src.rag.embeddings import GeminiEmbedder, HashingEmbedder, build_embedder


def _cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def test_hashing_embedder_is_deterministic():
    embedder = HashingEmbedder()
    first = embedder.embed(["solid-state batteries"])[0]
    second = embedder.embed(["solid-state batteries"])[0]
    assert first == second
    assert len(first) == 64


def test_related_text_ranks_closer_than_unrelated_text():
    embedder = HashingEmbedder()
    topic, related, other = embedder.embed(
        [
            "solid-state batteries",
            "solid-state batteries replace liquid electrolytes",
            "ancient olympic games in greece",
        ]
    )
    assert _cosine(topic, related) > _cosine(topic, other)


def test_build_embedder_stays_local_without_a_key():
    embedder = build_embedder(Settings(gemini_api_key=""))
    assert isinstance(embedder, HashingEmbedder)


def test_build_embedder_selects_gemini_when_a_key_is_set():
    embedder = build_embedder(Settings(gemini_api_key="test-key-not-used"))
    assert isinstance(embedder, GeminiEmbedder)
