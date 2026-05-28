import os, sys, re
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv()
os.environ["PATH"] = f"/home/panka/miniforge3/bin:{os.environ['PATH']}"

from scraper.mcp_client import dispatch_consumer_tool

URL = "https://blinkit.com/s/?q=amul+milk&pincode=560038"
print(f"Calling scrape_platform_url on: {URL}\n")

result_text = dispatch_consumer_tool(
    "scrape_platform_url",
    {"url": URL, "platform": "blinkit"},
)

success = not result_text.startswith(("SEARCH_ERROR", "SCRAPE_ERROR", "UNKNOWN_TOOL"))
prices = re.findall(r"₹\s*\d+", result_text)

print(f"ScrapeResult.success = {success}")
print(f"Prices found in output: {prices[:5]}")
print(f"\nFirst 500 chars:\n{'-'*40}")
print(result_text[:500])
print('-'*40)
