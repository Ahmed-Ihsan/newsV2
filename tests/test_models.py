"""Tests for data models."""

from datetime import datetime, timezone

from trend_radar.models import IntelItem, SourceType, TrendSnapshot


def test_intel_item_creation():
    item = IntelItem(
        title="test/repo",
        source=SourceType.GITHUB,
        url="https://github.com/test/repo",
        score=100,
        repo_stars=100,
        repo_language="Python",
    )
    assert item.title == "test/repo"
    assert item.score == 100
    assert item.score_display == "100"


def test_intel_item_score_display():
    item = IntelItem(title="test", source=SourceType.GITHUB, score=1500)
    assert item.score_display == "1.5k"


def test_intel_item_to_dict():
    item = IntelItem(
        title="test",
        source=SourceType.HACKERNEWS,
        score=42,
        author="user1",
    )
    d = item.to_dict()
    assert d["source"] == "hackernews"
    assert d["score"] == 42
    assert d["author"] == "user1"


def test_snapshot_top():
    items = [
        IntelItem(title=f"item{i}", source=SourceType.GITHUB, score=i * 10)
        for i in range(20)
    ]
    snapshot = TrendSnapshot(items=items)
    top5 = snapshot.top(5)
    assert len(top5) == 5
    assert top5[0].score == 190  # highest


def test_snapshot_by_source():
    items = [
        IntelItem(title="gh1", source=SourceType.GITHUB, score=100),
        IntelItem(title="hn1", source=SourceType.HACKERNEWS, score=50),
        IntelItem(title="gh2", source=SourceType.GITHUB, score=200),
    ]
    snapshot = TrendSnapshot(items=items)
    gh = snapshot.by_source(SourceType.GITHUB)
    assert len(gh) == 2


def test_snapshot_keywords():
    items = [
        IntelItem(title="New AI agent framework for LLM", source=SourceType.GITHUB),
        IntelItem(title="AI agent autonomous coding tool", source=SourceType.HACKERNEWS),
        IntelItem(title="Building LLM powered applications", source=SourceType.REDDIT),
    ]
    snapshot = TrendSnapshot(items=items)
    kw = snapshot.keywords()
    kw_dict = dict(kw)
    assert kw_dict.get("agent", 0) >= 2
    assert kw_dict.get("llm", 0) >= 2
    assert kw_dict.get("framework", 0) >= 1
