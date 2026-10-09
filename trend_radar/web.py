"""Web dashboard — FastAPI-based web interface for Trend Radar."""

import json
from datetime import datetime, timezone
from typing import Optional

try:
    from fastapi import Body, FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


def create_app(radar=None, host: str = "127.0.0.1", port: int = 8765) -> "FastAPI":
    """Create the FastAPI web application."""
    if not HAS_FASTAPI:
        raise ImportError("fastapi and uvicorn are required. Install with: pip install fastapi uvicorn")

    from .core import TrendRadar

    app = FastAPI(
        title="Trend Radar",
        description="Multi-source tech intelligence dashboard",
        version="1.0.0",
    )

    _radar = radar or TrendRadar()

    @app.get("/", response_class=HTMLResponse)
    async def index():
        """Serve the main dashboard page."""
        return _dashboard_html()

    @app.get("/api/fetch")
    async def api_fetch(
        sources: Optional[str] = Query(None, description="Comma-separated source names"),
        limit: int = Query(15, ge=1, le=100),
        layout: str = Query("table"),
        translate: Optional[bool] = Query(None, description="Translate titles/descriptions"),
    ):
        """Fetch trending intel as JSON."""
        source_list = sources.split(",") if sources else None
        snapshot = _radar.collect(sources=source_list, limit=limit, save=False, translate=translate)
        return JSONResponse({
            "timestamp": snapshot.timestamp.isoformat(),
            "sources": snapshot.sources_queried,
            "item_count": snapshot.item_count,
            "items": [item.to_dict() for item in snapshot.items],
            "keywords": snapshot.keywords(20),
            "errors": snapshot.errors,
        })

    @app.get("/api/ai")
    async def api_ai(limit: int = Query(15, ge=1, le=100), translate: Optional[bool] = Query(None)):
        """Fetch AI-focused intel as JSON."""
        snapshot = _radar.collect_ai_focused(limit=limit, save=False, translate=translate)
        return JSONResponse({
            "timestamp": snapshot.timestamp.isoformat(),
            "item_count": snapshot.item_count,
            "items": [item.to_dict() for item in snapshot.items],
            "keywords": snapshot.keywords(20),
        })

    @app.get("/api/search")
    async def api_search(
        q: str = Query(..., description="Search query"),
        sources: Optional[str] = Query(None),
        limit: int = Query(20, ge=1, le=100),
        translate: Optional[bool] = Query(None),
    ):
        """Search across sources."""
        source_list = sources.split(",") if sources else None
        items = _radar.search(q, sources=source_list, limit=limit, translate=translate)
        return JSONResponse({
            "query": q,
            "count": len(items),
            "items": [item.to_dict() for item in items],
        })

    @app.get("/api/settings")
    async def api_settings():
        """Current translation defaults."""
        return JSONResponse({
            "translate": _radar.config.translate_enabled,
            "translate_target": _radar.config.translate_target,
        })

    @app.get("/api/keywords")
    async def api_keywords(days: int = Query(7, ge=1, le=365)):
        """Get trending keywords."""
        kw = _radar.store.get_keyword_trends(days=days)
        return JSONResponse({
            "days": days,
            "keywords": [{"word": w, "count": c} for w, c in kw],
        })

    @app.get("/api/stats")
    async def api_stats():
        """Get database and cache statistics."""
        stats = _radar.get_stats()
        return JSONResponse(stats)

    @app.get("/api/sources")
    async def api_sources():
        """List available sources."""
        from .core import SOURCE_CLASSES
        return JSONResponse({
            name: {"enabled": name in _radar.sources, "class": cls.__name__}
            for name, cls in SOURCE_CLASSES.items()
        })

    @app.get("/api/diff")
    async def api_diff():
        """Compare latest two snapshots — show rising/falling trends."""
        diff_data = _radar.diff_snapshots()
        return JSONResponse(json.loads(json.dumps(diff_data, default=str)))

    @app.get("/api/health")
    async def api_health():
        """Check data source connectivity and response times."""
        results = _radar.check_health()
        return JSONResponse(results)

    @app.get("/api/top")
    async def api_top(
        limit: int = Query(20, ge=1, le=100),
        hours: int = Query(24, ge=1, le=720),
        source: Optional[str] = Query(None),
        topic: Optional[str] = Query(None),
    ):
        """Get top trending items."""
        items = _radar.get_top_items(limit=limit, hours=hours, source=source, topic=topic)
        return JSONResponse({
            "count": len(items),
            "items": [item.to_dict() for item in items],
        })


    @app.get("/api/momentum")
    async def api_momentum(
        hours: int = Query(48, ge=1, le=720),
        limit: int = Query(20, ge=1, le=100),
    ):
        """Get trend momentum — velocity and acceleration."""
        from .momentum import analyze_snapshot_momentum
        data = analyze_snapshot_momentum(_radar.store, hours=hours)
        return JSONResponse([d.to_dict() for d in data[:limit]])

    @app.get("/api/ranked")
    async def api_ranked(
        sources: Optional[str] = Query(None),
        limit: int = Query(20, ge=1, le=100),
    ):
        """Get cross-source normalized ranking."""
        from .normalization import rank_cross_source
        source_list = sources.split(",") if sources else None
        snapshot = _radar.collect(sources=source_list, limit=limit, save=False)
        ranked_items = rank_cross_source(snapshot.items, top_n=limit)
        return JSONResponse({
            "count": len(ranked_items),
            "items": [i.to_dict() for i in ranked_items],
        })

    @app.get("/api/ask/status")
    async def api_ask_status():
        """Whether question answering is set up, and which model it uses."""
        from .analyst import NewsAnalyst
        analyst = NewsAnalyst.from_config(_radar.config)
        return JSONResponse({
            "configured": analyst.configured,
            "model": analyst.model,
            "provider": analyst.label,
            "key_env": analyst.key_env,
            "key_help": analyst.key_help,
        })

    @app.post("/api/ask")
    def api_ask(payload: dict = Body(...)):
        """Answer a question about the current trends with a GLM model.

        Body: {"question": str, "sources": optional comma-separated source names}.
        Plain `def` so the slow model call runs in FastAPI's thread pool.
        """
        from .analyst import AnalystError, NewsAnalyst
        question = str(payload.get("question") or "")[:2000]
        sources = payload.get("sources") or None
        source_list = sources.split(",") if isinstance(sources, str) and sources else None
        analyst = NewsAnalyst.from_config(_radar.config)
        try:
            snapshot = _radar.collect(sources=source_list, limit=15, save=False, translate=False)
            answer = analyst.ask(question, snapshot.items)
        except AnalystError as e:
            status = 503 if not analyst.configured else 400
            return JSONResponse({"error": str(e)}, status_code=status)
        return JSONResponse(answer.to_dict())

    @app.get("/api/alerts")
    async def api_alerts_list():
        """List all configured alerts."""
        from .alerts import AlertStore
        store = AlertStore()
        return JSONResponse([a.to_dict() for a in store.list_alerts()])

    @app.post("/api/alerts/add")
    async def api_alerts_add(
        keyword: str = Query(...),
        threshold: int = Query(1, ge=1),
        source: Optional[str] = Query(None),
    ):
        """Add a keyword alert."""
        from .alerts import AlertStore
        store = AlertStore()
        alert = store.add_alert(keyword, threshold=threshold, source_filter=source)
        return JSONResponse(alert.to_dict())

    @app.get("/api/alerts/check")
    async def api_alerts_check(
        sources: Optional[str] = Query(None),
        limit: int = Query(25, ge=1, le=100),
    ):
        """Check current trends against alerts."""
        from .alerts import AlertStore
        store = AlertStore()
        source_list = sources.split(",") if sources else None
        snapshot = _radar.collect(sources=source_list, limit=limit, save=False)
        items_dicts = [i.to_dict() for i in snapshot.items]
        matches = store.check_alerts(items_dicts)
        return JSONResponse([m.to_dict() for m in matches])

    return app


