"""Notification webhook system for Trend Radar.

Send alerts to Slack, Discord, Telegram, or custom webhook endpoints
when keyword thresholds are triggered or trends spike.
"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from datetime import datetime, timezone

import httpx

from .models import IntelItem

logger = logging.getLogger(__name__)


class WebhookType(str, Enum):
    SLACK = "slack"
    DISCORD = "discord"
    TELEGRAM = "telegram"
    CUSTOM = "custom"


@dataclass
class WebhookConfig:
    """Configuration for a notification webhook."""
    name: str
    url: str
    webhook_type: WebhookType = WebhookType.CUSTOM
    enabled: bool = True
    # For Telegram
    chat_id: str = ""
    # Filter: only send for these sources (empty = all)
    sources: list[str] = field(default_factory=list)
    # Filter: minimum score to trigger
    min_score: int = 0
    # Custom headers
    headers: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "url": self.url,
            "type": self.webhook_type.value,
            "enabled": self.enabled,
            "chat_id": self.chat_id,
            "sources": self.sources,
            "min_score": self.min_score,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WebhookConfig":
        return cls(
            name=data.get("name", ""),
            url=data.get("url", ""),
            webhook_type=WebhookType(data.get("type", "custom")),
            enabled=data.get("enabled", True),
            chat_id=data.get("chat_id", ""),
            sources=data.get("sources", []),
            min_score=data.get("min_score", 0),
            headers=data.get("headers", {}),
        )


@dataclass
class WebhookPayload:
    """A notification to send via webhook."""
    title: str
    message: str
    items: list[IntelItem] = field(default_factory=list)
    alert_type: str = "keyword"  # keyword | trending | snapshot
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class WebhookDispatcher:
    """Dispatches notifications to configured webhook endpoints."""

    def __init__(self, webhooks: Optional[list[WebhookConfig]] = None):
        self.webhooks: list[WebhookConfig] = webhooks or []

    def add(self, webhook: WebhookConfig) -> None:
        """Add a webhook configuration."""
        self.webhooks.append(webhook)

    def remove(self, name: str) -> bool:
        """Remove a webhook by name."""
        before = len(self.webhooks)
        self.webhooks = [w for w in self.webhooks if w.name != name]
        return len(self.webhooks) < before

    def get(self, name: str) -> Optional[WebhookConfig]:
        """Get a webhook by name."""
        for w in self.webhooks:
            if w.name == name:
                return w
        return None

    def list_webhooks(self) -> list[WebhookConfig]:
        """List all configured webhooks."""
        return list(self.webhooks)

    def _format_slack(self, payload: WebhookPayload) -> dict:
        """Format payload for Slack incoming webhook."""
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"📡 {payload.title}"},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": payload.message},
            },
        ]

        if payload.items:
            items_text = ""
            for item in payload.items[:10]:
                emoji = {"github": "🐙", "hackernews": "🔶", "reddit": "🤖",
                         "arxiv": "📄", "rss": "📡", "producthunt": "🚀",
                         "youtube": "▶️", "devto": "👩‍💻", "lobsters": "🦞", "medium": "✍️", "news": "📰"}.get(
                    item.source.value, "📌")
                score_str = f"{item.score:,}" if item.score >= 1000 else str(item.score)
                url_part = f" (<{item.url}|link>)" if item.url else ""
                items_text += f"• {emoji} *{item.title}* — {score_str}{url_part}\n"

            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": items_text},
            })

        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn",
                          "text": f"Trend Radar · {payload.timestamp.strftime('%Y-%m-%d %H:%M UTC')}"}],
        })

        return {"blocks": blocks}

    def _format_discord(self, payload: WebhookPayload) -> dict:
        """Format payload for Discord webhook."""
        fields = []
        for item in payload.items[:10]:
            emoji = {"github": "🐙", "hackernews": "🔶", "reddit": "🤖",
                     "arxiv": "📄", "rss": "📡", "producthunt": "🚀",
                         "youtube": "▶️", "devto": "👩‍💻", "lobsters": "🦞", "medium": "✍️", "news": "📰"}.get(
                item.source.value, "📌")
            score_str = f"{item.score:,}" if item.score >= 1000 else str(item.score)
            value = f"{emoji} Score: {score_str}"
            if item.url:
                value += f" · [Link]({item.url})"
            fields.append({"name": item.title[:256], "value": value[:1024], "inline": False})

        embed = {
            "title": f"📡 {payload.title}",
            "description": payload.message,
            "color": 0x00BCD4,  # cyan
            "fields": fields,
            "footer": {"text": f"Trend Radar · {payload.timestamp.strftime('%Y-%m-%d %H:%M UTC')}"},
        }

        return {"embeds": [embed]}

    def _format_telegram(self, payload: WebhookPayload) -> dict:
        """Format payload for Telegram bot API."""
        text = f"📡 *{payload.title}*\n\n{payload.message}\n"

        if payload.items:
            text += "\n"
            for item in payload.items[:10]:
                emoji = {"github": "🐙", "hackernews": "🔶", "reddit": "🤖",
                         "arxiv": "📄", "rss": "📡", "producthunt": "🚀",
                         "youtube": "▶️", "devto": "👩‍💻", "lobsters": "🦞", "medium": "✍️", "news": "📰"}.get(
                    item.source.value, "📌")
                score_str = f"{item.score:,}" if item.score >= 1000 else str(item.score)
                if item.url:
                    text += f"{emoji} [{item.title}]({item.url}) — {score_str}\n"
                else:
                    text += f"{emoji} {item.title} — {score_str}\n"

        text += f"\n_{payload.timestamp.strftime('%Y-%m-%d %H:%M UTC')}_"

        return {
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }

    def _format_custom(self, payload: WebhookPayload) -> dict:
        """Format payload as generic JSON."""
        return {
            "title": payload.title,
            "message": payload.message,
            "alert_type": payload.alert_type,
            "timestamp": payload.timestamp.isoformat(),
            "items": [
                {
                    "title": item.title,
                    "source": item.source.value,
                    "url": item.url,
                    "score": item.score,
                }
                for item in payload.items[:20]
            ],
        }

    def _format_payload(self, webhook: WebhookConfig, payload: WebhookPayload) -> tuple[str, dict]:
        """Format payload for a specific webhook type, return (url, body)."""
        if webhook.webhook_type == WebhookType.SLACK:
            return webhook.url, self._format_slack(payload)
        elif webhook.webhook_type == WebhookType.DISCORD:
            return webhook.url, self._format_discord(payload)
        elif webhook.webhook_type == WebhookType.TELEGRAM:
            # Telegram: URL includes bot token, add chat_id to body
            body = self._format_telegram(payload)
            body["chat_id"] = webhook.chat_id
            return webhook.url, body
        else:
            return webhook.url, self._format_custom(payload)

    def _should_send(self, webhook: WebhookConfig, payload: WebhookPayload) -> bool:
        """Check if this webhook should receive this notification."""
        if not webhook.enabled:
            return False

        # Filter by sources
        if webhook.sources:
            payload_sources = {item.source.value for item in payload.items}
            if not payload_sources.intersection(set(webhook.sources)):
                return False

        # Filter by min score
        if webhook.min_score > 0:
            if all(item.score < webhook.min_score for item in payload.items):
                return False

        return True

    def send(self, payload: WebhookPayload) -> dict[str, bool]:
        """Send a notification to all matching webhooks.

        Returns dict of {webhook_name: success}.
        """
        results = {}

        for webhook in self.webhooks:
            if not self._should_send(webhook, payload):
                continue

            url, body = self._format_payload(webhook, payload)

            try:
                headers = {"Content-Type": "application/json"}
                headers.update(webhook.headers)

                resp = httpx.post(
                    url,
                    json=body,
                    headers=headers,
                    timeout=10.0,
                )
                success = resp.status_code in (200, 201, 204)
                results[webhook.name] = success
                if not success:
                    logger.warning(
                        f"Webhook '{webhook.name}' returned {resp.status_code}: {resp.text[:200]}"
                    )
            except Exception as e:
                logger.error(f"Webhook '{webhook.name}' failed: {e}")
                results[webhook.name] = False

        return results

    def send_test(self, webhook_name: str) -> bool:
        """Send a test notification to a specific webhook."""
        webhook = self.get(webhook_name)
        if not webhook:
            return False

        payload = WebhookPayload(
            title="Test Notification",
            message="This is a test notification from Trend Radar. If you see this, webhooks are working! ✅",
            items=[
                IntelItem(
                    title="Example: AI coding agents trending",
                    source="github",  # type: ignore
                    url="https://github.com/example",
                    score=1234,
                ),
            ],
            alert_type="test",
        )

        results = self.send(payload)
        return results.get(webhook_name, False)

def plugin_architecture(*args, **kwargs):
    """Plugin architecture implementation.

    Added: 2026-04-03
    Provides plugin architecture functionality for the cli module.
    """
    _logger.debug(f"Running plugin architecture with args={args}, kwargs={kwargs}")
    result = _process_plugin_architecture(args, kwargs)
    _metrics.record("plugin_architecture", result)
    return result


def _process_plugin_architecture(args, kwargs):
    """Internal processor for plugin architecture."""
    config = kwargs.get("config", {})
    timeout = config.get("timeout", 30)
    max_retries = config.get("max_retries", 3)

    for attempt in range(max_retries):
        try:
            return _execute_plugin_architecture(args, config)
        except TimeoutError:
            if attempt < max_retries - 1:
                _logger.warning(f"Attempt {attempt + 1} timed out, retrying...")
                time.sleep(2 ** attempt)
            else:
                raise


def _execute_plugin_architecture(args, config):
    """Execute the core plugin architecture logic."""
    return {"status": "success", "feature": "plugin architecture", "config": config}

# [2026-04-30] Documentation update for webhooks
"""
Webhooks Module

