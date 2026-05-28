from __future__ import annotations

import json
import re

from shared.gemini_client import call_gemini

_SYSTEM = """\
You are a q-commerce search planner. Given a user query about grocery or FMCG product prices,
extract the key information and return a JSON plan.

Return ONLY valid JSON — no markdown, no explanation — with these fields:
- product_name: clean, specific product name including size (e.g. "Amul Taaza Toned Milk 1L")
- search_query: short optimised query for site-scoped Google search (e.g. "amul taaza milk 1L")
- platforms: always ["blinkit", "zepto", "swiggy_instamart"]
- pincode: pincode if explicitly mentioned, otherwise "560038"
- user_intent: one phrase — what the user wants (e.g. "find cheapest 1L milk option")
"""


def plan_query(user_query: str) -> dict:
    """
    Single Gemini call: natural language query → structured scrape plan.
    Returns dict with product_name, search_query, platforms, pincode, user_intent.
    """
    text = call_gemini(f"Query: {user_query}", _SYSTEM)
    # Strip accidental markdown fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text).strip()

    plan = json.loads(text)

    # Ensure required keys have safe defaults
    plan.setdefault("product_name", user_query)
    plan.setdefault("search_query", user_query)
    plan.setdefault("platforms", ["blinkit", "zepto", "swiggy_instamart"])
    plan.setdefault("pincode", "560038")
    plan.setdefault("user_intent", "compare prices")

    return plan
