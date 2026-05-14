# Data Sources & Validation — stocks.ai

> Load this when: debugging data issues, adding new metrics, investigating wrong scores.
> Reference with: `@docs/data-sources.md`

---

## Source Priority

```
1. yfinance (primary)
      ↓ if incomplete/missing
2. Screener.in scraping (fallback)
      ↓ if both fail
3. Return partial data with data_warnings[], score missing components 0
      ↓ never
4. Crash or return 500
```

---

## yfinance Field Mapping

| Metric Used in Scorer | yfinance field | Notes |
|---|---|---|
| ROE | `info['returnOnEquity']` | Multiply by 100 for % |
| Debt/Equity | `info['debtToEquity']` | Already a ratio |
| Operating margin | `info['operatingMargins']` | Multiply by 100 for % |
| Gross margin | `info['grossMargins']` | Multiply by 100 for % |
| P/E ratio | `info['trailingPE']` | Use trailing, not forward |
| P/B ratio | `info['priceToBook']` | — |
| Revenue growth (1Y) | `info['revenueGrowth']` | Multiply by 100 for % |
| EPS (TTM) | `info['trailingEps']` | — |
| EPS history (3Y) | `stock.earnings` | DataFrame — need CAGR calc |
| Revenue history (3Y) | `stock.financials` | DataFrame row 'Total Revenue' |
| FCF | `info['freeCashflow']` | Raw ₹ value — divide by market cap for yield |
| Market cap | `info['marketCap']` | For FCF yield calc |
| 52w high | `info['fiftyTwoWeekHigh']` | — |
| 52w low | `info['fiftyTwoWeekLow']` | — |
| Current price | `info['regularMarketPrice']` | — |
| Promoter holding | Not in yfinance — use Screener.in | — |
| ROCE | Not direct — calculate: EBIT / Capital Employed | — |

---

## Screener.in Field Mapping

URL pattern: `https://www.screener.in/company/{SYMBOL}/consolidated/`

| Metric | Screener location | CSS selector / label |
|---|---|---|
| ROE | Key metrics table | "Return on equity" row |
| OPM (Operating margin) | Key metrics table | "OPM" row — 5Y trend available |
| EPS growth (3Y, 5Y) | Key metrics table | "EPS 3Yr CAGR" |
| Revenue growth (3Y) | Key metrics table | "Sales 3Yr CAGR" |
| Promoter holding | Shareholding section | Latest quarter % |
| ROCE | Key metrics table | "ROCE" row |
| D/E ratio | Key metrics table | "Debt to equity" |

⚠️ Screener.in uses **standalone vs consolidated** — always use `consolidated/` URL. If consolidated not available, fall back to `standalone/` and add a warning.

---

## Data Validation Rules

Before any value enters the scorer, run these checks in `fetcher.py`:

```python
VALIDATION_RULES = {
    'roe': {'min': -100, 'max': 500, 'warn_above': 100},
    'debt_equity': {'min': 0, 'max': 50, 'warn_above': 10},
    'operating_margin': {'min': -100, 'max': 100},
    'gross_margin': {'min': -50, 'max': 100},
    'pe_ratio': {'min': None, 'max': None, 'negative_means': 'loss-making'},
    'pb_ratio': {'min': 0, 'max': 100, 'warn_above': 50},
    'revenue_growth': {'min': -100, 'max': 1000, 'warn_above': 200},
    'eps_cagr_3y': {'min': -100, 'max': 500, 'warn_above': 200},
    'fcf': {'min': None, 'max': None},  # Can be negative
    'promoter_holding': {'min': 0, 'max': 100},
}
```

If a value exceeds `warn_above`: add to `data_warnings`, use the value anyway but flag it.
If a value is outside `min/max`: treat as missing, score that component 0, add to `data_warnings`.

---

## Known Data Gaps by Stock Type

| Stock Type | Missing Data | How to Handle |
|---|---|---|
| Banks (HDFCBANK, ICICIBANK, AXISBANK, etc.) | D/E meaningless, FCF meaningless | Apply bank override in scorer |
| NBFCs (BAJFINANCE, MUTHOOTFIN, etc.) | Same as banks | Apply bank override |
| New listings < 3Y (ZOMATO, NYKAA, MAMAEARTH) | 3Y CAGR, EPS history | Score CAGR components 0, add warning |
| Loss-making (PAYTM, ZOMATO as of some dates) | Negative P/E, PEG | Score 0 for those, never label "cheap" |
| Holding cos (BAJAJHLDNG, MAHABALAMB) | P/E distorted by investment gains | Add warning: "Holding company — P/E may be misleading" |
| Commodity cos (COALINDIA, NMDC, HINDCOPPER) | Cyclical OPM | Add warning: "Single-year margin noisy for commodity sector" |
| PSUs (NTPC, ONGC, COALINDIA) | Promoter = Govt ~60%+ | Score normally — high government holding is not a risk signal |

---

## Screener.in Monitoring Checklist

Run this check if Screener fallback starts returning wrong data:

- [ ] Try loading `https://www.screener.in/company/RELIANCE/consolidated/` manually
- [ ] Is the page structure intact? (Key metrics table visible?)
- [ ] Is the site returning a CAPTCHA or bot block? (HTTP 403 or redirect)
- [ ] Check: has Screener updated their HTML class names? (the most common breakage)
- [ ] If blocked: switch to yfinance-only mode, add `"screener_blocked": true` to cache status

---

## Cache File Structure

Each stock gets its own cache file: `/tmp/stocks_cache/RELIANCE.NS.json`

```json
{
  "ticker": "RELIANCE.NS",
  "fetched_at": "2025-03-15T08:30:00Z",
  "source": "yfinance",
  "screener_used": false,
  "raw": {
    "roe": 18.4,
    "debt_equity": 0.45,
    ...
  },
  "score": {
    "total": 68,
    "buffett": 20,
    "rj_style": 22,
    "quality_mf": 17,
    "graham": 9
  },
  "data_warnings": []
}
```

Cache index file `/tmp/stocks_cache/_index.json` tracks all tickers and their `fetched_at` timestamps for the `/api/cache/status` endpoint.
