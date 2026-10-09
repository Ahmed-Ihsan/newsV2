"""Tests for the interactive shell module."""

import pytest

from trend_radar.models import IntelItem, SourceType, TrendSnapshot


def test_shell_import():
    """Test that the shell module can be imported."""
    from trend_radar.shell import run_shell, _dispatch, COMMANDS
    assert "fetch" in COMMANDS
    assert "search" in COMMANDS
    assert "exit" in COMMANDS


def test_shell_commands_list():
    """Test that all expected commands are listed."""
    from trend_radar.shell import COMMANDS
    expected = ["fetch", "ai", "search", "keywords", "history", "stats", "sources", "config", "help", "exit", "quit", "clear"]
    for cmd in expected:
        assert cmd in COMMANDS


def test_shell_dispatch_unknown_command():
    """Test that unknown commands are handled gracefully."""
    from io import StringIO
    from rich.console import Console
    from trend_radar.shell import _dispatch

    buf = StringIO()
    console = Console(file=buf, width=120, force_terminal=True)

    # Should not raise
    _dispatch("unknown", [], None, console)
    output = buf.getvalue()
    assert "Unknown" in output


def test_shell_dispatch_help():
    """Test help command."""
    from io import StringIO
    from rich.console import Console
    from trend_radar.shell import _dispatch

    buf = StringIO()
    console = Console(file=buf, width=120, force_terminal=True)
    _dispatch("help", [], None, console)
    output = buf.getvalue()
    assert "Commands" in output


def test_shell_has_prompt_toolkit():
    """Test prompt_toolkit availability."""
    from trend_radar.shell import HAS_PROMPT_TOOLKIT
    # Just check it doesn't error
    assert isinstance(HAS_PROMPT_TOOLKIT, bool)
