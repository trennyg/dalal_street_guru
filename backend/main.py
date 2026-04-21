from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from datetime import datetime
import threading
import time
import requests
from bs4 import BeautifulSoup

app = FastAPI(title="Dalal Street Guru API", version="8.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_cache = {}
_cache_time = None
_cache_lock = threading.Lock()
_is_refreshing = False
_refresh_progress = {"done": 0, "total": 0}

NSE_UNIVERSE = [
    "RELIANCE", "TCS", "HDFCBANK", "BHARTIARTL", "ICICIBANK",
    "INFOSYS", "HINDUNILVR", "ITC", "LT", "KOTAKBANK",
    "HCLTECH", "AXISBANK", "BAJFINANCE", "MARUTI", "SUNPHARMA",
    "TITAN", "ULTRACEMCO", "ASIANPAINT", "NESTLEIND", "WIPRO",
    "TECHM", "ONGC", "POWERGRID", "NTPC", "TATAMOTORS",
    "BAJAJFINSV", "ADANIPORTS", "COALINDIA", "BRITANNIA", "CIPLA",
    "DRREDDY", "EICHERMOT", "HEROMOTOCO", "HINDALCO", "INDUSINDBK",
    "JSWSTEEL", "DIVISLAB", "SBIN", "TATASTEEL", "APOLLOHOSP",
    "PIDILITIND", "TATACONSUM", "DMART", "HAVELLS", "POLYCAB",
    "TORNTPHARM", "MARICO", "DABUR", "HDFCLIFE", "BAJAJ-AUTO",
]

SCREENER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.screener.in/",
}

def parse_number(text):
    if not text:
        return None
    text = str(text).strip().replace(",", "").replace("₹", "").replace("%", "").replace("Cr.", "").replace("Cr", "").strip()
    if text in ("", "-", "—", "N/A"):
        return None
    if "/" in text:
        text = text.split("/")[0].strip()
    try:
        return float(text)
    except:
        return None


