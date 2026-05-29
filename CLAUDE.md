# QuickLens

Real-time q-commerce intelligence system with two agentic AI loops — one reactive (consumer), one proactive (brand) — powered by Bright Data's live web data infrastructure and Google Gemini as the reasoning engine.

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM reasoning | Google Gemini (`gemini-2.5-flash-lite`) via `google-genai` SDK |
| Web data | Bright Data MCP (`@brightdata/mcp`) via `mcp` Python library |
| UI | Streamlit (two views: consumer search + brand dashboard) |
| Background jobs | APScheduler `BackgroundScheduler` (brand loop, 5-min interval) |
| State | `state.json` (shared by both loops, file-locked via `filelock`) |
| Data models | Pydantic v2 |

---

## Architecture

### Consumer Loop (reactive — user triggered)
```
user query
  └─ consumer/planner.py   — Gemini: NL query → structured search plan
  └─ scraper/mcp_client.py — scrape_all_platforms(): one search_engine_batch call
  └─ consumer/ranker.py    — Gemini: SERP JSON → ranked list (price, delivery, savings)
  └─ consumer/agent.py     — orchestrates the above, yields reasoning steps as strings
```

### Brand Loop (proactive — scheduler triggered)
```
APScheduler (every 5 min) or manual trigger
  └─ brand/agent.py      — sweeps watchlist, scrapes live data, diffs against state
  └─ brand/alerter.py    — Gemini: deltas → significance filter → alert text + recommendation
  └─ brand/scheduler.py  — start_brand_scheduler() + trigger_manual_sweep() for demo button
```

### Shared State (`state.json`)
```json
{
  "watchlist":     [ WatchlistItem, ... ],
  "price_history": { "sku": { "platform": [ PriceSnapshot, ... ] } },
  "alert_log":     [ AlertEntry, ... ]
}
```
Both loops read and write the same file. FileLock serialises concurrent access between the APScheduler background thread and the Streamlit main thread.

---

## Available Bright Data MCP Tools

Discovered via `session.list_tools()` on this account:

| Tool | Used for |
|---|---|
| `search_engine` | Single-platform SERP query |
| `search_engine_batch` | **Primary data path** — all 3 platforms in one API call |
| `scrape_as_markdown` | Static page scraping (price aggregator sites) |
| `scrape_batch` | Secondary enrichment when SERP snippet has no `₹` price |
| `discover` | AI-ranked web search (available, not currently used in main path) |

---

## Key Constraints Discovered During Build

| Constraint | Detail |
|---|---|
| `scraping_browser_*` tools **NOT available** | These tools don't exist on this Bright Data account |
| `web_unlocker` **NOT available** | Not on this account's plan |
| Direct platform scraping **blocked** | Blinkit, Zepto, Swiggy return `robots.txt` errors via `scrape_as_markdown` |
| **Working approach** | `search_engine_batch` with `site:blinkit.com`, `site:zepto.com`, `site:swiggy.com/instamart` — Google SERP titles contain current prices (e.g. "Buy Online at ₹59") |
| Secondary enrichment | `scrape_batch` called on top organic URL only when `₹` is absent from SERP snippet |
| Gemini model | `gemini-1.5-flash` → 404; `gemini-2.0-flash` / `gemini-2.0-flash-lite` / `gemini-2.0-flash-lite-001` → retired for new users (404); `gemini-2.5-flash` → available but frequent 503s; **use `gemini-2.5-flash-lite`** (confirmed working 2026-05-28) |
| Gemini 503s | `gemini-2.5-flash` hits UNAVAILABLE errors under demand spikes. `call_gemini()` in `shared/gemini_client.py` retries up to 3× on 503/UNAVAILABLE with 2s backoff; re-raises everything else immediately. |
| SERP price hits are inconsistent | `search_engine_batch` snippets sometimes contain no `₹` price (observed on Amul Milk 1L run). `DEMO_CACHE` in `mcp_client.py` fires as fallback when all platforms return price-less results. |
| Node.js | Not in system PATH — installed via conda: `/home/panka/miniforge3/bin/npx` |

---

## Default Pincode

**560038** — Indiranagar, Bangalore. Used as URL param `?pincode=560038` on Blinkit. Constant `DEFAULT_PINCODE` in `scraper/url_builder.py`.

---

## Environment Variables

```
GEMINI_API_KEY=AIza...          # Google Gemini API key
BRIGHT_DATA_API_TOKEN=...       # Bright Data account token (passed as API_TOKEN to MCP subprocess)
```

File: `~/quicklens/.env` — never committed. See `.env.example`.

---

## How to Run

```bash
cd ~/quicklens
# Ensure PATH includes conda Node.js
export PATH="/home/panka/miniforge3/bin:$PATH"
streamlit run app.py
```

---

## Demo Fallback Cache

`DEMO_CACHE` in `scraper/mcp_client.py` fires when `search_engine_batch` returns zero `₹` prices across all platforms (SERP data variance). Matched by keyword subset on the normalised query — both words must appear.

