"""Hacker News data source — Firebase API."""

import concurrent.futures

import httpx

from trend_radar.models import IntelItem, SourceType
from trend_radar.sources import DataSource


class HackerNewsSource(DataSource):
    """Fetches stories from Hacker News via Firebase API."""

    name = "hackernews"
    source_type = SourceType.HACKERNEWS

    BASE_URL = "https://hacker-news.firebaseio.com/v0"

    STORY_ENDPOINTS = {
        "top": "topstories",
        "best": "beststories",
        "new": "newstories",
        "ask": "askstories",
        "show": "showstories",
        "jobs": "jobstories",
    }

    def fetch(self, limit: int = 25, category: str = "top", **kwargs) -> list[IntelItem]:
        """Fetch top stories from Hacker News."""
        endpoint = self.STORY_ENDPOINTS.get(category, "topstories")
        url = f"{self.BASE_URL}/{endpoint}.json"

        try:
            with httpx.Client(timeout=15) as client:
                resp = client.get(url)
                resp.raise_for_status()
                story_ids = resp.json()[:limit]
        except Exception:
            return []

        # Fetch items in parallel
        items = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(self._fetch_item, sid): sid for sid in story_ids
            }
            for future in concurrent.futures.as_completed(futures):
                item = future.result()
                if item:
                    items.append(item)

        # Sort by score descending
        items.sort(key=lambda x: x.score, reverse=True)
        return items[:limit]

    def _fetch_item(self, item_id: int) -> IntelItem | None:
        """Fetch a single HN item."""
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(f"{self.BASE_URL}/item/{item_id}.json")
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            return None

        if not data or data.get("type") != "story":
            return None

        url = data.get("url", "")
        if not url:
            url = f"https://news.ycombinator.com/item?id={item_id}"

        return IntelItem(
            title=data.get("title", ""),
            source=SourceType.HACKERNEWS,
            url=url,
            score=data.get("score", 0),
            author=data.get("by", ""),
            extra={
                "hn_id": item_id,
                "comment_count": data.get("descendants", 0),
                "hn_url": f"https://news.ycombinator.com/item?id={item_id}",
            },
        )

    def fetch_item_by_id(self, item_id: int) -> IntelItem | None:
        """Fetch a specific HN item by ID."""
        return self._fetch_item(item_id)
