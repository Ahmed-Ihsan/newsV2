"""Tests for the Z.AI-backed news analyst (no network: httpx.MockTransport)."""

import json
from types import SimpleNamespace

import httpx
import pytest

from trend_radar.analyst import (
    AnalystError,
    NewsAnalyst,
    build_context,
    extract_citations,
)
from trend_radar.models import IntelItem, SourceType, TrendSnapshot


def _items():
    return [
        IntelItem(title="anthropic/claude-code", source=SourceType.GITHUB, url="https://github.com/a/b",
                  description="<p>Agentic coding <b>tool</b></p>", score=31000, repo_language="Python"),
        IntelItem(title="Show HN: A tiny vector DB", source=SourceType.HACKERNEWS,
                  url="https://news.ycombinator.com/item?id=1", score=420),
        IntelItem(title="Feed post", source=SourceType.RSS, url="https://example.com/post", score=0),
    ]


def _reply(content, finish="stop", status=200, model="glm-5.3"):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content)
        if status != 200:
            return httpx.Response(status, json={"error": {"message": "nope"}})
        return httpx.Response(200, json={
            "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": finish}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        })

    return httpx.MockTransport(handler), captured


def test_build_context_numbers_items_and_strips_html():
    ctx = build_context(_items())
    assert ctx.startswith("[1] (github) anthropic/claude-code | score 31000 | Python")
    assert "Agentic coding tool" in ctx and "<b>" not in ctx
    assert "[3] (rss) Feed post" in ctx and "score 0" not in ctx


def test_extract_citations_dedupes_and_bounds():
    assert extract_citations("A [2] and [1][2], not [9] or [0].", 3) == [2, 1]


def test_ask_sends_question_and_parses_answer():
    transport, captured = _reply("Claude Code leads on GitHub [1], with a vector DB on HN [2].")
    analyst = NewsAnalyst(api_key="k", base_url="https://api.z.ai/api/paas/v4/", model="glm-5.3", transport=transport)
    answer = analyst.ask("What's big?", _items())

    assert captured["url"] == "https://api.z.ai/api/paas/v4/chat/completions"
    assert captured["auth"] == "Bearer k"
    assert captured["body"]["model"] == "glm-5.3"
    assert captured["body"]["reasoning_effort"] == "low"
    assert captured["body"]["thinking"] == {"type": "enabled"}
    assert captured["body"]["messages"][0]["role"] == "system"
    assert "Question: What's big?" in captured["body"]["messages"][1]["content"]
    assert answer.cited == [1, 2]
    assert answer.to_dict()["items"][0]["title"] == "anthropic/claude-code"
    assert answer.usage["total_tokens"] == 120


def test_gemini_provider_uses_openai_endpoint_without_thinking(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    transport, captured = _reply("From Gemini [1].", model="gemini-2.5-flash")
    analyst = NewsAnalyst(provider="gemini", api_key="g", transport=transport)
    assert analyst.key_env == "GEMINI_API_KEY"
    assert analyst.model == "gemini-2.5-flash"
    analyst.ask("q", _items())
    assert captured["url"] == "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    assert captured["auth"] == "Bearer g"
    assert "thinking" not in captured["body"]           # Gemini rejects unknown fields
    assert captured["body"]["reasoning_effort"] == "low"


def test_gemini_missing_key_names_gemini_env(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(AnalystError, match="GEMINI_API_KEY"):
        NewsAnalyst(provider="gemini").ask("q", _items())


def test_unknown_provider_falls_back_to_default():
    assert NewsAnalyst(provider="nope").key_env == "ZAI_API_KEY"


def test_ask_without_key_explains_setup(monkeypatch):
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    with pytest.raises(AnalystError, match="ZAI_API_KEY"):
        NewsAnalyst().ask("q", _items())


def test_ask_reads_key_from_env(monkeypatch):
    monkeypatch.setenv("ZAI_API_KEY", "env-key")
    assert NewsAnalyst().configured


@pytest.mark.parametrize("status,match", [(401, "rejected the API key"), (429, r"HTTP 429\): nope"), (500, "HTTP 500: nope")])
def test_ask_maps_http_errors(status, match):
    transport, _ = _reply("", status=status)
    with pytest.raises(AnalystError, match=match):
        NewsAnalyst(api_key="k", transport=transport).ask("q", _items())


@pytest.mark.parametrize("payload", [
    [{"error": {"message": "bad model", "code": 404}}],   # Gemini sometimes wraps in a list
    {"error": "flat string error"},
    {"error": {"status": "RESOURCE_EXHAUSTED"}},
])
def test_ask_handles_non_dict_error_bodies(payload):
    def handler(request):
        return httpx.Response(400, json=payload)
    with pytest.raises(AnalystError) as exc:
        NewsAnalyst(api_key="k", transport=httpx.MockTransport(handler)).ask("q", _items())
    assert "HTTP 400" in str(exc.value)   # formats instead of crashing on a list/str body


def test_ask_flags_truncated_and_filtered_answers():
    transport, _ = _reply("Partial answer", finish="length")
    assert "cut off" in NewsAnalyst(api_key="k", transport=transport).ask("q", _items()).text
    transport, _ = _reply("", finish="sensitive")
    with pytest.raises(AnalystError, match="declined"):
        NewsAnalyst(api_key="k", transport=transport).ask("q", _items())


def test_ask_rejects_empty_question_and_no_items():
    analyst = NewsAnalyst(api_key="k")
    with pytest.raises(AnalystError, match="question"):
        analyst.ask("  ", _items())
    with pytest.raises(AnalystError, match="no collected items"):
        analyst.ask("q", [])


# ---- Web endpoints ----

class _FakeRadar:
    config = SimpleNamespace(translate_enabled=False, translate_target="ar",
                             ai_provider="zai", ai_base_url="", ai_model="",
                             ai_reasoning_effort="low")
    sources = ["github"]

    def collect(self, sources=None, limit=15, save=False, translate=None):
        return TrendSnapshot(items=_items(), sources_queried=["github", "hackernews", "rss"])


def _client():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from trend_radar.web import create_app
    return TestClient(create_app(radar=_FakeRadar()))


def test_ask_status_reports_configuration(monkeypatch):
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    data = _client().get("/api/ask/status").json()
    assert data["configured"] is False
    assert data["model"] == "glm-5.3-flash"
    assert data["provider"] == "Z.AI"
    assert data["key_env"] == "ZAI_API_KEY"


def test_ask_endpoint_without_key_returns_503(monkeypatch):
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    resp = _client().post("/api/ask", json={"question": "hi"})
    assert resp.status_code == 503
    assert "ZAI_API_KEY" in resp.json()["error"]


def test_ask_endpoint_returns_answer(monkeypatch):
    monkeypatch.setenv("ZAI_API_KEY", "k")
    transport, _ = _reply("See [2].")
    real_init = NewsAnalyst.__init__

    def init_with_transport(self, *args, **kwargs):
        kwargs["transport"] = transport
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(NewsAnalyst, "__init__", init_with_transport)
    resp = _client().post("/api/ask", json={"question": "What's on HN?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "See [2]." and body["cited"] == [2]
    assert len(body["items"]) == 3


def test_dashboard_has_ask_view():
    from trend_radar.web import _dashboard_html
    html = _dashboard_html()
    assert "btnAsk" in html and "/api/ask" in html
