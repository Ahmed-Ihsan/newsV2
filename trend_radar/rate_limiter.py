"""Rate limiter — token bucket algorithm for API call throttling.

Protects upstream APIs from being overwhelmed by concurrent requests.
Each source can have its own rate limiter with configurable limits.
"""

import threading
import time
from typing import Optional


class TokenBucketRateLimiter:
    """Token bucket rate limiter.

    Tokens are added at a fixed rate (refill_rate per second).
    Each request consumes one token. If no tokens are available,
    the caller waits until a token is available or times out.

    Args:
        capacity: Maximum number of tokens in the bucket.
        refill_rate: Tokens added per second.
    """

    def __init__(self, capacity: int = 10, refill_rate: float = 2.0):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_rate)
        self._last_refill = now

    def acquire(self, timeout: Optional[float] = None) -> bool:
        """Acquire a token, blocking if necessary.

        Args:
            timeout: Max seconds to wait. None = wait forever, 0 = non-blocking.

        Returns:
            True if token acquired, False if timed out.
        """
        deadline = None if timeout is None else time.monotonic() + timeout

        while True:
            with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return True

            if timeout is not None and timeout <= 0:
                return False

            # Calculate wait time for next token
            with self._lock:
                wait = max(0.0, (1.0 - self._tokens) / self.refill_rate)

            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                wait = min(wait, remaining)

            time.sleep(wait)

    def try_acquire(self) -> bool:
        """Try to acquire a token without blocking.

        Returns:
            True if token acquired immediately, False otherwise.
        """
        return self.acquire(timeout=0)

    @property
    def available_tokens(self) -> float:
        """Current number of available tokens (approximate)."""
        with self._lock:
            self._refill()
            return self._tokens

    def __repr__(self) -> str:
        return (
            f"TokenBucketRateLimiter(capacity={self.capacity}, "
            f"refill_rate={self.refill_rate}, available={self.available_tokens:.1f})"
        )


# Pre-configured rate limiters for common sources
DEFAULT_LIMITS: dict[str, dict] = {
    "github": {"capacity": 10, "refill_rate": 1.0},      # 10 req burst, 1/sec sustained
    "hackernews": {"capacity": 20, "refill_rate": 5.0},   # HN is generous
    "reddit": {"capacity": 5, "refill_rate": 0.5},        # Reddit is strict
    "arxiv": {"capacity": 3, "refill_rate": 0.3},         # arXiv XML API is slow
    "rss": {"capacity": 15, "refill_rate": 3.0},          # RSS feeds are local
    "producthunt": {"capacity": 5, "refill_rate": 1.0},   # PH GraphQL limits
    "youtube": {"capacity": 10, "refill_rate": 2.0},      # channel RSS feeds
    "devto": {"capacity": 5, "refill_rate": 1.0},
    "lobsters": {"capacity": 5, "refill_rate": 1.0},
    "medium": {"capacity": 5, "refill_rate": 0.5},        # Medium throttles feed scraping
    "news": {"capacity": 10, "refill_rate": 2.0},
}


class RateLimiterRegistry:
    """Registry of per-source rate limiters.

    Manages rate limiters for all data sources with sensible defaults.
    """

    def __init__(self, custom_limits: Optional[dict[str, dict]] = None):
        """Initialize the registry.

        Args:
            custom_limits: Override default limits.
                Format: {"source_name": {"capacity": N, "refill_rate": R}}
        """
        self._limiters: dict[str, TokenBucketRateLimiter] = {}
        limits = {**DEFAULT_LIMITS}
        if custom_limits:
            limits.update(custom_limits)

        for name, cfg in limits.items():
            self._limiters[name] = TokenBucketRateLimiter(
                capacity=cfg.get("capacity", 10),
                refill_rate=cfg.get("refill_rate", 2.0),
            )

    def get(self, source_name: str) -> Optional[TokenBucketRateLimiter]:
        """Get rate limiter for a source."""
        return self._limiters.get(source_name)

    def acquire(self, source_name: str, timeout: float = 30.0) -> bool:
        """Acquire a token for a source.

        Args:
            source_name: Name of the source.
            timeout: Max seconds to wait.

        Returns:
            True if acquired, False if timed out.
        """
        limiter = self._limiters.get(source_name)
        if limiter is None:
            return True  # No limiter = no limit
        return limiter.acquire(timeout=timeout)

    def try_acquire(self, source_name: str) -> bool:
        """Try to acquire without blocking."""
        limiter = self._limiters.get(source_name)
        if limiter is None:
            return True
        return limiter.try_acquire()

    def status(self) -> dict[str, dict]:
        """Get status of all rate limiters."""
        result = {}
        for name, limiter in self._limiters.items():
            result[name] = {
                "capacity": limiter.capacity,
                "refill_rate": limiter.refill_rate,
                "available": round(limiter.available_tokens, 1),
            }
        return result

    def __contains__(self, source_name: str) -> bool:
        return source_name in self._limiters
