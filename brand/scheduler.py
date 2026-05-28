"""
Brand loop scheduler.

start_brand_scheduler() — starts APScheduler BackgroundScheduler, runs sweep
                          every 5 minutes (or configurable interval).
trigger_manual_sweep()  — synchronous sweep for the Streamlit demo button.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

load_dotenv()

from brand.agent import run_brand_sweep
from brand.alerter import reason_and_alert

log = logging.getLogger(__name__)

_scheduler = BackgroundScheduler(timezone="UTC")
_started = False


def _sweep_job() -> None:
    """Scheduled job — exceptions are logged, never propagated to APScheduler."""
    try:
        deltas = run_brand_sweep()
        alerts = reason_and_alert(deltas) if deltas else []
        log.info("Brand sweep complete: %d delta(s), %d alert(s)", len(deltas), len(alerts))
    except Exception:
        log.exception("Brand sweep job failed")


def start_brand_scheduler(interval_seconds: int = 300) -> None:
    """
    Start the background scheduler. Idempotent — safe to call from Streamlit
    on every page render (only starts once per process).
    """
    global _started
    if _started:
        return
    _scheduler.add_job(_sweep_job, "interval", seconds=interval_seconds, id="brand_sweep")
    _scheduler.start()
    _started = True
    log.info("Brand scheduler started (interval=%ds)", interval_seconds)


def trigger_manual_sweep() -> list:
    """
    Run a full sweep synchronously and return the generated alerts.
    Called by the Streamlit 'Force Brand Sweep' demo button.
    """
    deltas = run_brand_sweep()
    if not deltas:
        return []
    return reason_and_alert(deltas)
