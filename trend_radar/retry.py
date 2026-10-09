"""Retry utility with exponential backoff for robust HTTP calls."""

import functools
import logging
import time
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    retryable_exceptions: tuple = (Exception,),
    on_retry: Optional[Callable] = None,
) -> Callable:
    """Decorator for retrying functions with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds.
        max_delay: Maximum delay cap in seconds.
        exponential_base: Base for exponential calculation.
        retryable_exceptions: Tuple of exception types to retry on.
        on_retry: Optional callback(retry_count, exception, delay) called on each retry.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = min(
                            base_delay * (exponential_base ** attempt),
                            max_delay,
                        )
                        if on_retry:
                            on_retry(attempt + 1, e, delay)
                        logger.debug(
                            "Retry %d/%d for %s: %s (waiting %.1fs)",
                            attempt + 1, max_retries, func.__name__, e, delay,
                        )
                        time.sleep(delay)
            raise last_exception  # type: ignore[misc]

        return wrapper

    return decorator


def make_robust_client(
    timeout: float = 15.0,
    max_retries: int = 3,
    headers: Optional[dict] = None,
) -> "RobustHttpClient":
    """Create an HTTP client with built-in retry logic."""
    return RobustHttpClient(timeout=timeout, max_retries=max_retries, headers=headers)


class RobustHttpClient:
    """HTTP client wrapper with automatic retry and backoff."""

    def __init__(
        self,
        timeout: float = 15.0,
        max_retries: int = 3,
        headers: Optional[dict] = None,
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self.headers = headers or {}

    def get(self, url: str, **kwargs: Any) -> "httpx.Response":
        """GET with retry."""
        import httpx

        @retry_with_backoff(
            max_retries=self.max_retries,
            retryable_exceptions=(httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError),
            on_retry=lambda n, e, d: logger.debug("GET %s retry %d: %s", url, n, e),
        )
        def _get() -> "httpx.Response":
            with httpx.Client(timeout=self.timeout, headers=self.headers) as client:
                resp = client.get(url, **kwargs)
                # Retry on 429 (rate limit) and 5xx
                if resp.status_code == 429 or resp.status_code >= 500:
                    resp.raise_for_status()
                return resp

        return _get()

    def post(self, url: str, **kwargs: Any) -> "httpx.Response":
        """POST with retry."""
        import httpx

        @retry_with_backoff(
            max_retries=self.max_retries,
            retryable_exceptions=(httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError),
        )
        def _post() -> "httpx.Response":
            with httpx.Client(timeout=self.timeout, headers=self.headers) as client:
                resp = client.post(url, **kwargs)
                if resp.status_code == 429 or resp.status_code >= 500:
                    resp.raise_for_status()
                return resp

        return _post()
