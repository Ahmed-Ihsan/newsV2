"""CLI entry point for Trend Radar — beautiful terminal dashboard."""

import json
import sys
import time

import click
from rich.console import Console
from rich.panel import Panel

from .core import TrendRadar
from .render import JsonRenderer, MarkdownRenderer, TerminalRenderer


def _get_radar(ctx) -> TrendRadar:
    return ctx.obj["radar"]


def _get_console(ctx) -> Console:
    return ctx.obj["console"]


@click.group()
@click.version_option("1.0.0")
@click.option("--db", default=None, help="Path to trends database")
@click.option("--github-token", default=None, help="GitHub personal access token")
@click.option("--config", "config_path", default=None, help="Path to config file")
@click.option("--no-cache", is_flag=True, help="Disable caching")
@click.option("--translate/--no-translate", "translate", default=None,
              help="Translate titles/descriptions for this run (overrides config; see `translate` command)")
@click.pass_context
def main(ctx, db, github_token, config_path, no_cache, translate):
    """📡 Trend Radar — Multi-source tech intelligence CLI.

    Aggregate tech trends from GitHub, Hacker News, Reddit, arXiv, RSS,
    and Product Hunt into a single beautiful terminal dashboard.
    """
    ctx.ensure_object(dict)
    ctx.obj["radar"] = TrendRadar(
        db_path=db,
        github_token=github_token,
        config_path=config_path,
        use_cache=not no_cache,
    )
    if translate is not None:
        ctx.obj["radar"].config.set("translate.enabled", translate)  # this run only (not saved)
    ctx.obj["console"] = Console()


@main.command()
@click.option("--sources", "-s", default=None, help="Comma-separated sources (github,hackernews,reddit,arxiv,rss,producthunt,youtube,devto,lobsters,medium,news)")
@click.option("--limit", "-n", default=15, help="Items per source", type=int)
@click.option("--layout", "-l", type=click.Choice(["table", "cards", "compact"]), default="table")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option("--markdown", "output_md", is_flag=True, help="Output as Markdown")
@click.option("--html", "output_html", is_flag=True, help="Output as standalone HTML")
@click.option("--csv", "output_csv", is_flag=True, help="Output as CSV")
@click.option("--watch", "-w", is_flag=False, type=int, default=0, help="Auto-refresh every N seconds (0=off)")
@click.option("--no-banner", is_flag=True, help="Hide ASCII banner")
@click.option("--output", "-o", "output_file", default=None, help="Write output to file")
@click.option("--topic", "-t", default=None, help="Filter by topic (ai, web, mobile, security, devops, data, lang)")
@click.option("--no-parallel", is_flag=True, help="Disable parallel source fetching")
@click.pass_context
def fetch(ctx, sources, limit, layout, output_json, output_md, output_html, output_csv, watch, no_banner, output_file, topic, no_parallel):
    """Fetch trending intel from all sources."""
    radar = _get_radar(ctx)
    console = _get_console(ctx)
    source_list = sources.split(",") if sources else None

    def do_fetch():
        # Use progress-aware fetch for terminal output, plain collect for file outputs
        is_terminal_output = not (output_json or output_md or output_html or output_csv or output_file)

        if is_terminal_output:
            from .render import SOURCE_EMOJI
            from .models import SourceType

            def progress_callback(event, data):
                src = data.get("source", "")
                try:
                    st = SourceType(src) if src != "producthunt" else SourceType.PRODUCTHUNT
                    emoji = SOURCE_EMOJI.get(st, "•")
                except ValueError:
                    emoji = "•"

                if event == "source_done":
                    n = data.get("items", 0)
                    cached = " (cached)" if data.get("cached") else ""
                    console.print(f"  [green]✓[/] {emoji} {src}: [bold]{n}[/] items{cached}")
                elif event == "source_error":
                    err = data.get("error", "")[:60]
                    console.print(f"  [red]✗[/] {emoji} {src}: {err}")

            with console.status("[bold bright_cyan]📡 Fetching intel from sources...[/]"):
                snapshot = radar.collect_with_progress(
                    sources=source_list,
                    limit=limit,
                    parallel=not no_parallel,
                    callback=progress_callback,
                )
        else:
            with console.status("[bold bright_cyan]📡 Fetching intel...[/]"):
                snapshot = radar.collect(
                    sources=source_list,
                    limit=limit,
                    parallel=not no_parallel,
                )

        # Apply topic filter
        if topic and snapshot.items:
            snapshot.items = [i for i in snapshot.items if radar._matches_topic(i, topic)]

        if output_json:
            text = JsonRenderer().render(snapshot)
        elif output_md:
            text = MarkdownRenderer().render(snapshot)
        elif output_html:
            from .exporters.html import HtmlRenderer
            text = HtmlRenderer().render(snapshot)
        elif output_csv:
            from .exporters.csv_export import CsvRenderer
            text = CsvRenderer().render(snapshot)
        elif output_file:
            # Auto-detect format from extension
            ext = output_file.rsplit(".", 1)[-1].lower() if "." in output_file else ""
            if ext == "html" or ext == "htm":
                from .exporters.html import HtmlRenderer
                text = HtmlRenderer().render(snapshot)
            elif ext == "csv":
                from .exporters.csv_export import CsvRenderer
                text = CsvRenderer().render(snapshot)
            elif ext == "json":
                text = JsonRenderer().render(snapshot)
            else:
                text = MarkdownRenderer().render(snapshot)
        else:
            TerminalRenderer(console, show_banner=not no_banner).render_snapshot(snapshot, layout=layout)
            return

        if output_file:
            from pathlib import Path
            Path(output_file).write_text(text, encoding="utf-8")
            console.print(f"[green]✓[/] Output written to [bold]{output_file}[/]")
        else:
            click.echo(text)

    if watch > 0:
        try:
            while True:
                console.clear()
                do_fetch()
                console.print(f"\n[dim]Refreshing in {watch}s... (Ctrl+C to stop)[/dim]")
                time.sleep(watch)
        except KeyboardInterrupt:
            console.print("\n[dim]Stopped.[/dim]")
    else:
        do_fetch()


@main.command()
@click.option("--limit", "-n", default=15, help="Items per source", type=int)
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option("--no-banner", is_flag=True, help="Hide ASCII banner")
@click.pass_context
def ai(ctx, limit, output_json, no_banner):
    """Fetch AI/LLM focused intel across all sources."""
    radar = _get_radar(ctx)
    console = _get_console(ctx)

    with console.status("[bold bright_cyan]🤖 Fetching AI intel...[/]"):
        snapshot = radar.collect_ai_focused(limit=limit)

    if output_json:
        click.echo(JsonRenderer().render(snapshot))
    else:
        TerminalRenderer(console, show_banner=not no_banner).render_snapshot(snapshot)


@main.command()
@click.argument("query")
@click.option("--sources", "-s", default="github,hackernews,reddit,arxiv", help="Sources to search")
@click.option("--limit", "-n", default=20, help="Max results", type=int)
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.pass_context
def search(ctx, query, sources, limit, output_json):
    """Search across all sources for a query."""
    radar = _get_radar(ctx)
    console = _get_console(ctx)
    source_list = sources.split(",")

    with console.status(f"[bold bright_cyan]🔍 Searching for '{query}'...[/]"):
        items = radar.search(query, sources=source_list, limit=limit)

    if output_json:
        from .models import TrendSnapshot
        snapshot = TrendSnapshot(items=items)
        click.echo(JsonRenderer().render(snapshot))
    else:
        TerminalRenderer(console, show_banner=False).render_items(items, title=f"🔍 Search: {query}")


