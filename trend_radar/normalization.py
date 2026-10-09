"""Cross-source score normalization — comparable 0-100 scores.

Different sources have wildly different score ranges:
- GitHub stars: 0 to 500k+
- HN points: 0 to 5000+
- Reddit upvotes: 0 to 100k+
- arXiv: no score (0)
- Product Hunt votes: 0 to 2000+

Normalization maps all scores to a 0-100 scale using
percentile-based scaling within each source type.
"""

import math
from typing import Optional

from .models import IntelItem, SourceType


# Score range definitions per source (empirical data)
# Format: (typical_max, excellent_threshold)
SOURCE_SCORE_PROFILES: dict[SourceType, dict] = {
    SourceType.GITHUB: {
        "typical_max": 10000,
        "excellent": 5000,
        "good": 1000,
        "method": "logarithmic",
    },
    SourceType.HACKERNEWS: {
        "typical_max": 2000,
        "excellent": 500,
        "good": 100,
        "method": "logarithmic",
    },
    SourceType.REDDIT: {
        "typical_max": 50000,
        "excellent": 10000,
        "good": 1000,
        "method": "logarithmic",
    },
    SourceType.ARXIV: {
        "typical_max": 0,
        "excellent": 0,
        "good": 0,
        "method": "binary",  # No score
    },
    SourceType.RSS: {
        "typical_max": 0,
        "excellent": 0,
        "good": 0,
        "method": "binary",  # No score
    },
    SourceType.PRODUCTHUNT: {
        "typical_max": 2000,
        "excellent": 500,
        "good": 100,
        "method": "logarithmic",
    },
    SourceType.YOUTUBE: {
        "typical_max": 1000000,
        "excellent": 200000,
        "good": 20000,
        "method": "logarithmic",  # views
    },
    SourceType.DEVTO: {
        "typical_max": 1000,
        "excellent": 300,
        "good": 50,
        "method": "logarithmic",  # reactions
    },
    SourceType.LOBSTERS: {
        "typical_max": 300,
        "excellent": 100,
        "good": 30,
        "method": "logarithmic",
    },
    SourceType.MEDIUM: {
        "typical_max": 0,
        "excellent": 0,
        "good": 0,
        "method": "binary",  # No score
    },
    SourceType.NEWS: {
        "typical_max": 0,
        "excellent": 0,
        "good": 0,
        "method": "binary",  # No score
    },
}


def normalize_score(item: IntelItem) -> float:
    """Normalize an item's score to 0-100 scale.

    Uses logarithmic scaling for sources with score data,
    and binary scoring (50) for sources without scores.

    Returns:
        Normalized score between 0.0 and 100.0
    """
    profile = SOURCE_SCORE_PROFILES.get(item.source)
    if not profile or profile["method"] == "binary":
        return 50.0 if item.title else 0.0

    raw = item.score
    if raw <= 0:
        return 0.0

    typical_max = profile["typical_max"]
    if typical_max <= 0:
        return 50.0

    # Logarithmic normalization: ln(1 + x) / ln(1 + max) * 100
    # This gives a nice curve where small values still get decent scores
    normalized = math.log(1 + raw) / math.log(1 + typical_max) * 100
    return min(100.0, max(0.0, normalized))


def normalized_badge(score_0_100: float) -> tuple[str, str]:
    """Return (emoji, style) for a normalized score.

    Args:
        score_0_100: Score on 0-100 scale.

    Returns:
        Tuple of (emoji, Rich style string).
    """
    if score_0_100 >= 90:
        return "🔥", "bold bright_red"
    elif score_0_100 >= 75:
        return "🔴", "bold bright_red"
    elif score_0_100 >= 50:
        return "🟡", "bold bright_yellow"
    elif score_0_100 >= 25:
        return "🟢", "bright_green"
    elif score_0_100 > 0:
        return "🔵", "bright_cyan"
    else:
        return "⚪", "dim"


def enrich_with_normalized(items: list[IntelItem]) -> list[IntelItem]:
    """Add normalized_score to item extra fields.

    Args:
        items: List of IntelItem objects.

    Returns:
        Same list with normalized_score added to extra dict.
    """
    for item in items:
        item.extra["normalized_score"] = round(normalize_score(item), 1)
    return items


def rank_cross_source(items: list[IntelItem], top_n: int = 20) -> list[IntelItem]:
    """Rank items across all sources by normalized score.

    This enables fair comparison between GitHub repos (10k+ stars)
    and HN posts (500 points) — they're scored on the same scale.

    Args:
        items: Mixed-source items.
        top_n: Number of top items to return.

    Returns:
        Top N items sorted by normalized score descending.
    """
    enrich_with_normalized(items)
    return sorted(
        items,
        key=lambda x: x.extra.get("normalized_score", 0),
        reverse=True,
    )[:top_n]

# [2026-04-09] Chore: update normalization
# Version bump and minor cleanup
__version_info__ = (1, 2, 0)
__version__ = ".".join(map(str, __version_info__))

# Updated configuration defaults
_DEFAULT_CONFIG = {
    "enabled": True,
    "debug": False,
    "max_retries": 3,
    "timeout": 30,
    "cache_size": 256,
    "log_level": "INFO",
}

# [2026-04-09] Chore: update normalization
# Version bump and minor cleanup
__version_info__ = (1, 2, 0)
__version__ = ".".join(map(str, __version_info__))

# Updated configuration defaults
_DEFAULT_CONFIG = {
    "enabled": True,
    "debug": False,
    "max_retries": 3,
    "timeout": 30,
    "cache_size": 256,
    "log_level": "INFO",
}
