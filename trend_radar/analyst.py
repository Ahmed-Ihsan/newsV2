"""Ask questions about the current news — answered by an AI model.

The model only sees the items Trend Radar collected, numbered [1]..[n], and is told to
answer from them alone and cite the items it used. Talks to any provider with an
OpenAI-style /chat/completions endpoint (Z.AI GLM or Google Gemini). The API key is
never stored in code or config — it is read from the provider's environment variable.
"""

import os
import re
from dataclasses import dataclass, field
from typing import Optional

import httpx

from .models import IntelItem

# Each provider exposes an OpenAI-compatible /chat/completions endpoint with Bearer auth.
# `thinking` is a Z.AI extension; Gemini's OpenAI layer rejects unknown fields, so it is
# sent only where the provider supports it. Both accept `reasoning_effort`.
PROVIDERS = {
    "zai": {
        "label": "Z.AI",
        "base_url": "https://api.z.ai/api/paas/v4",
        "key_env": "ZAI_API_KEY",
        "model": "glm-5.3-flash",
        "thinking": True,
        "key_help": "a pay-as-you-go key from your Z.AI account (the GLM Coding Plan key won't work here)",
    },
    "gemini": {
        "label": "Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "key_env": "GEMINI_API_KEY",
        "model": "gemini-2.5-flash",
        "thinking": False,
        "key_help": "a key from Google AI Studio (aistudio.google.com/apikey)",
    },
}

DEFAULT_PROVIDER = "zai"
DEFAULT_EFFORT = "low"
API_KEY_ENV = "ZAI_API_KEY"  # kept for backward compatibility with older imports

MAX_ITEMS = 150          # keep the prompt bounded
DESC_CHARS = 280         # per-item description budget
TIMEOUT_SECONDS = 120.0

SYSTEM_PROMPT = """You are a technology news analyst inside Trend Radar, a tool that collects \
trending items from GitHub, Hacker News, Reddit, arXiv, RSS feeds, Product Hunt and similar sources.

You get a numbered list of the items collected right now, then a question from the user.

How to answer:
- Use only the listed items. If they don't cover the question, say so plainly and mention \
the closest related items, if any. Never invent stories, numbers, or links.
- Cite the items you rely on with their numbers in square brackets, like [3] or [3][7], \
right after the claim they support.
- Scores are only comparable within the same source (GitHub stars, HN points, Reddit upvotes).
- Lead with the direct answer, then the supporting detail. Prefer short paragraphs; use "- " \
bullets only for lists of several distinct items. No headings, no tables.
- Answer in the same language as the question."""


class AnalystError(Exception):
    """A problem the user can act on (missing key, API error, bad response)."""


@dataclass
class Answer:
    question: str
    text: str
    model: str
    cited: list[int] = field(default_factory=list)   # 1-based item numbers the model cited
    items: list[IntelItem] = field(default_factory=list)
    usage: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "answer": self.text,
            "model": self.model,
            "cited": self.cited,
            "items": [i.to_dict() for i in self.items],
            "usage": self.usage,
        }


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def build_context(items: list[IntelItem]) -> str:
    """Render items as a compact numbered list for the prompt."""
    lines = []
    for n, item in enumerate(items, 1):
        parts = [f"[{n}] ({item.source.value}) {_clean(item.title)}"]
        if item.score:
            parts.append(f"score {item.score}")
        if item.repo_language:
            parts.append(item.repo_language)
        line = " | ".join(parts)
        desc = _clean(item.description)
        if desc:
            line += f"\n    {desc[:DESC_CHARS]}"
        lines.append(line)
    return "\n".join(lines)


def extract_citations(text: str, item_count: int) -> list[int]:
    """Item numbers cited as [n], in first-seen order, limited to valid numbers."""
    seen: list[int] = []
    for m in re.finditer(r"\[(\d{1,4})\]", text):
        n = int(m.group(1))
        if 1 <= n <= item_count and n not in seen:
            seen.append(n)
    return seen


