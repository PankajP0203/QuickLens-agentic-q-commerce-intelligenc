import os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ["PATH"] = f"/home/panka/miniforge3/bin:{os.environ['PATH']}"

from dotenv import load_dotenv
load_dotenv()

# Verify seed state before sweep
from shared.state_store import load_state
state = load_state()
watchlist = state["watchlist"]
zepto_salt = state["price_history"].get("Tata Salt 500g", {}).get("zepto", [])
latest = zepto_salt[-1] if zepto_salt else {}
print(f"Watchlist items:  {[w['sku_name'] for w in watchlist]}")
print(f"Zepto Tata Salt latest snapshot: available={latest.get('available')} price=₹{latest.get('price')}")
print(f"Alert log before sweep: {len(state['alert_log'])} entries\n")
print("=" * 60)
print("Running trigger_manual_sweep()...")
print("=" * 60)

from brand.scheduler import trigger_manual_sweep
alerts = trigger_manual_sweep()

print(f"\n{'='*60}")
print(f"ALERTS GENERATED: {len(alerts)}")
print(f"{'='*60}")
if alerts:
    for i, a in enumerate(alerts, 1):
        print(f"\n[{i}] {a.alert_type} — {a.sku} on {a.platform}")
        print(f"    Alert:  {a.alert_text}")
        print(f"    Action: {a.recommendation}")
else:
    print("No alerts generated.")

# Verify persisted
from shared.state_store import get_alert_log
persisted = get_alert_log()
print(f"\nalert_log entries after sweep: {len(persisted)}")