def fetch_screener(symbol: str) -> dict:
    session = requests.Session()
    session.headers.update(SCREENER_HEADERS)
    try:
        session.get("https://www.screener.in/", timeout=8)
        time.sleep(0.3)
    except:
        pass

    for suffix in ["/consolidated/", "/"]:
        try:
            url = f"https://www.screener.in/company/{symbol}{suffix}"
            r = session.get(url, timeout=12)
            if r.status_code in (404, 403):
                continue
            if r.status_code != 200:
                continue

            soup = BeautifulSoup(r.text, "html.parser")
            if not soup.select_one("#top-ratios"):
                continue

            # ── Collect ALL key-value pairs from ENTIRE page ──
            # This catches top-ratios, secondary ratios tables, and any named list
            all_kv = {}

            # 1. Top ratios section
            for li in soup.select("#top-ratios li"):
                name_el = li.select_one(".name")
                val_el  = li.select_one(".number, .value")
                if name_el and val_el:
                    all_kv[name_el.get_text(strip=True)] = val_el.get_text(strip=True)

            # 2. All other ratio list items anywhere on page
            for li in soup.select("ul.ratios li, .company-ratios li, #ratios li"):
                name_el = li.select_one(".name, span:first-child")
                val_el  = li.select_one(".number, .value, span:last-child")
                if name_el and val_el:
                    k = name_el.get_text(strip=True)
                    v = val_el.get_text(strip=True)
                    if k and v and k != v:
                        all_kv[k] = v

            # 3. Scan ALL list items with a "name" class anywhere
            for li in soup.select("li"):
                name_el = li.select_one(".name")
                val_el  = li.select_one(".number, .value")
                if name_el and val_el:
                    k = name_el.get_text(strip=True)
                    v = val_el.get_text(strip=True)
                    if k and v:
                        all_kv[k] = v

            # 4. Also check table rows (some Screener pages use tables)
            for tr in soup.select("table tr"):
                cells = tr.select("td")
                if len(cells) >= 2:
                    k = cells[0].get_text(strip=True)
                    v = cells[1].get_text(strip=True)
                    if k and v:
                        all_kv[k] = v

            # ── Extract fields ──
            def get(key, *aliases):
                for k in [key] + list(aliases):
                    if k in all_kv:
                        return parse_number(all_kv[k])
                    # Partial match
                    for ak in all_kv:
                        if k.lower() in ak.lower():
                            return parse_number(all_kv[ak])
                return None

            current_price = get("Current Price")
            mc_cr         = get("Market Cap")
            market_cap    = mc_cr * 1e7 if mc_cr else None
            pe            = get("Stock P/E", "P/E")
            book_value    = get("Book Value")
            pb            = round(current_price / book_value, 2) if current_price and book_value and book_value > 0 else None

            roe_raw  = get("ROE", "Return on equity")
            roe      = (roe_raw / 100) if roe_raw is not None else None

            roce_raw = get("ROCE", "Return on Capital Employed")
            roce     = (roce_raw / 100) if roce_raw is not None else None

            de       = get("Debt to equity", "D/E", "Debt / Equity")

            opm_raw  = get("OPM", "Operating Profit Margin", "Opr. Profit Margin", "EBITDA Margin")
            opm      = (opm_raw / 100) if opm_raw is not None else None

            # If OPM still null, try to infer from pros/cons text
            # e.g. "OPM has increased to 35.2%" in cons
            if opm is None:
                all_text = soup.get_text()
                import re
                opm_match = re.search(r'OPM[^\d]*(\d+\.?\d*)%', all_text)
                if opm_match:
                    opm = float(opm_match.group(1)) / 100

            dy_raw   = get("Dividend Yield")
            dy       = (dy_raw / 100) if dy_raw is not None else None

            # 52w high/low
            hl_text  = all_kv.get("High / Low", "")
            w52_high, w52_low = None, None
            if hl_text and "/" in hl_text:
                parts    = hl_text.replace("₹", "").replace(",", "").split("/")
                w52_high = parse_number(parts[0])
                w52_low  = parse_number(parts[1]) if len(parts) > 1 else None

            eps      = get("EPS")

            ph_raw   = get("Promoter holding", "Promoter Holding", "Promoter")
            promoter_holding = (ph_raw / 100) if ph_raw is not None else None

            # ── Company name ──
            company_name = symbol
            for sel in ["h1.margin-0", "h1"]:
                el = soup.select_one(sel)
                if el:
                    company_name = el.get_text(strip=True)
                    break

            # ── Sector: find /screen/ links ──
            sector = "Unknown"
            for a in soup.select("a[href*='/screen/']"):
                text = a.get_text(strip=True)
                if text and 2 < len(text) < 40:
                    sector = text
                    break

            pros = [li.get_text(strip=True) for li in soup.select(".pros li")][:3]
            cons = [li.get_text(strip=True) for li in soup.select(".cons li")][:3]

            result = {
                "company_name": company_name,
                "sector": sector,
                "current_price": current_price,
                "market_cap": market_cap,
                "pe_ratio": pe,
                "pb_ratio": pb,
                "book_value": book_value,
                "roe": roe,
                "roce": roce,
                "debt_to_equity": de,
                "operating_margins": opm,
                "gross_margins": opm,
                "dividend_yield": dy,
                "52w_high": w52_high,
                "52w_low": w52_low,
                "eps": eps,
                "promoter_holding": promoter_holding,
                "pros": pros,
                "cons": cons,
                "_all_fields": all_kv,
            }

            if not result.get("pe_ratio") and not result.get("current_price"):
                continue

            return result

        except Exception as e:
            print(f"  Screener error {symbol}: {e}")
            continue

    return {}


# ─── Scoring — India calibrated ──────────────────────────────────────────────────
def to_pct(val):
    return val * 100 if val is not None else None


