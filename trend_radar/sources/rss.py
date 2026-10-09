"""RSS/Atom feed data source."""

import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import httpx

from trend_radar.models import IntelItem, SourceType
from trend_radar.sources import DataSource


class RSSSource(DataSource):
    """Fetches items from RSS/Atom feeds."""

    name = "rss"
    source_type = SourceType.RSS

    TECH_FEEDS = {
        "Hacker News (RSS)": "https://hnrss.org/frontpage",
        "TechCrunch": "https://techcrunch.com/feed/",
        "The Verge": "https://www.theverge.com/rss/index.xml",
        "Ars Technica": "https://feeds.arstechnica.com/arstechnica/index",
        "MIT Tech Review": "https://www.technologyreview.com/feed/",
        "OpenAI Blog": "https://openai.com/blog/rss.xml",
        "Google AI Blog": "https://blog.google/technology/ai/rss/",
        "Anthropic Blog": "https://www.anthropic.com/rss.xml",
    }

    def __init__(self, feeds: dict[str, str] | None = None):
        self.feeds = feeds or self.TECH_FEEDS

    def fetch(self, limit: int = 25, feed_names: list[str] | None = None, **kwargs) -> list[IntelItem]:
        """Fetch items from configured RSS feeds."""
        targets = feed_names or list(self.feeds.keys())
        items = []

        for name in targets:
            url = self.feeds.get(name)
            if not url:
                continue
            feed_items = self._fetch_feed(name, url, limit=max(limit // len(targets), 3))
            items.extend(feed_items)

        # Sort by date, deduplicate
        seen_titles = set()
        unique = []
        for item in sorted(items, key=lambda x: x.fetched_at, reverse=True):
            if item.title not in seen_titles:
                seen_titles.add(item.title)
                unique.append(item)

        return unique[:limit]

    def _fetch_feed(self, source_name: str, url: str, limit: int = 5) -> list[IntelItem]:
        """Fetch and parse a single RSS/Atom feed."""
        headers = {"User-Agent": "TrendRadar/0.1 (RSS reader)"}

        try:
            with httpx.Client(timeout=15, headers=headers, follow_redirects=True) as client:
                resp = client.get(url)
                resp.raise_for_status()
        except Exception:
            return []

        try:
            root = ET.fromstring(resp.text)
        except ET.ParseError:
            return []

        items = []

        # Try RSS format
        for item_el in list(root.iter("item"))[:limit]:
            title = (item_el.findtext("title") or "").strip()
            link = (item_el.findtext("link") or "").strip()
            desc = (item_el.findtext("description") or "").strip()[:300]

            if title:
                items.append(
                    IntelItem(
                        title=title,
                        source=SourceType.RSS,
                        url=link,
                        description=desc,
                        score=0,
                        tags=[source_name],
                        extra={"feed": source_name},
                    )
                )

        # Try Atom format
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry_el in root.findall("atom:entry", ns)[:limit]:
            title = (entry_el.findtext("atom:title", namespaces=ns) or "").strip()
            link_el = entry_el.find("atom:link", ns)
            link = link_el.get("href", "") if link_el is not None else ""
            summary = (entry_el.findtext("atom:summary", namespaces=ns) or "").strip()[:300]

            if title:
                items.append(
                    IntelItem(
                        title=title,
                        source=SourceType.RSS,
                        url=link,
                        description=summary,
                        score=0,
                        tags=[source_name],
                        extra={"feed": source_name},
                    )
                )

        return items[:limit]