class NewsAnalyst:
    """Answer questions about a set of collected items using an AI model.

    `provider` picks the defaults (endpoint, model, key env var); any of them can be
    overridden. The key is read from the provider's env var unless passed explicitly.
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self.provider = (provider or DEFAULT_PROVIDER).strip().lower()
        spec = PROVIDERS.get(self.provider, PROVIDERS[DEFAULT_PROVIDER])
        self.label = spec["label"]
        self.key_env = spec["key_env"]
        self.key_help = spec["key_help"]
        self._send_thinking = spec["thinking"]
        self.api_key = api_key if api_key is not None else os.environ.get(self.key_env, "")
        self.base_url = (base_url or spec["base_url"]).rstrip("/")
        self.model = model or spec["model"]
        self.reasoning_effort = reasoning_effort or DEFAULT_EFFORT
        self._transport = transport

    @classmethod
    def from_config(cls, config, **kwargs) -> "NewsAnalyst":
        return cls(
            provider=getattr(config, "ai_provider", DEFAULT_PROVIDER),
            base_url=getattr(config, "ai_base_url", "") or None,
            model=getattr(config, "ai_model", "") or None,
            reasoning_effort=getattr(config, "ai_reasoning_effort", DEFAULT_EFFORT),
            **kwargs,
        )

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def ask(self, question: str, items: list[IntelItem]) -> Answer:
        question = (question or "").strip()
        if not question:
            raise AnalystError("Type a question first.")
        if not self.api_key:
            raise AnalystError(
                f"No {self.label} API key found. Set {self.key_env} in the environment that runs "
                "Trend Radar, then restart it."
            )
        if not items:
            raise AnalystError("There are no collected items to analyze yet. Fetch trends first.")

        items = items[:MAX_ITEMS]
        prompt = f"Collected items ({len(items)}):\n\n{build_context(items)}\n\nQuestion: {question}"
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "reasoning_effort": self.reasoning_effort,
            "max_tokens": 4096,
            "temperature": 0.3,
            "stream": False,
        }
        if self._send_thinking:
            body["thinking"] = {"type": "enabled"}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        try:
            with httpx.Client(timeout=TIMEOUT_SECONDS, transport=self._transport) as client:
                resp = client.post(f"{self.base_url}/chat/completions", json=body, headers=headers)
        except httpx.TimeoutException:
            raise AnalystError(f"{self.label} took too long to answer. Try again, or ask a narrower question.")
        except httpx.HTTPError as e:
            raise AnalystError(f"Couldn't reach {self.label} ({e.__class__.__name__}). Check your connection.")

        if resp.status_code in (401, 403):
            raise AnalystError(f"{self.label} rejected the API key (HTTP {resp.status_code}). Check {self.key_env}.")
        if resp.status_code == 429:
            raise AnalystError(
                f"{self.label} refused the request (HTTP 429): {_error_message(resp)}. You're either sending "
                f"too many requests (wait a minute) or out of quota/balance — check your {self.label} account."
            )
        if resp.status_code >= 400:
            raise AnalystError(f"{self.label} returned HTTP {resp.status_code}: {_error_message(resp)}")

        try:
            data = resp.json()
            choice = data["choices"][0]
            text = (choice["message"].get("content") or "").strip()
        except (ValueError, KeyError, IndexError, TypeError):
            raise AnalystError(f"{self.label} sent a response Trend Radar couldn't read.")

        finish = choice.get("finish_reason")
        if finish in ("sensitive", "content_filter"):
            raise AnalystError(f"{self.label} declined to answer this question (content filter).")
        if not text:
            raise AnalystError(f"{self.label} returned an empty answer. Try rephrasing the question.")
        if finish == "length":
            text += "\n\n(The answer was cut off at the length limit.)"

        cited = extract_citations(text, len(items))
        return Answer(
            question=question,
            text=text,
            model=data.get("model", self.model),
            cited=cited,
            items=items,
            usage=data.get("usage", {}) or {},
        )


def _error_message(resp: httpx.Response) -> str:
    try:
        err = resp.json().get("error", {})
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])[:300]
    except ValueError:
        pass
    return resp.text[:300] or "no details"