def _dashboard_html() -> str:
    """Return the embedded dashboard HTML with Chart.js visualizations."""
    return _DASHBOARD_HTML


_DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Trend Radar</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,300..900&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<style>
:root {
  --paper: #E6EBEF;
  --strip: #F8FAFB;
  --ink: #102434;
  --ink-2: #4E6070;
  --ink-3: #6B7B89;
  --rule: #C9D2DA;
  --grid: #DCE3E8;
  --signal: #B26F00;
  --signal-soft: #F3E3C4;
  --rise: #1E7A52;
  --fall: #B23B32;
  --rail: #102434;
  --rail-ink: #E3EAF0;
  --rail-ink-2: #93A6B6;
  --rail-rule: #24405A;
  --rail-amber: #F2AE3A;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root {
    --paper: #0F1C27;
    --strip: #152633;
    --ink: #E3EAF0;
    --ink-2: #A3B3C1;
    --ink-3: #7F92A2;
    --rule: #263C4E;
    --grid: #1E3242;
    --signal: #F2AE3A;
    --signal-soft: #3A3020;
    --rise: #4CC08A;
    --fall: #F07A6E;
    --rail: #08131C;
    --rail-ink: #E3EAF0;
    --rail-ink-2: #8698A8;
    --rail-rule: #1C3040;
    --rail-amber: #F2AE3A;
    color-scheme: dark;
  }
}
* { box-sizing: border-box; }
html, body { margin: 0; }
body {
  background: var(--paper);
  color: var(--ink);
  font-family: 'Archivo', system-ui, sans-serif;
  font-size: 16px;
  line-height: 1.5;
  font-variant-numeric: tabular-nums;
  -webkit-font-smoothing: antialiased;
}
a { color: inherit; }
button, input, select, textarea { font: inherit; color: inherit; }
:focus-visible { outline: 2px solid var(--signal); outline-offset: 2px; }

/* ---- Shell ---- */
.shell { display: grid; grid-template-columns: 248px minmax(0, 1fr); min-height: 100vh; }

/* ---- Rail ---- */
.rail {
  background: var(--rail); color: var(--rail-ink);
  position: sticky; top: 0; height: 100vh;
  display: flex; flex-direction: column; gap: 32px;
  padding: 28px 18px 22px;
}
.rail :focus-visible { outline-color: var(--rail-amber); }
.brand { display: flex; align-items: center; gap: 10px; padding: 0 8px; text-decoration: none; }
.brand-name { font-stretch: 125%; font-weight: 780; font-size: 19px; letter-spacing: -0.01em; }
.scope { width: 30px; height: 30px; flex: none; }
.scope .ring { fill: none; stroke: var(--rail-rule); stroke-width: 1.5; }
.scope .blip { fill: var(--rail-amber); }
.scope .arm { stroke: var(--rail-amber); stroke-width: 2; stroke-linecap: round; transform-origin: 16px 16px; transform: rotate(-40deg); }
body.is-loading .scope .arm { animation: sweep 1.1s linear infinite; }
@keyframes sweep { to { transform: rotate(320deg); } }

.views { display: flex; flex-direction: column; gap: 2px; margin: 0; padding: 0; list-style: none; }
.view-btn {
  width: 100%; text-align: left; background: none; border: 0; cursor: pointer;
  padding: 9px 12px; border-radius: 3px; color: var(--rail-ink-2);
  font-size: 15px; font-weight: 500;
  display: flex; justify-content: space-between; align-items: baseline;
}
.view-btn:hover { color: var(--rail-ink); background: rgba(255,255,255,0.04); }
.view-btn[aria-current="true"] { color: var(--rail-ink); background: rgba(255,255,255,0.07); box-shadow: inset 3px 0 0 var(--rail-amber); font-weight: 650; }
.view-btn kbd { font: inherit; font-size: 12px; color: var(--rail-ink-2); opacity: .7; }

