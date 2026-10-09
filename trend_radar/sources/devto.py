"""Dev.to data source — top articles via the public API."""

import httpx

from trend_radar.models import IntelItem, SourceType
from trend_radar.sources import DataSource


class DevToSource(DataSource):
    """Fetches top Dev.to articles of the past week."""

    name = "devto"
    source_type = SourceType.DEVTO

    API_URL = "https://dev.to/api/articles"

    def __init__(self, tag: str | None = None, top_days: int = 7):
        self.tag = tag
        self.top_days = top_days

    def fetch(self, limit: int = 25, **kwargs) -> list[IntelItem]:
        params = {"top": self.top_days, "per_page": min(limit, 100)}
        if self.tag:
            params["tag"] = self.tag
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.get(self.API_URL, params=params)
                resp.raise_for_status()
                articles = resp.json()
        except Exception:
            return []

        return [
            IntelItem(
                title=a.get("title", ""),
                source=SourceType.DEVTO,
                url=a.get("url", ""),
                description=(a.get("description") or "")[:300],
                score=a.get("positive_reactions_count", 0),
                author=(a.get("user") or {}).get("username", ""),
                tags=list(a.get("tag_list") or []),
                extra={"comments": a.get("comments_count", 0)},
            )
            for a in articles
            if a.get("title")
        ][:limit]
