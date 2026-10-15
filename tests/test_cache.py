from src.cache import DiskCache


def test_disk_cache_round_trip(tmp_path):
    cache = DiskCache(tmp_path)
    assert cache.get("llm", "prompt-a") is None
    cache.set("llm", "prompt-a", "value-a")
    assert cache.get("llm", "prompt-a") == "value-a"
    assert cache.get("llm", "prompt-b") is None


def test_same_material_is_stable(tmp_path):
    first = DiskCache(tmp_path / "one")
    second = DiskCache(tmp_path / "one")
    first.set("search", "same", "hits")
    assert second.get("search", "same") == "hits"
