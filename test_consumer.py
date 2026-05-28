import os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ["PATH"] = f"/home/panka/miniforge3/bin:{os.environ['PATH']}"

from dotenv import load_dotenv
load_dotenv()

from consumer.agent import run_consumer_query

query = "cheapest 1L Amul Milk in Indiranagar Bangalore"
print(f"Query: {query}\n{'='*60}")

ranked = None
for item in run_consumer_query(query):
    if isinstance(item, list):
        ranked = item
    else:
        print(item)

print(f"\n{'='*60}")
print("RANKED RESULTS")
print(f"{'='*60}")
if ranked:
    for i, r in enumerate(ranked, 1):
        price = f"₹{r.price}" if r.price else "N/A"
        delivery = f"{r.delivery_min} min" if r.delivery_min else "unknown"
        savings = f"  saves ₹{r.savings_vs_max}" if r.savings_vs_max else ""
        avail = "✓" if r.available else "✗ OOS"
        print(f"{i}. {r.platform:<20} {price:<10} {delivery:<12} {avail}{savings}")
        print(f"   {r.reasoning_note}")
else:
    print("No results.")
