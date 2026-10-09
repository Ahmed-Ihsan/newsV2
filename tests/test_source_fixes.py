"""Offline tests for the source fixes (arXiv https, Reddit Atom fallback,
Product Hunt Atom feed, RSS Atom + parallel fetch, visible failures, CLI collect).

All HTTP traffic is mocked with httpx.MockTransport — no network access.
"""

import json
import logging
from unittest.mock import MagicMock, patch

import httpx
import pytest
from click.testing import CliRunner

from trend_radar.cli import main
from trend_radar.models import IntelItem, SourceType, TrendSnapshot
from trend_radar.sources.arxiv import ArxivSource
from trend_radar.sources.github import GitHubSource
from trend_radar.sources.producthunt import ProductHuntSource
from trend_radar.sources.reddit import RedditSource
from trend_radar.sources.rss import RSSSource


def _mock_client_factory(handler):
    """Return a factory replacing httpx.Client in source modules so requests
    go through a MockTransport (no network)."""
    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def factory(**kwargs):
        kwargs["transport"] = transport
        return real_client(**kwargs)

    return factory


ARXIV_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>A Test Paper on Transformers</title>
    <id>http://arxiv.org/abs/2301.00001v1</id>
    <summary>We study transformers.</summary>
    <author><name>Ada Lovelace</name></author>
    <published>2026-10-01T00:00:00Z</published>
    <category term="cs.AI"/>
  </entry>
</feed>"""

def _reddit_atom_xml(sub: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>/r/{sub}</title>
  <entry>
    <title>Post One ({sub})</title>
    <link href="https://www.reddit.com/r/{sub}/comments/1/post_one/"/>
    <author><name>/u/alice</name></author>
    <updated>2026-10-09T00:00:00+00:00</updated>
    <summary>&lt;p&gt;Some &lt;b&gt;html&lt;/b&gt; body&lt;/p&gt;</summary>
  </entry>
  <entry>
    <title>Post Two ({sub})</title>
    <link rel="alternate" href="https://www.reddit.com/r/{sub}/comments/2/post_two/"/>
    <author><name>/u/bob</name></author>
    <updated>2026-10-08T00:00:00+00:00</updated>
    <content><![CDATA[<i>rich</i> content here]]></content>
  </entry>
</feed>"""

PRODUCTHUNT_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Product Hunt</title>
  <entry>
    <title>CoolApp — ship faster</title>
    <link rel="alternate" href="https://www.producthunt.com/posts/coolapp"/>
    <author><name>Hunter One</name></author>
    <published>2026-10-09T06:00:00Z</published>
    <content><![CDATA[<p>A tool for <b>shipping</b> faster.</p>]]></content>
  </entry>
  <entry>
    <title>DevTool 2.0</title>
    <link href="https://www.producthunt.com/posts/devtool-2"/>
    <author><name>Hunter Two</name></author>
    <updated>2026-10-08T06:00:00Z</updated>
    <summary>Plain summary text</summary>
  </entry>
