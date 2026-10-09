"""Reddit data source — JSON API with Atom feed fallback."""

import html
import logging
import re
import xml.etree.ElementTree as ET

import httpx
from httpx import HTTPStatusError

from trend_radar.models import IntelItem, SourceType
from trend_radar.sources import DataSource

logger = logging.getLogger(__name__)

# Reddit blocks non-browser user agents on the JSON endpoints
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def _strip_html(text: str) -> str:
    """Strip HTML tags/entities from a snippet."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


class RedditSource(DataSource):
    """Fetches hot/top posts from Reddit subreddits."""

    name = "reddit"
    source_type = SourceType.REDDIT

    DEFAULT_SUBREDDITS = [
        "MachineLearning",
        "LocalLLaMA",
        "artificial",
        "programming",
        "technology",
    ]

    AI_SUBREDDITS = [
        "MachineLearning",
        "LocalLLaMA",
        "artificial",
        "deeplearning",
        "LanguageTechnology",
        "singularity",
    ]

    def fetch(
        self,
        limit: int = 25,
        subreddits: list[str] | None = None,
        sort: str = "hot",
        **kwargs,
    ) -> list[IntelItem]:
        """Fetch posts from multiple subreddits."""
        subs = subreddits or self.DEFAULT_SUBREDDITS
        items = []
        last_error = ""
        json_blocked = False  # once Reddit 403s us, skip JSON for remaining subs

        for sub in subs:
            if json_blocked:
                sub_items = self._fetch_subreddit_atom(
                    sub, limit=max(limit // len(subs), 5), sort=sort
                )
            else:
                sub_items, blocked, error = self._fetch_subreddit(
                    sub, limit=max(limit // len(subs), 5), sort=sort
                )
                if blocked:
                    json_blocked = True
                if error:
                    last_error = error
            items.extend(sub_items)

        if not items:
            detail = last_error or "all endpoints failed"
            raise RuntimeError(f"reddit: no posts obtainable from any subreddit ({detail})")

        # Sort by score, deduplicate
        seen_urls = set()
        unique_items = []
        for item in sorted(items, key=lambda x: x.score, reverse=True):
            if item.url not in seen_urls:
                seen_urls.add(item.url)
                unique_items.append(item)

        return unique_items[:limit]

    def _fetch_subreddit(
        self, subreddit: str, limit: int = 10, sort: str = "hot"
    ) -> tuple[list[IntelItem], bool, str]:
        """Fetch posts from a single subreddit via the JSON API.

        Returns (items, json_blocked, error) where json_blocked is True when
        Reddit answered 403 (caller should skip JSON for further subreddits).
        """
        url = f"https://www.reddit.com/r/{subreddit}/{sort}.json"
        headers = {"User-Agent": USER_AGENT}
        params = {"limit": limit, "t": "day"}

        try:
            with httpx.Client(timeout=15, headers=headers, follow_redirects=True) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
        except HTTPStatusError as e:
            status = e.response.status_code
            if status in (403, 429):
                # Unauthenticated JSON access blocked — fall back to Atom feed
                logger.warning(
                    "reddit: r/%s JSON returned HTTP %s, falling back to Atom feed",
                    subreddit, status,
                )
                items = self._fetch_subreddit_atom(subreddit, limit=limit, sort=sort)
                return items, status == 403, f"HTTP {status} on JSON API"
            return [], False, f"HTTP {status} for r/{subreddit}"
        except Exception as e:
            logger.warning("reddit: r/%s fetch failed: %s", subreddit, e)
            return [], False, str(e)

        items = []
        for post in data.get("data", {}).get("children", []):
            p = post.get("data", {})
            items.append(
                IntelItem(
                    title=p.get("title", ""),
                    source=SourceType.REDDIT,
                    url=f"https://reddit.com{p.get('permalink', '')}",
                    description=p.get("selftext", "")[:200],
                    score=p.get("score", 0),
                    author=p.get("author", ""),
                    tags=[f"r/{subreddit}"],
                    extra={
                        "subreddit": p.get("subreddit", ""),
                        "comment_count": p.get("num_comments", 0),
                        "flair": p.get("link_flair_text", ""),
                    },
                )
            )
        return items, False, ""

    def _fetch_subreddit_atom(
        self, subreddit: str, limit: int = 10, sort: str = "hot"
    ) -> list[IntelItem]:
        """Fetch posts from a subreddit's public Atom feed (JSON blocked)."""
        if sort == "top":
            url = f"https://www.reddit.com/r/{subreddit}/top/.rss?t=day"
        elif sort == "new":
            url = f"https://www.reddit.com/r/{subreddit}/new/.rss"
        else:
            url = f"https://www.reddit.com/r/{subreddit}/.rss"
        headers = {"User-Agent": USER_AGENT}

        try:
            with httpx.Client(timeout=15, headers=headers, follow_redirects=True) as client:
                resp = client.get(url)
                resp.raise_for_status()
        except HTTPStatusError as e:
            logger.warning(
                "reddit: r/%s Atom feed returned HTTP %s", subreddit, e.response.status_code
            )
            return []
        except Exception as e:
            logger.warning("reddit: r/%s Atom feed failed: %s", subreddit, e)
            return []

        try:
            root = ET.fromstring(resp.text)
        except ET.ParseError as e:
            logger.warning("reddit: r/%s Atom feed unparsable: %s", subreddit, e)
            return []

        items = []
        for entry in root.findall("atom:entry", _ATOM_NS)[:limit]:
            title = (entry.findtext("atom:title", namespaces=_ATOM_NS) or "").strip()
            link = ""
            alt_link = ""
            for link_el in entry.findall("atom:link", _ATOM_NS):
                href = link_el.get("href", "")
                if not href:
                    continue
                if link_el.get("rel", "alternate") == "alternate":
                    alt_link = href
                    break
                if not link:
                    link = href
            link = alt_link or link
            author = (
                entry.findtext("atom:author/atom:name", namespaces=_ATOM_NS) or ""
            ).strip()
            updated = (
                entry.findtext("atom:updated", namespaces=_ATOM_NS)
                or entry.findtext("atom:published", namespaces=_ATOM_NS)
                or ""
            ).strip()
            summary = _strip_html(
                entry.findtext("atom:content", namespaces=_ATOM_NS)
                or entry.findtext("atom:summary", namespaces=_ATOM_NS)
                or ""
            )[:200]

            if not title:
                continue

            items.append(
                IntelItem(
                    title=title,
                    source=SourceType.REDDIT,
                    url=link,
                    description=summary,
                    score=0,  # Atom feeds carry no vote counts
                    author=author,
                    tags=[f"r/{subreddit}"],
                    extra={
                        "subreddit": subreddit,
                        "comment_count": 0,
                        "flair": "",
                        "published": updated,
                        "via": "atom",
                    },
                )
            )
        return items

    def fetch_ai_trends(self, limit: int = 25, **kwargs) -> list[IntelItem]:
        """Convenience: fetch from AI-focused subreddits."""
        return self.fetch(limit=limit, subreddits=self.AI_SUBREDDITS, **kwargs)
