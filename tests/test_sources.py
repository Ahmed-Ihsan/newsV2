"""Tests for data sources."""

from unittest.mock import MagicMock, patch

from trend_radar.models import SourceType
from trend_radar.sources.github import GitHubSource
from trend_radar.sources.hackernews import HackerNewsSource
from trend_radar.sources.reddit import RedditSource
from trend_radar.sources.arxiv import ArxivSource
from trend_radar.sources.rss import RSSSource


class TestGitHubSource:
    def test_init(self):
        src = GitHubSource()
        assert src.name == "github"
        assert src.source_type == SourceType.GITHUB

    def test_init_with_token(self):
        src = GitHubSource(token="test_token")
        assert src.token == "test_token"
        assert "Authorization" in src.headers


class TestHackerNewsSource:
    def test_init(self):
        src = HackerNewsSource()
        assert src.name == "hackernews"
        assert "top" in src.STORY_ENDPOINTS
        assert "best" in src.STORY_ENDPOINTS


class TestRedditSource:
    def test_init(self):
        src = RedditSource()
        assert src.name == "reddit"
        assert "MachineLearning" in src.DEFAULT_SUBREDDITS
        assert "LocalLLaMA" in src.AI_SUBREDDITS


class TestArxivSource:
    def test_init(self):
        src = ArxivSource()
        assert src.name == "arxiv"
        assert "ai" in src.CATEGORIES
        assert "ml" in src.CATEGORIES

    def test_parse_feed_empty(self):
        src = ArxivSource()
        items = src._parse_feed("", 10)
        assert items == []

    def test_parse_feed_invalid_xml(self):
        src = ArxivSource()
        items = src._parse_feed("not xml", 10)
        assert items == []


class TestRSSSource:
    def test_init(self):
        src = RSSSource()
        assert src.name == "rss"
        assert len(src.feeds) > 0

    def test_init_custom_feeds(self):
        custom = {"My Feed": "https://example.com/feed.xml"}
        src = RSSSource(feeds=custom)
        assert src.feeds == custom