@main.command()
@click.argument("question")
@click.option("--sources", "-s", default=None, help="Comma-separated sources to analyze (default: all enabled)")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.pass_context
def ask(ctx, question, sources, output_json):
    """Ask an AI analyst (Z.AI GLM) a question about the current trends.

    Needs a Z.AI API key in the ZAI_API_KEY environment variable.
    """
    from rich.markdown import Markdown
    from .analyst import AnalystError, NewsAnalyst

    radar = _get_radar(ctx)
    console = _get_console(ctx)
    analyst = NewsAnalyst.from_config(radar.config)
    source_list = sources.split(",") if sources else None

    try:
        with console.status("[bold bright_cyan]📡 Collecting trends...[/]"):
            snapshot = radar.collect(sources=source_list, limit=15, save=False, translate=False)
        with console.status(f"[bold bright_cyan]🧠 Asking {analyst.model}...[/]"):
            answer = analyst.ask(question, snapshot.items)
    except AnalystError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    if output_json:
        click.echo(json.dumps(answer.to_dict(), ensure_ascii=False, indent=2))
        return

    console.print(Panel(Markdown(answer.text), title=f"🧠 {question}", border_style="bright_cyan"))
    if answer.cited:
        console.print("[dim]Sources:[/]")
        for n in answer.cited:
            item = answer.items[n - 1]
            console.print(f"  [bold]\\[{n}][/] {item.title} [dim]({item.source.value})[/] {item.url}")
    console.print(f"[dim]{answer.model}, {len(answer.items)} items analyzed[/]")


@main.command()
@click.option("--hours", "-h", default=24, help="Hours of history", type=int)
@click.option("--source", "-s", default=None, help="Filter by source")
@click.option("--limit", "-n", default=30, help="Max items", type=int)
@click.pass_context
def history(ctx, hours, source, limit):
    """Show trending items from recent history."""
    radar = _get_radar(ctx)
    console = _get_console(ctx)

    items_raw = radar.store.get_trending_items(hours=hours, source=source, limit=limit)

    if not items_raw:
        console.print(Panel("[dim]No history found. Run 'trend-radar fetch' first.[/dim]", border_style="dim"))
        return

    from .models import IntelItem, SourceType
    items = []
    for r in items_raw:
        try:
            src = SourceType(r["source"])
        except ValueError:
            src = SourceType.RSS
        items.append(
            IntelItem(
                title=r["title"],
                source=src,
                url=r.get("url", ""),
                description=r.get("description", ""),
                score=r.get("score", 0),
                author=r.get("author", ""),
            )
        )

    TerminalRenderer(console, show_banner=False).render_items(items, title=f"📊 History ({hours}h)")


@main.command()
@click.option("--days", "-d", default=7, help="Days to look back", type=int)
@click.pass_context
def keywords(ctx, days):
    """Show trending keywords from recent data."""
    radar = _get_radar(ctx)
    console = _get_console(ctx)

    kw = radar.store.get_keyword_trends(days=days)

    if not kw:
        console.print("[dim]No data found. Run 'trend-radar fetch' first.[/dim]")
        return

    from .render import progress_bar
    max_count = max(c for _, c in kw) if kw else 1

    console.print(f"\n[bold]🔑 Trending Keywords ({days} days)[/]\n")
    for word, count in kw[:25]:
        bar = progress_bar(count, max_count, width=30)
        if count >= 5:
            style = "bold bright_red"
        elif count >= 3:
            style = "bright_yellow"
        else:
            style = "dim"
        console.print(f"  [{style}]{word:<20} {bar} {count:>4}[/{style}]")


@main.command()
@click.pass_context
def stats(ctx):
    """Show database and cache statistics."""
    radar = _get_radar(ctx)
    console = _get_console(ctx)

    st = radar.get_stats()

    from rich.table import Table as RichTable
    tbl = RichTable(title="📊 Trend Radar Stats", show_lines=False, border_style="bright_blue")
    tbl.add_column("Metric", style="bold")
    tbl.add_column("Value", justify="right")

    tbl.add_row("Snapshots", str(st.get("total_snapshots", 0)))
    tbl.add_row("Items", str(st.get("total_items", 0)))
    tbl.add_row("Sources", ", ".join(st.get("sources", [])) or "none")
    tbl.add_row("Latest", st.get("latest_snapshot") or "never")

    if "cache" in st:
        cache = st["cache"]
        tbl.add_row("Cache (memory)", str(cache.get("memory_entries", 0)))
        tbl.add_row("Cache (disk)", str(cache.get("disk_entries", 0)))
        disk_kb = cache.get("disk_size_bytes", 0) / 1024
        tbl.add_row("Cache size", f"{disk_kb:.1f} KB")

    console.print()
    console.print(tbl)


@main.command("translate")
@click.argument("state", type=click.Choice(["on", "off", "status"]), default="status")
@click.option("--lang", default=None, help="Target language code (default: ar). e.g. ar, en, fr, es, de, tr")
@click.pass_context
def translate_cmd(ctx, state, lang):
    """Turn auto-translation on/off (default language: Arabic).

    \b
    trend-radar translate on          # enable (saved in config)
    trend-radar translate off         # disable
    trend-radar translate status
    trend-radar translate on --lang fr
    """
    from .translate import LANGUAGES

    radar = _get_radar(ctx)
    console = _get_console(ctx)
    cfg = radar.config

    if lang:
        cfg.set("translate.target", lang)
    if state in ("on", "off"):
        cfg.set("translate.enabled", state == "on")
    if state in ("on", "off") or lang:
        cfg.save()

    target = cfg.translate_target
    name = LANGUAGES.get(target, target)
    if cfg.translate_enabled:
        console.print(f"[green]✓[/] Auto-translate is [bold]ON[/] → {name} ({target})")
    else:
        console.print(f"[yellow]○[/] Auto-translate is [bold]OFF[/] (target: {name})")


@main.command()
@click.pass_context
def config_show(ctx):
    """Show current configuration."""
    radar = _get_radar(ctx)
    console = _get_console(ctx)

    import yaml
    cfg = radar.config._config
    console.print("\n[bold]⚙️  Configuration[/]\n")
    console.print(yaml.dump(cfg, default_flow_style=False, sort_keys=False))


@main.command()
@click.argument("key")
@click.argument("value")
@click.pass_context
def config_set(ctx, key, value):
    """Set a configuration value (dot-separated path)."""
    radar = _get_radar(ctx)
    console = _get_console(ctx)

    # Try to parse as number/bool
    if value.lower() == "true":
        parsed = True
    elif value.lower() == "false":
        parsed = False
    else:
        try:
            parsed = int(value)
        except ValueError:
            try:
                parsed = float(value)
            except ValueError:
                parsed = value

    radar.config.set(key, parsed)
    radar.config.save()
    console.print(f"[green]✓[/] Set [bold]{key}[/] = {parsed}")


@main.command()
@click.pass_context
def sources_list(ctx):
    """List available data sources and their status."""
    radar = _get_radar(ctx)
    console = _get_console(ctx)

    from .core import SOURCE_CLASSES
    from .models import SourceType
    from .render import SOURCE_EMOJI

    from rich.table import Table as RichTable
    tbl = RichTable(title="📡 Data Sources", show_lines=False, border_style="bright_blue")
    tbl.add_column("", width=3)
    tbl.add_column("Source", style="bold")
    tbl.add_column("Status", justify="center")
    tbl.add_column("Class", style="dim")

    for name, cls in SOURCE_CLASSES.items():
        try:
            st = SourceType(name) if name != "producthunt" else SourceType.PRODUCTHUNT
        except ValueError:
            st = SourceType.RSS
        emoji = SOURCE_EMOJI.get(st, "•")
        enabled = name in radar.sources
        status = "[green]✓ enabled[/]" if enabled else "[red]✗ disabled[/]"
        tbl.add_row(emoji, name, status, cls.__name__)

    console.print()
    console.print(tbl)


