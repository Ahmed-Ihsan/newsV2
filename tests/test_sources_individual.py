"""Tests for individual data sources — mocked HTTP calls."""

import json
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime, timezone

import pytest

from trend_radar.models import IntelItem, SourceType


class TestHackerNewsSource:
    """Tests for HackerNews data source."""

    def _make_source(self):
        from trend_radar.sources.hackernews import HackerNewsSource
        return HackerNewsSource()

    def test_source_repr(self):
        src = self._make_source()
        assert "HackerNews" in repr(src) or "hackernews" in repr(src).lower()

    def test_is_available(self):
        src = self._make_source()
        assert src.is_available()

    @patch("trend_radar.sources.hackernews.httpx")
    def test_fetch_returns_items(self, mock_httpx):
        src = self._make_source()

        mock_ids_resp = MagicMock()
        mock_ids_resp.json.return_value = [1, 2, 3]
        mock_ids_resp.raise_for_status = MagicMock()

        mock_item_resp = MagicMock()
        mock_item_resp.json.return_value = {
            "id": 1,
            "title": "Test HN Story",
            "url": "https://example.com",
            "score": 300,
            "by": "user1",
            "time": 1684000000,
        }
        mock_item_resp.raise_for_status = MagicMock()

        mock_httpx.get.side_effect = [mock_ids_resp] + [mock_item_resp] * 3
        mock_httpx.Timeout.return_value = MagicMock()

        items = src.fetch(limit=3)
        assert isinstance(items, list)

    @patch("trend_radar.sources.hackernews.httpx")
    def test_fetch_handles_error(self, mock_httpx):
        src = self._make_source()
        mock_httpx.get.side_effect = Exception("Network error")
        mock_httpx.Timeout.return_value = MagicMock()

        items = src.fetch(limit=5)
        assert items == []


class TestRedditSource:
    """Tests for Reddit data source."""

    def _make_source(self):
        from trend_radar.sources.reddit import RedditSource
        return RedditSource()

    def test_source_repr(self):
        src = self._make_source()
        assert "Reddit" in repr(src) or "reddit" in repr(src).lower()

    def test_is_available(self):
        src = self._make_source()
        assert src.is_available()

    @patch("trend_radar.sources.reddit.httpx")
    def test_fetch_returns_items(self, mock_httpx):
        src = self._make_source()

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": {
                "children": [
                    {"data": {
                        "title": "Test Reddit Post",
                        "url": "https://example.com",
                        "score": 500,
                        "author": "user1",
                        "subreddit": "MachineLearning",
                        "permalink": "/r/ML/1",
                    }},
                ]
            }
        }
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_resp
        mock_httpx.Timeout.return_value = MagicMock()

        items = src.fetch(limit=5)
        assert isinstance(items, list)

    @patch("trend_radar.sources.reddit.httpx")
    def test_fetch_handles_error(self, mock_httpx):
        src = self._make_source()
        mock_httpx.get.side_effect = Exception("Rate limited")
        mock_httpx.Timeout.return_value = MagicMock()

        items = src.fetch(limit=5)
        assert items == []


class TestArxivSource:
    """Tests for arXiv data source."""

    def _make_source(self):
        from trend_radar.sources.arxiv import ArxivSource
        return ArxivSource()

    def test_source_repr(self):
        src = self._make_source()
        assert "Arxiv" in repr(src) or "arxiv" in repr(src).lower()

    def test_is_available(self):
        src = self._make_source()
        assert src.is_available()

    def test_parse_feed_valid_xml(self):
        src = self._make_source()
        atom_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
            <entry>
                <title>Test Paper Title</title>
                <id>http://arxiv.org/abs/2301.00001v1</id>
                <summary>Abstract of test paper</summary>
                <author><name>Author One</name></author>
                <published>2026-05-12T00:00:00Z</published>
                <category term="cs.AI"/>
            </entry>
        </feed>"""
        items = src._parse_feed(atom_xml, limit=5)
        assert len(items) == 1
        assert items[0].title == "Test Paper Title"
        assert items[0].source == SourceType.ARXIV
        assert items[0].author == "Author One"
        assert items[0].url == "https://arxiv.org/abs/2301.00001v1"

    def test_parse_feed_invalid_xml(self):
        src = self._make_source()
        items = src._parse_feed("not xml at all", limit=5)
        assert items == []

    def test_parse_feed_multiple_entries(self):
        src = self._make_source()
        atom_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
            <entry>
                <title>Paper One</title>
                <id>http://arxiv.org/abs/2301.00001v1</id>
                <summary>Summary one</summary>
                <author><name>A1</name></author>
                <published>2026-05-12T00:00:00Z</published>
            </entry>
            <entry>
                <title>Paper Two</title>
                <id>http://arxiv.org/abs/2301.00002v1</id>
                <summary>Summary two</summary>
                <author><name>A2</name></author><author><name>A3</name></author>
                <published>2026-05-11T00:00:00Z</published>
            </entry>
        </feed>"""
        items = src._parse_feed(atom_xml, limit=5)
        assert len(items) == 2
        assert items[1].author.startswith("A2")

    @patch("trend_radar.sources.arxiv.httpx")
    def test_fetch_handles_network_error(self, mock_httpx):
        src = self._make_source()
        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("Network error")
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_httpx.Client.return_value = mock_client

        items = src.fetch(limit=5)
        assert items == []


