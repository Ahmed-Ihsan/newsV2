"""Doctor command — diagnose system health and source connectivity.

Checks all data sources, dependencies, configuration, and cache status
to help users troubleshoot issues.
"""

import importlib
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table


@dataclass
class CheckResult:
    """Result of a single diagnostic check."""

    name: str
    status: str  # "ok", "warn", "error", "skip"
    message: str
    duration_ms: float = 0.0


@dataclass
class DoctorReport:
    """Full diagnostic report."""

    checks: list[CheckResult] = field(default_factory=list)

    @property
    def ok_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "ok")

    @property
    def warn_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "warn")

    @property
    def error_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "error")

    @property
    def healthy(self) -> bool:
        return self.error_count == 0


def run_doctor(console: Console | None = None) -> DoctorReport:
    """Run all diagnostic checks and optionally print results.

    Args:
        console: Rich Console for output. If None, runs silently.

    Returns:
        DoctorReport with all check results.
    """
    report = DoctorReport()

    # 1. Check Python version
    report.checks.append(_check_python_version())

    # 2. Check dependencies
    for dep in ["httpx", "rich", "click", "beautifulsoup4", "yaml"]:
        report.checks.append(_check_dependency(dep))

    # 3. Check optional dependencies
    for dep in ["fastapi", "uvicorn", "prompt_toolkit"]:
        report.checks.append(_check_dependency(dep, required=False))

    # 4. Check source connectivity
    report.checks.append(_check_source("GitHub API", "https://api.github.com/"))
    report.checks.append(_check_source("Hacker News API", "https://hacker-news.firebaseio.com/v0/topstories.json"))
    report.checks.append(_check_source("Reddit JSON", "https://www.reddit.com/r/programming/hot.json", headers={"User-Agent": "TrendRadar/1.0"}))
    report.checks.append(_check_source("arXiv API", "http://export.arxiv.org/api/query?max_results=1"))
    report.checks.append(_check_source("Product Hunt", "https://www.producthunt.com/"))

    # 5. Check config
    report.checks.append(_check_config())

    # 6. Check SQLite database
    report.checks.append(_check_database())

    if console:
        _print_report(console, report)

    return report


def _check_python_version() -> CheckResult:
    """Check Python version meets requirements."""
    import sys

    major, minor = sys.version_info[:2]
    if major >= 3 and minor >= 10:
        return CheckResult("Python version", "ok", f"Python {major}.{minor}.{sys.version_info[2]}")
    return CheckResult("Python version", "error", f"Python {major}.{minor} (requires 3.10+)")


def _check_dependency(name: str, required: bool = True) -> CheckResult:
    """Check if a dependency is importable."""
    # Map pip names to import names
    import_map = {
        "beautifulsoup4": "bs4",
        "yaml": "yaml",
        "prompt_toolkit": "prompt_toolkit",
    }
    import_name = import_map.get(name, name)

    try:
        mod = importlib.import_module(import_name)
        version = getattr(mod, "__version__", "unknown")
        return CheckResult(f"Dependency: {name}", "ok", f"v{version}")
    except ImportError:
        status = "error" if required else "warn"
        msg = f"{'Required' if required else 'Optional'} dependency not installed"
        return CheckResult(f"Dependency: {name}", status, msg)


def _check_source(name: str, url: str, headers: dict | None = None) -> CheckResult:
    """Check if a data source API is reachable."""
    start = time.monotonic()
    try:
        with httpx.Client(timeout=10, headers=headers or {}, follow_redirects=True) as client:
            resp = client.get(url)
            elapsed = (time.monotonic() - start) * 1000
            if resp.status_code < 400:
                return CheckResult(f"Source: {name}", "ok", f"HTTP {resp.status_code}", elapsed)
            return CheckResult(f"Source: {name}", "warn", f"HTTP {resp.status_code}", elapsed)
    except httpx.TimeoutException:
        elapsed = (time.monotonic() - start) * 1000
        return CheckResult(f"Source: {name}", "error", "Connection timeout", elapsed)
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        return CheckResult(f"Source: {name}", "error", str(e)[:60], elapsed)


def _check_config() -> CheckResult:
    """Check if config file exists and is valid."""
    from pathlib import Path

    config_path = Path.home() / ".trend-radar" / "config.yaml"
    if config_path.exists():
        try:
            import yaml

            with open(config_path) as f:
                yaml.safe_load(f)
            return CheckResult("Config file", "ok", str(config_path))
        except Exception as e:
            return CheckResult("Config file", "warn", f"Invalid YAML: {e}")
    return CheckResult("Config file", "warn", f"Not found ({config_path}) — using defaults")


def _check_database() -> CheckResult:
    """Check SQLite database accessibility."""
    from pathlib import Path

    db_path = Path.home() / ".trend-radar" / "trends.db"
    if db_path.exists():
        try:
            import sqlite3

            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute("SELECT COUNT(*) FROM items")
            count = cursor.fetchone()[0]
            conn.close()
            return CheckResult("Database", "ok", f"{count} items stored ({db_path})")
        except Exception as e:
            return CheckResult("Database", "warn", f"Error: {e}")
    return CheckResult("Database", "warn", f"Not found ({db_path}) — will be created on first fetch")


_STATUS_ICONS = {
    "ok": "[green]✓[/]",
    "warn": "[yellow]⚠[/]",
    "error": "[red]✗[/]",
    "skip": "[dim]−[/]",
}


def _print_report(console: Console, report: DoctorReport) -> None:
    """Print the diagnostic report as a Rich table."""
    table = Table(
        title="🏥 Trend Radar Doctor",
        show_header=True,
        header_style="bold bright_cyan",
        border_style="bright_blue",
        padding=(0, 1),
    )
    table.add_column("", width=3)
    table.add_column("Check", style="bold", min_width=25)
    table.add_column("Result", min_width=40)
    table.add_column("Time", justify="right", width=8)

    for check in report.checks:
        icon = _STATUS_ICONS.get(check.status, "?")
        time_str = f"{check.duration_ms:.0f}ms" if check.duration_ms > 0 else "—"
        table.add_row(icon, check.name, check.message, time_str)

    console.print()
    console.print(table)

    # Summary
    summary_parts = []
    if report.ok_count:
        summary_parts.append(f"[green]{report.ok_count} passed[/]")
    if report.warn_count:
        summary_parts.append(f"[yellow]{report.warn_count} warnings[/]")
    if report.error_count:
        summary_parts.append(f"[red]{report.error_count} errors[/]")

    console.print()
    if report.healthy:
        console.print(Panel(
            f"[green bold]All systems operational![/]  {' · '.join(summary_parts)}",
            border_style="green",
        ))
    else:
        console.print(Panel(
            f"[red bold]Issues detected.[/]  {' · '.join(summary_parts)}",
            border_style="red",
        ))
    console.print()
