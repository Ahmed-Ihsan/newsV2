"""Core engine — orchestrates sources, storage, rendering, and caching."""

import concurrent.futures
import os
import time
from typing import Optional

from .cache import TrendCache
from .config import TrendConfig
from .models import IntelItem, SourceType, TrendSnapshot
from .sources import DataSource
from .sources.github import GitHubSource
from .sources.hackernews import HackerNewsSource
from .sources.reddit import RedditSource
from .sources.arxiv import ArxivSource
from .sources.rss import RSSSource
from .sources.producthunt import ProductHuntSource
from .sources.youtube import YouTubeSource
from .sources.devto import DevToSource
from .sources.lobsters import LobstersSource
from .sources.medium import MediumSource
from .sources.news import NewsSource
from .store import TrendStore
from .translate import Translator


# Source class registry
SOURCE_CLASSES: dict[str, type[DataSource]] = {
    "github": GitHubSource,
    "hackernews": HackerNewsSource,
    "reddit": RedditSource,
    "arxiv": ArxivSource,
    "rss": RSSSource,
    "producthunt": ProductHuntSource,
    "youtube": YouTubeSource,
    "devto": DevToSource,
    "lobsters": LobstersSource,
    "medium": MediumSource,
    "news": NewsSource,
}


class TrendRadar:
    """Main engine that aggregates all data sources with caching and config."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        github_token: Optional[str] = None,
        config_path: Optional[str] = None,
        use_cache: bool = True,
    ):
        self.config = TrendConfig(config_path)
        self.store = TrendStore(db_path)
        self.github_token = (
            github_token
            or os.getenv("GITHUB_TOKEN", "")
            or self.config.source_config("github").get("token", "")
        )

        # Cache
        self.cache: Optional[TrendCache] = None
        if use_cache and self.config.cache_enabled:
            self.cache = TrendCache(
                memory_ttl=self.config.cache_memory_ttl,
                disk_ttl=self.config.cache_disk_ttl,
            )

        # Initialize sources
        self.sources: dict[str, DataSource] = {}
        self._init_sources()

    def translate_items(self, items: list[IntelItem], translate: bool | None = None) -> list[IntelItem]:
        """Translate items if enabled (config default, overridable per call)."""
        enabled = self.config.translate_enabled if translate is None else translate
        if not enabled or not items:
            return items
        target = self.config.translate_target
        if getattr(self, "_translator", None) is None or self._translator.target != target:
            self._translator = Translator(target)
        return self._translator.translate_items(items)

    def _init_sources(self):
        """Initialize all enabled sources from config."""
        for name, cls in SOURCE_CLASSES.items():
            src_cfg = self.config.source_config(name)
            if not src_cfg.get("enabled", True):
                continue

            if name == "github":
                self.sources[name] = cls(token=self.github_token)
            elif name == "rss":
                feeds = src_cfg.get("feeds")
                self.sources[name] = cls(feeds=feeds if feeds else None)
            elif name == "youtube":
                channels = src_cfg.get("channels")
                self.sources[name] = cls(channels=channels if channels else None)
            elif name == "devto":
                self.sources[name] = cls(tag=src_cfg.get("tag") or None)
            elif name == "medium":
                self.sources[name] = cls(tags=src_cfg.get("tags"), feeds=src_cfg.get("feeds"))
            elif name == "news":
                feeds = src_cfg.get("feeds")
                self.sources[name] = cls(feeds=feeds if feeds else None)
            else:
                self.sources[name] = cls()

    def collect(
        self,
        sources: list[str] | None = None,
        limit: int = 25,
        save: bool = True,
        use_cache: bool = True,
        parallel: bool = True,
        max_workers: int = 6,
        translate: bool | None = None,
        **kwargs,
    ) -> TrendSnapshot:
        """Collect intel from all (or specified) sources.

        Args:
            sources: Source names to fetch from. None = all enabled.
            limit: Max items per source.
            save: Save snapshot to SQLite store.
            use_cache: Check cache before fetching.
            parallel: Fetch sources in parallel (default True).
            max_workers: Thread pool size for parallel fetch.
            **kwargs: Extra args passed to source.fetch().

        Returns:
            TrendSnapshot with all collected items.
        """
        target_sources = sources or list(self.sources.keys())
        snapshot = TrendSnapshot()

        def _fetch_one(name: str) -> tuple[str, list[IntelItem], str | None]:
            """Fetch from a single source, return (name, items, error)."""
            source = self.sources.get(name)
            if not source:
                return name, [], f"Unknown source: {name}"

            # Check cache
            cache_key = None
            if use_cache and self.cache:
                cache_key = TrendCache.make_key(f"fetch:{name}", limit=limit, **kwargs)
                cached = self.cache.get(cache_key)
                if cached and isinstance(cached, list):
                    items = [IntelItem.from_dict(d) for d in cached]
                    return name, items, None

            try:
                items = source.fetch(limit=limit, **kwargs)

                # Store in cache
                if cache_key and self.cache:
                    self.cache.set(cache_key, [it.to_dict() for it in items])

                return name, items, None
            except Exception as e:
                return name, [], f"{name}: {e}"

        if parallel and len(target_sources) > 1:
            # Parallel fetch using thread pool
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {
                    pool.submit(_fetch_one, name): name for name in target_sources
                }
                for future in concurrent.futures.as_completed(futures):
                    name, items, error = future.result()
                    snapshot.items.extend(items)
                    if items:
                        snapshot.sources_queried.append(name)
                    if error:
                        snapshot.errors.append(error)
        else:
            # Sequential fetch
            for name in target_sources:
                name, items, error = _fetch_one(name)
                snapshot.items.extend(items)
                if items:
                    snapshot.sources_queried.append(name)
                if error:
                    snapshot.errors.append(error)

        if save:
            self.store.save_snapshot(snapshot)

        self.translate_items(snapshot.items, translate)
        return snapshot

    def collect_with_progress(
        self,
        sources: list[str] | None = None,
        limit: int = 25,
        save: bool = True,
        use_cache: bool = True,
        parallel: bool = True,
        max_workers: int = 6,
        callback=None,
        translate: bool | None = None,
        **kwargs,
    ) -> TrendSnapshot:
        """Collect intel with progress callbacks.

        Args:
            callback: Called with (event, data) where event is 'source_start',
                      'source_done', 'source_error'. data contains source name and details.
            ...other args same as collect()...

        Returns:
            TrendSnapshot with all collected items.
        """
        target_sources = sources or list(self.sources.keys())
        snapshot = TrendSnapshot()

        def _fetch_one(name: str) -> tuple[str, list[IntelItem], str | None]:
            if callback:
                callback("source_start", {"source": name})

            source = self.sources.get(name)
            if not source:
                if callback:
                    callback("source_error", {"source": name, "error": f"Unknown source: {name}"})
                return name, [], f"Unknown source: {name}"

            cache_key = None
            if use_cache and self.cache:
                cache_key = TrendCache.make_key(f"fetch:{name}", limit=limit, **kwargs)
                cached = self.cache.get(cache_key)
                if cached and isinstance(cached, list):
                    items = [IntelItem.from_dict(d) for d in cached]
                    if callback:
                        callback("source_done", {"source": name, "items": len(items), "cached": True})
                    return name, items, None

            try:
                items = source.fetch(limit=limit, **kwargs)
                if cache_key and self.cache:
                    self.cache.set(cache_key, [it.to_dict() for it in items])
                if callback:
                    callback("source_done", {"source": name, "items": len(items), "cached": False})
                return name, items, None
            except Exception as e:
                if callback:
                    callback("source_error", {"source": name, "error": str(e)})
                return name, [], f"{name}: {e}"

        if parallel and len(target_sources) > 1:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {pool.submit(_fetch_one, name): name for name in target_sources}
                for future in concurrent.futures.as_completed(futures):
                    name, items, error = future.result()
                    snapshot.items.extend(items)
                    if items:
                        snapshot.sources_queried.append(name)
                    if error:
                        snapshot.errors.append(error)
        else:
            for name in target_sources:
                name, items, error = _fetch_one(name)
                snapshot.items.extend(items)
                if items:
                    snapshot.sources_queried.append(name)
                if error:
                    snapshot.errors.append(error)

        if save:
            self.store.save_snapshot(snapshot)

        self.translate_items(snapshot.items, translate)
        return snapshot

    def collect_ai_focused(self, limit: int = 25, save: bool = True, translate: bool | None = None) -> TrendSnapshot:
        """Collect with AI/LLM focus across all sources."""
        snapshot = TrendSnapshot()

        # GitHub: search for AI repos
        try:
            gh_items = self.sources["github"].search("AI LLM agent", limit=limit, min_stars=50)
            snapshot.items.extend(gh_items)
            snapshot.sources_queried.append("github")
        except Exception as e:
            snapshot.errors.append(f"github: {e}")

        # HN: top stories
        try:
            hn_items = self.sources["hackernews"].fetch(limit=limit)
            snapshot.items.extend(hn_items)
            snapshot.sources_queried.append("hackernews")
        except Exception as e:
            snapshot.errors.append(f"hackernews: {e}")

        # Reddit: AI subreddits
        try:
            reddit_items = self.sources["reddit"].fetch_ai_trends(limit=limit)
            snapshot.items.extend(reddit_items)
            snapshot.sources_queried.append("reddit")
        except Exception as e:
            snapshot.errors.append(f"reddit: {e}")

        # arXiv: AI papers
        try:
            arxiv_items = self.sources["arxiv"].fetch(limit=limit // 2, category="ai")
            snapshot.items.extend(arxiv_items)
            snapshot.sources_queried.append("arxiv")
        except Exception as e:
            snapshot.errors.append(f"arxiv: {e}")

        if save:
            self.store.save_snapshot(snapshot)

        self.translate_items(snapshot.items, translate)
        return snapshot

    def search(self, query: str, sources: list[str] | None = None, limit: int = 25, translate: bool | None = None) -> list[IntelItem]:
        """Search across sources for a query."""
        items = []
        target = sources or ["github", "hackernews", "reddit", "arxiv"]

        if "github" in target:
            try:
                items.extend(self.sources["github"].search(query, limit=limit))
            except Exception:
                pass

        if "arxiv" in target:
            try:
                items.extend(self.sources["arxiv"].search(query, limit=limit))
            except Exception:
                pass

        # For HN and Reddit, filter fetched items
        if "hackernews" in target:
            try:
                hn = self.sources["hackernews"].fetch(limit=50)
                items.extend([i for i in hn if query.lower() in i.title.lower()][:limit])
            except Exception:
                pass

        if "reddit" in target:
            try:
                rd = self.sources["reddit"].fetch(limit=50)
                items.extend([i for i in rd if query.lower() in i.title.lower()][:limit])
            except Exception:
                pass

        results = sorted(items, key=lambda x: x.score, reverse=True)[:limit]
        return self.translate_items(results, translate)

    def analyze_opportunities(self, snapshot: TrendSnapshot) -> dict:
        """Analyze a snapshot for opportunities."""
        from collections import Counter

        keywords = snapshot.keywords(30)
        source_dist = Counter(i.source.value for i in snapshot.items)
        top = snapshot.top(10)
        high_star = [i for i in snapshot.items if i.source == SourceType.GITHUB and (i.repo_stars or 0) >= 100]
        lang_dist = Counter(i.repo_language for i in snapshot.items if i.repo_language)

        return {
            "total_items": snapshot.item_count,
            "sources_queried": snapshot.sources_queried,
            "top_items": [i.to_dict() for i in top],
            "keywords": keywords,
            "source_distribution": dict(source_dist),
            "high_star_repos": [i.to_dict() for i in high_star[:10]],
            "language_distribution": dict(lang_dist.most_common(10)),
            "errors": snapshot.errors,
        }

    def get_stats(self) -> dict:
        """Get engine statistics."""
        stats = self.store.get_stats()
        if self.cache:
            stats["cache"] = self.cache.stats()
        return stats

    def diff_snapshots(self, hours: int = 24) -> dict:
        """Compare the latest two snapshots to detect rising/falling trends.

        Returns a dict with 'rising', 'falling', 'new', and 'gone' items.
        """
        snapshots = self.store.get_snapshots(limit=2)
        if len(snapshots) < 2:
            return {
                "rising": [],
                "falling": [],
                "new": [],
                "gone": [],
                "current_count": 0,
                "previous_count": 0,
                "current_ts": "",
                "previous_ts": "",
            }

        current_items = self.store.get_snapshot_items(snapshots[0]["id"])
        previous_items = self.store.get_snapshot_items(snapshots[1]["id"])

        # Build lookup by title (case-insensitive)
        current_map: dict[str, dict] = {}
        for item in current_items:
            key = item["title"].lower().strip()
            if key not in current_map or item.get("score", 0) > current_map[key].get("score", 0):
                current_map[key] = item

        previous_map: dict[str, dict] = {}
        for item in previous_items:
            key = item["title"].lower().strip()
            if key not in previous_map or item.get("score", 0) > previous_map[key].get("score", 0):
                previous_map[key] = item

        rising = []
        falling = []
        new_items = []
        gone_items = []

        for key, item in current_map.items():
            if key in previous_map:
                prev_score = previous_map[key].get("score", 0)
                curr_score = item.get("score", 0)
                delta = curr_score - prev_score
                item["score_delta"] = delta
                if delta > 0:
                    rising.append(item)
                elif delta < 0:
                    falling.append(item)
            else:
                new_items.append(item)

        for key, item in previous_map.items():
            if key not in current_map:
                gone_items.append(item)

        # Sort by absolute delta
        rising.sort(key=lambda x: x.get("score_delta", 0), reverse=True)
        falling.sort(key=lambda x: x.get("score_delta", 0))

        return {
            "rising": rising[:20],
            "falling": falling[:20],
            "new": new_items[:20],
            "gone": gone_items[:20],
            "current_count": len(current_items),
            "previous_count": len(previous_items),
            "current_ts": snapshots[0].get("timestamp", ""),
            "previous_ts": snapshots[1].get("timestamp", ""),
        }

    def get_top_items(
        self,
        limit: int = 20,
        hours: int = 24,
        source: Optional[str] = None,
        topic: Optional[str] = None,
        translate: bool | None = None,
    ) -> list[IntelItem]:
        """Get top items from recent history, optionally filtered by source/topic.

        Args:
            limit: Max items to return.
            hours: Look back N hours.
            source: Filter by source name.
            topic: Filter by topic keywords (ai, web, mobile, security, etc).
        """
        items_raw = self.store.get_trending_items(hours=hours, source=source, limit=limit * 3)

        items = []
        for r in items_raw:
            try:
                src = SourceType(r["source"])
            except ValueError:
                src = SourceType.RSS

            item = IntelItem(
                title=r["title"],
                source=src,
                url=r.get("url", ""),
                description=r.get("description", ""),
                score=r.get("score", 0),
                author=r.get("author", ""),
            )

            # Apply topic filter
            if topic and not self._matches_topic(item, topic):
                continue

            items.append(item)

        results = sorted(items, key=lambda x: x.score, reverse=True)[:limit]
        return self.translate_items(results, translate)

    # Topic keywords for filtering
    TOPIC_KEYWORDS: dict[str, set[str]] = {
        "ai": {"ai", "llm", "gpt", "ml", "machine", "learning", "deep", "neural",
               "transformer", "model", "agent", "rag", "embedding", "diffusion",
               "copilot", "chatbot", "nlp", "llama", "claude", "openai", "anthropic"},
        "web": {"javascript", "typescript", "react", "vue", "angular", "next", "svelte",
                "css", "html", "frontend", "backend", "node", "deno", "bun", "web",
                "tailwind", "astro", "remix"},
        "mobile": {"android", "ios", "swift", "kotlin", "flutter", "react-native",
                   "mobile", "app", "swiftui", "jetpack"},
        "security": {"security", "vulnerability", "cve", "hack", "exploit", "malware",
                     "encryption", "auth", "zero-day", "pentest", "ctf", "cybersecurity"},
        "devops": {"docker", "kubernetes", "k8s", "terraform", "ci", "cd", "deploy",
                   "cloud", "aws", "gcp", "azure", "devops", "linux", "infra", "helm"},
        "data": {"database", "sql", "postgres", "redis", "mongo", "data", "pipeline",
                 "etl", "analytics", "warehouse", "spark", "kafka", "streaming"},
        "lang": {"rust", "go", "golang", "python", "java", "c++", "zig", "mojo",
                 "compiler", "language", "parser"},
    }

    def _matches_topic(self, item: IntelItem, topic: str) -> bool:
        """Check if an item matches a topic filter."""
        keywords = self.TOPIC_KEYWORDS.get(topic.lower(), set())
        if not keywords:
            return True  # Unknown topic, don't filter

        text = f"{item.title} {item.description} {' '.join(item.tags)}".lower()
        return any(kw in text for kw in keywords)

    def check_health(self) -> dict[str, dict]:
        """Check connectivity and responsiveness of all data sources.

        Returns a dict mapping source name to health info.
        """
        results = {}

        def _check_one(name: str) -> tuple[str, dict]:
            source = self.sources.get(name)
            if not source:
                return name, {"status": "disabled", "latency_ms": 0, "error": None}

            start = time.monotonic()
            try:
                items = source.fetch(limit=3)
                elapsed = (time.monotonic() - start) * 1000
                return name, {
                    "status": "ok" if items else "empty",
                    "latency_ms": round(elapsed),
                    "items_fetched": len(items),
                    "error": None,
                }
            except Exception as e:
                elapsed = (time.monotonic() - start) * 1000
                return name, {
                    "status": "error",
                    "latency_ms": round(elapsed),
                    "items_fetched": 0,
                    "error": str(e),
                }

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            futures = {pool.submit(_check_one, name): name for name in self.sources}
            for future in concurrent.futures.as_completed(futures):
                name, info = future.result()
                results[name] = info

        return results

# [2026-04-17] daily digest generation
class DailyDigestGenerationHandler:
    """Handler for daily digest generation operations."""

    def __init__(self, config: dict = None):
        self._config = config or {}
        self._initialized = False
        self._cache = {}

    def initialize(self) -> bool:
        """Initialize the handler with current configuration."""
        if self._initialized:
            return True
        try:
            self._validate_config()
            self._initialized = True
            return True
        except Exception as e:
            logger.warning(f"Initialization failed: {e}")
            return False

    def _validate_config(self):
        """Validate configuration parameters."""
        required = self._required_keys()
        missing = [k for k in required if k not in self._config]
        if missing:
            raise ValueError(f"Missing config keys: {missing}")

    def _required_keys(self) -> list:
        return ["enabled"]

    def process(self, data: dict) -> dict:
        """Process data through the handler."""
        if not self._initialized:
            self.initialize()
        result = self._transform(data)
        self._cache[data.get("id", "default")] = result
        return result

    def _transform(self, data: dict) -> dict:
        """Apply transformation to input data."""
        return {"status": "processed", "data": data, "handler": self.__class__.__name__}

    def clear_cache(self):
        """Clear the internal cache."""
        self._cache.clear()

# [2026-04-17] daily digest generation
class DailyDigestGenerationHandler:
    """Handler for daily digest generation operations."""

    def __init__(self, config: dict = None):
        self._config = config or {}
        self._initialized = False
        self._cache = {}

    def initialize(self) -> bool:
        """Initialize the handler with current configuration."""
        if self._initialized:
            return True
        try:
            self._validate_config()
            self._initialized = True
            return True
        except Exception as e:
            logger.warning(f"Initialization failed: {e}")
            return False

    def _validate_config(self):
        """Validate configuration parameters."""
        required = self._required_keys()
        missing = [k for k in required if k not in self._config]
        if missing:
            raise ValueError(f"Missing config keys: {missing}")

    def _required_keys(self) -> list:
        return ["enabled"]

    def process(self, data: dict) -> dict:
        """Process data through the handler."""
        if not self._initialized:
            self.initialize()
        result = self._transform(data)
        self._cache[data.get("id", "default")] = result
        return result

    def _transform(self, data: dict) -> dict:
        """Apply transformation to input data."""
        return {"status": "processed", "data": data, "handler": self.__class__.__name__}

    def clear_cache(self):
        """Clear the internal cache."""
        self._cache.clear()
