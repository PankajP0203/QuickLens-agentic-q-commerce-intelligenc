"""
Brand monitoring loop — one full sweep.

Two-pass design:
  Pass 1: surface any OOS snapshots in price_history that have no matching
          alert_log entry (catches pre-seeded demo data on the first run).
  Pass 2: live scrape every watchlist item via one scrape_all_platforms()
          batch call, diff against last known snapshot, collect new deltas.
"""
from __future__ import annotations

import re

from dotenv import load_dotenv

load_dotenv()

from scraper.mcp_client import scrape_all_platforms
from shared.models import PriceSnapshot
from shared.state_store import (
    get_latest_snapshot,
    get_watchlist,
    load_state,
    update_price_snapshot,
)


def run_brand_sweep() -> list[dict]:
    """
    Execute a full monitoring sweep and return a list of delta dicts.
    Each delta is passed to brand.alerter.reason_and_alert for significance filtering.
    """
    state = load_state()
    deltas: list[dict] = []

    # Pass 1 — unalerted pre-seeded events (runs before live scrape overwrites state)
    deltas.extend(_check_unalerted_oos(state))

    # Pass 2 — live scrape and diff
    for item in get_watchlist(state):
        sku: str = item["sku_name"]
        platforms: list[str] = item["platforms"]
        pincodes: list[str] = item["pincodes"]

        # Single batch call covers all 3 platforms
        results = scrape_all_platforms(sku)

        for platform in platforms:
            result = results.get(platform)
            if not result or not result.success:
                continue

            for pincode in pincodes:
                new_snap = _parse_serp_to_snapshot(sku, platform, pincode, result.raw_markdown)
                old_snap = get_latest_snapshot(sku, platform, pincode)

                delta = _compute_delta(old_snap, new_snap, item)
                if delta:
                    deltas.append(delta)

                update_price_snapshot(new_snap)

    return deltas


# ---------------------------------------------------------------------------
# Pass 1 helper
# ---------------------------------------------------------------------------


def _check_unalerted_oos(state: dict) -> list[dict]:
    """
    Find OOS snapshots in price_history with no matching OOS entry in alert_log.
    Guarantees the pre-seeded Zepto/Tata Salt OOS fires on the very first sweep.
    On subsequent sweeps the alert_log entry prevents re-firing.
    """
    alerted: set[str] = {
        f"{e['sku']}::{e['platform']}"
        for e in state.get("alert_log", [])
        if e.get("alert_type") == "OOS"
    }

    unalerted: list[dict] = []
    for sku, platforms in state.get("price_history", {}).items():
        for platform, snapshots in platforms.items():
            if not snapshots:
                continue
            latest = snapshots[-1]
            if not latest.get("available", True):
                key = f"{sku}::{platform}"
                if key not in alerted:
                    prev = snapshots[-2] if len(snapshots) > 1 else None
                    unalerted.append({
                        "sku": sku,
                        "platform": platform,
                        "pincode": latest.get("pincode", "560038"),
                        "alert_type": "OOS",
                        "old_snapshot": prev,
                        "new_snapshot": latest,
                        "change_pct": None,
                        "source": "preseed",
                    })
    return unalerted


# ---------------------------------------------------------------------------
# Pass 2 helpers
# ---------------------------------------------------------------------------


def _parse_serp_to_snapshot(
    sku: str, platform: str, pincode: str, serp_text: str
) -> PriceSnapshot:
    """Extract price, availability, and delivery time from SERP JSON text."""
    prices = re.findall(r"₹\s*(\d+(?:\.\d+)?)", serp_text)
    price = float(prices[0]) if prices else None

    delivery_match = re.search(r"(\d+)\s*(?:min|mins|minutes)", serp_text.lower())
    delivery_min = int(delivery_match.group(1)) if delivery_match else None

    oos_markers = ["out of stock", "currently unavailable", "sold out", "not available"]
    available = not any(m in serp_text.lower() for m in oos_markers)

    return PriceSnapshot(
        sku=sku,
        platform=platform,
        pincode=pincode,
        price=price,
        available=available,
        delivery_min=delivery_min,
    )


def _compute_delta(
    old_snap: dict | None,
    new_snap: PriceSnapshot,
    watchlist_item: dict,
) -> dict | None:
    """
    Return a delta dict if the transition is significant, otherwise None.
    No baseline (old_snap is None) → save quietly, don't alert.
    """
    if old_snap is None:
        return None

    threshold = watchlist_item.get("price_drop_threshold_pct", 5.0)
    alert_on_oos = watchlist_item.get("alert_on_oos", True)

    old_avail = old_snap.get("available", True)
    new_avail = new_snap.available

    # In-stock → OOS
    if alert_on_oos and old_avail and not new_avail:
        return _delta("OOS", new_snap, old_snap, None)

    # OOS → in-stock
    if not old_avail and new_avail:
        return _delta("BACK_IN_STOCK", new_snap, old_snap, None)

    # Price change (only when both snapshots are in-stock and have a price)
    old_price = old_snap.get("price")
    new_price = new_snap.price
    if old_price and new_price and old_price > 0:
        change_pct = ((new_price - old_price) / old_price) * 100
        if abs(change_pct) >= threshold:
            alert_type = "PRICE_DROP" if change_pct < 0 else "PRICE_RISE"
            return _delta(alert_type, new_snap, old_snap, round(change_pct, 2))

    return None


def _delta(
    alert_type: str,
    new: PriceSnapshot,
    old: dict,
    change_pct: float | None,
) -> dict:
    return {
        "sku": new.sku,
        "platform": new.platform,
        "pincode": new.pincode,
        "alert_type": alert_type,
        "old_snapshot": old,
        "new_snapshot": new.model_dump(),
        "change_pct": change_pct,
    }
