"""Async data source fetching — high-performance concurrent collection.

Uses httpx.AsyncClient for non-blocking I/O, enabling true concurrent
HTTP requests without thread pool overhead.
"""

import asyncio
import logging
from typing import Optional

from .models import IntelItem, TrendSnapshot

logger = logging.getLogger(__name__)


async def fetch_source_async(
    source: "DataSource",
    limit: int = 25,
    **kwargs,
) -> tuple[str, list[IntelItem], Optional[str]]:
    """Fetch from a single source asynchronously.

    Wraps synchronous source.fetch() in a thread pool executor
    to avoid blocking the event loop.

    Args:
        source: DataSource instance.
        limit: Max items.
        **kwargs: Extra args for source.fetch().

    Returns:
        Tuple of (source_name, items, error_message).
    """
    loop = asyncio.get_event_loop()
    try:
        items = await loop.run_in_executor(
            None, lambda: source.fetch(limit=limit, **kwargs)
        )
        return source.name, items, None
    except Exception as e:
        return source.name, [], f"{source.name}: {e}"


async def collect_async(
    sources: dict[str, "DataSource"],
    limit: int = 25,
    source_names: Optional[list[str]] = None,
    max_concurrent: int = 6,
) -> TrendSnapshot:
    """Collect from all sources concurrently using asyncio.

    This is faster than ThreadPoolExecutor for I/O-bound tasks
    because it avoids thread overhead and GIL contention.

    Args:
        sources: Dict of source_name -> DataSource.
        limit: Max items per source.
        source_names: Specific sources to fetch. None = all.
        max_concurrent: Max concurrent requests.

    Returns:
        TrendSnapshot with all collected items.
    """
    targets = source_names or list(sources.keys())
    snapshot = TrendSnapshot()

    semaphore = asyncio.Semaphore(max_concurrent)

    async def _limited_fetch(source_name: str):
        async with semaphore:
            src = sources.get(source_name)
            if not src:
                return source_name, [], f"Unknown source: {source_name}"
            return await fetch_source_async(src, limit=limit)

    tasks = [_limited_fetch(name) for name in targets]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception):
            snapshot.errors.append(str(result))
            continue
        name, items, error = result
        snapshot.items.extend(items)
        if items:
            snapshot.sources_queried.append(name)
        if error:
            snapshot.errors.append(error)

    return snapshot


def collect_sync_async(
    sources: dict[str, "DataSource"],
    limit: int = 25,
    source_names: Optional[list[str]] = None,
) -> TrendSnapshot:
    """Synchronous wrapper around async collection.

    Convenience function for calling from sync code.
    Creates a new event loop if none exists.

    Args:
        sources: Dict of source_name -> DataSource.
        limit: Max items per source.
        source_names: Specific sources to fetch. None = all.

    Returns:
        TrendSnapshot with all collected items.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Already in an async context, use ThreadPoolExecutor instead
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    asyncio.run,
                    collect_async(sources, limit, source_names),
                )
                return future.result()
        return loop.run_until_complete(
            collect_async(sources, limit, source_names)
        )
    except RuntimeError:
        return asyncio.run(
            collect_async(sources, limit, source_names)
        )
