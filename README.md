# 📡 Trend Radar

**Multi-source tech intelligence CLI — GitHub/HN/Reddit/arXiv/RSS/Product Hunt in one command.**

> See what's trending before everyone else. No browser tabs, no doom-scrolling.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-green.svg)]()
[![Tests](https://img.shields.io/badge/tests-497%20passed-brightgreen.svg)]()
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)]()
[![PyPI](https://img.shields.io/pypi/v/trend-radar?color=blue)](https://pypi.org/project/trend-radar/)

**One command. Six sources. Zero doom-scrolling.**

### Why Trend Radar?

| Feature | Hacker News Only | GitHub Trending | Trend Radar |
|---------|-----------------|-----------------|-------------|
| Sources | 1 | 1 | **6** (GitHub + HN + Reddit + arXiv + RSS + Product Hunt) |
| Live dashboard | ❌ | ❌ | ✅ Real-time auto-refreshing terminal UI |
| Radar chart | ❌ | ❌ | ✅ Topic distribution spider chart |
| Keyword tracking | ❌ | ❌ | ✅ Historical trends |
| Score normalization | ❌ | ❌ | ✅ Cross-source 0-100 scale |
| Trend momentum | ❌ | ❌ | ✅ Velocity + acceleration tracking |
| Keyword alerts | ❌ | ❌ | ✅ Watchlist with threshold alerts |
| Digest reports | ❌ | ❌ | ✅ Shareable Markdown/HTML reports |
| Bookmarks | ❌ | ❌ | ✅ Save & star interesting items |
| Plugin system | ❌ | ❌ | ✅ Custom data sources |
| Rate limiting | ❌ | ❌ | ✅ Token bucket API throttling |
| Shell completions | ❌ | ❌ | ✅ bash/zsh/fish |
| Web dashboard | ❌ | ❌ | ✅ Chart.js visualizations |
| JSON/CSV export | ❌ | ❌ | ✅ |
| Interactive shell | ❌ | ❌ | ✅ |
| Color themes | ❌ | ❌ | ✅ 7 built-in themes (Dracula, Monokai, Nord...) |
| Cross-source dedup | ❌ | ❌ | ✅ Detect same story across HN+Reddit+RSS |
| Snapshot diffing | ❌ | ❌ | ✅ Save & compare trend snapshots over time |
| Webhook alerts | ❌ | ❌ | ✅ Slack/Discord/Telegram notifications |
| Obsidian export | ❌ | ❌ | ✅ Markdown with YAML frontmatter + wikilinks |
| Timeline view | ❌ | ❌ | ✅ Topic trend sparklines over days/weeks |
| Self-contained | ❌ | ❌ | ✅ No API keys needed |

Trend Radar aggregates tech trends from **GitHub**, **Hacker News**, **Reddit**, **arXiv**, **RSS feeds**, and **Product Hunt** into a single, beautiful terminal dashboard. Track keywords over time, search across all sources, and never miss what's trending.

### 🆕 What's New in v1.0.0
- **`trend-radar demo`** 🎉 — Instant demo with synthetic data, no API keys needed! Perfect for first-time users
- **`trend-radar doctor`** 🏥 — System diagnostics: check source connectivity, dependencies, config, and database
- **Complete type annotations** — All public functions have return type hints for better IDE support
- **Integration test suite** — Real API connectivity tests for GitHub, HN, Reddit, arXiv, RSS
- **497 tests** all passing

### Previous: v0.9.0
- **`trend-radar themes`** — 7 built-in color themes: default, dracula, monokai, solarized, nord, gruvbox, light
- **`trend-radar dedup`** — Cross-source deduplication engine (detects same story on HN + Reddit + RSS)
- **`trend-radar snapshots`** — Save, list, and diff trend snapshots (see what changed over time)
- **`trend-radar webhooks`** — Send alert notifications to Slack, Discord, or Telegram
- **`trend-radar obsidian`** — Export trends as Obsidian-compatible markdown with YAML frontmatter
- **`trend-radar timeline`** — Topic trend visualization with sparklines over days/weeks

### Previous: v0.8.0
- **`trend-radar radar`** — Topic distribution spider chart in terminal (AI, Web, Security, DevOps...)
- **`trend-radar bookmark`** — Save, star, search, and export interesting items
- **`trend-radar plugins`** — Custom data source plugin system (drop .py files in ~/.trend-radar/plugins/)
- **`trend-radar compare`** — Compare trends between two time periods
- **`trend-radar completions`** — Shell auto-completion for bash/zsh/fish
- **`trend-radar rate-limits`** — View API rate limiter status for all sources
- **Token bucket rate limiter** — Per-source API throttling to protect upstream APIs
- **359 tests** all passing

### Previous: v0.7.0
- **`trend-radar live`** — Real-time auto-refreshing terminal dashboard (like `htop` for trends!)
- **`trend-radar digest`** — Generate shareable Markdown/HTML trend reports
- **`trend-radar init`** — Interactive first-run setup wizard
- **`trend-radar version`** — Show version and system info
- **Enhanced web dashboard** — Chart.js doughnut/bar charts, new Diff view
- **Source distribution visualization** — Visual breakdown in terminal
- **Keyword sparkline trends** — Trend direction with Unicode sparklines
- **Progress-aware fetching** — See per-source status with items count and cache hits
- **294 tests** all passing |

```
╭──────────────────────────────────────────────────────────────────────╮
│ 📡 Trend Radar                                                       │
│ 2026-05-13 18:00 UTC                                                 │
│ Sources: 🐙 github  🔶 hackernews  🤖 reddit  📄 arxiv  📡 rss       │
│ Items: 67                                                            │
╰──────────────────────────────────────────────────────────────────────╯

╭── 🐙 GITHUB ─────────────────────────────────────────────────────────╮
│ #  Title                          Score       Details                 │
│ 1  openai/codex-cli              🔥 12.4k    AI coding agent         │
│ 2  anthropic/claude-code          🟡 8.2k    CLI coding assistant    │
╰──────────────────────────────────────────────────────────────────────╯

╭── 🔶 HACKERNEWS ─────────────────────────────────────────────────────╮
│ #  Title                          Score       Details                 │
│ 1  Show HN: I built an AI agent   🔵 342     Autonomous coding       │
│ 2  Why every team needs MCP       🔵 287     MCP integration         │
╰──────────────────────────────────────────────────────────────────────╯

┌─ 🔑 Trending Keywords ─────────────────────────────────────────────────┐
│ agent      ████████████████████████  12                               │
│ coding     █████████████████         8                                │
│ llm        ██████████████            7                                │
│ mcp        ████████████              6                                │
└────────────────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

```bash
# Install (core)
pip install trend-radar

# Install with all features (web dashboard + interactive shell)
pip install trend-radar[all]

# 🎉 Try it instantly — no API keys, no setup!
trend-radar demo

# Or diagnose your system
trend-radar doctor

# First-time setup wizard (interactive)
trend-radar init

# Fetch from all sources (with per-source progress!)
trend-radar fetch

# Live auto-refreshing dashboard (Ctrl+C to stop)
trend-radar live

# AI-focused intelligence
trend-radar ai

# Generate a shareable digest report
trend-radar digest
trend-radar digest --format html -o weekly-report.html

# Search for a topic
trend-radar search "MCP server"

# Topic radar chart (AI, Web, Security, DevOps...)
trend-radar radar

# Compare trends (rising/falling)
trend-radar diff

# Cross-source normalized ranking
trend-radar ranked

# Trend momentum — see velocity & acceleration
trend-radar momentum

# Bookmark interesting items
trend-radar bookmark add "openai/codex-cli"
trend-radar bookmark list
trend-radar bookmark star 1

# Set keyword alerts
trend-radar alert-add "MCP server" --threshold 3
trend-radar alerts-check

# Plugin system (custom data sources)
trend-radar plugins list
trend-radar plugins load /path/to/plugins/

# Cross-source deduplication
trend-radar dedup                             # Find duplicates across all sources
trend-radar dedup -s hackernews,reddit        # Check specific sources
trend-radar dedup --threshold 0.8             # Stricter similarity threshold

# Snapshot management
trend-radar snapshots --list                  # List saved snapshots
trend-radar snapshots --save                  # Save current fetch as snapshot
trend-radar snapshots --save --label "v2.0"   # Save with label
trend-radar snapshots --auto-diff             # Diff two most recent snapshots
trend-radar snapshots --diff 1 2              # Diff specific snapshots

# Color themes
trend-radar themes --list                     # List available themes
trend-radar themes --preview dracula          # Preview a theme
trend-radar themes --set nord                 # Set active theme

# Webhook notifications
trend-radar webhooks --list                   # List configured webhooks
trend-radar webhooks --add https://hooks.slack.com/... --name slack-alerts --type slack
trend-radar webhooks --test slack-alerts      # Send test notification
trend-radar webhooks --remove slack-alerts    # Remove webhook

# Obsidian export
trend-radar obsidian --format daily           # Export as daily note with frontmatter
trend-radar obsidian --format vault -o notes/ # Export as full Obsidian vault
trend-radar obsidian --format item -o items/  # Export each item as a note

# Timeline visualization
trend-radar timeline                          # Show topic trends (7 days)
trend-radar timeline --days 30                # Last 30 days
trend-radar timeline -k "agent,llm,mcp"      # Track specific keywords

# Shell auto-completion
eval "$(trend-radar completions bash)"
eval "$(trend-radar completions zsh)"

# Check API rate limits
trend-radar rate-limits

# Check source health
trend-radar health

# Interactive shell (REPL mode)
trend-radar shell

# Web dashboard (with Chart.js visualizations!)
trend-radar serve

# Export as standalone HTML dashboard
trend-radar fetch --html -o dashboard.html

# Docker (web dashboard)
docker build -t trend-radar .
docker run -p 8765:8765 trend-radar
```

## ✨ Features

| Feature | Description |
|---------|-------------|
| 📡 **Live dashboard** | Real-time auto-refreshing terminal UI with Rich Live |
| 🕸️ **Radar chart** | Topic distribution spider chart in terminal |
| 🔍 **Multi-source aggregation** | GitHub, HN, Reddit, arXiv, RSS, Product Hunt |
| ⚡ **Parallel fetching** | All sources fetched concurrently with progress tracking |
| 🎨 **Beautiful terminal output** | Rich-powered tables, cards, compact layouts, sparklines |
| 📊 **Trend diff** | Compare snapshots — see rising/falling/new items |
| 📝 **Digest reports** | Generate shareable Markdown/HTML trend summaries |
| ⭐ **Bookmarks** | Save, star, search, and export interesting items |
| 🔌 **Plugin system** | Custom data source plugins (~/.trend-radar/plugins/) |
| ⏱️ **Rate limiting** | Token bucket per-source API throttling |
| 🏆 **Topic filtering** | Filter by AI, Web, Mobile, Security, DevOps, Data, Lang |
| 🔑 **Trending keywords** | Auto-extracted keyword frequency with sparkline trends |
| 📊 **History tracking** | SQLite-backed trend history with time-series |
| 💾 **Two-level caching** | Memory TTL + disk SQLite cache (with cache-hit indicators) |
| ⚙️ **YAML configuration** | `~/.trend-radar/config.yaml` for all settings |
| 🧙 **Setup wizard** | Interactive `trend-radar init` for first-time users |
| 🌐 **Web dashboard** | FastAPI + Chart.js visualizations |
| 💻 **Interactive shell** | prompt_toolkit REPL with tab completion |
| 📄 **Export formats** | JSON, Markdown, HTML, CSV |
| 🔄 **Watch mode** | Auto-refresh every N seconds |
| 🏥 **Health checks** | Source connectivity and latency monitoring |
| 🐳 **Docker ready** | One-command web dashboard deployment |
| 🤖 **Hermes Agent** | Built-in AI agent tool integration |
| 🎨 **Color themes** | 7 built-in themes: Dracula, Monokai, Nord, Solarized, Gruvbox, Light |
| 🔗 **Cross-source dedup** | Detect same story across HN + Reddit + RSS |
| 📸 **Snapshot diffing** | Save snapshots and compare over time |
| 🔔 **Webhook alerts** | Slack/Discord/Telegram notifications |
| 📝 **Obsidian export** | Markdown with YAML frontmatter + wikilinks |
| 📈 **Timeline view** | Topic trend sparklines over days/weeks |

## 📦 Data Sources

| Source | Emoji | What you get | API |
|--------|-------|-------------|-----|
| **GitHub** | 🐙 | Trending repos + search | REST API + page scraping |
| **Hacker News** | 🔶 | Top/best/new/ask/show stories | Firebase API |
| **Reddit** | 🤖 | Hot posts from tech/AI subreddits | JSON API |
| **arXiv** | 📄 | Latest AI/ML research papers | Atom API |
| **RSS/Atom** | 📡 | Tech blogs (TechCrunch, OpenAI, etc.) | Standard RSS/Atom |
| **Product Hunt** | 🚀 | Today's trending products | Web scraping |

## 🛠️ Commands

```bash
# 🎉 Demo mode — try Trend Radar with synthetic data (no API keys!)
trend-radar demo                          # Show demo data across all sources
trend-radar demo -s github,hn             # Demo for specific sources
trend-radar demo --json                   # Demo as JSON
trend-radar demo --seed 42                # Reproducible demo data

# 🏥 System diagnostics
trend-radar doctor                        # Check source connectivity, deps, config

# Fetch trending intel
trend-radar fetch                         # All sources, table layout (parallel!)
trend-radar fetch -s github,hn            # Specific sources
trend-radar fetch --layout cards          # Card layout
trend-radar fetch --layout compact        # Compact single-line
trend-radar fetch --json                  # JSON output (for scripting)
trend-radar fetch --markdown              # Markdown output
trend-radar fetch --html                  # Standalone HTML dashboard
trend-radar fetch --csv                   # CSV spreadsheet
trend-radar fetch --watch 30              # Auto-refresh every 30s
trend-radar fetch -o dashboard.html       # Auto-detect format from extension
trend-radar fetch -o trends.csv           # Save as CSV
trend-radar fetch -o report.md            # Save as Markdown
trend-radar fetch --topic ai              # Filter by topic
trend-radar fetch --no-parallel           # Sequential (non-parallel) fetch

# Live dashboard
trend-radar live                          # Auto-refresh every 30s (default)
trend-radar live -i 10                    # Refresh every 10s
trend-radar live -s github,hn             # Specific sources only
trend-radar live -n 20                    # 20 items per source

# Digest reports
trend-radar digest                        # Generate Markdown digest
trend-radar digest --format html          # Generate HTML digest
trend-radar digest -o report.html         # Save to file
trend-radar digest --title "Weekly Report" # Custom title

# AI-focused intel
trend-radar ai                            # AI/LLM across all sources
trend-radar ai --json                     # JSON output

# Search
trend-radar search "agent framework"      # Cross-source search
trend-radar search "MCP" -s github,arxiv  # Search specific sources

# Trend diff (rising/falling detection)
trend-radar diff                          # Compare last two snapshots
trend-radar diff --json                   # JSON output

# Top items
trend-radar top                           # Top 20 across all sources
trend-radar top --topic ai -n 10          # Top 10 AI items
trend-radar top --source github           # Top GitHub items only

# Health check
trend-radar health                        # Check all source connectivity

# History & Analysis
trend-radar history -h 48                 # Last 48h of data
trend-radar keywords                      # Trending keywords (7 days)
trend-radar keywords -d 30                # Last 30 days
trend-radar stats                         # Database statistics

# Interactive shell
trend-radar shell                         # Launch REPL with tab completion

# Web dashboard
trend-radar serve                         # Start web UI on :8765
trend-radar serve -p 3000                 # Custom port

# Configuration
trend-radar init                          # Interactive setup wizard
trend-radar config-show                   # Show current config
trend-radar config-set sources.reddit.enabled false
trend-radar config-set display.layout compact
trend-radar sources-list                  # List all sources + status
trend-radar version                       # Show version and system info
```

## 🌐 Web Dashboard

Launch a beautiful web dashboard with Chart.js visualizations:

```bash
# Install web dependencies
pip install trend-radar[web]

# Start the server
trend-radar serve --port 8765
```

Then open `http://localhost:8765` for the interactive dashboard with:
- 📊 **Source distribution** doughnut chart
- 🔑 **Keyword frequency** bar chart
- 📈 **Trend diff** view (rising/falling)
- 🔍 **Search** across all sources
- 📊 **Stats** overview with cache metrics

Or use the API directly:

```bash
curl http://localhost:8765/api/fetch
curl http://localhost:8765/api/ai
curl http://localhost:8765/api/search?q=MCP
curl http://localhost:8765/api/keywords?days=7
curl http://localhost:8765/api/stats
curl http://localhost:8765/api/diff
curl http://localhost:8765/api/top?limit=10&topic=ai
curl http://localhost:8765/api/health
curl http://localhost:8765/api/momentum
curl http://localhost:8765/api/ranked
```

## 🐳 Docker

```bash
# Build and run the web dashboard
docker build -t trend-radar .
docker run -p 8765:8765 trend-radar

# Fetch from CLI inside Docker
docker run trend-radar fetch --json

# With persistent data volume
docker run -v trend-data:/data trend-radar serve --host 0.0.0.0
```

## 💻 Interactive Shell

Launch an interactive REPL with tab completion:

```bash
pip install trend-radar[shell]
trend-radar shell
```

```
📡 trend-radar> fetch --limit 10
📡 trend-radar> search MCP server
📡 trend-radar> keywords --days 30
📡 trend-radar> stats
📡 trend-radar> exit
```

## 🤖 Use as a Python Library

```python
from trend_radar import TrendRadar

radar = TrendRadar()

# Fetch trending from all sources (parallel!)
snapshot = radar.collect(sources=["github", "hackernews"], limit=10)
print(f"Got {snapshot.item_count} items")

# Top items by score
for item in snapshot.top(5):
    print(f"  {item.title} ({item.score_display})")

# Trending keywords
for word, count in snapshot.keywords(10):
    print(f"  {word}: {count}")

# AI-focused collection
snapshot = radar.collect_ai_focused(limit=15)

# Search
items = radar.search("MCP server", limit=20)

# Trend diff (rising/falling)
diff = radar.diff_snapshots()
for item in diff["rising"][:5]:
    print(f"  🔺 {item['title']} (+{item['score_delta']})")

# Topic-filtered top items
items = radar.get_top_items(limit=10, topic="ai")

# Health check
health = radar.check_health()
for name, info in health.items():
    print(f"  {name}: {info['status']} ({info['latency_ms']}ms)")

# Export to HTML
from trend_radar.exporters.html import HtmlRenderer
html = HtmlRenderer().render(snapshot)
with open("dashboard.html", "w") as f:
    f.write(html)

# Export to CSV
from trend_radar.exporters.csv_export import CsvRenderer
csv_data = CsvRenderer().render(snapshot)

# Generate digest report
from trend_radar import generate_digest_markdown, generate_digest_html
md = generate_digest_markdown(snapshot, title="Weekly Tech Digest")
html = generate_digest_html(snapshot)

# ─── v0.9.0: Themes ───
from trend_radar import get_theme, list_themes
for name in list_themes():
    print(f"  {name}: {get_theme(name).primary}")
theme = get_theme("dracula")
style, emoji = theme.get_score_style(5000)  # "🔴"

# ─── v0.9.0: Deduplication ───
from trend_radar import DedupEngine
engine = DedupEngine(title_threshold=0.7)
unique, groups = engine.deduplicate(snapshot.items)
for g in groups:
    print(f"  Duplicate: {g.primary_title} ({g.source_count} sources)")

# ─── v0.9.0: Snapshots ───
from trend_radar import SnapshotManager
manager = SnapshotManager(radar.store)
snap_id = manager.save_snapshot(snapshot, label="morning_check")
diff = manager.auto_diff()
if diff:
    print(f"  New: {len(diff.new_items)}, Removed: {len(diff.removed_items)}")

# ─── v0.9.0: Webhooks ───
from trend_radar import WebhookDispatcher, WebhookConfig, WebhookType
dispatcher = WebhookDispatcher()
dispatcher.add(WebhookConfig(
    name="slack", url="https://hooks.slack.com/...",
    webhook_type=WebhookType.SLACK,
))

# ─── v0.9.0: Obsidian Export ───
from trend_radar import export_obsidian_daily, export_obsidian_vault
content = export_obsidian_daily(snapshot)  # Markdown with frontmatter
files = export_obsidian_vault(snapshot)    # Full vault with MOC

# ─── v0.9.0: Timeline ───
from trend_radar import compute_timeline
timeline = compute_timeline(radar.store, days=7)
for topic in timeline.top_topics:
    print(f"  {topic.keyword} {topic.trend} ({topic.total} mentions)")
```

## ⚙️ Configuration

Config file: `~/.trend-radar/config.yaml`

```yaml
sources:
  github:
    enabled: true
    token: ""           # Set GITHUB_TOKEN env var or fill this
    min_stars: 10
  hackernews:
    enabled: true
    category: top
  reddit:
    enabled: true
    subreddits:
      - MachineLearning
      - LocalLLaMA
      - artificial
      - programming
  arxiv:
    enabled: true
    category: ai
  rss:
    enabled: true
    feeds: {}           # Add custom feeds
  producthunt:
    enabled: true

display:
  layout: table          # table | cards | compact
  items_per_source: 15
  show_keywords: true
  color_theme: default   # default | dracula | monokai | solarized | nord | gruvbox | light

cache:
  enabled: true
  memory_ttl: 300        # 5 minutes in-memory
  disk_ttl: 3600         # 1 hour on disk

output:
  format: terminal       # terminal | json | markdown | html | csv
```

## 🏗️ Architecture

```
trend_radar/
├── __init__.py          # Public API exports
├── core.py              # TrendRadar engine — orchestrates everything
├── models.py            # IntelItem, TrendSnapshot, SourceType
├── store.py             # SQLite storage for history tracking
├── cache.py             # Two-level cache (memory TTL + disk SQLite)
├── config.py            # YAML config system
├── render.py            # Rich terminal renderer (tables, cards, compact, sparklines)
├── cli.py               # Click CLI with all commands
├── live.py              # Live auto-refreshing terminal dashboard
├── digest.py            # Shareable digest report generator (Markdown/HTML)
├── init_wizard.py       # Interactive first-run setup wizard
├── shell.py             # Interactive REPL with prompt_toolkit
├── web.py               # FastAPI web dashboard + REST API + Chart.js
├── normalization.py     # Cross-source score normalization (0-100)
├── momentum.py          # Trend velocity & acceleration tracking
├── alerts.py            # Keyword watchlist with threshold alerts
├── opml.py              # OPML/JSON feed import
├── async_fetch.py       # Async HTTP fetching with httpx
├── retry.py             # Exponential backoff retry logic
├── themes.py            # 🎨 7 built-in color themes (Dracula, Monokai, Nord...)
├── dedup.py             # 🔗 Cross-source deduplication engine
├── snapshots.py         # 📸 Snapshot save/load and diffing
├── webhooks.py          # 🔔 Webhook notification dispatcher (Slack/Discord/Telegram)
├── timeline.py          # 📈 Topic timeline with sparkline visualization
├── obsidian_export.py   # 📝 Obsidian-compatible markdown with frontmatter
├── bookmarks.py         # ⭐ Bookmark store
├── plugins.py           # 🔌 Plugin system
├── rate_limiter.py      # ⏱️ Token bucket rate limiter
├── radar_chart.py       # 🕸️ Topic distribution spider chart
├── exporters/
│   ├── __init__.py
│   ├── html.py          # Standalone HTML dashboard exporter
│   └── csv_export.py    # CSV spreadsheet exporter
├── sources/
│   ├── __init__.py      # DataSource ABC
│   ├── github.py        # GitHub trending + search API
│   ├── hackernews.py    # HN Firebase API (parallel fetching)
│   ├── reddit.py        # Reddit JSON API
│   ├── arxiv.py         # arXiv Atom API
│   ├── rss.py           # RSS/Atom feed parser
│   └── producthunt.py   # Product Hunt scraper
└── hermes_tool/
    └── __init__.py      # Hermes Agent integration
```

## 🔌 Hermes Agent Integration

Trend Radar works as a Hermes Agent tool:

```python
from trend_radar.hermes_tool import trend_fetch, trend_search, trend_keywords

# Fetch trending intel
result = trend_fetch(sources="github,hackernews", limit=10)

# Search across sources
result = trend_search("AI agent framework")

# Get trending keywords
result = trend_keywords(days=7)
```

## 🧪 Development

```bash
git clone https://github.com/Jane-o-O-o-O/trend-radar.git
cd trend-radar
pip install -e ".[all,dev]"
pytest
```

## 📊 Comparison

| Feature | Trend Radar | starcli | hn-cli | newsboat |
|---------|:-----------:|:------:|:------:|:--------:|
| Multi-source | ✅ 6 sources | GitHub only | HN only | RSS only |
| Live dashboard | ✅ Rich Live | ❌ | ❌ | ❌ |
| Parallel fetching | ✅ ThreadPool | ❌ | ❌ | ❌ |
| Terminal UI | ✅ Rich + sparklines | ✅ | ❌ | ✅ |
| Color themes | ✅ 7 themes | ❌ | ❌ | ❌ |
| Cross-source dedup | ✅ URL+title | ❌ | ❌ | ❌ |
| Snapshot diffing | ✅ Save & compare | ❌ | ❌ | ❌ |
| Webhook alerts | ✅ Slack/Discord/Telegram | ❌ | ❌ | ❌ |
| Obsidian export | ✅ Frontmatter | ❌ | ❌ | ❌ |
| Timeline view | ✅ Sparklines | ❌ | ❌ | ❌ |
| Trend diff | ✅ Rising/falling | ❌ | ❌ | ❌ |
| Topic filtering | ✅ 7 topics | ❌ | ❌ | ❌ |
| Digest reports | ✅ Markdown/HTML | ❌ | ❌ | ❌ |
| Web dashboard | ✅ Chart.js | ❌ | ❌ | ❌ |
| Interactive shell | ✅ REPL | ❌ | ❌ | ❌ |
| History tracking | ✅ SQLite | ❌ | ❌ | ✅ |
| Keyword trends | ✅ Sparklines | ❌ | ❌ | ❌ |
| HTML export | ✅ | ❌ | ❌ | ❌ |
| CSV export | ✅ | ❌ | ❌ | ❌ |
| Caching | ✅ Two-level | ❌ | ❌ | ❌ |
| Health checks | ✅ | ❌ | ❌ | ❌ |
| Setup wizard | ✅ Interactive | ❌ | ❌ | ❌ |
| Docker | ✅ | ❌ | ❌ | ❌ |
| Python API | ✅ | ❌ | ❌ | ❌ |
| AI agent tool | ✅ Hermes | ❌ | ❌ | ❌ |

## 📝 License

MIT © [Jane-o-O-o-O](https://github.com/Jane-o-O-o-O)
