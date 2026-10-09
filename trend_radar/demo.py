"""Demo data generator — synthetic trend data for showcasing Trend Radar.

No API keys needed. Generates realistic tech intelligence items across
all 6 sources for instant demo/screen recording purposes.
"""

import random
from datetime import datetime, timezone, timedelta

from .models import IntelItem, SourceType, TrendSnapshot

# Realistic repo names and descriptions
_GITHUB_REPOS = [
    ("openai/gpt-5-engine", "Next-generation reasoning engine with tool use and long-term memory", 42000, "Python", 8200),
    ("vercel/ai-sdk-v5", "Unified AI SDK for TypeScript — streaming, agents, and structured output", 28000, "TypeScript", 3100),
    ("anthropic/claude-code", "Agentic coding assistant built on Claude — file editing, terminal, web", 31000, "Python", 4500),
    ("facebook/react-compiler", "Automatic memoization compiler for React — zero manual optimization", 18500, "JavaScript", 2200),
    ("google/jax-next", "Composable transformations of Python+NumPy — GPU/TPU ready", 35000, "Python", 5800),
    ("huggingface/transformers-v5", "State-of-the-art ML for PyTorch, TF, JAX — LLMs, VLMs, and beyond", 142000, "Python", 21000),
    ("microsoft/TypeSQL", "SQL-powered type system for TypeScript — compile-time query validation", 12000, "TypeScript", 890),
    ("rust-lang/rust-ai", "Native AI/ML toolkit for Rust — ONNX, GGUF, and custom kernels", 9800, "Rust", 670),
    ("pydantic/pydantic-v3", "Data validation using Python type annotations — 10x faster core", 22000, "Python", 1800),
    ("fastapi/fastapi-v1", "Modern async web framework — OpenAPI, dependency injection, WebSocket", 82000, "Python", 12000),
    ("tailwindlabs/tailwind-v4", "Utility-first CSS framework — 50% smaller output, instant builds", 86000, "CSS", 9200),
    ("denoland/deno-3", "Modern runtime for JavaScript and TypeScript — Node compatible", 102000, "Rust", 7600),
    ("oven-sh/bun-2", "Incredibly fast JS runtime — bundler, transpiler, package manager built-in", 74000, "Zig", 5400),
    ("NousResearch/Hermes-4", "Open-weight reasoning LLM — state-of-the-art on code and math", 8900, "Python", 1200),
    ("sglang/sglang-v2", "Fast serving framework for LLMs — 3x throughput vs vLLM", 15000, "Python", 2100),
]

_HN_STORIES = [
    ("Show HN: I built an AI that writes its own unit tests", 1842, 567),
    ("The RISC-V revolution is finally here (and nobody noticed)", 2103, 892),
    ("Why we migrated 2M lines of Java to Kotlin in 6 months", 1456, 723),
    ("PostgreSQL 18: Native vector search and JSON path queries", 3201, 1204),
    ("Ask HN: What's the most underrated programming language in 2026?", 987, 634),
    ("WebAssembly just got garbage collection — what this means", 2567, 1023),
    ("I replaced my entire Kubernetes setup with a single binary", 3891, 1456),
    ("The death of REST: Why GraphQL won (with data)", 1678, 890),
    ("Show HN: Real-time code collaboration in the browser, zero config", 1234, 445),
    ("How we run 10M websockets on a single server with io_uring", 2890, 1102),
    ("SQLite is not a toy database (2026 edition)", 4521, 1823),
    ("The trillion-dollar reason Apple is switching to ARM servers", 1987, 923),
    ("Show HN: Open-source alternative to Figma, built with Rust + WebGPU", 2345, 876),
    ("Why your monorepo is slow (and how to fix it)", 1567, 678),
    ("Nix for normal people: A practical guide", 1123, 534),
]

_REDDIT_POSTS = [
    ("MachineLearning", "GPT-5 benchmarks leaked — 97.3% on MMLU, beats PhD-level experts", 4521, "AI"),
    ("LocalLLaMA", "Running Llama 4 70B on a single 4090 with 4-bit quantization", 3201, "LLM"),
    ("programming", "After 15 years of Python, I switched to Rust — my honest review", 2890, "Experience"),
    ("technology", "EU passes comprehensive AI regulation — what it means for developers", 3456, "Policy"),
    ("artificial", "New open-source model outperforms Claude on coding benchmarks", 2103, "AI"),
    ("MachineLearning", "Self-improving AI agents are now writing their own training loops", 5678, "AI"),
    ("LocalLLaMA", "The complete guide to running LLMs locally in 2026", 1890, "Guide"),
    ("programming", "Why I stopped using Docker and went back to bare metal", 2345, "DevOps"),
    ("technology", "GitHub Copilot now handles entire pull requests autonomously", 4102, "AI"),
    ("deeplearning", "Breakthrough: Neural networks that can explain their reasoning", 1678, "AI"),
    ("artificial", "OpenAI announces open-weight model — first time since GPT-2", 8901, "AI"),
    ("MachineLearning", "The attention mechanism is dead — long live state-space models", 3456, "Research"),
]