class TestRSSSource:
    """Tests for RSS data source."""

    def _make_source(self):
        from trend_radar.sources.rss import RSSSource
        return RSSSource()

    def test_source_repr(self):
        src = self._make_source()
        assert "RSS" in repr(src) or "rss" in repr(src).lower()

    def test_is_available(self):
        src = self._make_source()
        assert src.is_available()

    def test_has_default_feeds(self):
        src = self._make_source()
        assert len(src.feeds) >= 5

    def test_custom_feeds(self):
        from trend_radar.sources.rss import RSSSource
        custom = {"My Feed": "https://example.com/feed.xml"}
        src = RSSSource(feeds=custom)
        assert len(src.feeds) == 1
        assert "My Feed" in src.feeds

    @patch("trend_radar.sources.rss.httpx")
    def test_fetch_returns_items(self, mock_httpx):
        src = self._make_source()

        rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <item>
                    <title>Test RSS Item</title>
                    <link>https://example.com/1</link>
                    <description>Test description</description>
                </item>
            </channel>
        </rss>"""

        mock_resp = MagicMock()
        mock_resp.text = rss_xml
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_httpx.Client.return_value = mock_client

        # Use a source with just one feed to simplify
        from trend_radar.sources.rss import RSSSource
        single_feed = RSSSource(feeds={"Test": "https://example.com/rss"})
        items = single_feed.fetch(limit=5)
        assert isinstance(items, list)
        assert len(items) == 1
        assert items[0].title == "Test RSS Item"

    @patch("trend_radar.sources.rss.httpx")
    def test_fetch_handles_error(self, mock_httpx):
        src = self._make_source()

        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("Feed down")
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_httpx.Client.return_value = mock_client

        items = src.fetch(limit=5, feed_names=["Hacker News (RSS)"])
        assert items == []


class TestGitHubSource:
    """Tests for GitHub data source."""

    def _make_source(self):
        from trend_radar.sources.github import GitHubSource
        return GitHubSource()

    def test_source_repr(self):
        src = self._make_source()
        assert "GitHub" in repr(src) or "github" in repr(src).lower()

    def test_is_available(self):
        src = self._make_source()
        assert src.is_available()

    @patch("trend_radar.sources.github.httpx")
    def test_fetch_api_returns_items(self, mock_httpx):
        src = self._make_source()

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "items": [
                {
                    "full_name": "test/repo",
                    "html_url": "https://github.com/test/repo",
                    "description": "A test repo",
                    "stargazers_count": 5000,
                    "forks_count": 100,
                    "language": "Python",
                    "owner": {"login": "test"},
                },
            ]
        }
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_httpx.Client.return_value = mock_client

        items = src.fetch(limit=5)
        assert isinstance(items, list)
        assert len(items) == 1
        assert items[0].title == "test/repo"
        assert items[0].repo_stars == 5000

    @patch("trend_radar.sources.github.httpx")
    def test_fetch_handles_error(self, mock_httpx):
        src = self._make_source()

        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("GitHub API error")
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_httpx.Client.return_value = mock_client

        items = src.fetch(limit=5)
        assert items == []

    @patch("trend_radar.sources.github.httpx")
    def test_search(self, mock_httpx):
        src = self._make_source()

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "items": [
                {
                    "full_name": "test/ai-repo",
                    "html_url": "https://github.com/test/ai-repo",
                    "description": "AI framework",
                    "stargazers_count": 1000,
                    "forks_count": 50,
                    "language": "Python",
                    "owner": {"login": "test"},
                },
            ]
        }
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_httpx.Client.return_value = mock_client

        items = src.search("AI framework", limit=5)
        assert isinstance(items, list)
        assert len(items) == 1
        assert items[0].title == "test/ai-repo"