@main.command()
@click.option("--host", "-h", default="127.0.0.1", help="Host to bind")
@click.option("--port", "-p", default=8765, help="Port to listen on", type=int)
@click.option("--no-browser", is_flag=True, help="Don't auto-open browser")
@click.pass_context
def serve(ctx, host, port, no_browser):
    """Start the web dashboard server."""
    radar = _get_radar(ctx)
    console = _get_console(ctx)

    try:
        from .web import create_app, HAS_FASTAPI
        if not HAS_FASTAPI:
            console.print("[red]Error:[/red] fastapi and uvicorn are required.")
            console.print("Install with: [bold]pip install fastapi uvicorn[/]")
            sys.exit(1)
    except ImportError:
        console.print("[red]Error:[/red] fastapi and uvicorn are required.")
        console.print("Install with: [bold]pip install fastapi uvicorn[/]")
        sys.exit(1)

    app = create_app(radar=radar, host=host, port=port)

    console.print(f"\n[bold bright_cyan]📡 Trend Radar Web Dashboard[/]")
    console.print(f"   [dim]Open:[/] [link=http://{host}:{port}]http://{host}:{port}[/link]")
    console.print(f"   [dim]API:[/]  [link=http://{host}:{port}/api/fetch]http://{host}:{port}/api/fetch[/link]")
    console.print(f"\n[dim]Press Ctrl+C to stop.[/]\n")

    if not no_browser:
        import webbrowser
        try:
            webbrowser.open(f"http://{host}:{port}")
        except Exception:
            pass

    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="warning")


@main.command()
@click.pass_context
def shell(ctx):
    """Launch interactive Trend Radar shell."""
    radar = _get_radar(ctx)
    console = _get_console(ctx)
    from .shell import run_shell
    run_shell(radar, console)


@main.command()
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option("--no-banner", is_flag=True, help="Hide ASCII banner")
@click.pass_context
def diff(ctx, output_json, no_banner):
    """Compare latest two snapshots — show rising/falling trends."""
    radar = _get_radar(ctx)
    console = _get_console(ctx)

    with console.status("[bold bright_cyan]📊 Computing diff...[/]"):
        diff_data = radar.diff_snapshots()

    if output_json:
        import json
        click.echo(json.dumps(diff_data, indent=2, ensure_ascii=False, default=str))
    else:
        from .render import TerminalRenderer
        TerminalRenderer(console, show_banner=not no_banner).render_diff(diff_data)


@main.command()
@click.option("--limit", "-n", default=20, help="Max items", type=int)
@click.option("--hours", "-h", default=24, help="Hours to look back", type=int)
@click.option("--source", "-s", default=None, help="Filter by source")
@click.option("--topic", "-t", default=None, help="Filter by topic (ai, web, mobile, security, devops, data, lang)")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option("--no-banner", is_flag=True, help="Hide ASCII banner")
@click.pass_context
def top(ctx, limit, hours, source, topic, output_json, no_banner):
    """Quick view of top trending items across all sources."""
    radar = _get_radar(ctx)
    console = _get_console(ctx)

    with console.status("[bold bright_cyan]🏆 Loading top items...[/]"):
        items = radar.get_top_items(limit=limit, hours=hours, source=source, topic=topic)

    if output_json:
        from .models import TrendSnapshot
        snapshot = TrendSnapshot(items=items)
        click.echo(JsonRenderer().render(snapshot))
    else:
        topic_label = f" [{topic}]" if topic else ""
        source_label = f" ({source})" if source else ""
        from .render import TerminalRenderer
        TerminalRenderer(console, show_banner=not no_banner).render_items(
            items, title=f"🏆 Top {limit}{topic_label}{source_label} ({hours}h)"
        )


@main.command()
@click.pass_context
def health(ctx):
    """Check data source connectivity and response times."""
    radar = _get_radar(ctx)
    console = _get_console(ctx)

    with console.status("[bold bright_cyan]🏥 Checking sources...[/]"):
        results = radar.check_health()

    from .render import TerminalRenderer
    TerminalRenderer(console, show_banner=False).render_health(results)



@main.command()
@click.argument("keyword")
@click.option("--threshold", "-t", default=1, help="Alert when keyword appears N+ times", type=int)
@click.option("--source", "-s", default=None, help="Only watch specific source")
@click.pass_context
def alert_add(ctx, keyword, threshold, source):
    """Add a keyword alert to watchlist."""
    from .alerts import AlertStore
    console = _get_console(ctx)
    store = AlertStore()
    alert = store.add_alert(keyword, threshold=threshold, source_filter=source)
    console.print(f"[green]✓[/] Alert added: [bold]{keyword}[/] (threshold: {threshold})")


@main.command()
@click.pass_context
def alert_list(ctx):
    """List all configured alerts."""
    from .alerts import AlertStore
    from rich.table import Table as RichTable
    console = _get_console(ctx)
    store = AlertStore()
    alerts = store.list_alerts()

    if not alerts:
        console.print("[dim]No alerts configured. Use 'trend-radar alert-add <keyword>' to add one.[/dim]")
        return

    tbl = RichTable(title="🔔 Trend Alerts", border_style="bright_blue")
    tbl.add_column("Keyword", style="bold bright_cyan")
    tbl.add_column("Threshold", justify="right")
    tbl.add_column("Source", style="dim")
    tbl.add_column("Triggered", justify="right")
    tbl.add_column("Status")

    for a in alerts:
        status = "[green]✓ active[/]" if a.enabled else "[dim]disabled[/]"
        tbl.add_row(a.keyword, str(a.threshold), a.source_filter or "all", str(a.triggered_count), status)

    console.print(tbl)


@main.command()
@click.argument("keyword")
@click.pass_context
def alert_remove(ctx, keyword):
    """Remove a keyword alert."""
    from .alerts import AlertStore
    console = _get_console(ctx)
    store = AlertStore()
    if store.remove_alert(keyword):
        console.print(f"[green]✓[/] Removed alert: [bold]{keyword}[/]")
    else:
        console.print(f"[red]Alert not found:[/red] {keyword}")


@main.command()
@click.option("--sources", "-s", default=None, help="Comma-separated sources to check")
@click.option("--limit", "-n", default=25, help="Items per source", type=int)
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.pass_context
def alerts_check(ctx, sources, limit, output_json):
    """Check current trends against alert watchlist."""
    from .alerts import AlertStore
    radar = _get_radar(ctx)
    console = _get_console(ctx)
    store = AlertStore()

    source_list = sources.split(",") if sources else None
    with console.status("[bold bright_cyan]🔔 Checking alerts...[/]"):
        snapshot = radar.collect(sources=source_list, limit=limit, save=False)

    items_dicts = [i.to_dict() for i in snapshot.items]
    matches = store.check_alerts(items_dicts)

    if output_json:
        import json
        click.echo(json.dumps([m.to_dict() for m in matches], indent=2, ensure_ascii=False))
        return

    if not matches:
        console.print("[dim]No alerts triggered.[/dim]")
        return

    console.print()
    from rich.table import Table as RichTable
    for match in matches:
        tbl = RichTable(
            title=f"🔔 [bold bright_red]{match.alert.keyword}[/] — {match.count} matches",
            border_style="bright_red",
        )
        tbl.add_column("#", style="dim", width=3)
        tbl.add_column("Title", style="bright_white", ratio=3)
        tbl.add_column("Source", style="dim", width=12)
        tbl.add_column("Score", justify="right", width=10)

        for i, item in enumerate(match.matching_items[:10], 1):
            tbl.add_row(str(i), item.get("title", ""), item.get("source", ""), str(item.get("score", 0)))

        console.print(tbl)

    console.print()


