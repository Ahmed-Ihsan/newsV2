"""Lobsters data source — hottest stories via the public JSON feed."""

import httpx

from trend_radar.models import IntelItem, SourceType
from trend_radar.sources import DataSource


class LobstersSource(DataSource):
    """Fetches the hottest stories from lobste.rs."""

    name = "lobsters"
    source_type = SourceType.LOBSTERS

    URL = "https://lobste.rs/hottest.json"

    def fetch(self, limit: int = 25, **kwargs) -> list[IntelItem]:
        try:
            with httpx.Client(timeout=15, headers={"User-Agent": "TrendRadar/1.0"}) as client:
                resp = client.get(self.URL)
                resp.raise_for_status()
                stories = resp.json()
        except Exception:
            return []

        return [
            IntelItem(
                title=s.get("title", ""),
                source=SourceType.LOBSTERS,
                url=s.get("url") or s.get("comments_url", ""),
                description=(s.get("description_plain") or "")[:300],
                score=s.get("score", 0),
                author=s.get("submitter_user", "") if isinstance(s.get("submitter_user"), str)
                else (s.get("submitter_user") or {}).get("username", ""),
                tags=list(s.get("tags") or []),
                extra={"comments": s.get("comment_count", 0), "comments_url": s.get("comments_url", "")},
            )
            for s in stories
            if s.get("title")
        ][:limit]
