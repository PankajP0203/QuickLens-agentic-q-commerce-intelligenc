# QuickLens

Real-time q-commerce price intelligence across Blinkit, Zepto, and Swiggy Instamart — powered by live web data and AI reasoning.

---

## Problem

Grocery prices on q-commerce platforms change constantly and vary by platform, pincode, and time of day. Consumers overpay because comparing across three apps manually is too much friction. Brand managers miss OOS events and competitor undercuts because there is no proactive monitoring layer — only manual spot-checks.

QuickLens closes both gaps: one tool that watches all three platforms simultaneously, both on-demand and in the background.

---

## Architecture

Two independent agentic loops share a single live data layer:

```
┌─────────────────────────────────────────────────────────┐
│  CONSUMER LOOP  (reactive — user triggered)             │
│                                                         │
│  "cheapest 1L Amul Milk in Indiranagar"                 │
│       │                                                 │
│       ▼                                                 │
│  Gemini: NL query → structured search plan              │
│       │                                                 │
│       ▼                                                 │
│  Bright Data: search_engine_batch                       │
│    ├── site:blinkit.com  ──► SERP + prices              │
│    ├── site:zepto.com    ──► SERP + prices              │
│    └── site:swiggy.com   ──► SERP + prices              │
│       │  (scrape_batch on top URL if no ₹ in snippet)   │
│       ▼                                                 │
│  Gemini: rank by price · extract delivery · note        │
│       │                                                 │
│       ▼                                                 │
│  Streamlit: ranked table, 🏆 best deal badge            │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  BRAND LOOP  (proactive — runs every 5 min)             │
│                                                         │
│  Watchlist: [Amul Milk 1L, Tata Salt 500g, ...]         │
│       │                                                 │
│       ▼                                                 │
│  Bright Data: search_engine_batch (per SKU × platform)  │
│       │                                                 │
│       ▼                                                 │
│  Diff against last known price / availability           │
│       │                                                 │
│       ▼                                                 │
│  Gemini: filter noise → generate alert + recommendation │
│       │                                                 │
│       ▼                                                 │
│  Streamlit: alert feed · manual Refresh Alerts button   │
└─────────────────────────────────────────────────────────┘
```

Both loops share `state.json` (file-locked) for watchlist, price history, and alert log.

---

## Bright Data Tools Used

| Tool | Where | Purpose |
|---|---|---|
| `search_engine_batch` | Both loops | Primary data path — all 3 platforms in one API call via `site:`-scoped Google SERP |
| `scrape_batch` | Consumer loop | Secondary enrichment — fetches the top product page when the SERP snippet contains no price |
| `search_engine` | Per-URL fallback | Single-platform lookup in `scrape_platform_url` |

> Direct scraping of Blinkit, Zepto, and Swiggy is blocked by `robots.txt`. The `site:` SERP approach is the working solution — Google's indexed snippets carry current prices and delivery times.

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM reasoning | Google Gemini `gemini-2.5-flash-lite` via `google-genai` SDK |
| Live web data | Bright Data MCP (`@brightdata/mcp`) via `mcp` Python library |
| UI | Streamlit — Consumer Search tab + Brand Dashboard tab |
| Background jobs | APScheduler `BackgroundScheduler`, 5-minute sweep interval |
| State | `state.json`, file-locked with `filelock` |
| Data models | Pydantic v2 |
| Runtime | Python 3.11+ |

---

## How to Run Locally

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Add your API keys
cp .env.example .env
# Edit .env and fill in:
#   GEMINI_API_KEY=...
#   BRIGHT_DATA_API_TOKEN=...

# 3. Start the app
streamlit run app.py
```

Open `http://localhost:8501`.

> **Note:** Node.js is required for the Bright Data MCP subprocess (`npx`). If it is not in your PATH (e.g. on a conda environment), prepend it:
> ```bash
> export PATH="/path/to/conda/bin:$PATH"
> streamlit run app.py
> ```

The brand scheduler starts automatically in the background on first load. The Consumer Search tab is ready immediately. Click **🔄 Refresh Alerts** in the Brand Dashboard to pull in the latest alerts.

---

## Known Limitations

- **Partial N/A on niche or ambiguous SKUs.** When a product is not well-indexed on a platform (e.g. a specific 1L variant where only 800g results appear in SERP), Gemini returns N/A rather than report the wrong SKU's price. A wrong price is worse than no price.
- **SERP price data is inconsistent.** Not every snippet contains a price. `scrape_batch` enrichment covers the common case, but some platform pages block scrapers downstream. A demo fallback cache covers the two standard watchlist SKUs (Amul Milk 1L, Tata Salt 500g) when live data returns empty.
- **Delivery times rarely appear.** Q-commerce platforms do not include ETAs in Google SERP snippets. The delivery column is populated only when a `scrape_batch` page happens to include it.
- **Pincode specificity.** All queries default to pincode 560038 (Indiranagar, Bangalore). Availability is inferred from SERP results without hard pincode scoping on Zepto and Swiggy.
- **Brand sweep scales linearly.** Each sweep makes one `search_engine_batch` call per watchlist SKU sequentially. A large watchlist will increase sweep time proportionally.
