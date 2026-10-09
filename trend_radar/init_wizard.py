"""Interactive first-run setup wizard.

Guides new users through configuring Trend Radar with a beautiful
interactive experience.
"""

import os
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.text import Text
from rich.table import Table


DEFAULT_CONFIG = {
    "sources": {
        "github": {"enabled": True, "token": "", "min_stars": 10},
        "hackernews": {"enabled": True, "category": "top"},
        "reddit": {
            "enabled": True,
            "subreddits": [
                "MachineLearning",
                "LocalLLaMA",
                "artificial",
                "programming",
            ],
        },
        "arxiv": {"enabled": True, "category": "ai"},
        "rss": {
            "enabled": True,
            "feeds": {
                "TechCrunch": "https://techcrunch.com/feed/",
                "Hacker News (RSS)": "https://hnrss.org/frontpage",
                "OpenAI Blog": "https://openai.com/blog/rss.xml",
            },
        },
        "producthunt": {"enabled": True},
        "youtube": {"enabled": True},
        "devto": {"enabled": True},
        "lobsters": {"enabled": True},
        "medium": {"enabled": True},
        "news": {"enabled": True},
    },
    "display": {
        "layout": "table",
        "items_per_source": 15,
        "show_keywords": True,
        "color_theme": "default",
    },
    "cache": {
        "enabled": True,
        "memory_ttl": 300,
        "disk_ttl": 3600,
    },
    "output": {
        "format": "terminal",
    },
}


def run_init_wizard(console: Console, config_path: Optional[str] = None) -> dict:
    """Run the interactive setup wizard. Returns the config dict."""
    console.print()
    console.print(Panel(
        "[bold bright_cyan]\U0001f4e1 Welcome to Trend Radar![/]\n\n"
        "Let's set up your tech intelligence dashboard in 30 seconds.\n"
        "[dim]You can always change these settings later with `trend-radar config-set`[/]",
        border_style="bright_cyan",
        padding=(1, 2),
    ))
    console.print()

    config = _deep_copy_dict(DEFAULT_CONFIG)

    # ── GitHub Token ──
    console.print("[bold]\U0001f419 GitHub Configuration[/]")
    console.print("[dim]A GitHub token increases your API rate limit from 60 to 5000 req/hr.[/]")
    console.print("[dim]Create one at: https://github.com/settings/tokens[/]\n")

    gh_token = Prompt.ask(
        "  GitHub token (optional, press Enter to skip)",
        default="",
        console=console,
    )
    if gh_token:
        config["sources"]["github"]["token"] = gh_token
        console.print("  [green]\u2713[/] Token saved\n")
    else:
        console.print("  [dim]Skipping \u2014 using public API (60 req/hr limit)[/]\n")

    # ── Source selection ──
    console.print("[bold]\U0001f4e1 Data Sources[/]")
    console.print("[dim]Choose which sources to enable (you can change later):[/dim]\n")

    sources_table = Table(show_header=True, border_style="dim")
    sources_table.add_column("#", width=3)
    sources_table.add_column("Source", style="bold")
    sources_table.add_column("Description")
    sources_table.add_column("Auth?")

    source_info = [
        ("\U0001f419 GitHub", "Trending repos + search", "Optional token"),
        ("\U0001f536 Hacker News", "Top/best/new stories", "No auth needed"),
        ("\U0001f916 Reddit", "Tech/AI subreddits", "No auth needed"),
        ("\U0001f4c4 arXiv", "Latest research papers", "No auth needed"),
        ("\U0001f4e1 RSS/Atom", "Tech blog feeds", "No auth needed"),
        ("\U0001f680 Product Hunt", "Trending products", "No auth needed"),
        ("\u25b6\ufe0f YouTube", "Latest videos from tech channels", "No auth needed"),
        ("\U0001f469\u200d\U0001f4bb Dev.to", "Top developer articles", "No auth needed"),
        ("\U0001f99e Lobsters", "Hottest stories", "No auth needed"),
        ("\u270d\ufe0f Medium", "Articles by topic tag", "No auth needed"),
        ("\U0001f4f0 News", "BBC, Wired, NPR, Al Jazeera", "No auth needed"),
    ]

    for i, (name, desc, auth) in enumerate(source_info, 1):
        sources_table.add_row(str(i), name, desc, auth)

    console.print(sources_table)
    console.print()

    # Quick selection
    selection = Prompt.ask(
        "  Enable sources",
        default="all",
        console=console,
    )

    if selection.lower() == "all":
        # All enabled (default)
        pass
    else:
        try:
            enabled_indices = [int(x.strip()) for x in selection.split(",")]
            source_names = ["github", "hackernews", "reddit", "arxiv", "rss", "producthunt",
                            "youtube", "devto", "lobsters", "medium", "news"]
            for i, name in enumerate(source_names, 1):
                config["sources"][name]["enabled"] = i in enabled_indices
        except (ValueError, IndexError):
            console.print("  [yellow]Invalid selection, keeping all sources enabled[/]")

    # ── Display preference ──
    console.print()
    console.print("[bold]\U0001f3a8 Display Settings[/]\n")

    layout = Prompt.ask(
        "  Default layout",
        choices=["table", "cards", "compact"],
        default="table",
        console=console,
    )
    config["display"]["layout"] = layout

    items_per = Prompt.ask(
        "  Items per source",
        default="15",
        console=console,
    )
    try:
        config["display"]["items_per_source"] = int(items_per)
    except ValueError:
        pass

    # ── Save ──
    console.print()

    if config_path:
        save_path = Path(config_path)
    else:
        save_path = Path.home() / ".trend-radar" / "config.yaml"

    if Confirm.ask(f"  Save config to [bold]{save_path}[/]?", default=True, console=console):
        save_path.parent.mkdir(parents=True, exist_ok=True)

        import yaml
        with open(save_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        console.print(f"  [green]\u2713[/] Config saved to [bold]{save_path}[/]")
    else:
        console.print("  [dim]Config not saved \u2014 using defaults[/]")

    # ── Done ──
    console.print()
    console.print(Panel(
        "[bold bright_green]\u2705 Setup complete![/]\n\n"
        "Try these commands to get started:\n\n"
        "  [bold bright_cyan]trend-radar fetch[/]             Fetch from all sources\n"
        "  [bold bright_cyan]trend-radar ai[/]               AI-focused intelligence\n"
        "  [bold bright_cyan]trend-radar live[/]             Live auto-refreshing dashboard\n"
        '  [bold bright_cyan]trend-radar search "MCP"[/]     Search across sources\n'
        "  [bold bright_cyan]trend-radar digest[/]           Generate shareable report\n\n"
        "[dim]Run `trend-radar --help` for all commands[/]",
        border_style="bright_green",
        padding=(1, 2),
    ))

    return config


def _deep_copy_dict(d: dict) -> dict:
    """Simple deep copy for nested dicts."""
    result = {}
    for k, v in d.items():
        if isinstance(v, dict):
            result[k] = _deep_copy_dict(v)
        elif isinstance(v, list):
            result[k] = list(v)
        else:
            result[k] = v
    return result