@main.command()
@click.option("--hours", "-h", default=48, help="Hours of history to analyze", type=int)
@click.option("--limit", "-n", default=20, help="Max items to show", type=int)
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option("--no-banner", is_flag=True, help="Hide ASCII banner")
@click.pass_context
def momentum(ctx, hours, limit, output_json, no_banner):
    """Show trend momentum — velocity and acceleration of trending items."""
    from .momentum import analyze_snapshot_momentum
    radar = _get_radar(ctx)
    console = _get_console(ctx)

    with console.status("[bold bright_cyan]📈 Analyzing momentum...[/]"):
        data = analyze_snapshot_momentum(radar.store, hours=hours)

    if output_json:
        import json
        click.echo(json.dumps([d.to_dict() for d in data[:limit]], indent=2))
        return

    if not data:
        console.print("[dim]Not enough history. Run 'trend-radar fetch' at least twice.[/dim]")
        return

    from rich.table import Table as RichTable
    tbl = RichTable(title="📈 Trend Momentum", border_style="bright_cyan", show_lines=True)
    tbl.add_column("#", style="dim", width=3)
    tbl.add_column("Title", style="bright_white", ratio=3)
    tbl.add_column("Source", style="dim", width=10)
    tbl.add_column("Score", justify="right", width=8)
    tbl.add_column("Δ", justify="right", width=8)
    tbl.add_column("Velocity/hr", justify="right", width=12)
    tbl.add_column("Trajectory", justify="center", width=10)
    tbl.add_column("24h Pred", justify="right", width=10)

    trajectory_emoji = {
        "viral": "🔥",
        "rising": "🔺",
        "stable": "➡️",
        "falling": "🔻",
        "dead": "💀",
    }

    for i, m in enumerate(data[:limit], 1):
        emoji = trajectory_emoji.get(m.trajectory, "❓")
        vel_str = f"+{m.velocity:.0f}" if m.velocity > 0 else f"{m.velocity:.0f}"
        vel_style = "bright_green" if m.velocity > 0 else "red" if m.velocity < 0 else "dim"
        delta_str = f"+{m.score_delta}" if m.score_delta > 0 else str(m.score_delta)

        tbl.add_row(
            str(i),
            m.title[:60],
            m.source,
            str(m.current_score),
            f"[{'green' if m.score_delta > 0 else 'red'}]{delta_str}[/]",
            f"[{vel_style}]{vel_str}[/]",
            f"{emoji} {m.trajectory}",
            str(m.predicted_score_24h),
        )

    console.print()
    console.print(tbl)
    console.print()


@main.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--merge/--replace", default=True, help="Merge with existing feeds or replace")
@click.pass_context
def opml_import(ctx, file_path, merge):
    """Import RSS feeds from OPML/JSON/URL file."""
    from .opml import import_feeds
    radar = _get_radar(ctx)
    console = _get_console(ctx)

    try:
        feeds = import_feeds(file_path)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    if merge:
        existing = radar.config.get("sources.rss.feeds", {}) or {}
        existing.update(feeds)
        radar.config.set("sources.rss.feeds", existing)
    else:
        radar.config.set("sources.rss.feeds", feeds)

    radar.config.save()

    console.print(f"[green]✓[/] Imported [bold]{len(feeds)}[/] RSS feeds from [bold]{file_path}[/]")
    for name, url in list(feeds.items())[:10]:
        console.print(f"  [dim]•[/] {name}: {url}")
    if len(feeds) > 10:
        console.print(f"  [dim]... and {len(feeds) - 10} more[/]")


@main.command()
@click.option("--limit", "-n", default=20, help="Max items", type=int)
@click.option("--sources", "-s", default=None, help="Comma-separated sources")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option("--no-banner", is_flag=True, help="Hide ASCII banner")
@click.pass_context
def ranked(ctx, limit, sources, output_json, no_banner):
    """Cross-source normalized ranking — fair comparison across all sources."""
    from .normalization import rank_cross_source, normalized_badge, enrich_with_normalized
    from .render import SOURCE_EMOJI
    radar = _get_radar(ctx)
    console = _get_console(ctx)
    source_list = sources.split(",") if sources else None

    with console.status("[bold bright_cyan]🏆 Ranking across sources...[/]"):
        snapshot = radar.collect(sources=source_list, limit=limit, save=False)

    ranked_items = rank_cross_source(snapshot.items, top_n=limit)

    if output_json:
        import json
        click.echo(json.dumps([i.to_dict() for i in ranked_items], indent=2))
        return

    if not ranked_items:
        console.print("[dim]No items found.[/dim]")
        return

    from rich.table import Table as RichTable
    from rich.text import Text

    tbl = RichTable(title="🏆 Cross-Source Ranking (Normalized 0-100)", border_style="bright_cyan", show_lines=False)
    tbl.add_column("#", style="dim", width=3)
    tbl.add_column("", width=3)
    tbl.add_column("Title", style="bright_white", ratio=3)
    tbl.add_column("Source", style="dim", width=12)
    tbl.add_column("Raw Score", justify="right", width=10)
    tbl.add_column("Normalized", justify="right", width=12)

    for i, item in enumerate(ranked_items, 1):
        emoji = SOURCE_EMOJI.get(item.source, "•")
        norm = item.extra.get("normalized_score", 0)
        badge_emoji, badge_style = normalized_badge(norm)
        score_display = item.score_display

        tbl.add_row(
            str(i),
            emoji,
            item.title[:60],
            item.source.value,
            score_display,
            Text(f"{badge_emoji} {norm:.0f}", style=badge_style),
        )

    console.print()
    console.print(tbl)
    console.print()

@main.command()
@click.option("--sources", "-s", default=None, help="Comma-separated sources")
@click.option("--limit", "-n", default=15, help="Items per source", type=int)
@click.option("--interval", "-i", default=30, help="Refresh interval in seconds", type=int)
@click.pass_context
def live(ctx, sources, limit, interval):
    """Live auto-refreshing terminal dashboard (Ctrl+C to stop)."""
    from .live import LiveDashboard
    radar = _get_radar(ctx)
    console = _get_console(ctx)
    source_list = sources.split(",") if sources else None

    console.print("\n[bold bright_cyan]📡 Starting live dashboard...[/]")
    console.print(f"[dim]Refreshing every {interval}s · Press Ctrl+C to stop[/]\n")

    dashboard = LiveDashboard(radar, console, interval=interval)
    dashboard.run(sources=source_list, limit=limit)


