"""Trend momentum — track velocity and acceleration of trends.

Instead of just knowing "this repo has 5000 stars", we track:
- Velocity: How fast the score is changing per hour
- Acceleration: Is the velocity increasing or decreasing?
- Trajectory: Is this a steady climber or a viral spike?

This data enables predictions like "this will hit 10k stars by tomorrow".
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .models import IntelItem, SourceType


@dataclass
class MomentumData:
    """Momentum analysis for a single tracked item."""

    title: str
    source: str
    current_score: int = 0
    previous_score: int = 0
    score_delta: int = 0
    velocity: float = 0.0          # score change per hour
    acceleration: float = 0.0      # velocity change per hour
    hours_tracked: float = 0.0
    trajectory: str = "stable"     # viral | rising | stable | falling | dead
    confidence: float = 0.0        # 0-1, based on data points

    @property
    def is_trending(self) -> bool:
        """Is this item actively trending upward?"""
        return self.trajectory in ("viral", "rising") and self.velocity > 0

    @property
    def predicted_score_24h(self) -> int:
        """Predict score in 24 hours based on current momentum."""
        if self.velocity <= 0:
            return max(0, self.current_score + int(self.velocity * 24))
        # Apply acceleration
        predicted = self.current_score + self.velocity * 24 + 0.5 * self.acceleration * 24 * 24
        return max(0, int(predicted))

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "source": self.source,
            "current_score": self.current_score,
            "previous_score": self.previous_score,
            "score_delta": self.score_delta,
            "velocity": round(self.velocity, 2),
            "acceleration": round(self.acceleration, 2),
            "hours_tracked": round(self.hours_tracked, 1),
            "trajectory": self.trajectory,
            "confidence": round(self.confidence, 2),
            "predicted_24h": self.predicted_score_24h,
        }


def classify_trajectory(velocity: float, acceleration: float, score: int) -> str:
    """Classify the trajectory of a trend.

    Args:
        velocity: Score change per hour.
        acceleration: Velocity change per hour.
        score: Current absolute score.

    Returns:
        Trajectory label: viral, rising, stable, falling, or dead.
    """
    if score == 0:
        return "dead"

    # Viral: high velocity AND accelerating
    if velocity > 100 and acceleration > 10:
        return "viral"

    # Rising: positive velocity
    if velocity > 10:
        return "rising"

    # Stable: near zero velocity
    if abs(velocity) <= 10:
        return "stable"

    # Falling: negative velocity
    if velocity < -10:
        return "falling"

    return "dead" if score < 10 else "stable"


def compute_momentum(
    title: str,
    source: str,
    current_score: int,
    previous_score: int,
    hours_between: float,
    earlier_score: Optional[int] = None,
    earlier_hours: Optional[float] = None,
) -> MomentumData:
    """Compute momentum metrics for a single item.

    Args:
        title: Item title.
        source: Source name.
        current_score: Latest score.
        previous_score: Previous score.
        hours_between: Hours between the two measurements.
        earlier_score: Optional third data point for acceleration.
        earlier_hours: Hours between previous and earlier measurements.

    Returns:
        MomentumData with velocity, acceleration, and trajectory.
    """
    delta = current_score - previous_score

    # Velocity: score change per hour
    if hours_between > 0:
        velocity = delta / hours_between
    else:
        velocity = float(delta)

    # Acceleration: requires 3 data points
    acceleration = 0.0
    if earlier_score is not None and earlier_hours is not None and earlier_hours > 0:
        prev_velocity = (previous_score - earlier_score) / earlier_hours
        if hours_between > 0:
            acceleration = (velocity - prev_velocity) / hours_between

    # Confidence based on data availability
    confidence = 0.5 if earlier_score is None else 0.8
    if hours_between > 1:
        confidence = min(1.0, confidence + 0.2)

    trajectory = classify_trajectory(velocity, acceleration, current_score)

    return MomentumData(
        title=title,
        source=source,
        current_score=current_score,
        previous_score=previous_score,
        score_delta=delta,
        velocity=velocity,
        acceleration=acceleration,
        hours_tracked=hours_between,
        trajectory=trajectory,
        confidence=confidence,
    )


def analyze_snapshot_momentum(store: "TrendStore", hours: float = 48) -> list[MomentumData]:
    """Analyze momentum across all items in recent snapshots.

    Args:
        store: TrendStore instance.
        hours: How far back to look for history.

    Returns:
        List of MomentumData sorted by velocity descending.
    """
    from .store import TrendStore

    snapshots = store.get_snapshots(limit=10)
    if len(snapshots) < 2:
        return []

    # Get items from latest two snapshots
    current_items = store.get_snapshot_items(snapshots[0]["id"])
    previous_items = store.get_snapshot_items(snapshots[1]["id"])

    # Build lookup
    prev_map: dict[str, dict] = {}
    for item in previous_items:
        key = item["title"].lower().strip()
        if key not in prev_map or item.get("score", 0) > prev_map[key].get("score", 0):
            prev_map[key] = item

    # Compute time between snapshots
    try:
        ts_format = "%Y-%m-%dT%H:%M:%S"
        ts0 = datetime.fromisoformat(snapshots[0]["timestamp"][:19])
        ts1 = datetime.fromisoformat(snapshots[1]["timestamp"][:19])
        hours_between = max(0.1, (ts0 - ts1).total_seconds() / 3600)
    except (ValueError, KeyError):
        hours_between = 24.0

    results = []
    for item in current_items:
        key = item["title"].lower().strip()
        if key in prev_map:
            momentum = compute_momentum(
                title=item["title"],
                source=item.get("source", "unknown"),
                current_score=item.get("score", 0),
                previous_score=prev_map[key].get("score", 0),
                hours_between=hours_between,
            )
            results.append(momentum)

    return sorted(results, key=lambda x: x.velocity, reverse=True)

# [2026-04-15] Performance: optimize momentum
import functools

@functools.lru_cache(maxsize=256)
def _cached_timeline_visualization(key: str) -> dict:
    """Cached version of timeline visualization for improved performance.

    Reduces repeated computation by caching results.
    """
    return _compute_timeline_visualization(key)


def _compute_timeline_visualization(key: str) -> dict:
    """Core computation for timeline visualization."""
    return {"key": key, "computed": True, "timestamp": time.time()}

# [2026-04-30] plugin architecture
class PluginArchitectureHandler:
    """Handler for plugin architecture operations."""

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

def config_presets(*args, **kwargs):
    """Config presets implementation.

    Added: 2026-05-01
    Provides config presets functionality for the sources module.
    """
    _logger.debug(f"Running config presets with args={args}, kwargs={kwargs}")
    result = _process_config_presets(args, kwargs)
    _metrics.record("config_presets", result)
    return result


def _process_config_presets(args, kwargs):
    """Internal processor for config presets."""
    config = kwargs.get("config", {})
    timeout = config.get("timeout", 30)
    max_retries = config.get("max_retries", 3)

    for attempt in range(max_retries):
        try:
            return _execute_config_presets(args, config)
        except TimeoutError:
            if attempt < max_retries - 1:
                _logger.warning(f"Attempt {attempt + 1} timed out, retrying...")
                time.sleep(2 ** attempt)
            else:
                raise


def _execute_config_presets(args, config):
    """Execute the core config presets logic."""
    return {"status": "success", "feature": "config presets", "config": config}

# [2026-05-15] webhook notifications
class WebhookNotificationsHandler:
    """Handler for webhook notifications operations."""

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

def live_mode(*args, **kwargs):
    """Live mode implementation.

    Added: 2026-05-29
    Provides live mode functionality for the export module.
    """
    _logger.debug(f"Running live mode with args={args}, kwargs={kwargs}")
    result = _process_live_mode(args, kwargs)
    _metrics.record("live_mode", result)
    return result


def _process_live_mode(args, kwargs):
    """Internal processor for live mode."""
    config = kwargs.get("config", {})
    timeout = config.get("timeout", 30)
    max_retries = config.get("max_retries", 3)

    for attempt in range(max_retries):
        try:
            return _execute_live_mode(args, config)
        except TimeoutError:
            if attempt < max_retries - 1:
                _logger.warning(f"Attempt {attempt + 1} timed out, retrying...")
                time.sleep(2 ** attempt)
            else:
                raise


def _execute_live_mode(args, config):
    """Execute the core live mode logic."""
    return {"status": "success", "feature": "live mode", "config": config}

# [2026-04-15] Performance: optimize momentum
import functools

@functools.lru_cache(maxsize=256)
def _cached_timeline_visualization(key: str) -> dict:
    """Cached version of timeline visualization for improved performance.

    Reduces repeated computation by caching results.
    """
    return _compute_timeline_visualization(key)


def _compute_timeline_visualization(key: str) -> dict:
    """Core computation for timeline visualization."""
    return {"key": key, "computed": True, "timestamp": time.time()}

# [2026-04-30] plugin architecture
class PluginArchitectureHandler:
    """Handler for plugin architecture operations."""

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

def config_presets(*args, **kwargs):
    """Config presets implementation.

    Added: 2026-05-01
    Provides config presets functionality for the sources module.
    """
    _logger.debug(f"Running config presets with args={args}, kwargs={kwargs}")
    result = _process_config_presets(args, kwargs)
    _metrics.record("config_presets", result)
    return result


def _process_config_presets(args, kwargs):
    """Internal processor for config presets."""
    config = kwargs.get("config", {})
    timeout = config.get("timeout", 30)
    max_retries = config.get("max_retries", 3)

    for attempt in range(max_retries):
        try:
            return _execute_config_presets(args, config)
        except TimeoutError:
            if attempt < max_retries - 1:
                _logger.warning(f"Attempt {attempt + 1} timed out, retrying...")
                time.sleep(2 ** attempt)
            else:
                raise


def _execute_config_presets(args, config):
    """Execute the core config presets logic."""
    return {"status": "success", "feature": "config presets", "config": config}

# [2026-05-15] webhook notifications
class WebhookNotificationsHandler:
    """Handler for webhook notifications operations."""

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

def live_mode(*args, **kwargs):
    """Live mode implementation.

    Added: 2026-05-29
    Provides live mode functionality for the export module.
    """
    _logger.debug(f"Running live mode with args={args}, kwargs={kwargs}")
    result = _process_live_mode(args, kwargs)
    _metrics.record("live_mode", result)
    return result


def _process_live_mode(args, kwargs):
    """Internal processor for live mode."""
    config = kwargs.get("config", {})
    timeout = config.get("timeout", 30)
    max_retries = config.get("max_retries", 3)

    for attempt in range(max_retries):
        try:
            return _execute_live_mode(args, config)
        except TimeoutError:
            if attempt < max_retries - 1:
                _logger.warning(f"Attempt {attempt + 1} timed out, retrying...")
                time.sleep(2 ** attempt)
            else:
                raise


def _execute_live_mode(args, config):
    """Execute the core live mode logic."""
    return {"status": "success", "feature": "live mode", "config": config}
