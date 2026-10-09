"""Theme system for Trend Radar — customizable terminal color schemes.

Provides predefined themes (default, dracula, monokai, solarized, light, nord, gruvbox)
and allows user custom themes via config.yaml.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ThemeColors:
    """Color definitions for a terminal theme."""
    # Core
    primary: str = "bright_cyan"
    secondary: str = "bright_yellow"
    accent: str = "bright_green"
    muted: str = "dim"

    # Source colors
    github: str = "bright_white"
    hackernews: str = "bold bright_yellow"
    reddit: str = "bold bright_red"
    arxiv: str = "bold bright_cyan"
    rss: str = "bold bright_magenta"
    producthunt: str = "bold bright_green"

    # Source borders
    github_border: str = "bright_white"
    hackernews_border: str = "yellow"
    reddit_border: str = "red"
    arxiv_border: str = "cyan"
    rss_border: str = "magenta"
    producthunt_border: str = "green"

    # Score tiers
    score_fire: str = "bold bright_red"       # >= 10000
    score_hot: str = "bold bright_red"         # >= 5000
    score_high: str = "bold bright_yellow"     # >= 1000
    score_medium: str = "bright_green"         # >= 500
    score_low: str = "bright_cyan"             # >= 100
    score_dim: str = "dim"                     # < 100

    # UI elements
    panel_border: str = "bright_cyan"
    table_header: str = "bold bright_white"
    table_row_even: str = ""
    table_row_odd: str = "dim"
    banner_color: str = "bold bright_cyan"
    keyword_bar: str = "bright_cyan"
    progress_bar: str = "bright_cyan"
    sparkline: str = "bright_green"

    # Status
    success: str = "bright_green"
    warning: str = "bright_yellow"
    error: str = "bright_red"
    info: str = "bright_cyan"

    def get_source_color(self, source: str) -> str:
        """Get color for a source name."""
        return getattr(self, source, self.primary)

    def get_source_border(self, source: str) -> str:
        """Get border color for a source name."""
        return getattr(self, f"{source}_border", self.panel_border)

    def get_score_style(self, score: int) -> tuple[str, str]:
        """Return (style, emoji) for a score value."""
        tiers = [
            (10000, self.score_fire, "🔥"),
            (5000, self.score_hot, "🔴"),
            (1000, self.score_high, "🟡"),
            (500, self.score_medium, "🟢"),
            (100, self.score_low, "🔵"),
            (0, self.score_dim, "⚪"),
        ]
        for threshold, style, emoji in tiers:
            if score >= threshold:
                return style, emoji
        return self.score_dim, "⚪"


# ─── Predefined Themes ───────────────────────────────────────────────────────

THEMES: dict[str, ThemeColors] = {
    "default": ThemeColors(),

    "dracula": ThemeColors(
        primary="#bd93f9",
        secondary="#f1fa8c",
        accent="#50fa7b",
        muted="#6272a4",
        github="#f8f8f2",
        hackernews="bold #f1fa8c",
        reddit="bold #ff5555",
        arxiv="bold #8be9fd",
        rss="bold #bd93f9",
        producthunt="bold #50fa7b",
        github_border="#f8f8f2",
        hackernews_border="#f1fa8c",
        reddit_border="#ff5555",
        arxiv_border="#8be9fd",
        rss_border="#bd93f9",
        producthunt_border="#50fa7b",
        score_fire="bold #ff5555",
        score_hot="bold #ff5555",
        score_high="bold #f1fa8c",
        score_medium="#50fa7b",
        score_low="#8be9fd",
        score_dim="#6272a4",
        panel_border="#bd93f9",
        table_header="bold #f8f8f2",
        banner_color="bold #bd93f9",
        keyword_bar="#bd93f9",
        progress_bar="#bd93f9",
        sparkline="#50fa7b",
        success="#50fa7b",
        warning="#f1fa8c",
        error="#ff5555",
        info="#8be9fd",
    ),

    "monokai": ThemeColors(
        primary="#66d9ef",
        secondary="#e6db74",
        accent="#a6e22e",
        muted="#75715e",
        github="#f8f8f2",
        hackernews="bold #e6db74",
        reddit="bold #f92672",
        arxiv="bold #66d9ef",
        rss="bold #ae81ff",
        producthunt="bold #a6e22e",
        github_border="#f8f8f2",
        hackernews_border="#e6db74",
        reddit_border="#f92672",
        arxiv_border="#66d9ef",
        rss_border="#ae81ff",
        producthunt_border="#a6e22e",
        score_fire="bold #f92672",
        score_hot="bold #f92672",
        score_high="bold #e6db74",
        score_medium="#a6e22e",
        score_low="#66d9ef",
        score_dim="#75715e",
        panel_border="#66d9ef",
        table_header="bold #f8f8f2",
        banner_color="bold #66d9ef",
        keyword_bar="#66d9ef",
        progress_bar="#66d9ef",
        sparkline="#a6e22e",
        success="#a6e22e",
        warning="#e6db74",
        error="#f92672",
        info="#66d9ef",
    ),

    "solarized": ThemeColors(
        primary="#268bd2",
        secondary="#b58900",
        accent="#859900",
        muted="#93a1a1",
        github="#839496",
        hackernews="bold #b58900",
        reddit="bold #dc322f",
        arxiv="bold #2aa198",
        rss="bold #6c71c4",
        producthunt="bold #859900",
        github_border="#839496",
        hackernews_border="#b58900",
        reddit_border="#dc322f",
        arxiv_border="#2aa198",
        rss_border="#6c71c4",
        producthunt_border="#859900",
        score_fire="bold #dc322f",
        score_hot="bold #dc322f",
        score_high="bold #b58900",
        score_medium="#859900",
        score_low="#2aa198",
        score_dim="#93a1a1",
        panel_border="#268bd2",
        table_header="bold #839496",
        banner_color="bold #268bd2",
        keyword_bar="#268bd2",
        progress_bar="#268bd2",
        sparkline="#859900",
        success="#859900",
        warning="#b58900",
        error="#dc322f",
        info="#2aa198",
    ),

    "nord": ThemeColors(
        primary="#88c0d0",
        secondary="#ebcb8b",
        accent="#a3be8c",
        muted="#4c566a",
        github="#eceff4",
        hackernews="bold #ebcb8b",
        reddit="bold #bf616a",
        arxiv="bold #88c0d0",
        rss="bold #b48ead",
        producthunt="bold #a3be8c",
        github_border="#eceff4",
        hackernews_border="#ebcb8b",
        reddit_border="#bf616a",
        arxiv_border="#88c0d0",
        rss_border="#b48ead",
        producthunt_border="#a3be8c",
        score_fire="bold #bf616a",
        score_hot="bold #bf616a",
        score_high="bold #ebcb8b",
        score_medium="#a3be8c",
        score_low="#88c0d0",
        score_dim="#4c566a",
        panel_border="#88c0d0",
        table_header="bold #eceff4",
        banner_color="bold #88c0d0",
        keyword_bar="#88c0d0",
        progress_bar="#88c0d0",
        sparkline="#a3be8c",
        success="#a3be8c",
        warning="#ebcb8b",
        error="#bf616a",
        info="#88c0d0",
    ),

    "gruvbox": ThemeColors(
        primary="#458588",
        secondary="#d79921",
        accent="#b8bb26",
        muted="#928374",
        github="#ebdbb2",
        hackernews="bold #fabd2f",
        reddit="bold #fb4934",
        arxiv="bold #83a598",
        rss="bold #d3869b",
        producthunt="bold #b8bb26",
        github_border="#ebdbb2",
        hackernews_border="#fabd2f",
        reddit_border="#fb4934",
        arxiv_border="#83a598",
        rss_border="#d3869b",
        producthunt_border="#b8bb26",
        score_fire="bold #fb4934",
        score_hot="bold #fb4934",
        score_high="bold #fabd2f",
        score_medium="#b8bb26",
        score_low="#83a598",
        score_dim="#928374",
        panel_border="#458588",
        table_header="bold #ebdbb2",
        banner_color="bold #458588",
        keyword_bar="#458588",
        progress_bar="#458588",
        sparkline="#b8bb26",
        success="#b8bb26",
        warning="#fabd2f",
        error="#fb4934",
        info="#83a598",
    ),

    "light": ThemeColors(
        primary="blue",
        secondary="dark_orange",
        accent="dark_green",
        muted="grey50",
        github="black",
        hackernews="bold dark_orange",
        reddit="bold red",
        arxiv="bold dark_blue",
        rss="bold dark_magenta",
        producthunt="bold dark_green",
        github_border="black",
        hackernews_border="dark_orange",
        reddit_border="red",
        arxiv_border="dark_blue",
        rss_border="dark_magenta",
        producthunt_border="dark_green",
        score_fire="bold red",
        score_hot="bold red",
        score_high="bold dark_orange",
        score_medium="dark_green",
        score_low="dark_blue",
        score_dim="grey50",
        panel_border="blue",
        table_header="bold black",
        banner_color="bold blue",
        keyword_bar="blue",
        progress_bar="blue",
        sparkline="dark_green",
        success="dark_green",
        warning="dark_orange",
        error="red",
        info="dark_blue",
    ),
}


def get_theme(name: str = "default") -> ThemeColors:
    """Get a theme by name. Falls back to default if not found."""
    return THEMES.get(name, THEMES["default"])


def list_themes() -> list[str]:
    """List all available theme names."""
    return sorted(THEMES.keys())


def register_theme(name: str, colors: ThemeColors) -> None:
    """Register a custom theme."""
    THEMES[name] = colors


def theme_from_dict(data: dict) -> ThemeColors:
    """Create a ThemeColors from a config dict, falling back to defaults."""
    defaults = ThemeColors()
    kwargs = {}
    for field_name in defaults.__dataclass_fields__:
        if field_name in data:
            kwargs[field_name] = data[field_name]
    return ThemeColors(**kwargs)
