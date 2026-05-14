# Scoring Logic — stocks.ai

> Load this when: changing scoring formulas, adding investor profiles, debugging wrong scores.
> Reference with: `@docs/scoring.md`

---

## Framework Weights (Default / Blended)

| Framework | Weight | File | Key metrics |
|---|---|---|---|
| Buffett Quality | 30% | `scorer.py:score_buffett()` | ROE, D/E, margin trend, P/E vs sector |
| RJ Style | 30% | `scorer.py:score_rj()` | EPS CAGR, revenue CAGR, PEG, promoter holding |
| Quality / MF | 25% | `scorer.py:score_quality()` | Gross margin, FCF yield, ROCE, dividend consistency |
| Graham Value | 15% | `scorer.py:score_graham()` | P/B, P/E absolute, price vs 52w high |

---

## Conviction Tiers

| Score | Tier | Display color |
|---|---|---|
| 75–100 | Strong Buy | Green |
| 60–74 | Buy | Teal/Blue |
| 45–59 | Watch | Amber |
| 30–44 | Neutral | Gray |
| < 30 | Avoid | Red |

---

## Buffett Framework — 30 points max

| Metric | Thresholds | Points |
|---|---|---|
| ROE | >20% / 15–20% / 10–15% / <10% | 8 / 5 / 3 / 0 |
| Debt/Equity | <0.3 / 0.3–0.8 / 0.8–1.5 / >1.5 | 7 / 4 / 2 / 0 |
| Operating margin trend (3Y) | Stable or improving / volatile / declining | 8 / 3 / 0 |
| P/E vs sector median | <0.8× / 0.8–1.2× / 1.2–1.5× / >1.5× | 7 / 4 / 2 / 0 |

**Bank/NBFC override:** Replace D/E (7pts) with NIM >3.5%=5pts / 2.5–3.5%=3pts / <2.5%=0pts + CASA >45%=2pts / <45%=0pts

---

## RJ Style Framework — 30 points max

| Metric | Thresholds | Points |
|---|---|---|
| EPS CAGR (3Y) | >25% / 15–25% / 5–15% / negative | 10 / 7 / 4 / 0 |
| Revenue CAGR (3Y) | >20% / 10–20% / <10% | 8 / 5 / 2 |
| PEG ratio | <1 / 1–1.5 / 1.5–2.5 / >2.5 / N/A | 8 / 5 / 2 / 0 / 0 |
| Promoter holding | >60% / 40–60% / <40% | 4 / 2 / 0 |

**Pre-profit override:** EPS CAGR = 0, PEG = 0. Never treat negative earnings as a growth signal.

---

## Quality / MF Framework — 25 points max

| Metric | Thresholds | Points |
|---|---|---|
| Gross margin | >60% / 40–60% / 20–40% / <20% | 7 / 5 / 3 / 1 |
| FCF yield | >5% / 2–5% / 0–2% / negative | 7 / 4 / 2 / 0 |
| ROCE | >20% / 15–20% / 10–15% / <10% | 7 / 4 / 2 / 0 |
| Dividend (3Y+ growing) | Yes / No | 4 / 0 |

**Bank/NBFC override:** Replace FCF yield (7pts) with ROA >1.5%=6pts / 1–1.5%=4pts / <1%=0pts

---

## Graham Value Framework — 15 points max

| Metric | Thresholds | Points |
|---|---|---|
| P/B ratio | <1.5 / 1.5–2.5 / 2.5–4 / >4 | 6 / 4 / 2 / 0 |
| P/E absolute | <15 / 15–20 / 20–30 / >30 | 5 / 3 / 1 / 0 |
| Price vs 52w high | <70% / 70–85% / >85% | 4 / 2 / 0 |

---

## Investor Profile Weight Matrices

When a profile is selected, replace default weights with profile weights. Renormalize to 100.

| Profile | Buffett | RJ Style | Quality/MF | Graham |
|---|---|---|---|---|
| **Default (blended)** | 30% | 30% | 25% | 15% |
| Rakesh Jhunjhunwala | 20% | 50% | 20% | 10% |
| Warren Buffett | 50% | 10% | 30% | 10% |
| Ramesh Damani | 25% | 25% | 20% | 30% |
| Vijay Kedia (SMILE) | 15% | 45% | 30% | 10% |
| Parag Parikh Flexi | 35% | 25% | 35% | 5% |
| Nippon Small Cap | 10% | 45% | 35% | 10% |
| Anand Rathi Wealth | 40% | 15% | 40% | 5% |
| Enam Securities | 45% | 20% | 25% | 10% |

Profile score calculation:
```python
profile_score = (
    buffett_raw_score * profile_weights['buffett'] +
    rj_raw_score * profile_weights['rj_style'] +
    quality_raw_score * profile_weights['quality_mf'] +
    graham_raw_score * profile_weights['graham']
) / (30 * profile_weights['buffett'] + 30 * profile_weights['rj_style'] +
     25 * profile_weights['quality_mf'] + 15 * profile_weights['graham']) * 100
```

---

## Edge Case Handling

| Situation | Rule |
|---|---|
| Negative earnings | P/E = N/A, PEG = N/A → score both 0. Never label as "cheap" |
| Negative book value | P/B = N/A → Graham P/B component = 0 |
| Bank / NBFC | Apply D/E and FCF overrides (see above) |
| Newly listed < 3 years | 3Y CAGR metrics = 0, flag in data_warnings |
| FCF data missing | FCF component = 0, add to data_warnings |
| Promoter = 0% (PSU-type) | Score component normally — 0% = 0pts |
| Holding company | Add warning: "Consolidated P/E may be distorted" |
| Commodity/cyclical | Note in warnings: "Single-year OPM noisy — check 5Y average" |

---

## Score Health Checks (run after any scoring change)

Expected distribution in a healthy market:
- Strong Buy (75+): ~5%
- Buy (60–74): ~15%
- Watch (45–59): ~30%
- Neutral (30–44): ~35%
- Avoid (<30): ~15%

If > 20% Strong Buy → model is inflating scores. Recalibrate thresholds.

Benchmark regression (approximate expected tiers — verify with live data):
| Stock | Expected tier |
|---|---|
| HDFC Bank | Buy |
| Hindustan Unilever | Buy or Strong Buy |
| Infosys | Buy or Strong Buy |
| Zomato | Watch or Neutral (loss-making) |
| Tata Motors | Neutral or Watch (cyclical) |
| Coal India | Watch (low growth, high dividend) |
