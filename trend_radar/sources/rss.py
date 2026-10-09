"""RSS/Atom feed data source."""

import logging
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
from httpx import HTTPStatusError

from trend_radar.models import IntelItem, SourceType
from trend_radar.sources import DataSource

logger = logging.getLogger(__name__)

_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
_ATOM_ENTRY_TAG = "{http://www.w3.org/2005/Atom}entry"


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
    }

    def __init__(self, feeds: dict[str, str] | None = None):
        self.feeds = feeds or self.TECH_FEEDS

    def fetch(
        self,
        limit: int = 25,
        feed_names: list[str] | None = None,
        per_feed_limit: int | None = None,
        **kwargs,
    ) -> list[IntelItem]:
        """Fetch items from configured RSS feeds (in parallel).

        Args:
            limit: Max items returned overall.
            feed_names: Restrict to these feed display names.
            per_feed_limit: Max items fetched per feed; overrides the default
                ``max(limit // len(targets), 3)`` split.
        """
        targets = [n for n in (feed_names or list(self.feeds.keys())) if self.feeds.get(n)]
        if not targets:
            raise RuntimeError("rss: no matching feeds configured")

        effective = (
            per_feed_limit if per_feed_limit is not None else max(limit // len(targets), 3)
        )

        # Fetch feeds in parallel; results are re-assembled in target order so
        # the output stays deterministic.
        results: list[list[IntelItem]] = [[] for _ in targets]
        failures: list[str] = []

        with ThreadPoolExecutor(max_workers=min(8, len(targets))) as pool:
            futures = {
                pool.submit(self._fetch_feed, name, self.feeds[name], effective): i
                for i, name in enumerate(targets)
            }
            for future in as_completed(futures):
                idx = futures[future]
                name = targets[idx]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    failures.append(f"{name}: {e}")
                    logger.warning("rss: skipping feed %s: %s", name, e)

        items = [item for feed_items in results for item in feed_items]

        if not items:
            detail = "; ".join(failures) if failures else "no items returned"
            raise RuntimeError(f"rss: all {len(targets)} feeds failed or were empty ({detail})")

        # Sort by date, deduplicate
        seen_titles = set()
        unique = []
        for item in sorted(items, key=lambda x: x.fetched_at, reverse=True):
            if item.title not in seen_titles:
                seen_titles.add(item.title)
                unique.append(item)

        return unique[:limit]

    def _fetch_feed(self, source_name: str, url: str, limit: int = 5) -> list[IntelItem]:
        """Fetch and parse a single RSS/Atom feed.

        Raises on any failure so the caller can log/skip the individual feed.
        """
        headers = {"User-Agent": "TrendRadar/0.1 (RSS reader)"}

        try:
            with httpx.Client(timeout=15, headers=headers, follow_redirects=True) as client:
                resp = client.get(url)
                resp.raise_for_status()
        except HTTPStatusError as e:
            raise RuntimeError(f"HTTP {e.response.status_code} from {url}") from e
        except Exception as e:
            raise RuntimeError(f"request to {url} failed: {e}") from e

        try:
            root = ET.fromstring(resp.text)
        except ET.ParseError as e:
            raise RuntimeError(f"unparsable XML from {url}: {e}") from e

        items = []

        # RSS format
        for item_el in list(root.iter("item"))[:limit]:
            title = (item_el.findtext("title") or "").strip()
            link_el = item_el.find("link")
            link = (item_el.findtext("link") or "").strip()
            if not link and link_el is not None:
                link = (link_el.get("href") or "").strip()
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

        # Atom format (works whether <entry> sits under <feed> root or deeper)
        for entry_el in list(root.iter(_ATOM_ENTRY_TAG))[:limit]:
            title = (entry_el.findtext("atom:title", namespaces=_ATOM_NS) or "").strip()

            link = ""
            alt_link = ""
            for link_el in entry_el.findall("atom:link", _ATOM_NS):
                href = (link_el.get("href") or "").strip()
                if not href:
                    continue
                if link_el.get("rel", "alternate") == "alternate":
                    alt_link = href
                    break
                if not link:
                    link = href
            link = alt_link or link

            summary = (
                entry_el.findtext("atom:content", namespaces=_ATOM_NS)
                or entry_el.findtext("atom:summary", namespaces=_ATOM_NS)
                or ""
            ).strip()[:300]
            author = (
                entry_el.findtext("atom:author/atom:name", namespaces=_ATOM_NS) or ""
            ).strip()
            published = (
                entry_el.findtext("atom:published", namespaces=_ATOM_NS)
                or entry_el.findtext("atom:updated", namespaces=_ATOM_NS)
                or ""
            ).strip()

            if title:
                items.append(
                    IntelItem(
                        title=title,
                        source=SourceType.RSS,
                        url=link,
                        description=summary,
                        score=0,
                        author=author,
                        tags=[source_name],
                        extra={"feed": source_name, "published": published},
                    )
                )

        return items[:limit]