def score_buffett(d):
    s, r = 0, []
    roe = to_pct(d.get("roe"))
    if roe:
        if roe >= 25:   s += 28; r.append(f"Exceptional ROE {roe:.1f}%")
        elif roe >= 18: s += 20; r.append(f"Strong ROE {roe:.1f}%")
        elif roe >= 12: s += 12; r.append(f"Decent ROE {roe:.1f}%")
        elif roe >= 8:  s += 5
    de = d.get("debt_to_equity")
    if de is not None:
        if de < 0.1:   s += 25; r.append("Virtually debt-free")
        elif de < 0.3: s += 20; r.append("Near debt-free")
        elif de < 0.5: s += 14; r.append("Low debt")
        elif de < 1.0: s += 6
    else:
        pros_cons = " ".join(d.get("pros", []) + d.get("cons", []))
        if "debt free" in pros_cons.lower():
            s += 20; r.append("Debt-free (Screener confirmed)")
    opm = to_pct(d.get("operating_margins"))
    if opm:
        if opm >= 30:   s += 25; r.append(f"Excellent OPM {opm:.1f}%")
        elif opm >= 20: s += 18; r.append(f"Good OPM {opm:.1f}%")
        elif opm >= 12: s += 10
        elif opm >= 6:  s += 4
    pe = d.get("pe_ratio")
    if pe and pe > 0:
        if pe < 12:   s += 22; r.append(f"Very cheap P/E {pe:.1f}x")
        elif pe < 20: s += 16; r.append(f"Reasonable P/E {pe:.1f}x")
        elif pe < 30: s += 8
        elif pe < 45: s += 3
    return {"score": min(s, 100), "reasons": r, "label": "Buffett"}


def score_rj(d):
    s, r = 0, []
    roe = to_pct(d.get("roe"))
    if roe:
        if roe >= 30:   s += 30; r.append(f"Exceptional ROE {roe:.1f}% — RJ's favourite")
        elif roe >= 22: s += 22; r.append(f"Strong ROE {roe:.1f}%")
        elif roe >= 15: s += 14
        elif roe >= 10: s += 6
    roce = to_pct(d.get("roce"))
    if roce:
        if roce >= 30:   s += 20; r.append(f"Excellent ROCE {roce:.1f}%")
        elif roce >= 20: s += 14; r.append(f"Good ROCE {roce:.1f}%")
        elif roce >= 12: s += 7
    pe = d.get("pe_ratio")
    if pe and pe > 0:
        if pe < 15:   s += 20; r.append(f"Attractive P/E {pe:.1f}x")
        elif pe < 25: s += 14; r.append(f"Reasonable P/E {pe:.1f}x")
        elif pe < 40: s += 6
        elif pe < 60: s += 2
    ph = to_pct(d.get("promoter_holding"))
    if ph:
        if ph >= 60:   s += 30; r.append(f"Very high promoter holding {ph:.1f}%")
        elif ph >= 50: s += 22; r.append(f"High promoter holding {ph:.1f}%")
        elif ph >= 35: s += 12; r.append(f"Decent promoter holding {ph:.1f}%")
    return {"score": min(s, 100), "reasons": r, "label": "RJ Style"}


def score_quality(d):
    s, r = 0, []
    opm = to_pct(d.get("operating_margins"))
    if opm:
        if opm >= 30:   s += 30; r.append(f"Wide moat — OPM {opm:.1f}%")
        elif opm >= 20: s += 22; r.append(f"Strong margins {opm:.1f}%")
        elif opm >= 12: s += 12
        elif opm >= 6:  s += 5
    roce = to_pct(d.get("roce"))
    if roce:
        if roce >= 30:   s += 28; r.append(f"Exceptional ROCE {roce:.1f}%")
        elif roce >= 20: s += 20; r.append(f"Strong ROCE {roce:.1f}%")
        elif roce >= 12: s += 10
        elif roce >= 8:  s += 4
    dy = to_pct(d.get("dividend_yield"))
    if dy:
        if dy >= 4:   s += 22; r.append(f"High dividend yield {dy:.1f}%")
        elif dy >= 2: s += 14; r.append(f"Good dividend yield {dy:.1f}%")
        elif dy >= 1: s += 7
    de = d.get("debt_to_equity")
    if de is not None and de < 0.3:
        s += 20; r.append("Fortress balance sheet")
    elif de is None:
        pros_text = " ".join(d.get("pros", []))
        if "debt free" in pros_text.lower():
            s += 18; r.append("Debt-free company")
    return {"score": min(s, 100), "reasons": r, "label": "Quality/MF"}


