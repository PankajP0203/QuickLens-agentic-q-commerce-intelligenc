from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

from filelock import FileLock

from .models import AlertEntry, PriceSnapshot

_HERE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.abspath(os.path.join(_HERE, "..", "state.json"))
_LOCK_FILE = STATE_FILE + ".lock"

# ---------------------------------------------------------------------------
# Demo seed data
# ---------------------------------------------------------------------------

_DEMO_WATCHLIST = [
    {
        "sku_name": "Amul Milk 1L",
        "platforms": ["blinkit", "zepto", "swiggy_instamart"],
        "pincodes": ["560038"],
        "price_drop_threshold_pct": 5.0,
        "alert_on_oos": True,
    },
    {
        "sku_name": "Tata Salt 500g",
        "platforms": ["blinkit", "zepto", "swiggy_instamart"],
        "pincodes": ["560038"],
        "price_drop_threshold_pct": 5.0,
        "alert_on_oos": True,
    },
]

_BASE_PRICES: dict[str, dict[str, float]] = {
    "Amul Milk 1L": {"blinkit": 68.0, "zepto": 70.0, "swiggy_instamart": 72.0},
    "Tata Salt 500g": {"blinkit": 24.0, "zepto": 25.0, "swiggy_instamart": 26.0},
}


def _demo_price_history() -> dict:
    """5 synthetic snapshots per sku/platform; Zepto Tata Salt OOS on latest."""
    now = datetime.now(timezone.utc)
    history: dict = {}
    for sku, platforms in _BASE_PRICES.items():
        history[sku] = {}
        for platform, base in platforms.items():
            snapshots = []
            for hours_ago in range(5, 0, -1):
                is_oos = (
                    sku == "Tata Salt 500g"
                    and platform == "zepto"
                    and hours_ago == 1
                )
                snapshots.append(
                    {
                        "sku": sku,
                        "platform": platform,
                        "pincode": "560038",
                        "price": round(base + (hours_ago % 3 - 1), 2),
                        "available": not is_oos,
                        "delivery_min": 10 + (hours_ago % 3) * 5,
                        "scraped_at": (now - timedelta(hours=hours_ago)).isoformat(),
                    }
                )
            history[sku][platform] = snapshots
    return history


# ---------------------------------------------------------------------------
# Core load / save
# ---------------------------------------------------------------------------


def load_state() -> dict:
    with FileLock(_LOCK_FILE):
        if not os.path.exists(STATE_FILE):
            state = _fresh_state()
            _write_unlocked(state)
            return state

        with open(STATE_FILE) as f:
            state = json.load(f)

        changed = False
        if not state.get("watchlist"):
            state["watchlist"] = _DEMO_WATCHLIST
            changed = True
        if not state.get("price_history"):
            state["price_history"] = _demo_price_history()
            changed = True
        state.setdefault("alert_log", [])

        if changed:
            _write_unlocked(state)
        return state


def save_state(state: dict) -> None:
    with FileLock(_LOCK_FILE):
        _write_unlocked(state)


def _fresh_state() -> dict:
    return {
        "watchlist": _DEMO_WATCHLIST,
        "price_history": _demo_price_history(),
        "alert_log": [],
    }


def _write_unlocked(state: dict) -> None:
    """Atomic write via temp file. Caller must hold _LOCK_FILE."""
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_FILE)


def _load_unlocked() -> dict:
    """Load without acquiring lock. Caller must hold _LOCK_FILE."""
    if not os.path.exists(STATE_FILE):
        return _fresh_state()
    with open(STATE_FILE) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Granular helpers
# ---------------------------------------------------------------------------


def update_price_snapshot(snapshot: PriceSnapshot) -> None:
    with FileLock(_LOCK_FILE):
        state = _load_unlocked()
        sku_hist = state["price_history"].setdefault(snapshot.sku, {})
        platform_hist: list = sku_hist.setdefault(snapshot.platform, [])
        platform_hist.append(snapshot.model_dump())
        # Cap at 50 entries per sku/platform to keep file size bounded
        if len(platform_hist) > 50:
            sku_hist[snapshot.platform] = platform_hist[-50:]
        _write_unlocked(state)


def append_alert(alert: AlertEntry) -> None:
    with FileLock(_LOCK_FILE):
        state = _load_unlocked()
        state["alert_log"].append(alert.model_dump())
        _write_unlocked(state)


def get_latest_snapshot(sku: str, platform: str, pincode: str) -> dict | None:
    """Return most recent snapshot for sku/platform/pincode, or None."""
    state = load_state()
    snapshots: list = (
        state.get("price_history", {}).get(sku, {}).get(platform, [])
    )
    matching = [s for s in snapshots if s.get("pincode") == pincode]
    return matching[-1] if matching else None


def get_watchlist(state: dict | None = None) -> list[dict]:
    if state is None:
        state = load_state()
    return state.get("watchlist", [])


def get_alert_log(state: dict | None = None) -> list[dict]:
    if state is None:
        state = load_state()
    return state.get("alert_log", [])