</feed>"""


def _atom_feed_xml(entries: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<feed xmlns="http://www.w3.org/2005/Atom">\n'
        + entries
        + "</feed>"
    )


def _rss_entry(i: int) -> str:
    return f"""
  <entry>
    <title>Atom Entry {i}</title>
    <link rel="self" href="https://example.com/self/{i}"/>
    <link rel="alternate" href="https://example.com/post/{i}"/>
    <author><name>Author {i}</name></author>
    <published>2026-10-0{i + 1}T00:00:00Z</published>
    <content>Body of entry {i}</content>
  </entry>"""


class TestArxivHttpsAndRedirect:
    def test_fetch_uses_https_and_follows_redirect(self, monkeypatch):
        """arXiv fetch parses entries after following a redirect; first request is https."""
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if len(requests) == 1:
                # Simulate the legacy http->https redirect behaviour
                target = request.url.copy_with(scheme="https")
                return httpx.Response(301, headers={"Location": str(target)})
            return httpx.Response(200, text=ARXIV_ATOM)

        import trend_radar.sources.arxiv as arxiv_module
        monkeypatch.setattr(
            arxiv_module.httpx, "Client", _mock_client_factory(handler)
        )

        items = ArxivSource().fetch(limit=5)

        assert len(items) == 1
        assert items[0].title == "A Test Paper on Transformers"
        assert items[0].source == SourceType.ARXIV
        assert items[0].url == "https://arxiv.org/abs/2301.00001v1"
        # The redirect was followed (2 requests) and the code requested https
        assert len(requests) == 2
        assert requests[0].url.scheme == "https"
        assert requests[0].url.host == "export.arxiv.org"

    def test_search_uses_https(self, monkeypatch):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, text=ARXIV_ATOM)

        import trend_radar.sources.arxiv as arxiv_module
        monkeypatch.setattr(
            arxiv_module.httpx, "Client", _mock_client_factory(handler)
        )

        items = ArxivSource().search("transformers", limit=3)
        assert len(items) == 1
        assert requests[0].url.scheme == "https"

    def test_fetch_raises_on_http_error(self, monkeypatch):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, text="slow down")

        import trend_radar.sources.arxiv as arxiv_module
        monkeypatch.setattr(
            arxiv_module.httpx, "Client", _mock_client_factory(handler)
        )

        with pytest.raises(RuntimeError, match="arxiv.*503"):
            ArxivSource().fetch(limit=5)


class TestRedditAtomFallback:
    def test_403_falls_back_to_atom_and_stops_json(self, monkeypatch):
        json_requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path.endswith(".json"):
                json_requests.append(str(request.url))
                return httpx.Response(403, text="blocked")
            if path.endswith(".rss"):
                sub = path.split("/r/")[1].split("/")[0]
                return httpx.Response(200, text=_reddit_atom_xml(sub))
            return httpx.Response(404)

        import trend_radar.sources.reddit as reddit_module
        monkeypatch.setattr(
            reddit_module.httpx, "Client", _mock_client_factory(handler)
        )

        items = RedditSource().fetch(limit=10, subreddits=["sub1", "sub2", "sub3"])

        # Atom fallback yielded items
        assert len(items) == 6
        assert all(i.source == SourceType.REDDIT for i in items)
        assert all(i.score == 0 for i in items)
        post_one = next(i for i in items if i.title == "Post One (sub1)")
        assert post_one.url == "https://www.reddit.com/r/sub1/comments/1/post_one/"
        assert post_one.author == "/u/alice"
        assert "<" not in post_one.description and "html body" in post_one.description
        assert post_one.extra["published"] == "2026-10-09T00:00:00+00:00"
        post_two = next(i for i in items if i.title == "Post Two (sub1)")
        assert post_two.description == "rich content here"

        # JSON was abandoned after the first 403 (not retried per subreddit)
        assert len(json_requests) == 1

    def test_raises_when_json_and_atom_both_fail(self, monkeypatch):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(403, text="blocked")

        import trend_radar.sources.reddit as reddit_module
        monkeypatch.setattr(
            reddit_module.httpx, "Client", _mock_client_factory(handler)
        )

        with pytest.raises(RuntimeError, match="reddit"):
            RedditSource().fetch(limit=5, subreddits=["sub1"])


class TestProductHuntAtom:
    def test_feed_yields_items(self, monkeypatch):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, text=PRODUCTHUNT_ATOM)

        import trend_radar.sources.producthunt as ph_module
        monkeypatch.setattr(
            ph_module.httpx, "Client", _mock_client_factory(handler)
        )

        items = ProductHuntSource().fetch(limit=10)

        assert len(items) == 2
        assert requests[0].url.path == "/feed"
        assert items[0].title == "CoolApp — ship faster"
        assert items[0].url == "https://www.producthunt.com/posts/coolapp"
        assert items[0].author == "Hunter One"
        assert items[0].score == 0
        assert items[0].source == SourceType.PRODUCTHUNT
        assert "shipping" in items[0].description and "<" not in items[0].description
        assert items[1].description == "Plain summary text"
        assert items[1].extra["published"] == "2026-10-08T06:00:00Z"

    def test_raises_when_feed_fails(self, monkeypatch):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(403, text="forbidden")

        import trend_radar.sources.producthunt as ph_module
        monkeypatch.setattr(
            ph_module.httpx, "Client", _mock_client_factory(handler)
        )

        with pytest.raises(RuntimeError, match="producthunt.*403"):
            ProductHuntSource().fetch(limit=10)


class TestRSSAtomAndParallel:
    def _make_source(self):
        return RSSSource(feeds={"Atom Feed": "https://example.com/atom.xml"})

    def test_atom_entry_parsing(self, monkeypatch):
        xml = _atom_feed_xml("".join(_rss_entry(i) for i in range(2)))

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=xml)

        import trend_radar.sources.rss as rss_module
        monkeypatch.setattr(
            rss_module.httpx, "Client", _mock_client_factory(handler)
        )

        items = self._make_source().fetch(limit=10)

        assert len(items) == 2
        first = next(i for i in items if i.title == "Atom Entry 0")
        # rel=alternate link wins over rel=self
        assert first.url == "https://example.com/post/0"
        assert first.author == "Author 0"
        assert first.description == "Body of entry 0"
        assert first.extra["published"] == "2026-10-01T00:00:00Z"

    def test_extra_feed_set_and_per_feed_limit(self, monkeypatch):
        xml = _atom_feed_xml("".join(_rss_entry(i) for i in range(6)))

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=xml)

        import trend_radar.sources.rss as rss_module
        monkeypatch.setattr(
            rss_module.httpx, "Client", _mock_client_factory(handler)
        )

        items = self._make_source().fetch(limit=10, per_feed_limit=2)

        assert len(items) == 2
        assert all(i.extra["feed"] == "Atom Feed" for i in items)
        assert all("Atom Feed" in i.tags for i in items)

    def test_bad_feed_among_good_ones_warns_but_returns_items(
        self, monkeypatch, caplog
    ):
        feeds = {
            "Bad Feed": "https://bad.example.com/rss",
            "Good Feed": "https://good.example.com/atom.xml",
        }
        xml = _atom_feed_xml(_rss_entry(1))

        def handler(request: httpx.Request) -> httpx.Response:
            if "bad.example.com" in str(request.url):
                return httpx.Response(500, text="boom")
            return httpx.Response(200, text=xml)

        import trend_radar.sources.rss as rss_module
        monkeypatch.setattr(
            rss_module.httpx, "Client", _mock_client_factory(handler)
        )

        with caplog.at_level(logging.WARNING, logger="trend_radar.sources.rss"):
            items = RSSSource(feeds=feeds).fetch(limit=10)

        assert len(items) == 1
        assert items[0].extra["feed"] == "Good Feed"
        assert any("Bad Feed" in r.getMessage() for r in caplog.records)

    def test_raises_when_all_feeds_fail(self, monkeypatch):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="boom")

        import trend_radar.sources.rss as rss_module
        monkeypatch.setattr(
            rss_module.httpx, "Client", _mock_client_factory(handler)
        )

        with pytest.raises(RuntimeError, match="rss"):
            RSSSource(
                feeds={"Only Feed": "https://example.com/rss"}
            ).fetch(limit=10)

    def test_anthropic_blog_removed(self):
        assert "Anthropic Blog" not in RSSSource.TECH_FEEDS


class TestFailureVisibleInCollect:
    def test_collect_records_source_error(self, monkeypatch, tmp_path):
        """A source whose only endpoint fails raises, and collect() records it."""
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="internal error")

        import trend_radar.sources.arxiv as arxiv_module
        monkeypatch.setattr(
            arxiv_module.httpx, "Client", _mock_client_factory(handler)
        )

        from trend_radar.core import TrendRadar
        radar = TrendRadar(db_path=str(tmp_path / "t.db"), use_cache=False)
        snapshot = radar.collect(
            sources=["arxiv"], limit=5, save=False, use_cache=False
        )

        assert snapshot.items == []
        assert len(snapshot.errors) == 1
        assert "arxiv" in snapshot.errors[0]
        assert "500" in snapshot.errors[0]


class TestCliUsesCollect:
    def test_dedup_command_runs_via_collect(self):
        """dedup previously called radar.fetch_all (nonexistent); it must use collect."""
        snapshot = TrendSnapshot(
            items=[
                IntelItem(
                    title="Big AI breakthrough announced",
                    source=SourceType.HACKERNEWS,
                    url="https://news.ycombinator.com/item?id=1",
                    score=300,
                ),
                IntelItem(
                    title="Big AI breakthrough announced",
                    source=SourceType.REDDIT,
                    url="https://reddit.com/r/tech/1",
                    score=120,
                ),
            ],
            sources_queried=["hackernews", "reddit"],
        )

        runner = CliRunner()
        with patch("trend_radar.cli.TrendRadar") as MockRadar:
            radar = MockRadar.return_value
            radar.config = MagicMock()
            radar.collect.return_value = snapshot

            result = runner.invoke(
                main, ["dedup", "--sources", "hackernews,reddit", "--json"]
            )

            assert result.exit_code == 0, result.output
            radar.collect.assert_called_once()
            args, kwargs = radar.collect.call_args
            assert kwargs.get("sources") == ["hackernews", "reddit"]
            assert kwargs.get("limit") == 15  # CLI default

            data = json.loads(result.output)
            assert data["total_items"] == 2
            assert data["duplicate_groups"] == 1


class TestGitHubTrendingScrape:
    """fetch() must scrape the trending page first and use the Search API only
    as a fallback — the Search API's created:>X stars:>N query surfaces
    fake-star spam."""

    TRENDING_HTML = """<html><body>