@main.command()
@click.option("--sources", "-s", default=None, help="Comma-separated sources")
@click.option("--limit", "-n", default=15, help="Items per source", type=int)
@click.option("--format", "-f", "fmt", type=click.Choice(["markdown", "html"]), default="markdown")
@click.option("--title", "-t", default=None, help="Custom digest title")
@click.option("--output", "-o", "output_file", default=None, help="Output file path")
@click.pass_context
def digest(ctx, sources, limit, fmt, title, output_file):
    """Generate a shareable trend digest report."""
    from .digest import generate_digest_markdown, generate_digest_html
    radar = _get_radar(ctx)
    console = _get_console(ctx)
    source_list = sources.split(",") if sources else None

    with console.status("[bold bright_cyan]📝 Generating digest...[/]"):
        snapshot = radar.collect(sources=source_list, limit=limit, save=False)

    if fmt == "html":
        text = generate_digest_html(snapshot, title=title, top_n=limit)
        default_ext = ".html"
    else:
        text = generate_digest_markdown(snapshot, title=title, top_n=limit)
        default_ext = ".md"

    if output_file:
        from pathlib import Path
        Path(output_file).write_text(text, encoding="utf-8")
        console.print(f"[green]✓[/] Digest written to [bold]{output_file}[/]")
    else:
        # Auto-generate filename
        ts = snapshot.timestamp.strftime("%Y%m%d_%H%M")
        filename = f"trend-digest-{ts}{default_ext}"
        from pathlib import Path
        Path(filename).write_text(text, encoding="utf-8")
        console.print(f"[green]✓[/] Digest written to [bold]{filename}[/]")
        console.print(f"[dim]Share it on Slack, Discord, or social media![/]")


@main.command()
@click.option("--config", "config_path", default=None, help="Custom config file path")
@click.pass_context
def init(ctx, config_path):
    """Interactive first-run setup wizard."""
    from .init_wizard import run_init_wizard
    console = _get_console(ctx)
    run_init_wizard(console, config_path=config_path)


@main.command()
@click.pass_context
def version(ctx):
    """Show version and system info."""
    import platform
    console = _get_console(ctx)

    from rich.table import Table as RichTable
    tbl = RichTable(title="📡 Trend Radar", show_header=False, border_style="bright_cyan")
    tbl.add_column("Key", style="bold")
    tbl.add_column("Value")

    tbl.add_row("Version", "0.8.0")
    tbl.add_row("Python", platform.python_version())
    tbl.add_row("Platform", platform.platform())
    tbl.add_row("Sources", "GitHub, HN, Reddit, arXiv, RSS, Product Hunt")

    # Check optional deps
    deps = []
    for pkg, label in [("fastapi", "Web"), ("uvicorn", "Web"), ("prompt_toolkit", "Shell"), ("rich", "Rich")]:
        try:
            __import__(pkg)
            deps.append(f"✓ {label}")
        except ImportError:
            deps.append(f"✗ {label} (not installed)")

    tbl.add_row("Features", "\n".join(deps))

    console.print()
    console.print(tbl)
    console.print()


# ============================================================
# v0.8.0 — Radar Chart, Bookmarks, Plugins, Compare, Completions
# ============================================================

@main.command()
@click.option("--sources", "-s", default=None, help="Comma-separated sources")
@click.option("--limit", "-n", default=25, help="Items per source", type=int)
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.pass_context
def radar(ctx, sources, limit, output_json):
    """Show topic distribution as a radar/spider chart."""
    radar_inst = _get_radar(ctx)
    console = _get_console(ctx)
    source_list = sources.split(",") if sources else None

    with console.status("[bold bright_cyan]📡 Building radar...[/]"):
        snapshot = radar_inst.collect(sources=source_list, limit=limit, save=False)

    if output_json:
        from .radar_chart import compute_topic_distribution
        dist = compute_topic_distribution(snapshot.items)
        click.echo(json.dumps(dist, indent=2))
        return

    from .radar_chart import render_radar_chart, render_topic_breakdown
    render_radar_chart(console, snapshot.items)
    render_topic_breakdown(console, snapshot.items)


@main.command()
@click.argument("action", type=click.Choice(["add", "list", "search", "remove", "star", "export"]))
@click.argument("target", required=False, default=None)
@click.option("--source", "-s", default=None, help="Filter by source")
@click.option("--starred", is_flag=True, help="Show only starred bookmarks")
@click.option("--notes", "-n", default="", help="Notes for bookmark")
@click.option("--limit", "-l", default=20, help="Max results", type=int)
@click.pass_context
def bookmark(ctx, action, target, source, starred, notes, limit):
    """Manage bookmarks — save interesting items for later.

    \b
    Actions:
      add <title>       Add a bookmark by title (searches latest snapshot)
      list              List all bookmarks
      search <query>    Search bookmarks
      remove <id>       Remove bookmark by ID
      star <id>         Toggle star on bookmark
      export            Export bookmarks as JSON
    """
    from .bookmarks import BookmarkStore
    radar_inst = _get_radar(ctx)
    console = _get_console(ctx)
    store = BookmarkStore(db_path=radar_inst.store.db_path)

    if action == "add":
        if not target:
            console.print("[red]Error:[/red] Provide a title to bookmark")
            return
        # Find matching item in latest snapshot
        from .models import IntelItem, SourceType
        item = IntelItem(title=target, source=SourceType.RSS, description="", score=0)
        bid = store.add(item, notes=notes)
        console.print(f"[green]✓[/] Bookmarked [bold]{target}[/] (id: {bid})")

    elif action == "list":
        bookmarks = store.list_all(source=source, starred_only=starred, limit=limit)
        if not bookmarks:
            console.print("[dim]No bookmarks found.[/dim]")
            return

        from rich.table import Table as RichTable
        tbl = RichTable(title="⭐ Bookmarks", border_style="bright_yellow")
        tbl.add_column("ID", style="dim", width=4)
        tbl.add_column("⭐", width=3)
        tbl.add_column("Title", style="bright_white", ratio=3)
        tbl.add_column("Source", style="dim", width=12)
        tbl.add_column("Notes", style="dim", ratio=2)

        for bm in bookmarks:
            star = "★" if bm.get("starred") else " "
            tbl.add_row(str(bm["id"]), star, bm["title"][:60], bm["source"], (bm.get("notes") or "")[:40])

        console.print()
        console.print(tbl)
        console.print()

    elif action == "search":
        if not target:
            console.print("[red]Error:[/red] Provide a search query")
            return
        results = store.search(target, limit=limit)
        if not results:
            console.print(f"[dim]No bookmarks matching '{target}'[/dim]")
            return
        for bm in results:
            star = "★" if bm.get("starred") else " "
            console.print(f"  {star} [bold]{bm['id']}[/] {bm['title']} [dim]({bm['source']})[/]")

    elif action == "remove":
        if not target:
            console.print("[red]Error:[/red] Provide bookmark ID")
            return
        if store.remove(int(target)):
            console.print(f"[green]✓[/] Removed bookmark {target}")
        else:
            console.print(f"[red]Bookmark not found:[/red] {target}")

    elif action == "star":
        if not target:
            console.print("[red]Error:[/red] Provide bookmark ID")
            return
        new_state = store.toggle_star(int(target))
        if new_state is not None:
            label = "★ starred" if new_state else "☆ unstarred"
            console.print(f"[green]✓[/] {label} bookmark {target}")
        else:
            console.print(f"[red]Bookmark not found:[/red] {target}")

    elif action == "export":
        data = store.export_json(limit=limit)
        click.echo(data)


