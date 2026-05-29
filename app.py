import os
import sys
import time

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))
os.environ["PATH"] = f"/home/panka/miniforge3/bin:{os.environ['PATH']}"

from dotenv import load_dotenv
load_dotenv()

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="QuickLens", layout="wide", page_icon="🔍")

# ── Start brand scheduler exactly once per process ────────────────────────────
if "scheduler_started" not in st.session_state:
    from brand.scheduler import start_brand_scheduler
    start_brand_scheduler()
    st.session_state.scheduler_started = True

# ── Header ────────────────────────────────────────────────────────────────────
st.title("🔍 QuickLens")
st.caption("Real-time q-commerce intelligence · Blinkit · Zepto · Swiggy Instamart")

consumer_tab, brand_tab = st.tabs(["🛒 Consumer Search", "📊 Brand Dashboard"])


# ─────────────────────────────────────────────────────────────────────────────
# CONSUMER TAB
# ─────────────────────────────────────────────────────────────────────────────

# Session state keys — persist results across autorefresh reruns
for _k, _v in [
    ("c_ranked", None), ("c_steps", []), ("c_elapsed", 0),
    ("c_from_cache", False), ("c_error", None),
]:
    if _k not in st.session_state:
        st.session_state[_k] = _v

with consumer_tab:
    st.subheader("Find the best deal across platforms")

    col_q, col_btn = st.columns([5, 1])
    with col_q:
        query = st.text_input(
            "query",
            placeholder="e.g. cheapest 1L Amul Milk in Indiranagar",
            label_visibility="collapsed",
            key="consumer_query_input",
        )
    with col_btn:
        search_clicked = st.button("Search", type="primary", use_container_width=True)

    if search_clicked and not query.strip():
        st.warning("Please enter a search query.")

    if search_clicked and query.strip():
        # Clear previous results before new search
        st.session_state.c_ranked = None
        st.session_state.c_steps = []
        st.session_state.c_error = None

        from consumer.agent import run_consumer_query

        st.divider()
        st.markdown("**Live Reasoning**")
        reasoning_box = st.empty()
        steps: list[str] = []
        ranked = []

        t0 = time.time()
        try:
            with st.spinner("Scanning Blinkit, Zepto & Swiggy Instamart in real time..."):
                for item in run_consumer_query(query.strip()):
                    if isinstance(item, list):
                        ranked = item
                    else:
                        steps.append(item)
                        with reasoning_box.container():
                            for step in steps:
                                st.write(f"› {step}")
        except Exception as exc:
            st.session_state.c_error = str(exc)

        # Persist to session state so results survive autorefresh reruns
        st.session_state.c_ranked = ranked if ranked else None
        st.session_state.c_steps = steps
        st.session_state.c_elapsed = int(time.time() - t0)
        st.session_state.c_from_cache = bool(
            ranked and any("cached" in (r.reasoning_note or "").lower() for r in ranked)
        )

    # ── Render results — runs on every rerun, not just search click ───────────
    if st.session_state.c_error:
        st.error(f"Search failed: {st.session_state.c_error}")

    elif st.session_state.c_ranked:
        ranked = st.session_state.c_ranked
        elapsed = st.session_state.c_elapsed
        from_cache = st.session_state.c_from_cache

        if not search_clicked:
            # On autorefresh reruns, re-show the reasoning steps compactly
            st.divider()
            st.markdown("**Live Reasoning**")
            for step in st.session_state.c_steps:
                st.write(f"› {step}")

        st.divider()
        cache_note = " · *demo cache*" if from_cache else ""
        st.markdown(
            f"**Results** — sorted cheapest first · best deal highlighted{cache_note}"
        )

        rows = []
        for i, r in enumerate(ranked):
            platform_label = r.platform.replace("_", " ").title()
            if i == 0:
                platform_label = f"🏆 {platform_label}"
            rows.append({
                "Platform":  platform_label,
                "Price":     f"₹{r.price:.0f}" if r.price is not None else "N/A",
                "Delivery":  f"{r.delivery_min} min" if r.delivery_min else "—",
                "Saves":     f"₹{r.savings_vs_max:.0f}" if r.savings_vs_max else "—",
                "Available": "✓" if r.available else "✗ OOS",
                "Note":      r.reasoning_note,
            })

        df = pd.DataFrame(rows)

        st.dataframe(df, use_container_width=True, hide_index=True)

        source_label = "demo cache" if from_cache else "3 platforms live"
        st.caption(f"Results fetched in {elapsed}s from {source_label}.")

    elif st.session_state.c_steps and not st.session_state.c_error:
        st.warning("Search completed but no results could be ranked.")


