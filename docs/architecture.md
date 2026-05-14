# Architecture — stocks.ai

> Load this when: planning a new feature, debugging a cross-layer issue, or onboarding to the codebase.
> Reference with: `@docs/architecture.md`

---

## System Overview

```
User (browser / mobile)
        ↓
  Vercel (frontend)
  React CRA app
  stocks.relentlessais.com
        ↓ fetch (REACT_APP_API_URL)
  Render (backend)
  FastAPI Python app
  dalal-street-guru-api.onrender.com
        ↓ primary        ↓ fallback
    yfinance         Screener.in scraping
        ↓
  Disk cache (Render /tmp/)
  JSON files per ticker
```

---

## Frontend Architecture

```
frontend/
├── public/
├── src/
│   ├── components/
│   │   ├── StockCard.js         # Single stock with score bar + conviction badge
│   │   ├── StockGrid.js         # Grid of StockCards with sorting/filtering
│   │   ├── InvestorSelector.js  # Profile pills (Buffett, RJ, etc.)
│   │   ├── StockDetail.js       # Full score breakdown page
│   │   ├── SearchBar.js         # Client-side ticker/name filter
│   │   ├── ScoreBar.js          # Reusable visual score component
│   │   ├── SkeletonGrid.js      # Loading state — shown on cold start
│   │   └── ErrorMessage.js      # User-friendly API error display
│   ├── pages/
│   │   ├── ScreenerPage.js      # Main page — grid + filters
│   │   └── StockPage.js         # /stock/:ticker detail page
│   ├── hooks/
│   │   └── useStocks.js         # Data fetching + caching hook
│   ├── utils/
│   │   └── scoring.js           # Conviction tier labels, score colors
│   └── App.js
├── .env.local                   # REACT_APP_API_URL=http://localhost:8000 (never committed)
└── package.json
```

**State management:** React hooks only (`useState`, `useEffect`, `useMemo`). No Redux, no Context API unless the app grows significantly.

**Routing:** React Router. Two main routes:
- `/` → ScreenerPage (stock grid + investor profile filter)
- `/stock/:ticker` → StockPage (full score breakdown)
- `/learn/:slug` → Education articles (static or fetched from backend)

---

## Backend Architecture

```
backend/
├── main.py              # FastAPI app, all routes, startup event
├── scorer.py            # All scoring logic — 4 frameworks + profiles
├── fetcher.py           # yfinance + Screener.in data fetching
├── cache.py             # Disk cache read/write/invalidate logic
├── universe.py          # Load and manage the 585-stock universe
├── stock_universe.json  # Master list: ticker, name, exchange, sector
├── requirements.txt     # Python dependencies
└── .env                 # Local env vars (never committed)
```

### Request Flow (warm cache)
```
GET /api/screen
  → cache.py: check /tmp/stocks_cache/*.json
  → Load all cached stocks into memory
  → scorer.py: apply profile weight matrix if ?profile= param
  → Return sorted JSON response (< 500ms)
```

### Request Flow (cold / stale cache)
```
GET /api/screen
  → cache.py: no cache or expired
  → fetcher.py: batch yfinance calls (585 tickers, chunked)
  → For each ticker: try yfinance → if incomplete, try Screener.in
  → scorer.py: score each stock
  → cache.py: write to /tmp/stocks_cache/{ticker}.json
  → Return response (may take 30–120s for full universe refresh)
```

### Startup Event
On every server startup (`@app.on_event("startup")`):
1. Load all existing cache files into in-memory dict
2. Check cache age — start background refresh thread for stale entries
3. This means even after a Render cold start, cached data is served instantly

---

## Data Flow

```
yfinance.Ticker(symbol).info
    → dict of ~100 financial fields
    → fetcher.py extracts: ROE, D/E, EPS history, revenue history,
                           P/E, P/B, gross margin, FCF, ROCE,
                           52w high/low, promoter holding, OPM
    → scorer.py calculates sub-scores for each framework
    → Returns structured score object (see API contracts below)
```

---

## API Response Contract

```json
{
  "ticker": "RELIANCE.NS",
  "name": "Reliance Industries Ltd",
  "sector": "Energy",
  "exchange": "NSE",
  "total_score": 68,
  "conviction_tier": "Buy",
  "profile_score": null,
  "frameworks": {
    "buffett": {
      "score": 20,
      "max": 30,
      "metrics": {
        "roe": {"value": 18.4, "score": 5, "max": 8},
        "debt_equity": {"value": 0.45, "score": 4, "max": 7},
        "margin_trend": {"value": "stable", "score": 8, "max": 8},
        "pe_vs_sector": {"value": 1.15, "score": 3, "max": 7}
      }
    },
    "rj_style": { ... },
    "quality_mf": { ... },
    "graham": { ... }
  },
  "data_freshness_hours": 6,
  "data_warnings": [],
  "last_updated": "2025-03-15T08:30:00Z"
}
```

`data_warnings` examples:
- `"FCF data unavailable — scored 0"`
- `"Bank sector — D/E replaced with NIM/CASA"`
- `"Loss-making — P/E and PEG scored 0"`
- `"Newly listed — CAGR metrics unavailable"`

---

## Environment Variables

| Variable | Where | Value |
|---|---|---|
| `REACT_APP_API_URL` | `.env.local` (local) | `http://localhost:8000` |
| `REACT_APP_API_URL` | Vercel dashboard | `https://dalal-street-guru-api.onrender.com` |

Backend has no required env vars currently. Future additions (Screener auth, email alerts) go in Render dashboard → Environment Variables.

---

## Known Technical Debt
- Render free tier disk is ephemeral — full rebuild after every deploy
- No background warm-up job (would need paid tier or external cron)
- Screener.in scraper is fragile — any HTML change breaks it silently
- No database — everything is JSON files and in-memory dicts
- No authentication — fully public screener (intentional for now)
