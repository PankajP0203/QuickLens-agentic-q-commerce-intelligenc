from __future__ import annotations

import json
import re

from shared.gemini_client import call_gemini
from shared.models import RankedResult, ScrapeResult

_SYSTEM = """\
You are a q-commerce price analyst. You receive raw Google SERP data from three platforms
and must extract structured pricing information for a specific product.

Return ONLY a valid JSON array — no markdown, no explanation.

Each element must have:
- platform: "blinkit" | "zepto" | "swiggy_instamart"
- price_inr: numeric price in INR as a float (e.g. 59.0), or null if not found
- delivery_mins: delivery time in minutes as an int (e.g. 8), or null if unknown
- available: true if in stock, false if "out of stock" is explicitly mentioned
- reasoning_note: one concise sentence explaining what you found (price source, variant, caveat)

Rules:
- Focus on the exact size/variant requested. If the query says 1L, prefer 1L results.
- Extract price from title or description. Accept all common Indian price formats:
  ₹72, ₹72.00, Rs.72, Rs 72, MRP ₹72, MRP Rs.72 — always return as integer rupees only (e.g. 72.0, not 72.50).
- If a selling price and MRP both appear, use the selling price (the lower one).
- If multiple prices appear for the same platform, use the price most clearly matching the requested variant.
- If a platform section says NO DATA, still include it with null price and available: false.
- Return exactly one row per platform — the cheapest available variant only. Never return multiple rows for the same platform.
- Sort the array by price_inr ascending. Null prices go last.
"""


def rank_results(
    product_name: str,
    scrape_results: dict[str, ScrapeResult],
) -> list[RankedResult]:
    """
    Single Gemini call: SERP JSON per platform → ranked list of RankedResult.

    Returns list sorted cheapest-first. Platforms with no data included as
    unavailable entries so the UI can show the full comparison table.
    """
    sections: list[str] = []
    for platform, result in scrape_results.items():
        if result.success and result.raw_markdown:
            # Truncate to stay within prompt budget while keeping the useful top results
            sections.append(f"=== {platform.upper()} ===\n{result.raw_markdown[:2000]}")
        else:
            sections.append(f"=== {platform.upper()} ===\nNO DATA")

    context = "\n\n".join(sections)

    text = call_gemini(f"Product requested: {product_name}\n\nSERP data:\n{context}", _SYSTEM)
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text).strip()

    raw_list: list[dict] = json.loads(text)

    # Compute savings_vs_max in rupees
    valid_prices = [
        item["price_inr"]
        for item in raw_list
        if item.get("price_inr") is not None
    ]
    max_price = max(valid_prices) if valid_prices else None

    ranked: list[RankedResult] = []
    for item in raw_list:
        price = item.get("price_inr")
        savings = (
            round(max_price - price, 2)
            if (max_price is not None and price is not None)
            else None
        )
        ranked.append(
            RankedResult(
                platform=item.get("platform", "unknown"),
                price=price,
                delivery_min=item.get("delivery_mins"),
                available=item.get("available", True),
                savings_vs_max=savings,
                reasoning_note=item.get("reasoning_note", ""),
            )
        )

    ranked.sort(key=lambda r: (r.price is None, r.price or 0))
    return ranked
