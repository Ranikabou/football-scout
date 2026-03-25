"""Per-source rate limiting."""

from __future__ import annotations

import random
import time
import logging
from threading import Lock

logger = logging.getLogger(__name__)

# Default rate limits per source (min_delay_seconds, jitter_range)
SOURCE_RATE_LIMITS: dict[str, tuple[float, float]] = {
    "statsbomb": (0.0, 0.0),       # Static GitHub files, no delay
    "fbref": (6.0, 2.0),           # 6s + 0-2s jitter
    "understat": (3.0, 1.0),       # 3s + 0-1s jitter
    "transfermarkt": (5.0, 2.0),   # 5s + 0-2s jitter
}


class RateLimiter:
    """Thread-safe per-source rate limiter."""

    def __init__(self) -> None:
        self._last_request: dict[str, float] = {}
        self._lock = Lock()

    def wait(self, source_name: str) -> None:
        limits = SOURCE_RATE_LIMITS.get(source_name, (1.0, 0.5))
        min_delay, jitter_range = limits

        if min_delay == 0.0:
            return

        with self._lock:
            now = time.time()
            last = self._last_request.get(source_name, 0.0)
            elapsed = now - last
            delay = min_delay + random.uniform(0, jitter_range)
            remaining = delay - elapsed

            if remaining > 0:
                logger.debug(
                    "Rate limiting %s: sleeping %.1fs", source_name, remaining
                )
                time.sleep(remaining)

            self._last_request[source_name] = time.time()


# Singleton instance
rate_limiter = RateLimiter()