@main.command()
@click.argument("action", type=click.Choice(["list", "load", "info"]))
@click.argument("name", required=False, default=None)
@click.pass_context
def plugins(ctx, action, name):
    """Manage custom data source plugins.

    \b
    Actions:
      list              List all registered plugins
      load <dir>        Load plugins from a directory
      info <name>       Show plugin details
    """
    from .plugins import PluginManager
    console = _get_console(ctx)
    manager = PluginManager()

    if action == "list":
        # Also load from default directory
        manager.load_from_directory()
        plugins_list = manager.list_plugins()

        if not plugins_list:
            console.print("[dim]No plugins registered.[/dim]")
            console.print("[dim]Place .py files in ~/.trend-radar/plugins/ to add custom sources.[/dim]")
            return

        from rich.table import Table as RichTable
        tbl = RichTable(title="🔌 Plugins", border_style="bright_magenta")
        tbl.add_column("Name", style="bold bright_cyan")
        tbl.add_column("Class", style="bright_white")
        tbl.add_column("Module", style="dim")
        tbl.add_column("Description", ratio=2)

        for pname, info in plugins_list.items():
            tbl.add_row(pname, info["class"], info["module"], info["doc"])

        console.print()
        console.print(tbl)
        console.print()

    elif action == "load":
        if not name:
            console.print("[red]Error:[/red] Provide a directory path")
            return
        manager = PluginManager(plugin_dirs=[name])
        loaded = manager.load_from_directory()
        if loaded:
            console.print(f"[green]✓[/] Loaded {len(loaded)} plugin(s): {', '.join(loaded)}")
        else:
            console.print(f"[dim]No plugins found in {name}[/]")

    elif action == "info":
        if not name:
            console.print("[red]Error:[/red] Provide a plugin name")
            return
        manager.load_from_directory()
        plugins_list = manager.list_plugins()
        if name in plugins_list:
            info = plugins_list[name]
            console.print(f"\n[bold]Plugin:[/] {name}")
            console.print(f"[bold]Class:[/] {info['class']}")
            console.print(f"[bold]Module:[/] {info['module']}")
            console.print(f"[bold]Description:[/] {info['doc']}")
        else:
            console.print(f"[red]Plugin not found:[/red] {name}")


@main.command()
@click.option("--period1", "-p1", default=1, help="Days ago for first snapshot", type=int)
@click.option("--period2", "-p2", default=0, help="Days ago for second snapshot (0=latest)", type=int)
@click.option("--limit", "-n", default=20, help="Max items to show", type=int)
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option("--no-banner", is_flag=True, help="Hide banner")
@click.pass_context
def compare(ctx, period1, period2, limit, output_json, no_banner):
    """Compare trends between two time periods.

    Shows what's rising, falling, new, and gone between snapshots.
    By default compares the latest two snapshots.
    """
    radar_inst = _get_radar(ctx)
    console = _get_console(ctx)

    with console.status("[bold bright_cyan]📊 Comparing snapshots...[/]"):
        diff_data = radar_inst.diff_snapshots()

    if output_json:
        click.echo(json.dumps(diff_data, indent=2, ensure_ascii=False, default=str))
        return

    from .render import TerminalRenderer
    TerminalRenderer(console, show_banner=not no_banner).render_diff(diff_data)


@main.command()
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]))
@click.pass_context
def completions(ctx, shell):
    """Generate shell completion scripts.

    \b
    Usage:
      eval "$(trend-radar completions bash)"
      eval "$(trend-radar completions zsh)"
      trend-radar completions fish > ~/.config/fish/completions/trend-radar.fish
    """
    if shell == "bash":
        click.echo("_trend_radar_completion() {")
        click.echo("  COMPREPLY=( $(compgen -W 'fetch ai search ask history keywords stats "
                   "config-show config-set sources-list serve shell diff top health "
                   "alert-add alert-list alert-remove alerts-check momentum opml-import "
                   "ranked live digest init version radar bookmark plugins compare "
                   "completions' -- ${COMP_WORDS[1]}) )")
        click.echo("}")
        click.echo("complete -F _trend_radar_completion trend-radar")
        click.echo("complete -F _trend_radar_completion tr")
    elif shell == "zsh":
        click.echo("#compdef trend-radar tr")
        click.echo("_trend_radar() {")
        click.echo("  _arguments '1:command:(fetch ai search ask history keywords stats "
                   "config-show config-set sources-list serve shell diff top health "
                   "alert-add alert-list alert-remove alerts-check momentum opml-import "
                   "ranked live digest init version radar bookmark plugins compare completions)'")
        click.echo("}")
        click.echo("_trend_radar")
    elif shell == "fish":
        click.echo("complete -c trend-radar -f")
        cmds = ["fetch", "ai", "search", "ask", "history", "keywords", "stats",
                "config-show", "config-set", "sources-list", "serve", "shell",
                "diff", "top", "health", "alert-add", "alert-list", "alert-remove",
                "alerts-check", "momentum", "opml-import", "ranked", "live",
                "digest", "init", "version", "radar", "bookmark", "plugins",
                "compare", "completions"]
        for cmd in cmds:
            click.echo(f"complete -c trend-radar -f -a '{cmd}'")
        click.echo("complete -c tr -f")
        for cmd in cmds:
            click.echo(f"complete -c tr -f -a '{cmd}'")


@main.command()
@click.pass_context
def rate_limits(ctx):
    """Show API rate limiter status for all sources."""
    from .rate_limiter import RateLimiterRegistry
    console = _get_console(ctx)
    registry = RateLimiterRegistry()
    status = registry.status()

    from rich.table import Table as RichTable
    tbl = RichTable(title="⏱️ Rate Limits", border_style="bright_yellow")
    tbl.add_column("Source", style="bold", width=15)
    tbl.add_column("Capacity", justify="right", width=10)
    tbl.add_column("Refill/sec", justify="right", width=12)
    tbl.add_column("Available", justify="right", width=10)

    for name, info in sorted(status.items()):
        tbl.add_row(name, str(info["capacity"]), f"{info['refill_rate']:.1f}", str(info["available"]))

    console.print()
    console.print(tbl)
    console.print()


# ─── v0.9.0 Commands ──────────────────────────────────────────────────────────


@main.command("themes")
@click.option("--list", "list_themes_flag", is_flag=True, help="List available themes")
@click.option("--set", "theme_name", default=None, help="Set active theme")
@click.option("--preview", default=None, help="Preview a theme")
@click.pass_context
def themes_cmd(ctx, list_themes_flag, theme_name, preview):
    """Manage terminal color themes."""
    from .themes import THEMES, list_themes, get_theme
    console = _get_console(ctx)

    if list_themes_flag or (not theme_name and not preview):
        theme_list = list_themes()
        from rich.table import Table as RichTable
        tbl = RichTable(title="🎨 Available Themes", border_style="bright_cyan")
        tbl.add_column("#", width=3, style="dim")
        tbl.add_column("Theme", style="bold")
        tbl.add_column("Primary", width=12)
        tbl.add_column("Accent", width=12)
        tbl.add_column("Description")

        descs = {
            "default": "Clean cyan/yellow theme (default)",
            "dracula": "Popular dark purple/green theme",
            "monokai": "Classic warm orange/green theme",
            "solarized": "Elegant blue/earth-tone theme",
            "nord": "Arctic blue/teal theme",
            "gruvbox": "Retro warm earth-tone theme",
            "light": "Light background theme",
        }
        for i, name in enumerate(theme_list, 1):
            t = get_theme(name)
            tbl.add_row(str(i), name, t.primary, t.accent, descs.get(name, ""))
        console.print()
        console.print(tbl)
        console.print()
        return

    if theme_name:
        if theme_name not in THEMES:
            console.print(f"[red]Theme '{theme_name}' not found. Use --list to see available themes.[/red]")
            return
        # Save to config
        from .config import TrendConfig
        config = TrendConfig(ctx.obj["radar"].config._path if hasattr(ctx.obj["radar"].config, "_path") else None)
        console.print(f"[bright_green]✓ Theme set to '{theme_name}'[/bright_green]")
        console.print(f"[dim]Add 'display.color_theme: {theme_name}' to ~/.trend-radar/config.yaml[/dim]")

    if preview:
        theme = get_theme(preview)
        console.print(f"\n[bold]Preview: {preview}[/bold]")
        console.print(f"  Primary:  [{theme.primary}]██████[/] {theme.primary}")
        console.print(f"  Secondary: [{theme.secondary}]██████[/] {theme.secondary}")
        console.print(f"  Accent:   [{theme.accent}]██████[/] {theme.accent}")
        console.print(f"  GitHub:   [{theme.github}]██████[/] {theme.github}")
        console.print(f"  HN:       [{theme.hackernews}]██████[/] {theme.hackernews}")
        console.print(f"  Reddit:   [{theme.reddit}]██████[/] {theme.reddit}")
        console.print(f"  arXiv:    [{theme.arxiv}]██████[/] {theme.arxiv}")
        console.print(f"  Success:  [{theme.success}]██████[/] {theme.success}")
        console.print(f"  Error:    [{theme.error}]██████[/] {theme.error}")
        console.print()


