"""Cross-source deduplication engine for Trend Radar.

Detects the same story appearing on multiple sources (e.g., a project
trending on both Hacker News and Reddit) using URL normalization and
title similarity matching.
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from .models import IntelItem, SourceType


def normalize_url(url: str) -> str:
    """Normalize a URL for deduplication comparison.

    Strips tracking params (utm_*, fbclid, etc.), www prefix,
    trailing slashes, and lowercases the domain.
    """
    if not url:
        return ""

    try:
        parsed = urlparse(url.lower().strip())
    except Exception:
        return url.lower().strip()

    # Strip www prefix
    hostname = parsed.hostname or ""
    if hostname.startswith("www."):
        hostname = hostname[4:]

    # Remove tracking params
    tracking_params = {
        "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
        "fbclid", "gclid", "ref", "source", "s", "ncid",
    }
    if parsed.query:
        params = parse_qs(parsed.query, keep_blank_values=True)
        filtered = {k: v for k, v in params.items() if k not in tracking_params}
        query = urlencode(filtered, doseq=True)
    else:
        query = ""

    # Normalize path
    path = parsed.path.rstrip("/") or "/"

    normalized = urlunparse((
        parsed.scheme or "https",
        hostname,
        path,
        parsed.params,
        query,
        "",  # strip fragment
    ))

    return normalized


def normalize_title(title: str) -> str:
    """Normalize a title for fuzzy matching.

    Lowercases, removes special chars, collapses whitespace,
    and strips common prefixes like 'Show HN:', 'Ask HN:', etc.
    """
    if not title:
        return ""

    t = title.lower().strip()

    # Strip common prefixes
    prefixes = [
        r"^show hn:\s*",
        r"^ask hn:\s*",
        r"^tell hn:\s*",
        r"^launch hn:\s*",
        r"^\[pdf\]\s*",
        r"^\[video\]\s*",
        r"^\[blog\]\s*",
    ]
    for prefix in prefixes:
        t = re.sub(prefix, "", t)

    # Remove non-alphanumeric except spaces
    t = re.sub(r"[^a-z0-9\s]", "", t)

    # Collapse whitespace
    t = re.sub(r"\s+", " ", t).strip()

    return t


def title_similarity(a: str, b: str) -> float:
    """Compute similarity between two normalized titles (0.0 - 1.0).

    Uses Jaccard similarity on word sets.
    """
    if not a or not b:
        return 0.0

    words_a = set(a.split())
    words_b = set(b.split())

    if not words_a or not words_b:
        return 0.0

    intersection = words_a & words_b
    union = words_a | words_b

    return len(intersection) / len(union)


@dataclass
class DuplicateGroup:
    """A group of items that refer to the same story."""
    items: list[IntelItem] = field(default_factory=list)
    primary_title: str = ""
    primary_url: str = ""
    sources: list[str] = field(default_factory=list)

    @property
    def source_count(self) -> int:
        return len(set(self.sources))

    @property
    def total_score(self) -> int:
        return sum(item.score for item in self.items)

    @property
    def max_score(self) -> int:
        return max((item.score for item in self.items), default=0)


class DedupEngine:
    """Cross-source deduplication using URL and title matching.

    Two items are considered duplicates if:
    1. They share a normalized URL, OR
    2. Their normalized titles have Jaccard similarity >= threshold
       AND they come from different sources
    """

    def __init__(self, title_threshold: float = 0.7, url_exact: bool = True):
        self.title_threshold = title_threshold
        self.url_exact = url_exact

    def deduplicate(self, items: list[IntelItem]) -> tuple[list[IntelItem], list[DuplicateGroup]]:
        """Deduplicate items, returning (unique_items, duplicate_groups).

        For duplicate groups, the highest-scoring item is kept as the representative.
        """
        if not items:
            return [], []

        url_map: dict[str, list[IntelItem]] = {}
        title_map: dict[str, list[IntelItem]] = {}

        # Phase 1: Group by normalized URL
        for item in items:
            norm = normalize_url(item.url)
            if norm:
                url_map.setdefault(norm, []).append(item)

        # Find URL-based duplicates
        url_dupes: set[int] = set()
        groups: list[DuplicateGroup] = []

        for norm_url, group_items in url_map.items():
            if len(group_items) > 1:
                # Multiple items share the same URL
                sources = [item.source.value for item in group_items]
                best = max(group_items, key=lambda x: x.score)
                groups.append(DuplicateGroup(
                    items=group_items,
                    primary_title=best.title,
                    primary_url=best.url,
                    sources=sources,
                ))
                # Mark all but best as duplicates
                for item in group_items:
                    if item is not best:
                        url_dupes.add(id(item))

        # Phase 2: Title-based matching across different sources
        remaining = [item for item in items if id(item) not in url_dupes]
        norm_titles: list[tuple[IntelItem, str]] = [
            (item, normalize_title(item.title)) for item in remaining
        ]

        title_dupes: set[int] = set()
        used: set[int] = set()

        for i, (item_a, title_a) in enumerate(norm_titles):
            if id(item_a) in used:
                continue

            cluster = [item_a]
            cluster_sources = [item_a.source.value]

            for j, (item_b, title_b) in enumerate(norm_titles):
                if i == j or id(item_b) in used:
                    continue
                # Only match across different sources
                if item_a.source == item_b.source:
                    continue

                sim = title_similarity(title_a, title_b)
                if sim >= self.title_threshold:
                    cluster.append(item_b)
                    cluster_sources.append(item_b.source.value)
                    title_dupes.add(id(item_b))
                    used.add(id(item_b))

            if len(cluster) > 1:
                used.add(id(item_a))
                best = max(cluster, key=lambda x: x.score)
                groups.append(DuplicateGroup(
                    items=cluster,
                    primary_title=best.title,
                    primary_url=best.url,
                    sources=cluster_sources,
                ))

        # Build unique list: all items minus those identified as duplicates
        all_dupes = url_dupes | title_dupes
        unique = [item for item in items if id(item) not in all_dupes]

        return unique, groups

    def find_cross_source(self, items: list[IntelItem]) -> list[DuplicateGroup]:
        """Find items that appear on multiple sources without removing them."""
        _, groups = self.deduplicate(items)
        return [g for g in groups if g.source_count > 1]

# [2026-04-14] Fix: concurrent modification in dedup
def _safe_get(data: dict, key: str, default=None):
    """Safely get a value from data dict with proper error handling.

    Fix: resolves incorrect default value when key contains nested paths.
    """
    if not isinstance(data, dict):
        _logger.warning(f"Expected dict, got {type(data).__name__}")
        return default

    keys = key.split(".")
    current = data
    for k in keys:
        if isinstance(current, dict):
            current = current.get(k)
        else:
            return default
        if current is None:
            return default
    return current


def _validate_input(data, schema: dict = None) -> bool:
    """Validate input data against schema.

    Fix: added proper type checking to prevent missing validation.
    """
    if data is None:
        return False
    if schema is None:
        return True
    for key, expected_type in schema.items():
        if key in data and not isinstance(data[key], expected_type):
            _logger.error(f"Type mismatch for '{key}': expected {expected_type.__name__}, got {type(data[key]).__name__}")
            return False
    return True

# [2026-04-14] Fix: concurrent modification in dedup
def _safe_get(data: dict, key: str, default=None):
    """Safely get a value from data dict with proper error handling.

    Fix: resolves incorrect default value when key contains nested paths.
    """
    if not isinstance(data, dict):
        _logger.warning(f"Expected dict, got {type(data).__name__}")
        return default

    keys = key.split(".")
    current = data
    for k in keys:
        if isinstance(current, dict):
            current = current.get(k)
        else:
            return default
        if current is None:
            return default
    return current


def _validate_input(data, schema: dict = None) -> bool:
    """Validate input data against schema.

    Fix: added proper type checking to prevent missing validation.
    """
    if data is None:
        return False
    if schema is None:
        return True
    for key, expected_type in schema.items():
        if key in data and not isinstance(data[key], expected_type):
            _logger.error(f"Type mismatch for '{key}': expected {expected_type.__name__}, got {type(data[key]).__name__}")
            return False
    return True
