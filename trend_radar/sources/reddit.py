"""Reddit data source — JSON API."""

import httpx

from trend_radar.models import IntelItem, SourceType
from trend_radar.sources import DataSource


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

        for sub in subs:
            sub_items = self._fetch_subreddit(sub, limit=max(limit // len(subs), 5), sort=sort)
            items.extend(sub_items)

        # Sort by score, deduplicate
        seen_urls = set()
        unique_items = []
        for item in sorted(items, key=lambda x: x.score, reverse=True):
            if item.url not in seen_urls:
                seen_urls.add(item.url)
                unique_items.append(item)

        return unique_items[:limit]

    def _fetch_subreddit(self, subreddit: str, limit: int = 10, sort: str = "hot") -> list[IntelItem]:
        """Fetch posts from a single subreddit."""
        url = f"https://www.reddit.com/r/{subreddit}/{sort}.json"
        headers = {"User-Agent": "TrendRadar/0.1 (intelligence aggregator)"}
        params = {"limit": limit, "t": "day"}

        try:
            with httpx.Client(timeout=15, headers=headers) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            return []

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
        return items

    def fetch_ai_trends(self, limit: int = 25, **kwargs) -> list[IntelItem]:
        """Convenience: fetch from AI-focused subreddits."""
        return self.fetch(limit=limit, subreddits=self.AI_SUBREDDITS, **kwargs)
