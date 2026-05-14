# stocks.ai — Multi-Agent System
## Quick Reference Guide

---

## The 8 Agents + Orchestrator

| # | Agent | File | Session Tag | What to ask it |
|---|---|---|---|---|
| 0 | **Orchestrator** | `00_ORCHESTRATOR.md` | Any | "Route this task for me" |
| 1 | **Data Intelligence** | `01_DATA_INTELLIGENCE.md` | `[DATA]` | Data accuracy, yfinance issues, Screener scraping |
| 2 | **Scoring Engine** | `02_SCORING_ENGINE.md` | `[DATA]` | Score logic, investor profiles, edge cases |
| 3 | **Quality Analyst** | `03_QUALITY_ANALYST.md` | `[BUG]` | Pre-deploy checks, bug reports, regressions |
| 4 | **Frontend / UI** | `04_FRONTEND_UI.md` | `[UI]` | React components, design, loading states |
| 5 | **Backend / API** | `05_BACKEND_API.md` | `[FEATURE]` | FastAPI routes, cache, yfinance pipeline |
| 6 | **DevOps** | `06_DEVOPS.md` | `[DEPLOY]` | Deploy, env vars, Render/Vercel issues |
| 7 | **Growth & Content** | `07_GROWTH_MARKETING.md` | `[MARKETING]` | Social posts, YouTube scripts, influencer outreach |
| 8 | **Education / Learn** | `08_EDUCATION_LEARN.md` | `[FEATURE]` | /learn articles, metric explainers |

---

## How to Use These Agents in Claude

### Method 1 — Paste the agent's system prompt at the start of a new chat
Open a fresh Claude conversation. Paste the contents of the relevant `.md` file before your question.

Example:
```
[Paste contents of 01_DATA_INTELLIGENCE.md]

---

My question: yfinance is returning ROE of 9,200% for RTNPOWER.NS — 
is this a data error or real?
```

### Method 2 — Use in a Claude Project
Create a Claude Project called "stocks.ai". Upload all agent files. Reference them by name in your prompts.

### Method 3 — Start with the Orchestrator
For any new task, paste `00_ORCHESTRATOR.md` and describe your task. The Orchestrator will tell you which agent(s) to use and in what order.

---

## Common Workflows

### "I found a bug — stock X shows wrong score"
1. Start with **[BUG]** tag → Orchestrator routes to Quality Analyst
2. QA reproduces and assesses severity
3. QA determines which layer: Data Intelligence (bad data?) or Scoring Engine (bad logic?) or Backend (bad calculation?)
4. Fix agent delivers the corrected file
5. QA signs off
6. DevOps deploys

### "I want to add a new investor profile"
1. **Growth & Content** — research the investor's philosophy (or Education agent)
2. **Scoring Engine** — define the custom weight matrix
3. **Backend** — implement the profile endpoint in FastAPI
4. **Frontend** — add profile to the selector UI
5. **Education** — write the investor profile explainer page
6. **QA** — end-to-end test
7. **DevOps** — deploy

### "Weekly Stock of the Week post"
1. Run the screener — find top Buy/Strong Buy stocks this week
2. **Growth & Content** agent — generate the post using the template
3. Verify the stock data is accurate with **Data Intelligence** agent if uncertain
4. Post to Twitter/X, Instagram, WhatsApp groups

### "Something is broken after a deploy"
1. **DevOps** — check Render and Vercel build logs
2. If API is down → **Backend** agent
3. If UI is broken → **Frontend** agent
4. If scores are wrong → **Data Intelligence** + **Scoring Engine**
5. **QA** runs the smoke test checklist

---

## Data Integrity Priority Order

When multiple agents could solve something, data-related issues always take this priority:

```
Data Intelligence → Scoring Engine → Backend → QA → Frontend
```

Never let the Frontend display a number that Data Intelligence hasn't validated. Never let the Scoring Engine score a metric that Data Intelligence hasn't confirmed is available and accurate.

---

## Key Rules (apply to all agents)

1. **Complete files only.** Owner is non-technical. No partial diffs.
2. **Render is free tier.** Always mention cold start implications when relevant.
3. **yfinance can lie.** Always wrap in try/except. Always validate with Data Intelligence agent first.
4. **QA must sign off** on any change that affects score output or user-visible data.
5. **NSE symbols use `.NS` suffix.** Never forget this.
6. **No hardcoded URLs.** Always use `REACT_APP_API_URL` env var.
7. **Never show a blank screen.** Always handle loading and error states.
