"""YouTube data source — latest videos from channels, via public channel feeds (no API key)."""

from trend_radar.models import IntelItem, SourceType
from trend_radar.sources import DataSource
from trend_radar.sources.feeds import fetch_feeds


class YouTubeSource(DataSource):
    """Fetches recent videos (with view counts) from YouTube channels."""

    name = "youtube"
    source_type = SourceType.YOUTUBE

    FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={}"

    # channel name -> channel id (the UC... id from the channel page / URL)
    DEFAULT_CHANNELS = {
        "Fireship": "UCsBjURrPoezykLs9EqgamOA",
        "Two Minute Papers": "UCbfYPyITQ-7l4upoX8nvctg",
        "Andrej Karpathy": "UCXUPKJO5MZQN11PqgIvyuvQ",
        "Computerphile": "UC9-y-6csu5WGm29I7JiwpnA",
        "Yannic Kilcher": "UCZHmQk67mSJgfCCTn7xBfew",
        "The PrimeTime": "UCUyeluBRhGPCW4rPe_UvBZQ",
    }

    def __init__(self, channels: dict[str, str] | None = None):
        self.channels = channels or self.DEFAULT_CHANNELS

    def fetch(self, limit: int = 25, **kwargs) -> list[IntelItem]:
        feeds = {name: self.FEED_URL.format(cid) for name, cid in self.channels.items()}
        items = fetch_feeds(feeds, SourceType.YOUTUBE, limit=limit * 3, per_feed=5)
        items.sort(key=lambda i: i.score, reverse=True)
        return items[:limit]