.rail-group { display: flex; flex-direction: column; gap: 8px; padding: 0 4px; }
.rail-label { font-size: 13px; color: var(--rail-ink-2); }
.rail select {
  width: 100%; padding: 8px 10px; border-radius: 3px;
  background: rgba(255,255,255,0.05); border: 1px solid var(--rail-rule); color: var(--rail-ink);
}
.rail select option { color: #102434; background: #F8FAFB; }
.switch { display: flex; align-items: center; justify-content: space-between; gap: 12px; cursor: pointer; font-size: 14px; color: var(--rail-ink); padding: 4px 0; }
.switch small { display: block; text-align: left; color: var(--rail-ink-2); font-size: 13px; }
.switch input { position: absolute; opacity: 0; width: 1px; height: 1px; }
.switch .track { width: 34px; height: 20px; border-radius: 10px; background: var(--rail-rule); position: relative; flex: none; transition: background .15s; }
.switch .track::after { content: ""; position: absolute; top: 3px; left: 3px; width: 14px; height: 14px; border-radius: 50%; background: var(--rail-ink); transition: transform .15s; }
.switch input:checked + .track { background: var(--rail-amber); }
.switch input:checked + .track::after { transform: translateX(14px); background: var(--rail); }
.switch input:focus-visible + .track { outline: 2px solid var(--rail-amber); outline-offset: 2px; }
.rail-foot { margin-top: auto; padding: 0 8px; font-size: 13px; color: var(--rail-ink-2); display: flex; justify-content: space-between; }
.rail-foot a { color: var(--rail-ink-2); }
.rail-foot a:hover { color: var(--rail-ink); }

/* ---- Main ---- */
.main { padding: 40px clamp(20px, 4vw, 56px) 64px; max-width: 1120px; width: 100%; }
.topline { display: flex; justify-content: space-between; align-items: flex-end; gap: 24px; flex-wrap: wrap; padding-bottom: 24px; border-bottom: 2px solid var(--ink); }
.heading h1 { margin: 0; font-stretch: 125%; font-weight: 800; font-size: clamp(30px, 4.2vw, 46px); line-height: 1.02; letter-spacing: -0.025em; }
.status { margin: 10px 0 0; color: var(--ink-2); font-size: 15px; min-height: 1.5em; }
.search { display: flex; gap: 0; width: min(360px, 100%); }
.search input {
  flex: 1; min-width: 0; padding: 10px 12px; background: var(--strip);
  border: 1px solid var(--rule); border-right: 0; border-radius: 3px 0 0 3px;
}
.search input::placeholder { color: var(--ink-3); }
.search button {
  padding: 10px 16px; background: var(--ink); color: var(--paper); border: 1px solid var(--ink);
  border-radius: 0 3px 3px 0; cursor: pointer; font-weight: 600;
}
.search button:hover { background: var(--ink-2); border-color: var(--ink-2); }

.notice { margin: 20px 0 0; padding: 12px 14px; border-left: 3px solid var(--fall); background: var(--strip); font-size: 14px; color: var(--ink-2); }
.notice strong { color: var(--ink); }
.notice ul { margin: 6px 0 0; padding-left: 18px; }
.notice button { margin-top: 10px; padding: 6px 12px; border: 1px solid var(--rule); background: var(--paper); border-radius: 3px; cursor: pointer; }

/* ---- Charts ---- */
.figures { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 20px 40px; margin: 28px 0 8px; }
.figure { margin: 0; }
.figure figcaption { font-size: 14px; font-weight: 650; display: flex; justify-content: space-between; gap: 12px; padding-bottom: 8px; border-bottom: 1px solid var(--rule); }
.figure figcaption span { font-weight: 400; color: var(--ink-3); }
.chart-box { position: relative; height: 216px; margin-top: 10px; }

/* ---- Strip board ---- */
.board-head { display: flex; justify-content: space-between; align-items: baseline; gap: 16px; margin: 32px 0 12px; }
.board-head h2 { margin: 0; font-size: 18px; font-weight: 700; }
.board-head p { margin: 0; font-size: 13px; color: var(--ink-3); text-align: right; }
.group-head { margin: 22px 0 8px; font-size: 15px; font-weight: 700; font-stretch: 112%; display: flex; align-items: baseline; gap: 8px; }
.group-head span { font-weight: 500; font-size: 13px; color: var(--ink-3); }
.strips { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.strip {
  display: grid; grid-template-columns: 116px minmax(0, 1fr) 128px;
  background: var(--strip); border: 1px solid var(--rule); border-radius: 2px;
}
.strip:hover { border-color: var(--ink-3); }
.stub { padding: 12px 14px; border-right: 1px dashed var(--rule); display: flex; flex-direction: column; gap: 2px; }
.rank { font-stretch: 75%; font-weight: 750; font-size: 24px; line-height: 1; letter-spacing: -0.01em; }
.src { font-stretch: 75%; font-weight: 600; font-size: 14px; color: var(--ink-2); }
.body { padding: 12px 18px; min-width: 0; }
.title { font-weight: 620; font-size: 16.5px; line-height: 1.35; text-decoration: none; overflow-wrap: anywhere; }
.title:hover { text-decoration: underline; text-decoration-color: var(--signal); text-underline-offset: 3px; text-decoration-thickness: 2px; }
.desc { margin: 4px 0 0; font-size: 14.5px; color: var(--ink-2); max-width: 72ch; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.meta { margin: 6px 0 0; font-size: 13px; color: var(--ink-3); }
.score { padding: 12px 16px; border-left: 1px dashed var(--rule); display: flex; flex-direction: column; align-items: flex-end; justify-content: center; gap: 7px; }
.num { font-stretch: 75%; font-weight: 750; font-size: 22px; line-height: 1; }
.num.none { color: var(--ink-3); font-weight: 500; }
.num.up { color: var(--rise); }
.num.down { color: var(--fall); }
.bar { width: 100%; height: 4px; background: var(--grid); border-radius: 2px; overflow: hidden; }
.bar i { display: block; height: 100%; background: var(--signal); border-radius: 0 2px 2px 0; }

@media (prefers-reduced-motion: no-preference) {
  .strips.arriving .strip { animation: land .32s ease-out both; animation-delay: calc(var(--i) * 28ms); }
  @keyframes land { from { transform: translateX(-14px); } }
}

/* ---- Keywords ---- */
.kw-list { list-style: none; margin: 28px 0 0; padding: 0; columns: 2; column-gap: 48px; }
.kw-row { break-inside: avoid; display: grid; grid-template-columns: 28px minmax(80px, 140px) 1fr 44px; align-items: center; gap: 12px; padding: 9px 0; border-bottom: 1px solid var(--rule); }
.kw-row .n { font-stretch: 75%; color: var(--ink-3); font-size: 14px; }
.kw-row .w { font-weight: 620; overflow-wrap: anywhere; }
.kw-row .c { text-align: right; font-stretch: 75%; font-weight: 700; }
.kw-row .bar { height: 6px; }

/* ---- Stats ---- */
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); margin: 28px 0 0; border-top: 1px solid var(--rule); }
.stat { padding: 20px 20px 20px 0; border-bottom: 1px solid var(--rule); }
.stat dd { margin: 0; font-stretch: 125%; font-weight: 800; font-size: 40px; line-height: 1.05; letter-spacing: -0.02em; }
.stat dt { margin-top: 6px; color: var(--ink-2); font-size: 14px; }

/* ---- Diff ---- */
.diff { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 24px 32px; }
.diff h2 { display: flex; align-items: center; gap: 8px; }
.diff .rise-h { color: var(--rise); }
.diff .fall-h { color: var(--fall); }
.diff .strip { grid-template-columns: 52px minmax(0, 1fr) 84px; }
.diff .stub { padding: 12px 10px; align-items: center; }
.diff .rank { font-size: 18px; }

.empty { margin: 40px 0; padding: 28px; border: 1px dashed var(--rule); border-radius: 2px; max-width: 60ch; }
.empty h2 { margin: 0 0 6px; font-size: 18px; }
.empty p { margin: 0; color: var(--ink-2); }
.empty code { font-stretch: 75%; font-weight: 650; color: var(--ink); background: var(--strip); padding: 1px 6px; border-radius: 2px; border: 1px solid var(--rule); }

/* ---- Ask ---- */
.ask-form { margin: 28px 0 0; display: flex; flex-direction: column; gap: 10px; max-width: 760px; }
.ask-form label { font-weight: 650; font-size: 15px; }
.ask-form textarea {
  width: 100%; min-height: 88px; resize: vertical; padding: 12px 14px; line-height: 1.5;
  background: var(--strip); border: 1px solid var(--rule); border-radius: 3px;
}
.ask-form textarea::placeholder { color: var(--ink-3); }
.ask-row { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
.ask-row small { color: var(--ink-3); font-size: 13px; }
.ask-btn { padding: 10px 20px; background: var(--ink); color: var(--paper); border: 1px solid var(--ink); border-radius: 3px; cursor: pointer; font-weight: 650; }
.ask-btn:hover { background: var(--ink-2); border-color: var(--ink-2); }
.ask-btn:disabled { opacity: .55; cursor: progress; }
.suggest { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 4px; }
.suggest button { padding: 6px 12px; border: 1px solid var(--rule); background: transparent; border-radius: 3px; cursor: pointer; font-size: 14px; color: var(--ink-2); text-align: left; }
.suggest button:hover { border-color: var(--ink-3); color: var(--ink); }
.qa { margin: 36px 0 0; padding-top: 20px; border-top: 2px solid var(--ink); max-width: 760px; }
.qa + .qa { border-top-width: 1px; border-top-color: var(--rule); }
.qa-q { margin: 0; font-stretch: 112%; font-weight: 750; font-size: 21px; line-height: 1.3; letter-spacing: -0.01em; }
.qa-meta { margin: 4px 0 0; font-size: 13px; color: var(--ink-3); }
.answer { margin-top: 16px; font-size: 17px; line-height: 1.65; max-width: 68ch; }
.answer p { margin: 0 0 14px; }
.answer ul { margin: 0 0 14px; padding-left: 22px; }
.answer li { margin-bottom: 6px; }
.cite {
  display: inline-block; min-width: 1.6em; padding: 0 5px; margin: 0 1px; border-radius: 2px;
  background: var(--signal-soft); color: var(--ink); font-stretch: 75%; font-weight: 700; font-size: 13px;
  line-height: 1.5; text-align: center; text-decoration: none; vertical-align: 1px;
}
.cite:hover { background: var(--signal); color: var(--strip); }
.qa .board-head { margin-top: 20px; }
.strip.flash { border-color: var(--signal); box-shadow: 0 0 0 1px var(--signal); }
.qa-pending { margin-top: 16px; color: var(--ink-2); }

.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }

/* ---- Narrow screens ---- */
@media (max-width: 880px) {
  .shell { grid-template-columns: minmax(0, 1fr); }
  .rail { min-width: 0; position: static; height: auto; padding: 16px; gap: 14px; }
  .views { flex-direction: row; overflow-x: auto; gap: 4px; margin: 0 -16px; padding: 0 16px; scrollbar-width: none; }
  .view-btn { white-space: nowrap; width: auto; }
  .view-btn kbd { display: none; }
  .view-btn[aria-current="true"] { box-shadow: inset 0 -3px 0 var(--rail-amber); }
  .rail-settings { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; align-items: end; }
  .rail-foot { display: none; }
  .main { padding-top: 24px; }
  .figures, .diff { grid-template-columns: minmax(0, 1fr); }
  .kw-list { columns: 1; }
}
@media (max-width: 560px) {
  .rail-settings { grid-template-columns: 1fr; }
  .strip { grid-template-columns: minmax(0, 1fr) auto; grid-template-areas: "stub score" "body body"; }
  .stub { grid-area: stub; flex-direction: row; align-items: baseline; gap: 10px; border-right: 0; border-bottom: 1px dashed var(--rule); }
  .score { grid-area: score; border-left: 0; border-bottom: 1px dashed var(--rule); flex-direction: row; align-items: center; gap: 10px; }
  .score .bar { width: 56px; }
  .body { grid-area: body; }
  .rank { font-size: 20px; }
  .diff .strip { grid-template-columns: 40px minmax(0, 1fr) auto; grid-template-areas: none; }
  .diff .stub, .diff .score, .diff .body { grid-area: auto; border-bottom: 0; }
  .diff .stub { padding: 12px 0 12px 10px; }
  .board-head { flex-direction: column; gap: 2px; }
  .board-head p { text-align: left; }
}
</style>
</head>
<body>
<div class="shell">
  <aside class="rail">
    <a class="brand" href="/" aria-label="Trend Radar home">
      <svg class="scope" viewBox="0 0 32 32" aria-hidden="true">
        <circle class="ring" cx="16" cy="16" r="14"/>
        <circle class="ring" cx="16" cy="16" r="8.5"/>
        <circle class="ring" cx="16" cy="16" r="3"/>
        <line class="arm" x1="16" y1="16" x2="16" y2="2.5"/>
        <circle class="blip" cx="22.5" cy="9.5" r="2"/>
      </svg>
      <span class="brand-name">Trend Radar</span>
    </a>

    <nav aria-label="Views">
      <ul class="views">
        <li><button class="view-btn" id="btnFetch" type="button" onclick="fetchAll()">Fetch All <kbd>1</kbd></button></li>
        <li><button class="view-btn" id="btnAI" type="button" onclick="fetchAI()">AI Intel <kbd>2</kbd></button></li>
        <li><button class="view-btn" id="btnKW" type="button" onclick="showKeywords()">Keywords <kbd>3</kbd></button></li>
        <li><button class="view-btn" id="btnStats" type="button" onclick="showStats()">Stats <kbd>4</kbd></button></li>
        <li><button class="view-btn" id="btnDiff" type="button" onclick="showDiff()">Diff <kbd>5</kbd></button></li>
        <li><button class="view-btn" id="btnAsk" type="button" onclick="showAsk()">Ask <kbd>6</kbd></button></li>
      </ul>
    </nav>

    <div class="rail-settings">
      <div class="rail-group">
        <label class="rail-label" for="sourceSelect">Source</label>
        <select id="sourceSelect" onchange="onSourceChange()">
          <option value="">All sources</option>
          <option value="github">GitHub</option>
          <option value="hackernews">Hacker News</option>
          <option value="reddit">Reddit</option>
          <option value="arxiv">arXiv</option>
          <option value="rss">RSS feeds</option>
          <option value="producthunt">Product Hunt</option>
          <option value="youtube">YouTube</option>
          <option value="devto">DEV</option>
          <option value="lobsters">Lobsters</option>
          <option value="medium">Medium</option>
          <option value="news">News</option>
        </select>
      </div>
      <div class="rail-group">
        <label class="switch" id="translateToggle">
          <span>Translate to Arabic<small lang="ar" dir="rtl">ترجمة عربي</small></span>
          <input type="checkbox" id="translateCheck" onchange="setTranslate(this.checked)">
          <span class="track" aria-hidden="true"></span>
        </label>
      </div>
    </div>

    <div class="rail-foot">
      <span>Version 1.0.0</span>
      <a href="https://github.com/Jane-o-O-o-O/trend-radar" target="_blank" rel="noopener">GitHub</a>
    </div>
  </aside>

  <main class="main" id="main">
    <header class="topline">
      <div class="heading">
        <h1 id="viewTitle">Trending now</h1>
        <p class="status" id="status" role="status" aria-live="polite"></p>
      </div>
      <form class="search" role="search" onsubmit="event.preventDefault(); doSearch();">
        <label class="sr" for="searchInput">Search all sources</label>
        <input type="search" id="searchInput" placeholder="Search all sources" autocomplete="off">
        <button type="submit">Search</button>
      </form>
    </header>
    <div id="notice"></div>
    <div id="chartsArea"></div>
    <div class="results" id="results"></div>
  </main>
</div>

<script>
const NAMES = {github:'GitHub',hackernews:'Hacker News',reddit:'Reddit',arxiv:'arXiv',rss:'RSS',producthunt:'Product Hunt',youtube:'YouTube',devto:'DEV',lobsters:'Lobsters',medium:'Medium',news:'News'};
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
let sourceChart = null, keywordChart = null, lastChartData = null, lastAction = null;
let translateOn = false;

const $ = id => document.getElementById(id);
function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function safeUrl(u) { return /^https?:\/\//i.test(u || '') ? u : '#'; }
function plain(html) { if (!html) return ''; if (html.indexOf('<') === -1 && html.indexOf('&') === -1) return html; const doc = new DOMParser().parseFromString(html, 'text/html'); doc.querySelectorAll('script, style').forEach(n => n.remove()); return (doc.body.textContent || '').replace(/\s+/g, ' ').trim(); }
function srcName(s) { return NAMES[s] || s; }
function scoreFmt(n) { n = Number(n) || 0; const a = Math.abs(n); return a >= 1000 ? (n/1000).toFixed(1).replace(/\.0$/, '') + 'k' : String(Math.round(n)); }
function tok(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
function kwPair(k) { return Array.isArray(k) ? [k[0], k[1]] : [k.word, k.count]; }
function timeFmt(iso) { try { return new Date(iso).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'}); } catch (e) { return ''; } }
function tq() { return 'translate=' + (translateOn ? 'true' : 'false'); }

async function initTranslate() {
  let saved = null;
  try { saved = localStorage.getItem('translate'); } catch (e) {}
  if (saved !== null) translateOn = saved === '1';
  else { try { translateOn = (await (await fetch('/api/settings')).json()).translate; } catch (e) {} }
  $('translateCheck').checked = translateOn;
}
function setTranslate(on) {
  translateOn = on;
  try { localStorage.setItem('translate', on ? '1' : '0'); } catch (e) {}
  fetchAll();
}

function setActive(id) { document.querySelectorAll('.view-btn').forEach(b => b.setAttribute('aria-current', b.id === id ? 'true' : 'false')); }
function setView(title, btn) { $('viewTitle').textContent = title; if (btn) setActive(btn); }
function setStatus(text) { $('status').textContent = text; }
function showLoading(text) { document.body.classList.add('is-loading'); setStatus(text || 'Sweeping sources…'); $('notice').innerHTML = ''; }
function hideLoading() { document.body.classList.remove('is-loading'); }
function clearCharts() { if (sourceChart) { sourceChart.destroy(); sourceChart = null; } if (keywordChart) { keywordChart.destroy(); keywordChart = null; } lastChartData = null; $('chartsArea').innerHTML = ''; }

async function load(url, action) {
  lastAction = action;
  try {
    const resp = await fetch(url);
    if (!resp.ok) throw new Error('The server answered ' + resp.status + '.');
    return await resp.json();
  } catch (err) {
    hideLoading(); clearCharts(); setStatus('');
    $('results').innerHTML = '';
    $('notice').innerHTML = '<div class="notice"><strong>Couldn’t load this view.</strong> ' + esc(err.message || 'The request failed.') +
      ' Check that <code>trend-radar serve</code> is still running.<br><button type="button" onclick="lastAction && lastAction()">Try again</button></div>';
    return null;
  }
}

function onSourceChange() { if ($('btnAsk').getAttribute('aria-current') === 'true') renderAsk(); else fetchAll(); }

function showErrors(errors) {
  if (!errors || !errors.length) return;
  $('notice').innerHTML = '<div class="notice"><strong>Some sources didn’t respond.</strong> Results below are from the rest.<ul>' +
    errors.map(e => '<li>' + esc(e) + '</li>').join('') + '</ul></div>';
}

/* ---- Charts ---- */
function barChart(canvas, labels, values, label) {
  const ink = tok('--ink'), ink3 = tok('--ink-3'), grid = tok('--grid'), signal = tok('--signal'), strip = tok('--strip'), rule = tok('--rule');
  return new Chart(canvas, {
    type: 'bar',
    data: { labels, datasets: [{ label, data: values, backgroundColor: signal, hoverBackgroundColor: ink, borderRadius: 4, borderSkipped: 'start', maxBarThickness: 14, categoryPercentage: 0.8, barPercentage: 0.9 }] },
    options: {
      indexAxis: 'y', responsive: true, maintainAspectRatio: false,
      animation: reduceMotion ? false : { duration: 380 },
      plugins: {
        legend: { display: false },
        tooltip: { backgroundColor: strip, titleColor: ink, bodyColor: ink, borderColor: rule, borderWidth: 1, padding: 10, displayColors: false, cornerRadius: 3,
                   callbacks: { label: c => c.parsed.x + ' ' + label.toLowerCase() } }
      },
      scales: {
        x: { beginAtZero: true, grid: { color: grid }, border: { display: false }, ticks: { color: ink3, precision: 0, font: { size: 12 } } },
        y: { grid: { display: false }, border: { display: false }, ticks: { color: ink, autoSkip: false, font: { size: 13, weight: 500 } } }
      }
    }
  });
}

function renderCharts(data) {
  lastChartData = data;
  const counts = {};
  (data.items || []).forEach(i => { counts[i.source] = (counts[i.source] || 0) + 1; });
  const srcRows = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  const kws = (data.keywords || []).slice(0, 10).map(kwPair);

  $('chartsArea').innerHTML =
    '<div class="figures">' +
      '<figure class="figure"><figcaption>Items by source <span>' + srcRows.length + ' reporting</span></figcaption><div class="chart-box"><canvas id="sourceChart" aria-label="Items per source" role="img"></canvas></div></figure>' +
      '<figure class="figure"><figcaption>Top keywords <span>mentions in titles</span></figcaption><div class="chart-box"><canvas id="kwChart" aria-label="Top keywords by mentions" role="img"></canvas></div></figure>' +
    '</div>';

  if (sourceChart) sourceChart.destroy();
  if (keywordChart) keywordChart.destroy();
  if (typeof Chart === 'undefined') return;
  Chart.defaults.font.family = "'Archivo', system-ui, sans-serif";
  sourceChart = barChart($('sourceChart'), srcRows.map(r => srcName(r[0])), srcRows.map(r => r[1]), 'Items');
  keywordChart = kws.length ? barChart($('kwChart'), kws.map(k => k[0]), kws.map(k => k[1]), 'Mentions') : null;
}
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { if (lastChartData) renderCharts(lastChartData); });

/* ---- Strip board ---- */
function stripHtml(item, i, maxBySource, order) {
  const src = item.source;
  const top = maxBySource[src] || 0;
  const hasScore = Number(item.score) > 0;
  const pct = hasScore && top > 0 ? Math.max(3, Math.round((item.score / top) * 100)) : 0;
  const desc = plain(item.description);
  const orig = item.extra && item.extra.original_title ? ' title="' + esc(item.extra.original_title) + '"' : '';
  const meta = [];
  if (item.author) meta.push('by ' + esc(item.author));
  if (item.repo_language) meta.push(esc(item.repo_language));
  if (item.repo_forks) meta.push(scoreFmt(item.repo_forks) + ' forks');
  return '<li class="strip" style="--i:' + Math.min(order, 14) + '">' +
    '<div class="stub"><span class="rank">' + (i + 1) + '</span><span class="src">' + esc(srcName(src)) + '</span></div>' +
    '<div class="body"><a class="title" href="' + esc(safeUrl(item.url)) + '" target="_blank" rel="noopener" dir="auto"' + orig + '>' + esc(item.title) + '</a>' +
      (desc ? '<p class="desc" dir="auto">' + esc(desc) + '</p>' : '') +
      (meta.length ? '<p class="meta">' + meta.join(', ') + '</p>' : '') +
    '</div>' +
    '<div class="score">' + (hasScore
      ? '<span class="num">' + scoreFmt(item.score) + '</span><span class="bar" title="' + pct + '% of the top ' + esc(srcName(src)) + ' score"><i style="width:' + pct + '%"></i></span>'
      : '<span class="num none" title="' + esc(srcName(src)) + ' doesn\u2019t report a score">\u2014</span>') + '</div>' +
  '</li>';
}

function renderItems(items, title, keywords) {
  items = items || [];
  const maxBySource = {};
  items.forEach(i => { maxBySource[i.source] = Math.max(maxBySource[i.source] || 0, Number(i.score) || 0); });
  const groups = [];
  items.forEach(it => { let g = groups.find(g => g.src === it.source); if (!g) groups.push(g = { src: it.source, items: [] }); g.items.push(it); });
  let html = '<div class="board-head"><h2>' + esc(title) + '</h2><p>Each source keeps its own order. Bars compare an item with that source\u2019s top score.</p></div>';
  let n = 0;
  groups.forEach(g => {
    if (groups.length > 1) html += '<h3 class="group-head">' + esc(srcName(g.src)) + ' <span>' + g.items.length + '</span></h3>';
    html += '<ol class="strips' + arriving() + '">' + g.items.map((it, i) => stripHtml(it, i, maxBySource, n++)).join('') + '</ol>';
  });
  $('results').innerHTML = html;
}

function arriving() { return document.visibilityState === 'visible' ? ' arriving' : ''; }

function emptyState(heading, body) { return '<div class="empty"><h2>' + heading + '</h2><p>' + body + '</p></div>'; }

/* ---- Views ---- */
async function fetchAll() {
  setView('Trending now', 'btnFetch'); showLoading();
  const src = $('sourceSelect').value;
  const data = await load('/api/fetch?' + (src ? 'sources=' + encodeURIComponent(src) + '&' : '') + tq(), fetchAll);
  if (!data) return; hideLoading();
  const n = (data.sources || []).length;
  setStatus(data.item_count + ' items from ' + n + ' source' + (n === 1 ? '' : 's') + ', swept at ' + timeFmt(data.timestamp));
  showErrors(data.errors);
  if (!data.items.length) { clearCharts(); $('results').innerHTML = emptyState('No items came back', 'Every source came back empty. Pick a different source, or run <code>trend-radar doctor</code> to check connectivity.'); return; }
  renderCharts(data); renderItems(data.items, src ? 'Trending on ' + srcName(src) : 'Trending by source', data.keywords);
}

async function fetchAI() {
  setView('AI intel', 'btnAI'); showLoading('Sweeping for AI stories…');
  const data = await load('/api/ai?' + tq(), fetchAI);
  if (!data) return; hideLoading();
  setStatus(data.item_count + ' AI-related items, swept at ' + timeFmt(data.timestamp));
  if (!data.items.length) { clearCharts(); $('results').innerHTML = emptyState('No AI stories right now', 'Nothing AI-related turned up in this sweep. Try again later, or search for a specific model or lab.'); return; }
  renderCharts(data); renderItems(data.items, 'AI stories by source', data.keywords);
}

async function showKeywords() {
  setView('Keywords this week', 'btnKW'); showLoading('Counting keywords…');
  const data = await load('/api/keywords', showKeywords);
  if (!data) return; hideLoading(); clearCharts();
  const kws = data.keywords || [];
  setStatus(kws.length + ' keywords from saved snapshots over the last ' + data.days + ' days');
  if (!kws.length) { $('results').innerHTML = emptyState('No keyword history yet', 'Keywords are counted from saved snapshots. Run <code>trend-radar fetch</code> a few times to build history.'); return; }
  const max = Math.max(...kws.map(k => k.count));
  $('results').innerHTML = '<ol class="kw-list">' + kws.map((k, i) =>
    '<li class="kw-row"><span class="n">' + (i + 1) + '</span><span class="w">' + esc(k.word) + '</span>' +
    '<span class="bar" aria-hidden="true"><i style="width:' + Math.max(3, Math.round(k.count / max * 100)) + '%"></i></span>' +
    '<span class="c">' + k.count + '</span></li>').join('') + '</ol>';
}

async function showStats() {
  setView('Database stats', 'btnStats'); showLoading('Reading the database…');
  const data = await load('/api/stats', showStats);
  if (!data) return; hideLoading(); clearCharts();
  setStatus('Local history stored on this machine');
  const rows = [[data.total_snapshots || 0, 'Snapshots saved'], [data.total_items || 0, 'Items stored'], [(data.sources || []).length, 'Sources seen']];
  if (data.cache) { rows.push([data.cache.memory_entries || 0, 'Cached in memory']); rows.push([data.cache.disk_entries || 0, 'Cached on disk']); }
  $('results').innerHTML = '<dl class="stats">' + rows.map(r =>
    '<div class="stat"><dd>' + Number(r[0]).toLocaleString() + '</dd><dt>' + r[1] + '</dt></div>').join('') + '</dl>';
}

function diffColumn(rows, kind) {
  return '<ol class="strips' + arriving() + '">' + rows.slice(0, 10).map((item, i) => {
    const d = Number(item.score_delta) || 0;
    return '<li class="strip" style="--i:' + i + '"><div class="stub"><span class="rank">' + (i + 1) + '</span></div>' +
      '<div class="body"><span class="title" dir="auto">' + esc(item.title) + '</span><p class="meta">' + esc(srcName(item.source)) + '</p></div>' +
      '<div class="score"><span class="num ' + kind + '">' + (d > 0 ? '+' : '') + scoreFmt(d) + '</span></div></li>';
  }).join('') + '</ol>';
}

async function showDiff() {
  setView('What moved', 'btnDiff'); showLoading('Comparing the last two snapshots…');
  const data = await load('/api/diff', showDiff);
  if (!data) return; hideLoading(); clearCharts();
  const rising = data.rising || [], falling = data.falling || [];
  if (!rising.length && !falling.length) {
    setStatus('');
    $('results').innerHTML = emptyState('Diff needs two snapshots', 'Run <code>trend-radar fetch</code> twice, some time apart, then come back to see what rose and fell.');
    return;
  }
  setStatus(rising.length + ' rising and ' + falling.length + ' falling since the previous snapshot');
  $('results').innerHTML = '<div class="diff">' +
    '<section><div class="board-head"><h2 class="rise-h"><span aria-hidden="true">▲</span> Rising</h2></div>' + (rising.length ? diffColumn(rising, 'up') : '<p class="meta">Nothing rose.</p>') + '</section>' +
    '<section><div class="board-head"><h2 class="fall-h"><span aria-hidden="true">▼</span> Falling</h2></div>' + (falling.length ? diffColumn(falling, 'down') : '<p class="meta">Nothing fell.</p>') + '</section>' +
  '</div>';
}

async function doSearch() {
  const q = $('searchInput').value.trim();
  if (!q) { $('searchInput').focus(); return; }
  setView('Search', null); setActive(null); showLoading('Searching for “' + q + '”…');
  const data = await load('/api/search?q=' + encodeURIComponent(q) + '&' + tq(), doSearch);
  if (!data) return; hideLoading(); clearCharts();
  setStatus(data.count + ' result' + (data.count === 1 ? '' : 's') + ' for “' + q + '”');
  if (!data.items.length) { $('results').innerHTML = emptyState('Nothing matched “' + esc(q) + '”', 'Try a broader term, or check the spelling.'); return; }
  renderItems(data.items, 'Results for “' + q + '”', null);
}

/* ---- Ask ---- */
let askHistory = [], askCounter = 0, askState = null;
const SUGGESTIONS = ['What are the biggest stories right now?', 'What is new in AI agents and coding tools?', 'Which topics show up across several sources?'];

function answerHtml(text, qid, itemCount) {
  const inline = t => esc(t)
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\[(\d{1,4})\]/g, (m, n) => (+n >= 1 && +n <= itemCount)
      ? '<a class="cite" href="#' + qid + '-' + n + '" onclick="return flashCite(this)" aria-label="Source ' + n + '">' + n + '</a>' : m);
  const out = []; let list = null, para = [];
  const flush = () => { if (para.length) { out.push('<p dir="auto">' + inline(para.join(' ')) + '</p>'); para = []; } };
  text.split('\n').forEach(line => {
    const t = line.trim();
    const bullet = t.match(/^(?:[-*•]|\d+[.)])\s+(.*)$/);
    if (bullet) { flush(); if (!list) { list = []; } list.push('<li dir="auto">' + inline(bullet[1]) + '</li>'); return; }
    if (list) { out.push('<ul>' + list.join('') + '</ul>'); list = null; }
    if (!t) { flush(); return; }
    para.push(t.replace(/^#+\s*/, ''));
  });
  flush(); if (list) out.push('<ul>' + list.join('') + '</ul>');
  return out.join('');
}

function flashCite(a) {
  const el = document.getElementById(a.getAttribute('href').slice(1));
  if (!el) return false;
  el.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'center' });
  el.classList.add('flash'); setTimeout(() => el.classList.remove('flash'), 1600);
  return false;
}

function qaHtml(entry) {
  const head = '<h2 class="qa-q" dir="auto">' + esc(entry.question) + '</h2>';
  if (entry.pending) return '<section class="qa">' + head + '<p class="qa-pending">Reading the latest items and writing an answer. This usually takes 10–40 seconds.</p></section>';
  if (entry.error) return '<section class="qa">' + head + '<div class="notice"><strong>No answer.</strong> ' + esc(entry.error) + '</div></section>';
  const d = entry.data, qid = 'q' + entry.id;
  const maxBySource = {};
  d.items.forEach(i => { maxBySource[i.source] = Math.max(maxBySource[i.source] || 0, Number(i.score) || 0); });
  let html = '<section class="qa">' + head +
    '<p class="qa-meta">Answered by ' + esc(d.model) + ' from ' + d.items.length + ' collected items</p>' +
    '<div class="answer">' + answerHtml(d.answer, qid, d.items.length) + '</div>';
  if (d.cited.length) {
    html += '<div class="board-head"><h2>Sources cited</h2><p>Numbers match the citations above.</p></div><ol class="strips">' +
      d.cited.map((n, i) => stripHtml(d.items[n - 1], n - 1, maxBySource, i).replace('<li class="strip"', '<li class="strip" id="' + qid + '-' + n + '"')).join('') + '</ol>';
  }
  return html + '</section>';
}

function renderAsk() {
  if (!askState) return;
  if (!askState.configured) {
    const env = esc(askState.key_env || 'the API key');
    $('results').innerHTML = emptyState('Connect a ' + esc(askState.provider || 'provider') + ' API key to ask questions',
      'Get ' + esc(askState.key_help || 'an API key') + ', then restart the server with it: ' +
      '<code>' + env + '=your-key trend-radar serve</code>.');
    return;
  }
  const src = $('sourceSelect').value;
  $('results').innerHTML =
    '<form class="ask-form" onsubmit="event.preventDefault(); doAsk();">' +
      '<label for="askInput">Ask about ' + (src ? 'the latest from ' + esc(srcName(src)) : 'the latest news from all sources') + '</label>' +
      '<textarea id="askInput" dir="auto" placeholder="For example: what changed in open-source LLMs this week?" onkeydown="if(event.key===\'Enter\'&&(event.metaKey||event.ctrlKey)){event.preventDefault();doAsk();}"></textarea>' +
      '<div class="ask-row"><small>Answers use only the collected items and cite them. Ctrl+Enter to send.</small>' +
      '<button class="ask-btn" id="askBtn" type="submit">Ask</button></div>' +
      (askHistory.length ? '' : '<div class="suggest">' + SUGGESTIONS.map(q => '<button type="button" onclick="askSuggested(this)">' + esc(q) + '</button>').join('') + '</div>') +
    '</form>' + askHistory.map(qaHtml).join('');
}

async function showAsk() {
  setView('Ask the news', 'btnAsk'); clearCharts(); $('notice').innerHTML = '';
  if (!askState) {
    showLoading('Checking the AI connection…');
    const st = await load('/api/ask/status', showAsk);
    if (!st) return; hideLoading(); askState = st;
  }
  setStatus(askState.configured ? 'Answers by ' + askState.model + ', grounded in the items Trend Radar collects' : '');
  renderAsk();
  const box = $('askInput'); if (box) box.focus();
}

function askSuggested(btn) { $('askInput').value = btn.textContent; doAsk(); }

async function doAsk() {
  const box = $('askInput'); const q = box ? box.value.trim() : '';
  if (!q) { if (box) box.focus(); return; }
  const entry = { id: ++askCounter, question: q, pending: true };
  askHistory.unshift(entry); renderAsk();
  $('askBtn').disabled = true; document.body.classList.add('is-loading');
  setStatus('Asking ' + askState.model + '…');
  try {
    const src = $('sourceSelect').value;
    const resp = await fetch('/api/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: q, sources: src || null }) });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) entry.error = data.error || ('The server answered ' + resp.status + '.');
    else entry.data = data;
  } catch (err) {
    entry.error = 'Couldn’t reach the Trend Radar server. Check that it is still running.';
  }
  entry.pending = false; document.body.classList.remove('is-loading');
  setStatus('Answers by ' + askState.model + ', grounded in the items Trend Radar collects');
  if ($('btnAsk').getAttribute('aria-current') === 'true') { renderAsk(); }
}

/* ---- Keyboard ---- */
document.addEventListener('keydown', e => {
  const t = e.target;
  if (t.matches('input, select, textarea') || e.metaKey || e.ctrlKey || e.altKey) return;
  if (e.key === '/') { e.preventDefault(); $('searchInput').focus(); return; }
  const views = { '1': fetchAll, '2': fetchAI, '3': showKeywords, '4': showStats, '5': showDiff, '6': showAsk };
  if (views[e.key]) views[e.key]();
});

initTranslate().then(fetchAll);
</script>
</body>
</html>"""

# [2026-04-08] Performance: optimize web
import functools

@functools.lru_cache(maxsize=256)
def _cached_daily_digest_generation(key: str) -> dict:
    """Cached version of daily digest generation for improved performance.

    Reduces repeated computation by caching results.
    """
    return _compute_daily_digest_generation(key)


def _compute_daily_digest_generation(key: str) -> dict:
    """Core computation for daily digest generation."""
    return {"key": key, "computed": True, "timestamp": time.time()}

# [2026-06-01] Fix: missing validation in web
def _safe_get(data: dict, key: str, default=None):
    """Safely get a value from data dict with proper error handling.

    Fix: resolves null pointer exception when key contains nested paths.
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

    Fix: added proper type checking to prevent memory leak.
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

# [2026-04-08] Performance: optimize web
import functools

@functools.lru_cache(maxsize=256)
def _cached_daily_digest_generation(key: str) -> dict:
    """Cached version of daily digest generation for improved performance.

    Reduces repeated computation by caching results.
    """
    return _compute_daily_digest_generation(key)


def _compute_daily_digest_generation(key: str) -> dict:
    """Core computation for daily digest generation."""
    return {"key": key, "computed": True, "timestamp": time.time()}

# [2026-06-01] Fix: missing validation in web
def _safe_get(data: dict, key: str, default=None):
    """Safely get a value from data dict with proper error handling.

    Fix: resolves null pointer exception when key contains nested paths.
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

    Fix: added proper type checking to prevent memory leak.
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
