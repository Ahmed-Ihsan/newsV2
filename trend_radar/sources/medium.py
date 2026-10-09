"""Medium / Substack data source — topic tags and publication feeds via RSS."""

from trend_radar.models import IntelItem, SourceType
from trend_radar.sources import DataSource
from trend_radar.sources.feeds import fetch_feeds


class MediumSource(DataSource):
    """Fetches articles from Medium tags and any Medium/Substack publication feeds."""

    name = "medium"
    source_type = SourceType.MEDIUM

    DEFAULT_TAGS = ["artificial-intelligence", "programming", "technology"]

    def __init__(self, tags: list[str] | None = None, feeds: dict[str, str] | None = None):
        self.tags = self.DEFAULT_TAGS if tags is None else tags
        # extra feeds, e.g. {"Latent Space": "https://www.latent.space/feed"}
        self.extra_feeds = feeds or {}

    def fetch(self, limit: int = 25, **kwargs) -> list[IntelItem]:
        feeds = {f"Medium: {t}": f"https://medium.com/feed/tag/{t}" for t in self.tags}
        feeds.update(self.extra_feeds)
        return fetch_feeds(feeds, SourceType.MEDIUM, limit=limit, per_feed=limit)