@main.command("dedup")
@click.option("--sources", "-s", default=None, help="Comma-separated sources to check")
@click.option("--limit", "-n", default=15, help="Items per source", type=int)
@click.option("--threshold", "-t", default=0.7, help="Title similarity threshold (0-1)", type=float)
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.pass_context
def dedup_cmd(ctx, sources, limit, threshold, output_json):
    """Find cross-source duplicates — same story on HN + Reddit + RSS."""
    from .dedup import DedupEngine
    console = _get_console(ctx)
    radar = _get_radar(ctx)

    source_list = sources.split(",") if sources else None
    snapshot = radar.fetch_all(sources=source_list, limit=limit)
    items = snapshot.items

    engine = DedupEngine(title_threshold=threshold)
    unique, groups = engine.deduplicate(items)

    if output_json:
        import json as json_mod
        result = {
            "total_items": len(items),
            "unique_items": len(unique),
            "duplicate_groups": len(groups),
            "groups": [
                {
                    "title": g.primary_title,
                    "url": g.primary_url,
                    "sources": g.sources,
                    "source_count": g.source_count,
                    "total_score": g.total_score,
                    "items": [{"title": i.title, "source": i.source.value, "score": i.score}
                              for i in g.items],
                }
                for g in groups
            ],
        }
        click.echo(json_mod.dumps(result, indent=2, default=str))
        return

    from rich.table import Table as RichTable
    console.print()
    console.print(f"[bold bright_cyan]🔍 Deduplication Results[/]")
    console.print(f"[dim]Total: {len(items)} items → {len(unique)} unique + {len(groups)} duplicate groups[/dim]")
    console.print()

    if not groups:
        console.print("[dim]No cross-source duplicates found.[/dim]")
        console.print()
        return

    tbl = RichTable(title="🔗 Cross-Source Duplicates", border_style="bright_yellow")
    tbl.add_column("#", width=3, style="dim")
    tbl.add_column("Title", style="bold", min_width=30)
    tbl.add_column("Sources", width=20)
    tbl.add_column("Total Score", justify="right", width=12, style="bright_yellow")

    for i, group in enumerate(groups[:20], 1):
        src_str = " + ".join(group.sources)
        tbl.add_row(str(i), group.primary_title[:60], src_str, str(group.total_score))

    console.print(tbl)
    console.print()


@main.command("snapshots")
@click.option("--list", "list_flag", is_flag=True, help="List saved snapshots")
@click.option("--save", "save_flag", is_flag=True, help="Save current fetch as snapshot")
@click.option("--diff", nargs=2, type=int, default=None, help="Diff two snapshots by ID")
@click.option("--auto-diff", is_flag=True, help="Diff the two most recent snapshots")
@click.option("--label", default="", help="Label for saved snapshot")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.pass_context
def snapshots_cmd(ctx, list_flag, save_flag, diff, auto_diff, label, output_json):
    """Save, list, and diff trend snapshots."""
    from .snapshots import SnapshotManager
    console = _get_console(ctx)
    radar = _get_radar(ctx)
    manager = SnapshotManager(radar.store)

    if save_flag:
        snapshot = radar.fetch_all(limit=15)
        snap_id = manager.save_snapshot(snapshot, label=label or "manual")
        console.print(f"[bright_green]✓ Snapshot #{snap_id} saved with {len(snapshot.items)} items[/bright_green]")
        return

    if list_flag or (not diff and not auto_diff):
        snapshots = manager.list_snapshots(limit=20)
        if not snapshots:
            console.print("[dim]No snapshots saved yet. Use `trend-radar fetch` or `trend-radar snapshots --save` first.[/dim]")
            return

        from rich.table import Table as RichTable
        tbl = RichTable(title="📸 Saved Snapshots", border_style="bright_cyan")
        tbl.add_column("ID", width=5, style="bold")
        tbl.add_column("Timestamp", width=22)
        tbl.add_column("Items", justify="right", width=6)
        tbl.add_column("Label", width=20)

        for snap in snapshots:
            tbl.add_row(
                str(snap.get("id", "?")),
                str(snap.get("timestamp", ""))[:19],
                str(snap.get("item_count", "?")),
                snap.get("label", ""),
            )
        console.print()
        console.print(tbl)
        console.print()
        return

    if auto_diff:
        diff_result = manager.auto_diff()
        if not diff_result:
            console.print("[dim]Need at least 2 snapshots to diff.[/dim]")
            return
    elif diff:
        diff_result = manager.diff_snapshots(diff[0], diff[1])
    else:
        return

    if output_json:
        import json as json_mod
        click.echo(json_mod.dumps(diff_result.summary(), indent=2, default=str))
        return

    from rich.panel import Panel
    from rich.text import Text
    summary = diff_result.summary()
    txt = Text()
    txt.append(f"  Snapshot #{diff_result.snapshot_old_id}", style="dim")
    txt.append(f" → ", style="dim")
    txt.append(f"#{diff_result.snapshot_new_id}", style="dim")
    txt.append(f"\n\n")
    txt.append(f"  🆕 New items:      ", style="bright_cyan")
    txt.append(f"{summary['new_items']}", style="bold bright_green")
    txt.append(f"\n")
    txt.append(f"  🗑️  Removed items:   ", style="bright_cyan")
    txt.append(f"{summary['removed_items']}", style="bold bright_red")
    txt.append(f"\n")
    txt.append(f"  📊 Score changes:   ", style="bright_cyan")
    txt.append(f"{summary['score_changes']}", style="bold bright_yellow")
    txt.append(f"\n")

    if summary["top_new"]:
        txt.append(f"\n  Top new items:\n", style="bold")
        for item in summary["top_new"]:
            txt.append(f"    • {item['title'][:50]} ({item['source']}, {item['score']})\n", style="bright_green")

    if summary["top_scored_up"]:
        txt.append(f"\n  Biggest score jumps:\n", style="bold")
        for item in summary["top_scored_up"]:
            txt.append(f"    • {item['title'][:40]} +{item['delta']}\n", style="bright_yellow")

    console.print()
    console.print(Panel(txt, title="📸 Snapshot Diff", border_style="bright_cyan"))
    console.print()


@main.command("webhooks")
@click.option("--list", "list_flag", is_flag=True, help="List configured webhooks")
@click.option("--add", "add_url", default=None, help="Add a webhook URL")
@click.option("--name", default=None, help="Webhook name (used with --add)")
@click.option("--type", "wh_type", default="custom",
              type=click.Choice(["slack", "discord", "telegram", "custom"]),
              help="Webhook type (used with --add)")
