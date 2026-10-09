"""General news data source — mainstream outlets via RSS."""

from trend_radar.models import IntelItem, SourceType
from trend_radar.sources import DataSource
from trend_radar.sources.feeds import fetch_feeds


class NewsSource(DataSource):
    """Fetches headlines from mainstream news outlets."""

    name = "news"
    source_type = SourceType.NEWS

    DEFAULT_FEEDS = {
        "BBC Technology": "https://feeds.bbci.co.uk/news/technology/rss.xml",
        "BBC World": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "Wired": "https://www.wired.com/feed/rss",
        "NPR Technology": "https://feeds.npr.org/1019/rss.xml",
        "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    }

    def __init__(self, feeds: dict[str, str] | None = None):
        self.feeds = feeds or self.DEFAULT_FEEDS

    def fetch(self, limit: int = 25, **kwargs) -> list[IntelItem]:
        return fetch_feeds(self.feeds, SourceType.NEWS, limit=limit, per_feed=limit)
