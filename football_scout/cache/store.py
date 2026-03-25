"""SQLite-backed cache with TTL support."""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
import zlib
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


class CacheStore:
    """Key-value store backed by SQLite with TTL expiry."""

    def __init__(self, db_path: str = "data/cache.sqlite"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    cache_key TEXT PRIMARY KEY,
                    source_name TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    value BLOB NOT NULL,
                    created_at REAL NOT NULL,
                    ttl_seconds REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cache_source
                ON cache(source_name)
            """)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    @staticmethod
    def _make_key(source_name: str, endpoint: str, params: dict[str, Any]) -> str:
        sorted_params = json.dumps(params, sort_keys=True, default=str)
        param_hash = hashlib.sha256(sorted_params.encode()).hexdigest()
        return f"{source_name}:{endpoint}:{param_hash}"

    def get(self, source_name: str, endpoint: str, params: dict[str, Any]) -> bytes | None:
        key = self._make_key(source_name, endpoint, params)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value, created_at, ttl_seconds FROM cache WHERE cache_key = ?",
                (key,),
            ).fetchone()
            if row is None:
                return None
            value, created_at, ttl_seconds = row
            if time.time() - created_at > ttl_seconds:
                conn.execute("DELETE FROM cache WHERE cache_key = ?", (key,))
                return None
            return zlib.decompress(value)

    def put(
        self,
        source_name: str,
        endpoint: str,
        params: dict[str, Any],
        value: bytes,
        ttl_seconds: float = 86400,
    ) -> None:
        key = self._make_key(source_name, endpoint, params)
        compressed = zlib.compress(value)
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO cache
                   (cache_key, source_name, endpoint, value, created_at, ttl_seconds)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (key, source_name, endpoint, compressed, time.time(), ttl_seconds),
            )

    def get_or_fetch(
        self,
        source_name: str,
        endpoint: str,
        params: dict[str, Any],
        fetch_fn: Callable[[], bytes],
        ttl_seconds: float = 86400,
    ) -> bytes:
        cached = self.get(source_name, endpoint, params)
        if cached is not None:
            logger.debug("Cache hit: %s/%s", source_name, endpoint)
            return cached
        logger.debug("Cache miss: %s/%s, fetching...", source_name, endpoint)
        value = fetch_fn()
        self.put(source_name, endpoint, params, value, ttl_seconds)
        return value

    def clear(self, source_name: str | None = None) -> int:
        with self._connect() as conn:
            if source_name:
                cursor = conn.execute(
                    "DELETE FROM cache WHERE source_name = ?", (source_name,)
                )
            else:
                cursor = conn.execute("DELETE FROM cache")
            return cursor.rowcount

    def evict_expired(self) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM cache WHERE (? - created_at) > ttl_seconds",
                (time.time(),),
            )
            return cursor.rowcount