def score_value(d):
    s, r = 0, []
    pb = d.get("pb_ratio")
    if pb and pb > 0:
        if pb < 1:    s += 40; r.append(f"Below book value P/B {pb:.2f}x")
        elif pb < 2:  s += 28; r.append(f"Near book value P/B {pb:.2f}x")
        elif pb < 4:  s += 16; r.append(f"Moderate P/B {pb:.2f}x")
        elif pb < 8:  s += 6
        elif pb < 15: s += 2
    pe = d.get("pe_ratio")
    if pe and pe > 0:
        if pe < 10:   s += 35; r.append(f"Deep value P/E {pe:.1f}x")
        elif pe < 15: s += 25; r.append(f"Value zone P/E {pe:.1f}x")
        elif pe < 22: s += 15; r.append(f"Fair value P/E {pe:.1f}x")
        elif pe < 30: s += 7
        elif pe < 40: s += 2
    price = d.get("current_price")
    high  = d.get("52w_high")
    if price and high and high > 0:
        pct_off = ((high - price) / high) * 100
        if pct_off >= 35:   s += 25; r.append(f"{pct_off:.0f}% below 52w high")
        elif pct_off >= 20: s += 16; r.append(f"Down {pct_off:.0f}% from highs")
        elif pct_off >= 10: s += 8
        elif pct_off >= 5:  s += 3
    return {"score": min(s, 100), "reasons": r, "label": "Graham Value"}


def compute_score(d):
    b  = score_buffett(d)
    rj = score_rj(d)
    q  = score_quality(d)
    v  = score_value(d)
    composite = round(b["score"]*0.30 + rj["score"]*0.30 + q["score"]*0.25 + v["score"]*0.15, 1)
    reasons   = b["reasons"] + rj["reasons"] + q["reasons"] + v["reasons"]
    return {
        "composite": composite,
        "scores": {"buffett": b["score"], "rj_style": rj["score"], "quality": q["score"], "value": v["score"]},
        "top_reasons": reasons[:5],
        "sub_scores": [b, rj, q, v],
    }


def conviction_tier(score):
    if score >= 70: return "Strong Buy"
    if score >= 55: return "Buy"
    if score >= 40: return "Watch"
    if score >= 25: return "Neutral"
    return "Avoid"


def build_entry(symbol, raw):
    scoring = compute_score(raw)
    return {
        "symbol":           symbol,
        "company_name":     raw.get("company_name", symbol),
        "sector":           raw.get("sector", "Unknown"),
        "current_price":    raw.get("current_price"),
        "market_cap":       raw.get("market_cap"),
        "52w_high":         raw.get("52w_high"),
        "52w_low":          raw.get("52w_low"),
        "pe_ratio":         raw.get("pe_ratio"),
        "pb_ratio":         raw.get("pb_ratio"),
        "book_value":       raw.get("book_value"),
        "roe":              raw.get("roe"),
        "roce":             raw.get("roce"),
        "debt_to_equity":   raw.get("debt_to_equity"),
        "operating_margins":raw.get("operating_margins"),
        "dividend_yield":   raw.get("dividend_yield"),
        "promoter_holding": raw.get("promoter_holding"),
        "eps":              raw.get("eps"),
        "pros":             raw.get("pros", []),
        "cons":             raw.get("cons", []),
        "scoring":          scoring,
        "conviction":       conviction_tier(scoring["composite"]),
        "cached_at":        datetime.now().isoformat(),
        "source":           "screener.in",
    }


# ─── Debug ────────────────────────────────────────────────────────────────────────
@app.get("/api/debug/{symbol}")
def debug_stock(symbol: str):
    raw = fetch_screener(symbol.upper())
    return {"symbol": symbol.upper(), "raw": raw}


