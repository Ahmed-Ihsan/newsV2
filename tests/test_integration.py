"""Integration tests — actually fetch data from real APIs.

These tests hit live endpoints. Mark with @pytest.mark.integration
to skip in offline environments.

Run with: pytest tests/test_integration.py -v -m integration
"""

import pytest

from trend_radar.sources.github import GitHubSource
from trend_radar.sources.hackernews import HackerNewsSource
from trend_radar.sources.reddit import RedditSource
from trend_radar.sources.arxiv import ArxivSource
from trend_radar.sources.rss import RSSSource
from trend_radar.sources.producthunt import ProductHuntSource
from trend_radar.core import TrendRadar
from trend_radar.models import IntelItem, SourceType


# Custom marker
pytestmark = pytest.mark.integration


class TestGitHubSourceIntegration:
    """Test GitHub source with real API."""

    def test_fetch_trending(self):
        """GitHub trending repos are fetchable."""
        src = GitHubSource()
        items = src.fetch(limit=5)
        assert len(items) > 0
        assert all(isinstance(i, IntelItem) for i in items)
        assert all(i.source == SourceType.GITHUB for i in items)
        assert all(i.url.startswith("https://") for i in items)

    def test_fetch_has_stars(self):
        """GitHub items have star counts."""
        src = GitHubSource()
        items = src.fetch(limit=3)
        for item in items:
            assert item.repo_stars is not None
            assert item.repo_stars >= 0

    def test_search(self):
        """GitHub search returns results."""
        src = GitHubSource()
        items = src.search("python web framework", limit=5)
        assert len(items) > 0
        assert all(i.source == SourceType.GITHUB for i in items)


class TestHackerNewsIntegration:
    """Test HN source with real Firebase API."""

    def test_fetch_top(self):
        """HN top stories are fetchable."""
        src = HackerNewsSource()
        items = src.fetch(limit=5)
        assert len(items) > 0
        assert all(isinstance(i, IntelItem) for i in items)
        assert all(i.source == SourceType.HACKERNEWS for i in items)

    def test_fetch_has_scores(self):
        """HN items have scores."""
        src = HackerNewsSource()
        items = src.fetch(limit=3)
        for item in items:
            assert item.score > 0

    def test_fetch_item_by_id(self):
        """Can fetch a specific HN item by ID."""
        src = HackerNewsSource()
        # First, get some IDs from top stories
        items = src.fetch(limit=1)
        if items:
            hn_id = items[0].extra.get("hn_id")
            if hn_id:
                item = src.fetch_item_by_id(hn_id)
                assert item is not None
                assert item.title


class TestRedditIntegration:
    """Test Reddit source with real JSON API.

    Note: Reddit may block server-side requests. If blocked, tests are skipped.
    """

    def test_fetch_hot(self):
        """Reddit hot posts are fetchable (may be blocked by Reddit)."""
        src = RedditSource()
        items = src.fetch(limit=5, subreddits=["programming"])
        if not items:
            pytest.skip("Reddit blocked the request (common on servers)")
        assert all(isinstance(i, IntelItem) for i in items)
        assert all(i.source == SourceType.REDDIT for i in items)

    def test_fetch_has_subreddit(self):
        """Reddit items have subreddit info (may be blocked by Reddit)."""
        src = RedditSource()
        items = src.fetch(limit=3, subreddits=["MachineLearning"])
        if not items:
            pytest.skip("Reddit blocked the request")
        for item in items:
            assert "subreddit" in item.extra


class TestArxivIntegration:
    """Test arXiv source with real API."""

    def test_fetch_recent(self):
        """arXiv recent papers are fetchable."""
        src = ArxivSource()
        items = src.fetch(limit=5, category="ai")
        assert len(items) > 0
        assert all(isinstance(i, IntelItem) for i in items)
        assert all(i.source == SourceType.ARXIV for i in items)

    def test_fetch_has_authors(self):
        """arXiv items have authors."""
        src = ArxivSource()
        items = src.fetch(limit=3)
        for item in items:
            assert item.author  # non-empty

    def test_search(self):
        """arXiv search returns results."""
        src = ArxivSource()
        items = src.search("large language model", limit=5)
        assert len(items) > 0


class TestRSSIntegration:
    """Test RSS source with real feeds."""

    def test_fetch_hn_rss(self):
        """HN RSS feed is fetchable."""
        src = RSSSource()
        items = src.fetch(limit=5, feed_names=["Hacker News (RSS)"])
        assert len(items) > 0
        assert all(i.source == SourceType.RSS for i in items)

    def test_fetch_multiple_feeds(self):
        """Multiple RSS feeds are fetchable."""
        src = RSSSource()
        items = src.fetch(limit=10, feed_names=["Hacker News (RSS)", "Ars Technica"])
        assert len(items) > 0


class TestCoreIntegration:
    """Test TrendRadar core with real sources."""

    def test_collect_hn(self):
        """Core collect works with HN."""
        radar = TrendRadar(use_cache=False)
        snapshot = radar.collect(sources=["hackernews"], limit=5, save=False)
        assert snapshot.item_count > 0
        assert "hackernews" in snapshot.sources_queried

    def test_collect_github(self):
        """Core collect works with GitHub."""
        radar = TrendRadar(use_cache=False)
        snapshot = radar.collect(sources=["github"], limit=5, save=False)
        assert snapshot.item_count > 0

    def test_collect_arxiv(self):
        """Core collect works with arXiv."""
        radar = TrendRadar(use_cache=False)
        snapshot = radar.collect(sources=["arxiv"], limit=5, save=False)
        assert snapshot.item_count > 0