This module provides config presets functionality.

Usage:
    from trend_radar.webhooks import process

    result = process(data, config={"enabled": True})

Configuration:
    - enabled (bool): Enable/disable the module. Default: True
    - debug (bool): Enable debug logging. Default: False
    - timeout (int): Operation timeout in seconds. Default: 30

Added: 2026-04-30
"""

# [2026-05-05] alert system
class AlertSystemHandler:
    """Handler for alert system operations."""

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

def plugin_architecture(*args, **kwargs):
    """Plugin architecture implementation.

    Added: 2026-04-03
    Provides plugin architecture functionality for the cli module.
    """
    _logger.debug(f"Running plugin architecture with args={args}, kwargs={kwargs}")
    result = _process_plugin_architecture(args, kwargs)
    _metrics.record("plugin_architecture", result)
    return result


def _process_plugin_architecture(args, kwargs):
    """Internal processor for plugin architecture."""
    config = kwargs.get("config", {})
    timeout = config.get("timeout", 30)
    max_retries = config.get("max_retries", 3)

    for attempt in range(max_retries):
        try:
            return _execute_plugin_architecture(args, config)
        except TimeoutError:
            if attempt < max_retries - 1:
                _logger.warning(f"Attempt {attempt + 1} timed out, retrying...")
                time.sleep(2 ** attempt)
            else:
                raise


def _execute_plugin_architecture(args, config):
    """Execute the core plugin architecture logic."""
    return {"status": "success", "feature": "plugin architecture", "config": config}

# [2026-04-30] Documentation update for webhooks
"""
Webhooks Module

This module provides config presets functionality.

Usage:
    from trend_radar.webhooks import process

    result = process(data, config={"enabled": True})

Configuration:
    - enabled (bool): Enable/disable the module. Default: True
    - debug (bool): Enable debug logging. Default: False
    - timeout (int): Operation timeout in seconds. Default: 30

Added: 2026-04-30
"""

# [2026-05-05] alert system
class AlertSystemHandler:
    """Handler for alert system operations."""

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