_ARXIV_PAPERS = [
    ("Scaling Laws for Neural Language Models: Beyond 10T Tokens", "Kaplan et al.", "cs.CL"),
    ("Tree of Thoughts: Deliberate Problem Solving with Large Language Models", "Yao et al.", "cs.AI"),
    ("Mamba-3: Linear Attention with Sub-quadratic Complexity", "Gu et al.", "cs.LG"),
    ("Constitutional AI: Harmlessness from AI Feedback", "Bai et al.", "cs.AI"),
    ("Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks", "Lewis et al.", "cs.CL"),
    ("FlashAttention-3: Fast and Memory-Efficient Exact Attention", "Dao et al.", "cs.LG"),
    ("Direct Preference Optimization: Your Language Model is Secretly a Reward Model", "Rafailov et al.", "cs.LG"),
    ("QLoRA: Efficient Finetuning of Quantized LLMs", "Dettmers et al.", "cs.CL"),
    ("Mixture of Experts Meets Instruction Tuning", "Jiang et al.", "cs.AI"),
    ("Self-RAG: Learning to Retrieve, Generate, and Critique", "Asai et al.", "cs.CL"),
    ("DeepSeek-V3 Technical Report: Multi-head Latent Attention", "DeepSeek", "cs.LG"),
    ("Test-Time Compute: Scaling Inference for Better Reasoning", "Snell et al.", "cs.AI"),
]

_RSS_ITEMS = [
    ("TechCrunch", "Anthropic raises $5B at $60B valuation to build safe AI", "https://techcrunch.com/2026/05/14/anthropic-raises"),
    ("The Verge", "Apple Vision Pro 2 announced — lighter, cheaper, better", "https://theverge.com/2026/5/14/apple-vision-pro-2"),
    ("Ars Technica", "Linux kernel 7.0 released with native Rust drivers", "https://arstechnica.com/linux-7"),
    ("MIT Tech Review", "The 10 breakthrough technologies of 2026", "https://technologyreview.com/2026/breakthroughs"),
    ("OpenAI Blog", "Introducing GPT-5: Our most capable model yet", "https://openai.com/blog/gpt-5"),
    ("Google AI Blog", "Gemini Ultra 2: Multimodal reasoning at scale", "https://blog.google/gemini-ultra-2"),
    ("Anthropic Blog", "Claude 4: Extended thinking and computer use", "https://anthropic.com/claude-4"),
    ("Hacker News (RSS)", "Show HN: I built a database that runs in your browser", "https://hnrss.org/show-hn-db"),
]

_PH_PRODUCTS = [
    ("Cursor IDE", "The AI-first code editor — write code 10x faster", 2345),
    ("v0 by Vercel", "Generate React UI from text prompts", 1890),
    ("Replit Agent", "Full-stack apps from a single prompt", 1567),
    ("Windsurf", "AI coding assistant that understands your whole codebase", 1234),
    ("Bolt.new", "Full-stack web app builder in the browser", 2100),
    ("Lovable", "AI-powered full-stack development platform", 987),
    ("Perplexity Pro", "AI-powered search engine with real-time answers", 3201),
    ("Midjourney v7", "Photorealistic AI image generation", 4567),
]


def generate_demo_snapshot(
    sources: list[str] | None = None,
    limit: int = 15,
    seed: int | None = None,
) -> TrendSnapshot:
    """Generate a realistic demo snapshot with synthetic data.

    Args:
        sources: Sources to include (default: all 6).
        limit: Items per source.
        seed: Random seed for reproducibility.

    Returns:
        A TrendSnapshot populated with demo data.
    """
    if seed is not None:
        random.seed(seed)

    all_sources = sources or ["github", "hackernews", "reddit", "arxiv", "rss", "producthunt"]
    items: list[IntelItem] = []
    now = datetime.now(timezone.utc)

    for src in all_sources:
        src = src.strip().lower()
        if src == "github":
            items.extend(_gen_github(limit, now))
        elif src in ("hackernews", "hn"):
            items.extend(_gen_hn(limit, now))
        elif src == "reddit":
            items.extend(_gen_reddit(limit, now))
        elif src == "arxiv":
            items.extend(_gen_arxiv(limit, now))
        elif src == "rss":
            items.extend(_gen_rss(limit, now))
        elif src in ("producthunt", "ph"):
            items.extend(_gen_producthunt(limit, now))

    return TrendSnapshot(
        timestamp=now,
        items=items,
        sources_queried=all_sources,
        errors=[],
    )


