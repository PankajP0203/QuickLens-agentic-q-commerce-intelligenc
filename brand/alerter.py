"""
Brand alerter — Gemini reasons about delta significance, generates
natural language alerts with actionable recommendations.
"""
from __future__ import annotations

import json
import re

from shared.gemini_client import call_gemini
from shared.models import AlertEntry
from shared.state_store import append_alert

_SYSTEM = """\
You are a q-commerce brand intelligence analyst. You receive platform events
(price changes, OOS, back-in-stock) and decide which ones warrant an alert.

Filtering rules:
- ALWAYS alert on OOS (out of stock) — flag immediately, no threshold
- ALWAYS alert on BACK_IN_STOCK events
- Ignore price changes under 3% (noise)
- Alert on price changes >= 3%

For each significant event return a JSON object with:
- sku: product name (copy from input)
- platform: platform name (copy from input)
- pincode: pincode (copy from input)
- alert_type: "OOS" | "PRICE_DROP" | "PRICE_RISE" | "BACK_IN_STOCK" (copy from input)
- alert_text: one natural language sentence — what happened
  Example: "Zepto is out of stock on Tata Salt 500g in Bangalore (pincode 560038)"
- recommendation: specific, actionable sentence for the brand team
  Example: "Consider boosting Blinkit ad spend for Tata Salt 500g for the next 2 hrs to capture demand spillover"

Return ONLY a valid JSON array. Return [] if nothing is significant.
No markdown fences, no explanation — just the array.
"""


def reason_and_alert(deltas: list[dict]) -> list[AlertEntry]:
    """
    Single Gemini call: batch of deltas → filtered, enriched list of AlertEntry.
    Each alert is persisted to state.json via append_alert before returning.
    """
    if not deltas:
        return []

    text = call_gemini(
        f"Analyse these q-commerce events:\n{json.dumps(deltas, indent=2, default=str)}",
        _SYSTEM,
    )
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text).strip()

    raw_list: list[dict] = json.loads(text)
    alerts: list[AlertEntry] = []

    for item in raw_list:
        alert = AlertEntry(
            sku=item.get("sku", ""),
            platform=item.get("platform", ""),
            pincode=item.get("pincode", "560038"),
            alert_type=item.get("alert_type", "OOS"),
            alert_text=item.get("alert_text", ""),
            recommendation=item.get("recommendation", ""),
        )
        append_alert(alert)
        alerts.append(alert)

    return alerts
