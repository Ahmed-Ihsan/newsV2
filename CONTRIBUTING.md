# 🤝 Contributing to Trend Radar

Thanks for your interest in contributing! Here's how to get started.

## Development Setup

```bash
# Clone the repo
git clone https://github.com/Jane-o-O-o-O/trend-radar.git
cd trend-radar

# Install in dev mode
pip install -e ".[dev]"

# Run tests
pytest -v

# Run linter
ruff check trend_radar/ tests/
```

## Project Structure

```
trend_radar/
├── __init__.py       # Public API exports
├── models.py         # Data models (IntelItem, TrendSnapshot, SourceType)
├── core.py           # TrendRadar engine — orchestrates sources
├── cli.py            # Click CLI commands
├── render.py         # Rich terminal rendering (the wow factor!)
├── store.py          # SQLite persistence
├── cache.py          # Two-level cache (memory + disk)
├── config.py         # YAML configuration
└── sources/          # Data source implementations
    ├── __init__.py   # DataSource ABC
    ├── github.py     # GitHub trending + search API
    ├── hackernews.py # HN Firebase API
    ├── reddit.py     # Reddit JSON API
    ├── arxiv.py      # arXiv Atom API
    ├── rss.py        # RSS/Atom feeds
    └── producthunt.py # Product Hunt scraping
```

## Adding a New Data Source

1. Create `trend_radar/sources/my_source.py`
2. Subclass `DataSource` from `sources/__init__.py`
3. Implement `fetch()` and `is_available()`
4. Register in `core.py` → `SOURCE_CLASSES`
5. Add `SourceType.MY_SOURCE` enum in `models.py`
6. Add emoji/color/border in `render.py`
7. Write tests in `tests/test_sources_individual.py`

## Pull Request Guidelines

- Write tests for new features
- Keep PRs focused — one feature per PR
- Use Chinese commit messages (项目惯例)
- Ensure all tests pass before submitting
- Add docstrings to new public APIs

## Running Tests

```bash
# All tests
pytest

# Specific test file
pytest tests/test_core.py -v

# With coverage
pytest --cov=trend_radar --cov-report=term-missing
```

## Code Style

- Python 3.10+ (type hints with `list[str]`, not `List[str]`)
- Max line length: 100
- Docstrings on all public classes and methods
- Type annotations on all function signatures

## Questions?

Open an issue on GitHub — we're friendly! 🚀
