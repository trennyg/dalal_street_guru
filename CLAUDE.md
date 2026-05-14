# stocks.ai — Claude Code Configuration

## What This Is
AI-powered stock screener for Indian retail investors. Scores 585 NSE + BSE stocks using Buffett, Rakesh Jhunjhunwala, Quality/MF, and Graham frameworks. Domain: stocks.relentlessais.com. GitHub repo folder: dalal-street-guru (legacy name — do not rename).

---

## Project Structure
```
dalal-street-guru/
├── frontend/          # React (Create React App) → Vercel
├── backend/           # FastAPI (Python) → Render free tier
├── CLAUDE.md          # You are here
└── docs/
    ├── architecture.md
    ├── scoring.md
    ├── data-sources.md
    └── agents/        # Sub-agent system prompts
```

---

## Local Dev Commands

```bash
# Backend (Terminal 1)
cd C:\Users\trenn\Downloads\dalal-street-guru\backend
python -m uvicorn main:app --reload --port 8000

# Frontend (Terminal 2)
cd C:\Users\trenn\Downloads\dalal-street-guru\frontend
npm start
# .env.local must contain: REACT_APP_API_URL=http://localhost:8000
```

## Deploy Commands
```bash
cd C:\Users\trenn\Downloads\dalal-street-guru
git add .
git commit -m "[TAG] Description"
git push
# Vercel auto-deploys frontend. Render auto-deploys backend.
```

Commit tags: `[BUG]` `[FEATURE]` `[UI]` `[DATA]` `[DEPLOY]` `[MARKETING]`

---

## Tech Stack

| Layer | Tech | Deployed At |
|---|---|---|
| Frontend | React (CRA), functional components + hooks only | Vercel — dalal-street-guru-trennyg.vercel.app |
| Backend | FastAPI (Python) | Render — dalal-street-guru-api.onrender.com |
| Data primary | yfinance | — |
| Data fallback | Screener.in scraping (requests + BeautifulSoup) | — |
| Cache | Disk-based JSON on Render filesystem | Ephemeral — wipes on redeploy |

---

## Non-Negotiable Coding Rules

**Backend:**
- Wrap every yfinance call in `try/except` — bad tickers must never crash the API
- NSE symbols always use `.NS` suffix (e.g. `RELIANCE.NS`), BSE use `.BO`
- Serve stale cache instantly on cold start, refresh in background thread
- Never return a 500 for an unknown ticker — return 404 with a clear message
- All scoring logic lives in `scorer.py`, not inline in routes

**Frontend:**
- Functional components with hooks only — no class components
- API URL always via `process.env.REACT_APP_API_URL` — never hardcoded
- Always show a loading skeleton — never a blank screen (Render sleeps after 15 min)
- Always show a user-friendly error if the API is unreachable
- No new npm packages without checking bundle size impact first

**Both:**
- Always deliver complete, working files — owner is non-technical, no partial diffs
- Never commit `.env`, `.env.local`, `node_modules/`, `__pycache__/`, or cache JSON files

---

## Render Free Tier — Critical Context
- Sleeps after 15 min inactivity → ~30–60s cold start on first request
- Disk (`/tmp/`) is **ephemeral** — wiped on every redeploy
- After any backend deploy: warn that first loads will be slow while cache rebuilds
- `/api/cache/status` shows cache age and coverage

---

## Scoring Model (Summary)
4 frameworks → total score 0–100:
- Buffett 30% | RJ Style 30% | Quality/MF 25% | Graham 15%
- Tiers: Strong Buy 75+ | Buy 60–74 | Watch 45–59 | Neutral 30–44 | Avoid <30
- 8 investor profiles remap framework weights (Buffett, RJ, Damani, Kedia, Parag Parikh, Nippon, Anand Rathi, Enam)
- Banks/NBFCs: D/E exception applies — use NIM + CASA instead
- Loss-making companies: P/E and PEG score 0, not "cheap"

Full scoring logic: @docs/scoring.md
Data validation rules: @docs/data-sources.md

---

## Key API Endpoints
```
GET /api/health                  → liveness check
GET /api/screen                  → all 585 stocks, scored + sorted
GET /api/screen?profile={name}   → filtered by investor profile
GET /api/stock/{ticker}          → full score breakdown for one stock
GET /api/cache/status            → cache age + coverage stats
```

---

## Agent System
This project uses a multi-agent system. When working on a specific area, load the relevant agent for deeper context:

```
@docs/agents/00_ORCHESTRATOR.md      → Route any task to the right agent
@docs/agents/01_DATA_INTELLIGENCE.md → Data validation, yfinance issues
@docs/agents/02_SCORING_ENGINE.md    → Score logic, edge cases, profiles
@docs/agents/03_QUALITY_ANALYST.md   → Pre-deploy checklist, bug triage
@docs/agents/04_FRONTEND_UI.md       → React components, theming
@docs/agents/05_BACKEND_API.md       → FastAPI, cache, pipeline
@docs/agents/06_DEVOPS.md            → Deploy, env vars, Render/Vercel
@docs/agents/07_GROWTH_MARKETING.md  → Content, social posts, SEO
@docs/agents/08_EDUCATION_LEARN.md   → /learn articles, metric explainers
```

---

## Before You Touch Any Code
1. Check which agent owns this area (see above)
2. If data or scoring is involved → validate with Data Intelligence agent first
3. QA agent must sign off before any deploy that changes score output
4. After backend deploy → run smoke test: `/api/health`, `/api/stock/RELIANCE.NS`, `/api/stock/ZOMATO.NS` (loss-making edge case)
