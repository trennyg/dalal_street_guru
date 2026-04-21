# ◈ Dalal Street Guru

Stock analysis app for Indian markets using principles from Warren Buffett, Rakesh Jhunjhunwala, and top Indian mutual funds.

## Scoring methodology

| Principle | Weight | What it checks |
|---|---|---|
| Buffett | 30% | ROE >15%, low D/E, margins, P/E |
| RJ Style | 30% | Earnings growth, PEG ratio, revenue growth |
| Quality/MF | 25% | Gross margins, FCF yield, dividends |
| Graham Value | 15% | P/B ratio, P/E, price vs 52w high |

Conviction tiers: **Strong Buy** (75+) · **Buy** (60+) · **Watch** (45+) · **Neutral** (30+) · **Avoid** (<30)

---

## Local development

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
# Create .env.local:
echo "REACT_APP_API_URL=http://localhost:8000" > .env.local
npm start
```

App runs at http://localhost:3000

---

## Deploy to the web (free)

### Step 1 — Deploy backend to Render

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your GitHub repo
4. **Root directory**: `backend`
5. **Build command**: `pip install -r requirements.txt`
6. **Start command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
7. Choose **Free** tier → Deploy
8. Copy the URL Render gives you (e.g. `https://dalal-guru-api.onrender.com`)

### Step 2 — Deploy frontend to Vercel

1. Go to [vercel.com](https://vercel.com) → New Project
2. Import your GitHub repo
3. **Root directory**: `frontend`
4. Add environment variable:
   - Key: `REACT_APP_API_URL`
   - Value: `https://your-render-url.onrender.com` (from Step 1)
5. Deploy → Share the Vercel URL with your friends!

---

## Upgrade data sources (when ready)

Replace `fetch_yfinance_data()` in `backend/main.py` with:

| Provider | Cost | What you get |
|---|---|---|
| [Tickertape API](https://tickertape.in) | ₹999/mo | Better fundamentals, MF holdings |
| [Trendlyne](https://trendlyne.com) | ₹1499/mo | Promoter pledges, DII/FII data |
| [BSE/NSE direct](https://www.nseindia.com/api) | Free | Official price data |

The scoring engine in `compute_composite_score()` is already designed to accept richer data — just swap the data source functions.

---

## Adding stocks to the universe

Edit `NSE_UNIVERSE` list in `backend/main.py` to add/remove symbols for the screener.

## Customising weights

Edit the `compute_composite_score()` function:
```python
composite = (
    b["score"] * 0.30 +   # Buffett weight
    rj["score"] * 0.30 +  # RJ Style weight
    q["score"] * 0.25 +   # Quality weight
    v["score"] * 0.15     # Value weight
)
```