def _gen_github(limit: int, now: datetime) -> list[IntelItem]:
    """Generate demo GitHub items."""
    repos = random.sample(_GITHUB_REPOS, min(limit, len(_GITHUB_REPOS)))
    items = []
    for name, desc, stars, lang, forks in repos:
        jitter = random.randint(-200, 200)
        items.append(IntelItem(
            title=name,
            source=SourceType.GITHUB,
            url=f"https://github.com/{name}",
            description=desc,
            score=max(0, stars + jitter),
            author=name.split("/")[0],
            repo_stars=max(0, stars + jitter),
            repo_language=lang,
            repo_forks=forks,
            tags=[lang] if lang else [],
            fetched_at=now - timedelta(minutes=random.randint(0, 30)),
        ))
    return items


def _gen_hn(limit: int, now: datetime) -> list[IntelItem]:
    """Generate demo HN items."""
    stories = random.sample(_HN_STORIES, min(limit, len(_HN_STORIES)))
    items = []
    for i, (title, points, comments) in enumerate(stories):
        jitter = random.randint(-50, 50)
        hn_id = 40000000 + i * 1234
        items.append(IntelItem(
            title=title,
            source=SourceType.HACKERNEWS,
            url=f"https://news.ycombinator.com/item?id={hn_id}",
            score=max(0, points + jitter),
            author=f"user_{random.randint(1000, 9999)}",
            extra={
                "hn_id": hn_id,
                "comment_count": comments,
                "hn_url": f"https://news.ycombinator.com/item?id={hn_id}",
            },
            fetched_at=now - timedelta(minutes=random.randint(0, 60)),
        ))
    return items


def _gen_reddit(limit: int, now: datetime) -> list[IntelItem]:
    """Generate demo Reddit items."""
    posts = random.sample(_REDDIT_POSTS, min(limit, len(_REDDIT_POSTS)))
    items = []
    for sub, title, score, flair in posts:
        jitter = random.randint(-100, 100)
        items.append(IntelItem(
            title=title,
            source=SourceType.REDDIT,
            url=f"https://reddit.com/r/{sub}/comments/demo_{random.randint(1000,9999)}",
            description=title[:200],
            score=max(0, score + jitter),
            author=f"u/demo_user_{random.randint(100, 999)}",
            tags=[f"r/{sub}"],
            extra={"subreddit": sub, "comment_count": random.randint(50, 800), "flair": flair},
            fetched_at=now - timedelta(minutes=random.randint(0, 45)),
        ))
    return items


def _gen_arxiv(limit: int, now: datetime) -> list[IntelItem]:
    """Generate demo arXiv items."""
    papers = random.sample(_ARXIV_PAPERS, min(limit, len(_ARXIV_PAPERS)))
    items = []
    for title, author, cat in papers:
        arxiv_id = f"2026.{random.randint(10000, 99999)}"
        items.append(IntelItem(
            title=title,
            source=SourceType.ARXIV,
            url=f"https://arxiv.org/abs/{arxiv_id}",
            description=f"Abstract for {title[:60]}...",
            score=0,
            author=author,
            tags=[cat, "cs.AI"],
            extra={"published": (now - timedelta(days=random.randint(0, 7))).isoformat(), "arxiv_id": arxiv_id},
            fetched_at=now - timedelta(hours=random.randint(0, 24)),
        ))
    return items


def _gen_rss(limit: int, now: datetime) -> list[IntelItem]:
    """Generate demo RSS items."""
    feeds = random.sample(_RSS_ITEMS, min(limit, len(_RSS_ITEMS)))
    items = []
    for source_name, title, url in feeds:
        items.append(IntelItem(
            title=title,
            source=SourceType.RSS,
            url=url,
            description=f"Latest from {source_name}: {title[:100]}",
            score=0,
            tags=[source_name],
            extra={"feed": source_name},
            fetched_at=now - timedelta(hours=random.randint(0, 12)),
        ))
    return items


def _gen_producthunt(limit: int, now: datetime) -> list[IntelItem]:
    """Generate demo Product Hunt items."""
    products = random.sample(_PH_PRODUCTS, min(limit, len(_PH_PRODUCTS)))
    items = []
    for name, desc, votes in products:
        slug = name.lower().replace(" ", "-").replace(".", "")
        jitter = random.randint(-50, 50)
        items.append(IntelItem(
            title=name,
            source=SourceType.PRODUCTHUNT,
            url=f"https://producthunt.com/posts/{slug}",
            description=desc,
            score=max(0, votes + jitter),
            tags=["producthunt"],
            extra={"source": "producthunt"},
            fetched_at=now - timedelta(hours=random.randint(0, 8)),
        ))
    return items
