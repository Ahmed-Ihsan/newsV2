"""Core data models for Trend Radar."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


STOP_WORDS: set[str] = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
    "by", "from", "this", "that", "it", "as", "can", "do", "does",
    "not", "no", "have", "has", "had", "will", "would", "could",
    "should", "may", "might", "new", "how", "what", "when", "where",
    "who", "which", "why", "your", "you", "my", "we", "our",
    "open", "source", "free", "github", "just", "like", "get",
    "use", "all", "more", "also", "one", "two",
}


class SourceType(str, Enum):
    GITHUB = "github"
    HACKERNEWS = "hackernews"
    REDDIT = "reddit"
    ARXIV = "arxiv"
    RSS = "rss"
    PRODUCTHUNT = "producthunt"
    YOUTUBE = "youtube"
    DEVTO = "devto"
    LOBSTERS = "lobsters"
    MEDIUM = "medium"
    NEWS = "news"


@dataclass
class IntelItem:
    """A single intelligence item from any source."""

    title: str
    source: SourceType
    url: str = ""
    description: str = ""
    score: int = 0  # stars, upvotes, points, etc.
    author: str = ""
    tags: list[str] = field(default_factory=list)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # GitHub-specific
    repo_stars: Optional[int] = None
    repo_language: Optional[str] = None
    repo_forks: Optional[int] = None

    # Metadata
    extra: dict = field(default_factory=dict)

    @property
    def score_display(self) -> str:
        if self.score >= 1_000_000:
            return f"{self.score/1_000_000:.1f}M"
        if self.score >= 1000:
            return f"{self.score/1000:.1f}k"
        return str(self.score)

    @classmethod
    def from_dict(cls, d: dict) -> "IntelItem":
        """Rebuild an item from the output of to_dict()."""
        d = dict(d)
        d["source"] = SourceType(d["source"])
        d["tags"] = list(d.get("tags") or [])
        d["extra"] = dict(d.get("extra") or {})
        fetched_at = d.get("fetched_at")
        if isinstance(fetched_at, str):
            d["fetched_at"] = datetime.fromisoformat(fetched_at)
        return cls(**d)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "source": self.source.value,
            "url": self.url,
            "description": self.description,
            "score": self.score,
            "author": self.author,
            "tags": list(self.tags),
            "fetched_at": self.fetched_at.isoformat(),
            "repo_stars": self.repo_stars,
            "repo_language": self.repo_language,
            "repo_forks": self.repo_forks,
            "extra": dict(self.extra),
        }


@dataclass
class TrendSnapshot:
    """A snapshot of trends at a point in time."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    items: list[IntelItem] = field(default_factory=list)
    sources_queried: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def item_count(self) -> int:
        return len(self.items)

    def top(self, n: int = 10) -> list[IntelItem]:
        """Return top N items by score."""
        return sorted(self.items, key=lambda x: x.score, reverse=True)[:n]

    def by_source(self, source: SourceType) -> list[IntelItem]:
        """Filter items by source."""
        return [i for i in self.items if i.source == source]

    def keywords(self, top_n: int = 20) -> list[tuple[str, int]]:
        """Extract most common keywords from titles."""
        from collections import Counter
        import re

        words = Counter()
        for item in self.items:
            tokens = re.findall(r"[a-zA-Z]{3,}", item.title.lower())
            for w in tokens:
                if w not in STOP_WORDS and len(w) > 2:
                    words[w] += 1
        return words.most_common(top_n)

# [2026-04-24] Refactor: simplified models logic
class _BaseHandler:
    """Base handler with common functionality.

    Refactored from inline logic to reusable base class.
    """

    __slots__ = ("_config", "_logger", "_metrics")

    def __init__(self, config: dict = None):
        self._config = config or {}
        self._logger = logging.getLogger(self.__class__.__module__)
        self._metrics = _MetricsCollector(self.__class__.__name__)

    def __enter__(self):
        self._setup()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._teardown()
        return False

    def _setup(self):
        """Setup resources."""
        pass

    def _teardown(self):
        """Cleanup resources."""
        self._metrics.flush()

# [2026-04-24] Refactor: simplified models logic
class _BaseHandler:
    """Base handler with common functionality.

    Refactored from inline logic to reusable base class.
    """

    __slots__ = ("_config", "_logger", "_metrics")

    def __init__(self, config: dict = None):
        self._config = config or {}
        self._logger = logging.getLogger(self.__class__.__module__)
        self._metrics = _MetricsCollector(self.__class__.__name__)

    def __enter__(self):
        self._setup()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._teardown()
        return False

    def _setup(self):
        """Setup resources."""
        pass

    def _teardown(self):
        """Cleanup resources."""
        self._metrics.flush()
