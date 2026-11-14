"""Small TTL cache with stale-while-degraded support.

The provider must not overwrite a good bulletin or catalog with an empty
response. Expired entries are returned only when the caller explicitly asks
for stale data and records that fact in its warnings.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class CacheEntry:
    key: str
    data: bytes
    content_type: str
    fetched_at: datetime
    expires_at: datetime

    @property
    def text(self) -> str:
        return self.data.decode("utf-8", errors="replace")

    @property
    def is_fresh(self) -> bool:
        return utcnow() < self.expires_at


class Cache(Protocol):
    async def get(self, key: str, *, allow_stale: bool = False) -> CacheEntry | None: ...

    async def set(self, key: str, data: bytes, content_type: str, ttl: timedelta) -> CacheEntry: ...

    async def delete(self, key: str) -> None: ...


class MemoryCache:
    def __init__(self, clock: Callable[[], datetime] = utcnow) -> None:
        self._clock = clock
        self._entries: dict[str, CacheEntry] = {}

    async def get(self, key: str, *, allow_stale: bool = False) -> CacheEntry | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if not allow_stale and self._clock() >= entry.expires_at:
            return None
        return entry

    async def set(self, key: str, data: bytes, content_type: str, ttl: timedelta) -> CacheEntry:
        now = self._clock()
        entry = CacheEntry(
            key=key,
            data=data,
            content_type=content_type,
            fetched_at=now,
            expires_at=now + ttl,
        )
        self._entries[key] = entry
        return entry

    async def delete(self, key: str) -> None:
        self._entries.pop(key, None)


class FileCache:
    """Content-addressed, atomic file cache.

    Keys are hashed so untrusted upstream names never become path components.
    The metadata and data are replaced atomically; a corrupt or partial entry
    is treated as a cache miss.
    """

    def __init__(self, root: Path, clock: Callable[[], datetime] = utcnow) -> None:
        self.root = Path(root)
        self._clock = clock
        self.root.mkdir(parents=True, exist_ok=True)

    def _paths(self, key: str) -> tuple[Path, Path]:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.root / f"{digest}.data", self.root / f"{digest}.json"

    async def get(self, key: str, *, allow_stale: bool = False) -> CacheEntry | None:
        data_path, meta_path = self._paths(key)
        try:
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
            data = data_path.read_bytes()
            fetched_at = datetime.fromisoformat(metadata["fetched_at"])
            expires_at = datetime.fromisoformat(metadata["expires_at"])
        except (OSError, KeyError, ValueError, json.JSONDecodeError):
            return None
        if metadata.get("key") not in (None, key):
            return None
        if not allow_stale and self._clock() >= expires_at:
            return None
        return CacheEntry(
            key=key,
            data=data,
            content_type=str(metadata.get("content_type", "")),
            fetched_at=fetched_at,
            expires_at=expires_at,
        )

    async def set(self, key: str, data: bytes, content_type: str, ttl: timedelta) -> CacheEntry:
        now = self._clock()
        entry = CacheEntry(
            key=key,
            data=data,
            content_type=content_type,
            fetched_at=now,
            expires_at=now + ttl,
        )
        data_path, meta_path = self._paths(key)
        self._atomic_write(data_path, data)
        metadata = {
            "key": key,
            "content_type": content_type,
            "fetched_at": entry.fetched_at.isoformat(),
            "expires_at": entry.expires_at.isoformat(),
            "size": len(data),
        }
        self._atomic_write(meta_path, json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8"))
        return entry

    async def delete(self, key: str) -> None:
        for path in self._paths(key):
            with contextlib.suppress(FileNotFoundError):
                path.unlink()

    @staticmethod
    def _atomic_write(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(prefix=path.name, dir=path.parent)
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(temporary)