<article class="Box-row">
  <h2 class="h3 lh-condensed">
    <a href="/BerriAI/litellm">
      <svg aria-hidden="true"></svg>
      BerriAI
      /
      litellm
    </a>
  </h2>
  <p class="col-9 color-fg-muted my-1 pr-4">Proxy server to access LLMs</p>
  <div class="f6 color-fg-muted mt-2">
    <span itemprop="programmingLanguage">Python</span>
    <a href="/BerriAI/litellm/stargazers" class="Link--muted d-inline-block mr-3">
      <svg aria-hidden="true"></svg>
      25,300
    </a>
    <a href="/BerriAI/litellm/forks" class="Link--muted d-inline-block mr-3">2,100</a>
    <span class="d-inline-block float-sm-right">
      <svg aria-hidden="true"></svg>
      1,512 stars today
    </span>
  </div>
</article>
<article class="Box-row">
  <h2 class="h3 lh-condensed">
    <a href="/mattpocock/skills">mattpocock / skills</a>
  </h2>
  <p class="col-9 color-fg-muted my-1 pr-4">Offline-first notes app</p>
  <div class="f6 color-fg-muted mt-2">
    <a href="/mattpocock/skills/stargazers" class="Link--muted d-inline-block mr-3">980</a>
  </div>
</article>
</body></html>"""

    def _trending_handler(self, calls, trending_html):
        """Serve the trending page for github.com and Search API JSON for api.github.com."""

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            if request.url.host == "api.github.com":
                return httpx.Response(200, json={
                    "items": [{
                        "full_name": "fallback/repo",
                        "html_url": "https://github.com/fallback/repo",
                        "description": "API fallback result",
                        "stargazers_count": 4321,
                        "owner": {"login": "fallback"},
                        "language": "Rust",
                        "forks_count": 10,
                    }],
                })
            return httpx.Response(200, text=trending_html)

        return handler

    def test_trending_html_parses_into_items(self, monkeypatch):
        calls = []
        import trend_radar.sources.github as github_module
        monkeypatch.setattr(
            github_module.httpx,
            "Client",
            _mock_client_factory(self._trending_handler(calls, self.TRENDING_HTML)),
        )

        items = GitHubSource().fetch(limit=10)

        assert [i.title for i in items] == ["BerriAI/litellm", "mattpocock/skills"]
        assert items[0].url == "https://github.com/BerriAI/litellm"
        assert items[0].source == SourceType.GITHUB
        # total stars are the score
        assert items[0].score == 25300
        assert items[0].repo_stars == 25300
        assert items[0].description == "Proxy server to access LLMs"
        assert items[0].repo_language == "Python"
        assert items[0].author == "BerriAI"
        # "stars today" badge -> extra["stars_today"]; absent when not shown
        assert items[0].extra["stars_today"] == 1512
        assert items[1].score == 980
        assert items[1].extra["stars_today"] is None
        assert items[1].repo_language is None
        # browser-like User-Agent was sent
        assert "Mozilla/5.0" in calls[0].headers["user-agent"]

    def test_api_not_called_when_scrape_succeeds(self, monkeypatch):
        calls = []
        import trend_radar.sources.github as github_module
        monkeypatch.setattr(
            github_module.httpx,
            "Client",
            _mock_client_factory(self._trending_handler(calls, self.TRENDING_HTML)),
        )

        GitHubSource().fetch(limit=10)

        assert len(calls) == 1
        assert calls[0].url.host == "github.com"
        assert all("api.github.com" not in str(c.url) for c in calls)

    def test_falls_back_to_api_when_scrape_yields_nothing(self, monkeypatch):
        calls = []
        empty_page = "<html><body><div>no repos here</div></body></html>"
        import trend_radar.sources.github as github_module
        monkeypatch.setattr(
            github_module.httpx,
            "Client",
            _mock_client_factory(self._trending_handler(calls, empty_page)),
        )

        items = GitHubSource().fetch(limit=5)

        assert len(items) == 1
        assert items[0].title == "fallback/repo"
        assert items[0].score == 4321
        hosts = [c.url.host for c in calls]
        assert hosts == ["github.com", "api.github.com"]

    def test_raises_when_both_paths_fail(self, monkeypatch):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="boom")

        import trend_radar.sources.github as github_module
        monkeypatch.setattr(
            github_module.httpx, "Client", _mock_client_factory(handler)
        )

        with pytest.raises(RuntimeError, match="github"):
            GitHubSource().fetch(limit=5)
