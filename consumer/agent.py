from __future__ import annotations

import json
import re
from typing import Any, Generator

from dotenv import load_dotenv

load_dotenv()

from consumer.planner import plan_query
from consumer.ranker import rank_results
from scraper.mcp_client import scrape_all_platforms
from shared.models import RankedResult, ScrapeResult

# Yields: str (reasoning step) or list[RankedResult] (final output, one yield at end)
ConsumerStream = Generator[Any, None, None]

_MAX_RETRIES = 1


def run_consumer_query(user_query: str) -> ConsumerStream:
    """
    Reactive consumer agentic loop.

    Yields strings for each reasoning step so Streamlit can stream them live.
    Yields list[RankedResult] exactly once at the end as the final payload.
    Yields [] on total failure — never raises.
    """

    # ── Step 1: Plan ─────────────────────────────────────────────────────────
    yield "Planning: analysing query and identifying search strategy..."

    try:
        plan = plan_query(user_query)
    except Exception as exc:
        yield f"Planning failed: {exc}"
        yield []
        return

    product_name: str = plan["product_name"]
    search_query: str = plan["search_query"]
    platforms: list[str] = plan["platforms"]
    intent: str = plan["user_intent"]

    yield (
        f"Planning: identified '{product_name}' · intent: {intent} · "
        f"platforms: {', '.join(platforms)}"
    )

    # ── Step 2: Scrape — single batch call for all platforms ─────────────────
    yield f"Scraping: fetching live data from Blinkit, Zepto, Swiggy Instamart..."

    results: dict[str, ScrapeResult] = {}
    for attempt in range(_MAX_RETRIES + 1):
        try:
            results = scrape_all_platforms(search_query)
            break
        except Exception as exc:
            if attempt < _MAX_RETRIES:
                yield f"Scraping: attempt {attempt + 1} failed ({exc}), retrying..."
            else:
                yield f"Scraping: all attempts failed — {exc}"
                yield []
                return

    # ── Step 3: Observe ──────────────────────────────────────────────────────
    observations: list[str] = []
    successes: dict[str, ScrapeResult] = {}
    failures: dict[str, ScrapeResult] = {}

    for platform, result in results.items():
        if result.success and result.raw_markdown:
            try:
                data = json.loads(result.raw_markdown)
                organic = data.get("organic", [])
                count = len(organic)
                prices = re.findall(r"₹\s*(\d+)", result.raw_markdown)
                price_str = (
                    ", ".join(f"₹{p}" for p in prices[:3]) if prices else "no prices found"
                )
                observations.append(f"{platform} → {count} results ({price_str})")
            except Exception:
                observations.append(f"{platform} → data received (unparsed)")
            successes[platform] = result
        else:
            err = result.error_msg or "empty response"
            observations.append(f"{platform} → failed: {err}")
            failures[platform] = result

    yield f"Observing: {' | '.join(observations)}"

    # ── Step 4a: Total failure ────────────────────────────────────────────────
    if not successes:
        yield (
            "Error: all three platforms returned no data. "
            "Cannot build a price comparison. Please try again."
        )
        yield []
        return

    # ── Step 4b: Partial failure → replan (note gaps, proceed with available) ─
    if failures:
        missing = ", ".join(failures.keys())
        yield (
            f"Replanning: {missing} returned no usable data — "
            f"comparing {len(successes)} available platform(s) only"
        )

    # ── Step 5: Rank ─────────────────────────────────────────────────────────
    yield f"Ranking: extracting prices and delivery times, sorting cheapest first..."

    try:
        ranked: list[RankedResult] = rank_results(product_name, results)
    except Exception as exc:
        yield f"Ranking failed: {exc}"
        yield []
        return

    if not ranked:
        yield "Ranking: no structured results could be extracted from the SERP data."
        yield []
        return

    best = ranked[0]
    price_str = f"₹{best.price}" if best.price else "price unknown"
    delivery_str = f"{best.delivery_min} min" if best.delivery_min else "unknown delivery"
    yield (
        f"Complete: cheapest is {best.platform} at {price_str} "
        f"({delivery_str} delivery)"
    )

    # Final yield — list signals end of stream to the Streamlit consumer
    yield ranked