# ─── Cache ────────────────────────────────────────────────────────────────────────
def refresh_cache():
    global _cache, _cache_time, _is_refreshing, _refresh_progress
    if _is_refreshing:
        return
    _is_refreshing = True
    _refresh_progress = {"done": 0, "total": len(NSE_UNIVERSE)}
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Cache refresh — {len(NSE_UNIVERSE)} stocks\n")

    new_cache = {}
    for i, symbol in enumerate(NSE_UNIVERSE):
        try:
            print(f"  [{i+1}/{len(NSE_UNIVERSE)}] {symbol}...", end=" ", flush=True)
            raw = fetch_screener(symbol)
            if raw and (raw.get("pe_ratio") or raw.get("current_price")):
                entry = build_entry(symbol, raw)
                new_cache[symbol] = entry
                roe_d = f"{to_pct(raw.get('roe')):.1f}%" if raw.get("roe") else "-"
                opm_d = f"{to_pct(raw.get('operating_margins')):.1f}%" if raw.get("operating_margins") else "-"
                ph_d  = f"{to_pct(raw.get('promoter_holding')):.1f}%" if raw.get("promoter_holding") else "-"
                print(f"✓ score={entry['scoring']['composite']} conviction={entry['conviction']} ROE={roe_d} OPM={opm_d} Promoter={ph_d}")
            else:
                print("✗ no data")
            _refresh_progress["done"] = i + 1
            time.sleep(2)
        except Exception as e:
            print(f"✗ {e}")
            _refresh_progress["done"] = i + 1
            time.sleep(2)

    with _cache_lock:
        _cache     = new_cache
        _cache_time = datetime.now()
    print(f"\n✓ Cache ready: {len(new_cache)}/{len(NSE_UNIVERSE)} at {_cache_time.strftime('%H:%M:%S')}\n")
    _is_refreshing = False


@app.on_event("startup")
async def startup():
    threading.Thread(target=refresh_cache, daemon=True).start()


# ─── Routes ──────────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "status": "running", "version": "8.0.0",
        "cached_stocks": len(_cache), "refreshing": _is_refreshing,
        "refresh_progress": f"{_refresh_progress['done']}/{_refresh_progress['total']}" if _is_refreshing else "idle",
        "cache_age": str(datetime.now() - _cache_time).split(".")[0] if _cache_time else "warming up",
    }

@app.get("/api/cache/status")
def cache_status():
    return {
        "ready": len(_cache) > 0, "count": len(_cache),
        "refreshing": _is_refreshing, "progress": _refresh_progress,
        "last_updated": _cache_time.isoformat() if _cache_time else None,
    }

@app.get("/api/cache/refresh")
def trigger_refresh(background_tasks: BackgroundTasks):
    if _is_refreshing:
        return {"message": "Already refreshing", "progress": _refresh_progress}
    background_tasks.add_task(refresh_cache)
    return {"message": "Refresh started"}

@app.get("/api/stock/{symbol}")
def get_stock(symbol: str):
    symbol = symbol.upper().strip()
    with _cache_lock:
        if symbol in _cache:
            return _cache[symbol]
    raw = fetch_screener(symbol)
    if not raw:
        raise HTTPException(404, f"Could not find {symbol} on Screener.in")
    entry = build_entry(symbol, raw)
    with _cache_lock:
        _cache[symbol] = entry
    return entry

@app.get("/api/screen")
def screen(
    min_score: float = Query(40),
    sector: Optional[str] = Query(None),
    conviction: Optional[str] = Query(None),
    limit: int = Query(20, le=50),
):
    with _cache_lock:
        stocks = list(_cache.values())
    if not stocks:
        done  = _refresh_progress.get("done", 0)
        total = _refresh_progress.get("total", len(NSE_UNIVERSE))
        return {"count": 0, "stocks": [], "warming": True,
                "message": f"Loading... {done}/{total} done. Try again shortly."}
    results = [
        s for s in stocks
        if s["scoring"]["composite"] >= min_score
        and (not conviction or conviction.lower() in s["conviction"].lower())
        and (not sector or sector.lower() in (s.get("sector") or "").lower())
    ]
    results.sort(key=lambda x: x["scoring"]["composite"], reverse=True)
    return {"count": len(results), "stocks": results[:limit],
            "total_cached": len(stocks),
            "cache_age": str(datetime.now() - _cache_time).split(".")[0] if _cache_time else "unknown"}

@app.get("/api/watchlist")
def watchlist(symbols: str = Query(...)):
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()][:20]
    results, missing = [], []
    with _cache_lock:
        cached = dict(_cache)
    for sym in symbol_list:
        if sym in cached:
            results.append(cached[sym])
        else:
            missing.append(sym)
    for sym in missing:
        try:
            raw = fetch_screener(sym)
            if raw:
                entry = build_entry(sym, raw)
                with _cache_lock:
                    _cache[sym] = entry
                results.append(entry)
            time.sleep(2)
        except Exception as e:
            print(f"Error {sym}: {e}")
    results.sort(key=lambda x: x["scoring"]["composite"], reverse=True)
    return {"count": len(results), "stocks": results}