| Cache entry | Keywords | Blinkit | Zepto | Swiggy Instamart |
|---|---|---|---|---|
| Amul Milk 1L | `amul` + `milk` | ₹72 | ₹72 | ₹83 |
| Tata Salt 500g | `tata` + `salt` | ₹22 | ₹21 | ₹24 |

Cached `ScrapeResult`s have `cached=True`. The UI shows **· *demo cache*** next to the results heading and "demo cache" in the elapsed-time caption when this fires.

To add a new entry: add a `_PRODUCT_SERP` dict (realistic SERP JSON with `₹` in title/snippet) and append `({"kw1", "kw2"}, _PRODUCT_SERP)` to `DEMO_CACHE`.

---

## Demo Watchlist (Pre-seeded)

`state.json` is auto-seeded on first load if empty:

| SKU | Platforms | Pincode | Special |
|---|---|---|---|
| Amul Milk 1L | blinkit, zepto, swiggy_instamart | 560038 | — |
| Tata Salt 500g | blinkit, zepto, swiggy_instamart | 560038 | **Zepto seeded as OOS** — fires alert on first brand sweep |

The Zepto OOS on Tata Salt is intentionally seeded to demonstrate the brand alert loop during the 5-minute demo. `brand/agent._check_unalerted_oos()` detects it on the first sweep because `alert_log` is empty.

---

## Build Status

| Phase | Files | Status |
|---|---|---|
| Phase 1 — Foundation | `shared/models.py`, `shared/state_store.py`, `scraper/mcp_client.py`, `scraper/url_builder.py` | ✅ Complete |
| Phase 2 — Consumer Loop | `consumer/planner.py`, `consumer/agent.py`, `consumer/ranker.py` | ✅ Complete |
| Phase 3 — Brand Loop | `brand/agent.py`, `brand/alerter.py`, `brand/scheduler.py` | ✅ Complete |
| Phase 4 — UI | `app.py` | ✅ Complete |
| Phase 5 — Gemini Retry | `shared/gemini_client.py` + update callers in planner, ranker, alerter | ✅ Complete |
| Phase 6 — Demo Polish | `scraper/mcp_client.py` DEMO_CACHE · `shared/models.py` `cached` field · `app.py` spinner + elapsed time | ✅ Complete |
| Phase 7 — Bug Fixes | `app.py`, `scraper/mcp_client.py` | ✅ Complete |

### Phase 7 details

- **`st_autorefresh` removed** — the 30-second JS timer was firing mid-search (during the ~5–20 s generator window), causing the Streamlit script run to be interrupted before session state was written. Results silently disappeared. Replaced with a manual **🔄 Refresh Alerts** button in the Brand Dashboard; the APScheduler brand sweep still runs every 5 min in the background.
- **`_has_price(None)` crash fixed** — `_has_price` in `mcp_client.py` called `re.search()` on `r.raw_markdown`, which is `None` for platforms that returned an empty SERP. This raised `TypeError` inside `_all_no_price`, preventing the demo cache from ever firing. Added an early `if not text: return False` guard.
- **Demo cache confirmed working** — `_cache_lookup` keyword matching (`{"amul","milk"}`, `{"tata","salt"}`) is correct; the only blocker was the `_has_price` crash above.
- **Best deal highlighting** — replaced Pandas `.style.apply()` (dark background + white text legibility issues) with a `🏆` emoji badge prepended to the Platform cell of row 0. Plain `st.dataframe`, no CSS.
- **App confirmed working** — consumer loop tested 3× in a row post-fix; all three searches returned results.

---

## Project Structure

```
quicklens/
├── app.py                      # Streamlit UI — two tabs: Consumer Search + Brand Dashboard; spinner + elapsed time; manual Refresh Alerts button (no st_autorefresh)
├── state.json                  # Runtime state — auto-created, not committed
├── .env                        # Secrets — not committed
├── .env.example
├── requirements.txt
├── CLAUDE.md
│
├── consumer/
│   ├── planner.py              # Gemini: NL query → scrape plan
│   ├── agent.py                # Agentic loop, yields reasoning steps as strings
│   └── ranker.py               # Gemini: SERP → ranked RankedResult list
│
├── brand/
│   ├── agent.py                # One full monitoring sweep, returns deltas
│   ├── alerter.py              # Gemini: deltas → AlertEntry list
│   └── scheduler.py            # APScheduler + trigger_manual_sweep()
│
├── scraper/
│   ├── mcp_client.py           # Bright Data MCP wrapper, CONSUMER_TOOLS schemas, DEMO_CACHE fallback
│   └── url_builder.py          # Platform search URL construction
│
└── shared/
    ├── models.py               # Pydantic v2: WatchlistItem, PriceSnapshot, AlertEntry, ScrapeResult (cached field)
    ├── state_store.py          # Thread-safe JSON state: load, save, helpers
    └── gemini_client.py        # call_gemini() — MODEL=gemini-2.5-flash-lite, 3× retry on 503
```
