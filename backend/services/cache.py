"""
UBID Platform — In-Memory LRU Cache Layer

Wraps frequently-read, rarely-changed data (thresholds, dashboard counts)
in a simple TTL cache to avoid repeated DB round-trips.

Performance benefit:
  - Dashboard polls every 15s from multiple browser tabs → 4–10 DB hits/min → 0 with cache
  - Threshold fetches on every ingest → cached for 60s → single DB read per minute
"""

import time
import asyncio
from functools import wraps
from typing import Any, Optional, Callable, Tuple


class TTLCache:
    """
    Thread-safe, in-process TTL cache with O(1) get/set.
    Keys expire after `ttl` seconds.
    """
    def __init__(self):
        self._store: dict[str, Tuple[Any, float]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expiry = entry
            if time.monotonic() > expiry:
                del self._store[key]
                return None
            return value

    async def set(self, key: str, value: Any, ttl: float = 15.0):
        async with self._lock:
            self._store[key] = (value, time.monotonic() + ttl)

    async def invalidate(self, key: str):
        async with self._lock:
            self._store.pop(key, None)

    async def invalidate_prefix(self, prefix: str):
        """Invalidate all keys starting with prefix."""
        async with self._lock:
            keys_to_drop = [k for k in self._store if k.startswith(prefix)]
            for k in keys_to_drop:
                del self._store[k]


# ── Global singleton cache instances ─────────────────────────────────────────
# These live for the lifetime of the FastAPI process.

dashboard_cache = TTLCache()   # TTL: 10s  — dashboard metrics
threshold_cache = TTLCache()   # TTL: 60s  — active threshold config
search_cache    = TTLCache()   # TTL: 30s  — entity lookup results


def cached(cache: TTLCache, ttl: float = 15.0, key_fn: Optional[Callable] = None):
    """
    Decorator for async functions. Caches the return value in `cache` for `ttl` seconds.
    `key_fn(*args, **kwargs)` determines the cache key; defaults to function name + args repr.
    """
    def decorator(fn):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            if key_fn:
                cache_key = key_fn(*args, **kwargs)
            else:
                cache_key = f"{fn.__name__}:{repr(args)}:{repr(sorted(kwargs.items()))}"

            cached_val = await cache.get(cache_key)
            if cached_val is not None:
                return cached_val

            result = await fn(*args, **kwargs)
            await cache.set(cache_key, result, ttl=ttl)
            return result
        return wrapper
    return decorator
