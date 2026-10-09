"""Tests for the HTML exporter."""

from trend_radar.models import IntelItem, SourceType, TrendSnapshot
from trend_radar.exporters.html import HtmlRenderer


def _make_snapshot() -> TrendSnapshot:
    return TrendSnapshot(
        items=[
            IntelItem(
                title="test/repo",
                source=SourceType.GITHUB,
                score=1200,
                author="user",
                description="A test repository",
                url="https://github.com/test/repo",
                repo_language="Python",
                repo_stars=1200,
            ),
            IntelItem(
                title="Show HN: Something",
                source=SourceType.HACKERNEWS,
                score=300,
                url="https://news.ycombinator.com/item?id=123",
            ),
            IntelItem(
                title="Reddit post about AI",
                source=SourceType.REDDIT,
                score=150,
                description="An AI discussion",
                url="https://reddit.com/r/MachineLearning/post1",
            ),
            IntelItem(
                title="AI Research Paper",
                source=SourceType.ARXIV,
                score=0,
                description="A research paper about transformers",
                author="John Doe +3",
                url="https://arxiv.org/abs/2401.00001",
            ),
        ],
        sources_queried=["github", "hackernews", "reddit", "arxiv"],
    )


def test_html_renderer_produces_html():
    snap = _make_snapshot()
    renderer = HtmlRenderer()
    output = renderer.render(snap)
    assert output.startswith("<!DOCTYPE html>")
    assert "</html>" in output


def test_html_contains_items():
    snap = _make_snapshot()
    renderer = HtmlRenderer()
    output = renderer.render(snap)
    assert "test/repo" in output
    assert "Show HN: Something" in output
    assert "1.2k" in output


def test_html_contains_source_sections():
    snap = _make_snapshot()
    renderer = HtmlRenderer()
    output = renderer.render(snap)
    assert "GITHUB" in output
    assert "HACKERNEWS" in output
    assert "REDDIT" in output
    assert "ARXIV" in output


def test_html_contains_keywords():
    snap = _make_snapshot()
    renderer = HtmlRenderer()
    output = renderer.render(snap)
    assert "Trending Keywords" in output


def test_html_contains_links():
    snap = _make_snapshot()
    renderer = HtmlRenderer()
    output = renderer.render(snap)
    assert "https://github.com/test/repo" in output


def test_html_escape():
    """Test HTML escaping of special characters."""
    snap = TrendSnapshot(
        items=[
            IntelItem(
                title='Test <script>alert("xss")</script>',
                source=SourceType.GITHUB,
                score=100,
            ),
        ],
        sources_queried=["github"],
    )
    renderer = HtmlRenderer()
    output = renderer.render(snap)
    assert "<script>" not in output
    assert "&lt;script&gt;" in output


def test_html_custom_title():
    snap = _make_snapshot()
    renderer = HtmlRenderer()
    output = renderer.render(snap, title="Custom Title")
    assert "Custom Title" in output


def test_html_empty_snapshot():
    snap = TrendSnapshot()
    renderer = HtmlRenderer()
    output = renderer.render(snap)
    assert "<!DOCTYPE html>" in output
    assert "0" in output