# ─────────────────────────────────────────────────────────────────────────────
# BRAND TAB
# ─────────────────────────────────────────────────────────────────────────────
with brand_tab:

    col_wl, col_alerts = st.columns([1, 2])

    # ── Watchlist ─────────────────────────────────────────────────────────────
    with col_wl:
        st.subheader("Watchlist")

        from shared.state_store import load_state, get_alert_log
        state = load_state()
        watchlist = state.get("watchlist", [])

        if watchlist:
            wl_df = pd.DataFrame([
                {
                    "SKU":       w["sku_name"],
                    "Platforms": len(w["platforms"]),
                    "Pincode":   ", ".join(w["pincodes"]),
                    "OOS Alert": "✓" if w.get("alert_on_oos") else "✗",
                    "Threshold": f"{w.get('price_drop_threshold_pct', 5)}%",
                }
                for w in watchlist
            ])
            st.dataframe(wl_df, use_container_width=True, hide_index=True)
        else:
            st.info("Watchlist is empty.")

        st.divider()

        if st.button("⚡ Run Brand Sweep Now", type="primary", use_container_width=True):
            with st.spinner("Sweeping all platforms…"):
                from brand.scheduler import trigger_manual_sweep
                new_alerts = trigger_manual_sweep()
            if new_alerts:
                st.success(f"{len(new_alerts)} new alert(s) generated.")
            else:
                st.info("No significant changes detected.")
            st.rerun()

        if st.button("🔄 Refresh Alerts", use_container_width=True):
            st.rerun()
        st.caption(f"Brand scheduler: {'running ✓' if st.session_state.get('scheduler_started') else 'not started'}")

    # ── Alert feed ────────────────────────────────────────────────────────────
    with col_alerts:
        st.subheader("Alert Feed")

        _BADGE = {
            "OOS": (
                '<span style="background:#dc3545;color:white;'
                'padding:2px 9px;border-radius:4px;font-size:0.78em;font-weight:600">'
                'OOS</span>'
            ),
            "PRICE_DROP": (
                '<span style="background:#fd7e14;color:white;'
                'padding:2px 9px;border-radius:4px;font-size:0.78em;font-weight:600">'
                'PRICE DROP</span>'
            ),
            "BACK_IN_STOCK": (
                '<span style="background:#28a745;color:white;'
                'padding:2px 9px;border-radius:4px;font-size:0.78em;font-weight:600">'
                'BACK IN STOCK</span>'
            ),
            "PRICE_RISE": (
                '<span style="background:#ffc107;color:#212529;'
                'padding:2px 9px;border-radius:4px;font-size:0.78em;font-weight:600">'
                'PRICE RISE</span>'
            ),
        }

        alerts = get_alert_log()

        if alerts:
            for entry in reversed(alerts):  # newest first
                alert_type = entry.get("alert_type", "")
                badge = _BADGE.get(alert_type, "")

                raw_ts = entry.get("timestamp", "")
                try:
                    from datetime import datetime, timezone
                    ts = datetime.fromisoformat(raw_ts).strftime("%d %b %H:%M UTC")
                except Exception:
                    ts = raw_ts[:16]

                with st.container(border=True):
                    st.markdown(
                        f"{badge}&nbsp;&nbsp;**{entry.get('sku')}**"
                        f" · {entry.get('platform', '').replace('_', ' ').title()}"
                        f"&nbsp;&nbsp;<small style='color:grey'>{ts}</small>",
                        unsafe_allow_html=True,
                    )
                    st.write(entry.get("alert_text", ""))
                    st.caption(f"💡 {entry.get('recommendation', '')}")
        else:
            st.info("No alerts yet. Click **Run Brand Sweep Now** to trigger the first sweep.")

        st.caption("Use 🔄 Refresh Alerts to reload the feed.")