@click.option("--remove", default=None, help="Remove a webhook by name")
@click.option("--test", default=None, help="Send test notification to webhook")
@click.option("--chat-id", default="", help="Telegram chat ID (used with --add for telegram)")
@click.pass_context
def webhooks_cmd(ctx, list_flag, add_url, name, wh_type, remove, test, chat_id):
    """Configure notification webhooks for alerts."""
    from .webhooks import WebhookDispatcher, WebhookConfig, WebhookType
    from .config import get_config_dir
    console = _get_console(ctx)

    config_path = get_config_dir() / "webhooks.json"
    dispatcher = WebhookDispatcher()

    # Load existing
    if config_path.exists():
        try:
            import json as json_mod
            data = json_mod.loads(config_path.read_text())
            for w in data:
                dispatcher.add(WebhookConfig.from_dict(w))
        except Exception:
            pass

    if list_flag or (not add_url and not remove and not test):
        webhooks = dispatcher.list_webhooks()
        if not webhooks:
            console.print("[dim]No webhooks configured. Use `trend-radar webhooks --add <url> --name <name>` to add one.[/dim]")
            return

        from rich.table import Table as RichTable
        tbl = RichTable(title="🔔 Webhooks", border_style="bright_magenta")
        tbl.add_column("Name", style="bold")
        tbl.add_column("Type", width=10)
        tbl.add_column("URL", min_width=30)
        tbl.add_column("Enabled", width=8)

        for w in webhooks:
            tbl.add_row(w.name, w.webhook_type.value, w.url[:50] + ("..." if len(w.url) > 50 else ""),
                        "✅" if w.enabled else "❌")
        console.print()
        console.print(tbl)
        console.print()
        return

    if add_url:
        if not name:
            console.print("[red]--name is required when adding a webhook.[/red]")
            return
        wh = WebhookConfig(
            name=name,
            url=add_url,
            webhook_type=WebhookType(wh_type),
            chat_id=chat_id,
        )
        dispatcher.add(wh)
        _save_webhooks(config_path, dispatcher)
        console.print(f"[bright_green]✓ Webhook '{name}' added ({wh_type})[/bright_green]")
        return

    if remove:
        if dispatcher.remove(remove):
            _save_webhooks(config_path, dispatcher)
            console.print(f"[bright_green]✓ Webhook '{remove}' removed[/bright_green]")
        else:
            console.print(f"[red]Webhook '{remove}' not found.[/red]")
        return

    if test:
        console.print(f"[dim]Sending test to '{test}'...[/dim]")
        success = dispatcher.send_test(test)
        if success:
            console.print(f"[bright_green]✓ Test notification sent successfully![/bright_green]")
        else:
            console.print(f"[red]✗ Failed to send test notification.[/red]")
        return


def _save_webhooks(path, dispatcher):
    """Save webhooks to config file."""
    import json as json_mod
    data = [w.to_dict() for w in dispatcher.list_webhooks()]
    path.write_text(json_mod.dumps(data, indent=2))


@main.command("obsidian")
@click.option("--format", "fmt", default="daily",
              type=click.Choice(["daily", "vault", "item"]),
              help="Export format")
@click.option("--sources", "-s", default=None, help="Comma-separated sources")
@click.option("--limit", "-n", default=15, help="Items per source", type=int)
@click.option("--output", "-o", "output_dir", default=None, help="Output directory")
@click.option("--title", default=None, help="Custom title for daily note")
@click.pass_context
def obsidian_cmd(ctx, fmt, sources, limit, output_dir, title):
    """Export trends as Obsidian-compatible markdown with frontmatter."""
    from .obsidian_export import export_obsidian_daily, export_obsidian_vault, export_obsidian_item
    console = _get_console(ctx)
    radar = _get_radar(ctx)

    source_list = sources.split(",") if sources else None
    snapshot = radar.fetch_all(sources=source_list, limit=limit)

    if not output_dir:
        output_dir = "."

    from pathlib import Path
    out = Path(output_dir)

    if fmt == "daily":
        content = export_obsidian_daily(snapshot, title=title)
        filepath = out / f"trend-radar-{snapshot.timestamp.strftime('%Y-%m-%d')}.md"
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content)
        console.print(f"[bright_green]✓ Exported daily note to {filepath}[/bright_green]")

    elif fmt == "vault":
        files = export_obsidian_vault(snapshot)
        for fname, content in files.items():
            filepath = out / fname
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content)
        console.print(f"[bright_green]✓ Exported {len(files)} files to {out}/[/bright_green]")

    elif fmt == "item":
        for item in snapshot.items[:limit]:
            content = export_obsidian_item(item)
            safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in item.title)[:50]
            filepath = out / f"{safe_title}.md"
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content)
        console.print(f"[bright_green]✓ Exported {min(limit, len(snapshot.items))} item notes to {out}/[/bright_green]")


@main.command("timeline")
@click.option("--days", "-d", default=7, help="Days to look back", type=int)
@click.option("--keywords", "-k", default=None, help="Comma-separated keywords to track")
@click.option("--top", "-n", default=15, help="Top N keywords to auto-track", type=int)
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.pass_context
def timeline_cmd(ctx, days, keywords, top, output_json):
    """Show topic trends over time with sparklines."""
    from .timeline import compute_timeline, render_timeline_panel
    console = _get_console(ctx)
    radar = _get_radar(ctx)

    kw_list = keywords.split(",") if keywords else None
    timeline_data = compute_timeline(radar.store, days=days, keywords=kw_list, top_n=top)

    if output_json:
        import json as json_mod
        result = {
            "time_range": [t.isoformat() for t in timeline_data.time_range],
            "total_snapshots": timeline_data.total_snapshots,
            "topics": [
                {
                    "keyword": t.keyword,
                    "total": t.total,
                    "trend": t.trend,
                    "peak_count": t.peak_count,
                    "peak_time": t.peak_time.isoformat() if t.peak_time else None,
                }
                for t in timeline_data.top_topics
            ],
        }
        click.echo(json_mod.dumps(result, indent=2, default=str))
        return

    console.print()
    console.print(render_timeline_panel(timeline_data, console))
    console.print()


@main.command("demo")
@click.option("--sources", "-s", default=None, help="Comma-separated sources (default: all)")
@click.option("--limit", "-n", default=10, help="Items per source", type=int)
@click.option("--layout", "-l", type=click.Choice(["table", "cards", "compact"]), default="table")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option("--no-banner", is_flag=True, help="Hide ASCII banner")
@click.option("--seed", default=None, type=int, help="Random seed for reproducibility")
@click.pass_context
def demo(ctx, sources, limit, layout, output_json, no_banner, seed):
    """🎉 Show demo data — no API keys needed!

    Generates realistic synthetic trend data across all sources.
    Perfect for first-time users and screenshots.
    """
    from .demo import generate_demo_snapshot
    from .render import SOURCE_EMOJI, BANNER_ART
    from .models import SourceType

    console = _get_console(ctx)
    source_list = sources.split(",") if sources else None

    if not no_banner and not output_json:
        console.print(BANNER_ART)
        console.print()
        console.print("[dim italic]  🎭 Demo mode — showing synthetic data (no API calls)[/dim italic]")
        console.print()

    snapshot = generate_demo_snapshot(sources=source_list, limit=limit, seed=seed)

    if output_json:
        renderer = JsonRenderer()
        click.echo(renderer.render(snapshot))
        return

    renderer = TerminalRenderer(console=console)
    renderer.render_snapshot(snapshot, layout=layout, show_banner=False)


@main.command("doctor")
@click.pass_context
def doctor(ctx):
    """🏥 Diagnose system health and source connectivity.

    Checks dependencies, API reachability, config, and database.
    """
    from .doctor import run_doctor
    console = _get_console(ctx)
    run_doctor(console)


if __name__ == "__main__":
    main()
