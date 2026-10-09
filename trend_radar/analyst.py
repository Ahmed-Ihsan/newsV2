"""Ask questions about the current news — answered by a Z.AI GLM model.

The model only sees the items Trend Radar collected, numbered [1]..[n], and is told to
answer from them alone and cite the items it used. Uses Z.AI's pay-as-you-go
OpenAI-style chat endpoint; the API key is read from the ZAI_API_KEY environment variable.
"""

import os
import re
from dataclasses import dataclass, field
from typing import Optional

import httpx

from .models import IntelItem

DEFAULT_BASE_URL = "https://api.z.ai/api/paas/v4"
DEFAULT_MODEL = "glm-5.3-flash"
DEFAULT_EFFORT = "low"
API_KEY_ENV = "ZAI_API_KEY"

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
    """Answer questions about a set of collected items using a GLM model."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self.api_key = api_key if api_key is not None else os.environ.get(API_KEY_ENV, "")
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.model = model or DEFAULT_MODEL
        self.reasoning_effort = reasoning_effort or DEFAULT_EFFORT
        self._transport = transport

    @classmethod
    def from_config(cls, config, **kwargs) -> "NewsAnalyst":
        return cls(base_url=config.ai_base_url, model=config.ai_model,
                   reasoning_effort=config.ai_reasoning_effort, **kwargs)

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def ask(self, question: str, items: list[IntelItem]) -> Answer:
        question = (question or "").strip()
        if not question:
            raise AnalystError("Type a question first.")
        if not self.api_key:
            raise AnalystError(
                f"No Z.AI API key found. Set {API_KEY_ENV} in the environment that runs "
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
            "thinking": {"type": "enabled"},
            "reasoning_effort": self.reasoning_effort,
            "max_tokens": 4096,
            "temperature": 0.3,
            "stream": False,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        try:
            with httpx.Client(timeout=TIMEOUT_SECONDS, transport=self._transport) as client:
                resp = client.post(f"{self.base_url}/chat/completions", json=body, headers=headers)
        except httpx.TimeoutException:
            raise AnalystError("Z.AI took too long to answer. Try again, or ask a narrower question.")
        except httpx.HTTPError as e:
            raise AnalystError(f"Couldn't reach Z.AI ({e.__class__.__name__}). Check your connection.")

        if resp.status_code in (401, 403):
            raise AnalystError(f"Z.AI rejected the API key (HTTP {resp.status_code}). Check {API_KEY_ENV}.")
        if resp.status_code == 429:
            raise AnalystError(
                f"Z.AI refused the request (HTTP 429): {_error_message(resp)}. This means either too many "
                f"requests (wait a minute) or no balance on a pay-as-you-go key (check billing at z.ai). "
                f"A Coding Plan key won't work here."
            )
        if resp.status_code >= 400:
            raise AnalystError(f"Z.AI returned HTTP {resp.status_code}: {_error_message(resp)}")

        try:
            data = resp.json()
            choice = data["choices"][0]
            text = (choice["message"].get("content") or "").strip()
        except (ValueError, KeyError, IndexError, TypeError):
            raise AnalystError("Z.AI sent a response Trend Radar couldn't read.")

        finish = choice.get("finish_reason")
        if finish == "sensitive":
            raise AnalystError("Z.AI declined to answer this question (content filter).")
        if not text:
            raise AnalystError("Z.AI returned an empty answer. Try rephrasing the question.")
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
