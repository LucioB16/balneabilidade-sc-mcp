from datetime import UTC, datetime, timedelta
from pathlib import Path

from balneabilidade_sc_mcp.cache import FileCache, MemoryCache

NOW = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)


async def test_memory_cache_ttl_and_stale() -> None:
    current = [NOW]
    cache = MemoryCache(clock=lambda: current[0])
    await cache.set("k", b"value", "text/plain", timedelta(hours=1))
    fresh = await cache.get("k")
    assert fresh is not None
    assert fresh.text == "value"
    current[0] = NOW + timedelta(hours=2)
    assert await cache.get("k") is None
    stale = await cache.get("k", allow_stale=True)
    assert stale is not None
    assert stale.text == "value"


async def test_file_cache_roundtrip_and_stale(tmp_path: Path) -> None:
    current = [NOW]
    cache = FileCache(tmp_path, clock=lambda: current[0])
    await cache.set("catalog", b"abc", "text/plain", timedelta(hours=1))
    entry = await cache.get("catalog")
    assert entry is not None
    assert entry.data == b"abc"
    current[0] = NOW + timedelta(hours=2)
    assert await cache.get("catalog") is None
    assert (await cache.get("catalog", allow_stale=True)) is not None
    await cache.delete("catalog")
    assert await cache.get("catalog", allow_stale=True) is None


async def test_file_cache_corrupt_metadata_is_a_miss(tmp_path: Path) -> None:
    cache = FileCache(tmp_path, clock=lambda: NOW)
    await cache.set("k", b"abc", "text/plain", timedelta(hours=1))
    data_path, meta_path = cache._paths("k")
    meta_path.write_text("not json", encoding="utf-8")
    assert await cache.get("k") is None
    assert data_path.exists()
