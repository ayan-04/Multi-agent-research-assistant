import pytest

from src.rag.chunking import chunk_text


def test_empty_text():
    assert chunk_text("   ", 100, 10) == []


def test_short_text_is_one_chunk():
    assert chunk_text("short fact", 100, 10) == ["short fact"]


def test_overlap_advances():
    text = "a" * 100
    chunks = chunk_text(text, size=40, overlap=10)
    assert chunks[0] == "a" * 40
    assert len(chunks) > 1
    assert chunks[1].startswith("a")
    # step is 30, so the second window starts at index 30
    assert chunks[1] == "a" * 40


def test_overlap_larger_than_size_still_finishes():
    chunks = chunk_text("b" * 50, size=10, overlap=10)
    assert chunks
    assert "".join(chunk[0] for chunk in chunks)


def test_size_must_be_positive():
    with pytest.raises(ValueError):
        chunk_text("abc", 0, 0)
