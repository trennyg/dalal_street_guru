from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from datetime import datetime
import threading
import time
import json
import os
import re
import requests
from bs4 import BeautifulSoup
import yfinance as yf

app = FastAPI(title="stocks.ai API", version="12.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ─── Nifty PE ─────────────────────────────────────────────────────────────────
_nifty_pe_cache = {"pe": None, "fetched_at": None}

def fetch_nifty_pe() -> float:
    """Fetch current Nifty 50 P/E ratio."""
    global _nifty_pe_cache
    if _nifty_pe_cache["pe"] and _nifty_pe_cache["fetched_at"]:
        age_h = (datetime.now() - _nifty_pe_cache["fetched_at"]).total_seconds() / 3600
        if age_h < 4:
            return _nifty_pe_cache["pe"]
    # Try multiple sources
    # Source 1: yfinance ^NSEI
    try:
        ticker = yf.Ticker("^NSEI")
        info = ticker.info
        pe = info.get("trailingPE") or info.get("forwardPE")
        if pe and isinstance(pe, (int, float)) and 8 < pe < 60:
            _nifty_pe_cache = {"pe": round(float(pe), 1), "fetched_at": datetime.now()}
            return round(float(pe), 1)
    except: pass
    # Source 2: Screener.in NIFTY page
    try:
        r = requests.get("https://www.screener.in/company/NIFTY/",
                        timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        m = re.search(r"P/E[^\d]*?(\d{1,2}\.?\d*)", r.text)
        if m:
            pe = float(m.group(1))
            if 8 < pe < 60:
                _nifty_pe_cache = {"pe": pe, "fetched_at": datetime.now()}
                return pe
    except: pass
    # Source 3: NSE India API
    try:
        r = requests.get(
            "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%2050",
            timeout=8, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json",
                                "Referer": "https://www.nseindia.com/"}
        )
        if r.status_code == 200:
            data = r.json()
            pe = data.get("data", [{}])[0].get("pe")
            if pe and 8 < float(pe) < 60:
                _nifty_pe_cache = {"pe": round(float(pe), 1), "fetched_at": datetime.now()}
                return round(float(pe), 1)
    except: pass
    return 22.0  # historical average fallback — market is currently near fair value


def get_market_valuation(pe: float) -> dict:
    """Return market valuation context based on Nifty PE."""
    if pe < 15:
        return {"zone": "Deep Value", "color": "#16a34a", "description": "Market is historically cheap. Aggressive equity allocation justified.", "equity_modifier": 1.15}
    elif pe < 18:
        return {"zone": "Undervalued", "color": "#65a30d", "description": "Market is trading below historical average. Good time to be invested.", "equity_modifier": 1.08}
    elif pe < 22:
        return {"zone": "Fair Value", "color": "#2563eb", "description": "Market at historical average. Maintain base allocation.", "equity_modifier": 1.0}
    elif pe < 26:
        return {"zone": "Slightly Expensive", "color": "#d97706", "description": "Market above historical average. Slightly reduce equity, build cash.", "equity_modifier": 0.90}
    elif pe < 30:
        return {"zone": "Expensive", "color": "#ea580c", "description": "Market significantly overvalued. Reduce equity, increase safety assets.", "equity_modifier": 0.80}
    else:
        return {"zone": "Bubble Territory", "color": "#dc2626", "description": "Extreme overvaluation. Only highest-conviction equity positions justified.", "equity_modifier": 0.65}


# ─── Asset allocation per profile ─────────────────────────────────────────────
PROFILE_ALLOCATION = {
    "rj": {
        "base": {"equity": 90, "gold": 0, "debt": 5, "cash": 5},
        "pe_sensitive": False,
        "logic": "RJ believed in staying fully invested. He once said 'I have never tried to time the market and never will.' Maximum equity always.",
        "gold_instrument": None,
        "debt_instrument": "Liquid Fund",
        "cash_note": "Keep as SIP reserve for averaging down on dips",
    },
    "buffett": {
        "base": {"equity": 70, "gold": 5, "debt": 10, "cash": 15},
        "pe_sensitive": True,
        "logic": "Buffett is famous for holding cash. At Berkshire, cash reaches 25%+ at market peaks. He waits patiently for the fat pitch.",
        "gold_instrument": "Sovereign Gold Bond",
        "debt_instrument": "Short Duration Debt Fund",
        "cash_note": "Buffett's dry powder — deploy when market offers genuine bargains",
    },
    "ben_graham": {
        "base": {"equity": 50, "gold": 0, "debt": 40, "cash": 10},
        "pe_sensitive": True,
        "logic": "Graham's timeless rule: never less than 25% or more than 75% in stocks. Adjust within this band based on market valuation. When stocks are cheap, go to 75%. When expensive, go to 25%.",
        "gold_instrument": None,
        "debt_instrument": "Medium Duration Bond Fund",
        "cash_note": "Margin of safety cash — never fully deploy into stocks",
    },
    "parag_parikh": {
        "base": {"equity": 65, "gold": 10, "debt": 15, "cash": 10},
        "pe_sensitive": True,
        "logic": "PPFAS actively manages allocation. Their fund currently holds ~20% cash+debt. They believe gold is a necessary portfolio hedge against currency debasement.",
        "gold_instrument": "Sovereign Gold Bond (SGB) — 2.5% tax-free interest + gold appreciation",
        "debt_instrument": "Liquid Fund or FD",
        "cash_note": "Opportunity fund — PPFAS deployed cash aggressively in March 2020",
    },
    "marcellus": {
        "base": {"equity": 95, "gold": 0, "debt": 0, "cash": 5},
        "pe_sensitive": False,
        "logic": "Marcellus is always fully invested. Mukherjea believes their 12 stocks outperform any cash position at any valuation. No market timing.",
        "gold_instrument": None,
        "debt_instrument": None,
        "cash_note": "Transaction reserve only",
    },
    "charlie_munger": {
        "base": {"equity": 80, "gold": 0, "debt": 5, "cash": 15},
        "pe_sensitive": True,
        "logic": "Munger concentrated in very few positions. He kept significant cash for the rare exceptional opportunity. 'Opportunity cost is the only real cost.'",
        "gold_instrument": None,
        "debt_instrument": "T-Bills / Liquid Fund",
        "cash_note": "Waiting for the exceptional — Munger would only deploy cash for truly wonderful businesses",
    },
    "vijay_kedia": {
        "base": {"equity": 92, "gold": 0, "debt": 3, "cash": 5},
        "pe_sensitive": False,
        "logic": "Kedia stays almost fully invested. His SMILE framework requires long-term conviction — trying to time the market distracts from finding the right businesses.",
        "gold_instrument": None,
        "debt_instrument": "Liquid Fund",
        "cash_note": "Reserve for adding to existing positions on dips",
    },
    "peter_lynch": {
        "base": {"equity": 85, "gold": 0, "debt": 5, "cash": 10},
        "pe_sensitive": True,
        "logic": "Lynch was fully invested as a fund manager. For personal portfolios he recommended staying mostly invested but keeping some cash for PEG < 1 opportunities.",
        "gold_instrument": None,
        "debt_instrument": "Liquid Fund",
        "cash_note": "PEG opportunity fund — deploy when you find PEG below 0.5",
    },
    "default": {
        "base": {"equity": 70, "gold": 8, "debt": 12, "cash": 10},
        "pe_sensitive": True,
        "logic": "Balanced allocation adjusted for current market valuation.",
        "gold_instrument": "Sovereign Gold Bond",
        "debt_instrument": "Short Duration Debt Fund",
        "cash_note": "Opportunity reserve",
    },
}

def compute_asset_allocation(profile_id: str, total_capital: float, nifty_pe: float) -> dict:
    """Compute final asset allocation based on profile + market PE."""
    alloc_config = PROFILE_ALLOCATION.get(profile_id, PROFILE_ALLOCATION["default"])
    base = dict(alloc_config["base"])
    market = get_market_valuation(nifty_pe)

    if alloc_config["pe_sensitive"]:
        modifier = market["equity_modifier"]
        equity_adj = round(base["equity"] * modifier)
        reduction = base["equity"] - equity_adj
        base["equity"] = equity_adj
        # Add reduction to cash
        base["cash"] = base.get("cash", 0) + reduction

    # Normalize to 100%
    total = sum(base.values())
    for k in base:
        base[k] = round(base[k] / total * 100, 1)

    # Compute rupee amounts
    amounts = {k: round(v / 100 * total_capital) for k, v in base.items()}
    equity_capital = amounts["equity"]

    return {
        "allocation_pct": base,
        "allocation_amt": amounts,
        "equity_capital": equity_capital,
        "nifty_pe": nifty_pe,
        "market_valuation": market,
        "logic": alloc_config["logic"],
        "instruments": {
            "gold": alloc_config.get("gold_instrument") or "Digital Gold / Gold ETF",
            "debt": alloc_config.get("debt_instrument") or "Liquid Fund",
            "cash": alloc_config.get("cash_note") or "Keep in savings account",
        },
        "rebalance_triggers": [
            f"If Nifty PE drops below 16x, shift 10% from debt/cash to equity",
            f"If Nifty PE rises above 28x, reduce equity by 15%, park in debt",
            f"Rebalance annually or when any asset class drifts >5% from target",
        ]
    }


CACHE_FILE = "stock_cache.json"
SECTOR_CACHE_FILE = "sector_cache.json"

_cache = {}
_cache_time = None
_cache_lock = threading.Lock()
_is_refreshing = False
_refresh_progress = {"done": 0, "total": 0}
_sector_averages = {}

# ─── NSE Universe ─────────────────────────────────────────────────────────────
NIFTY_500 = [
    "RELIANCE","TCS","HDFCBANK","BHARTIARTL","ICICIBANK","INFOSYS","HINDUNILVR",
    "ITC","LT","KOTAKBANK","HCLTECH","AXISBANK","BAJFINANCE","MARUTI","SUNPHARMA",
    "TITAN","ULTRACEMCO","ASIANPAINT","NESTLEIND","WIPRO","TECHM","ONGC","POWERGRID",
    "NTPC","TATAMOTORS","BAJAJFINSV","ADANIPORTS","COALINDIA","BRITANNIA","CIPLA",
    "DRREDDY","EICHERMOT","HEROMOTOCO","HINDALCO","INDUSINDBK","JSWSTEEL","DIVISLAB",
    "SBIN","TATASTEEL","APOLLOHOSP","PIDILITIND","TATACONSUM","DMART","HAVELLS",
    "POLYCAB","TORNTPHARM","MARICO","DABUR","HDFCLIFE","BAJAJ-AUTO","ADANIENT",
    "AMBUJACEM","BANKBARODA","BERGEPAINT","BEL","BPCL","CANBK","CHOLAFIN","COLPAL",
    "DLF","GAIL","GODREJCP","GRASIM","HAL","HDFCAMC","ICICIGI","ICICIPRULI",
    "INDUSTOWER","INDIGO","IOC","IRCTC","JINDALSTEL","LICI","LTIM","LUPIN",
    "MCDOWELL-N","NHPC","NMDC","OFSS","OIL","PAGEIND","PERSISTENT","PETRONET",
    "PFC","PIIND","PNB","RECLTD","SAIL","SHRIRAMFIN","SIEMENS","TATAPOWER","TRENT",
    "VBL","ZOMATO","ABCAPITAL","ALKEM","APOLLOTYRE","ASHOKLEY","ASTRAL","AUROPHARMA",
    "BALKRISIND","BANDHANBNK","BIOCON","CAMS","CANFINHOME","COFORGE","CONCOR",
    "CROMPTON","CUMMINSIND","DEEPAKNTR","DIXON","ESCORTS","EXIDEIND","FEDERALBNK",
    "FORTIS","GLENMARK","GODREJIND","GODREJPROP","GRANULES","IDFCFIRSTB","IEX",
    "INDHOTEL","INDIANB","ISEC","JKCEMENT","JUBLFOOD","KAJARIACER","KANSAINER",
    "LICHSGFIN","LTTS","MANAPPURAM","MAXHEALTH","MCX","MFSL","MPHASIS","MRF",
    "MUTHOOTFIN","NATCOPHARM","NAUKRI","OBEROIRLTY","PAGEIND","PFIZER","PHOENIX",
    "PRESTIGE","RADICO","RAMCOCEM","RELAXO","RITES","ROUTE","SBICARD","SBILIFE",
    "SCHAEFFLER","SKFINDIA","SONACOMS","SRF","SUNDARMFIN","SUPREMEIND","SYNGENE",
    "TATACHEM","TATACOMM","TATAELXSI","TVSMOTORS","UBL","UNIONBANK","VGUARD",
    "VOLTAS","WHIRLPOOL","AAVAS","AFFLE","AJANTPHARM","AMBER","ANGELONE","APTUS",
    "ATGL","CDSL","CENTURYPLY","CERA","CGPOWER","CHAMBLFERT","CLEAN","CREDITACC",
    "DALBHARAT","DCMSHRIRAM","DELHIVERY","DEVYANI","DOMS","ELGIEQUIP","EMAMILTD",
    "ENDURANCE","ERIS","FINEORG","FINPIPE","FLUOROCHEM","GAEL","GALAXYSURF","GICRE",
    "GLAND","GNFC","GREENPANEL","GRINDWELL","GUJGASLTD","HBLPOWER","HIKAL",
    "HOMEFIRST","HUDCO","INDIAMART","INDIGOPNTS","INTELLECT","IPCALAB","IRB","IRFC",
    "JBCHEPHARM","JKPAPER","JSWENERGY","JUSTDIAL","KPITTECH","LALPATHLAB","LAURUSLABS",
    "MAPMYINDIA","METROBRAND","NBCC","NLCINDIA","OLECTRA","PGHH","PRINCEPIPE",
    "RAJESHEXPO","ROSSARI","SAFARI","STARHEALTH","TANLA","THYROCARE","TTKPRESTIG",
    "UTIAMC","VINATIORGA","ZEEL","ABBOTINDIA","AIAENG","ATUL","BAJAJELEC","BEML",
    "BHARATFORG","BHEL","BOSCHLTD","CASTROLIND","CEATLTD","CENTRALBK","CENTURYTEX",
    "COROMANDEL","CRISIL","DEEPAKFERT","EDELWEISS","EPIGRAL","EQUITASBNK","ESABINDIA",
    "GABRIEL","GILLETTE","GIPCL","GPIL","GRAPHITE","GSKCONS","GULFOILLUB",
    "HAPPSTMNDS","HINDCOPPER","HPCL","IDBI","IFBIND","IIFL","INDIACEM","INGERRAND",
    "INOXWIND","INSECTICID","ISGEC","ITI","JAMNAAUTO","JKIL","JKLAKSHMI","JKTYRE",
    "JMFINANCIL","KARURVYSYA","KFINTECH","KIMS","KNRCON","KOLTEPATIL","KPRMILL",
    "KRBL","LAOPALA","LATENTVIEW","LAXMIMACH","LUXIND","MAHINDCIE","MASFIN",
    "MATRIMONY","MAYURUNIQ","MINDACORP","MMTC","MOLDTKPAC","MOTHERSON","MRPL",
    "NAVINFLUOR","NETWORK18","NFL","NIITLTD","NILKAMAL","NOCIL","NUCLEUS","OLECTRA",
    "ORIENTELEC","PANACEABIO","PATELENG","PATINTLOG","PENIND","PGHL","PHOENIXLTD",
    "PILANIINVS","PLASTIBLEN","POKARNA","POLYPLEX","POLYMED","POONAWALLA","PRICOLLTD",
    "PVRINOX","QUESS","RAILTEL","RAIN","RALLIS","RAYMOND","RBLBANK","REDINGTON",
    "REPCOHOME","RVNL","SAGARCEM","SAKSOFT","SANDHAR","SANGHIIND","SAREGAMA",
    "SEQUENT","SHAREINDIA","SHILPAMED","SHOPERSTOP","SHYAMMETL","SKIPPER","SOLARA",
    "SPANDANA","SPARC","STYLAM","SUBROS","SUDARSCHEM","SUMICHEM","SUNDARAM",
    "SUPRIYA","SWSOLAR","SYMPHONY","TALBROAUTO","TCIEXP","TCNSBRANDS","TEJASNET",
    "TIINDIA","TIMKEN","TINPLATE","TIPSINDLTD","TITAGARH","TORNTPOWER","TRIDENT",
    "TRIVENI","TTML","UCOBANK","UFLEX","UJJIVAN","UNIPARTS","UNOMINDA","UTTAMSUGAR",
    "VINATIORGA","VIPIND","VISAKAIND","VOLTAMP","VRLLOG","VSTIND","WABCOINDIA",
    "WELCORP","WELSPUNIND","WESTLIFE","WONDERLA","ZENSARTECH","NYKAA","POLICYBZR",
    "PAYTM","DELHIVERY","CAMPUS","DEVYANI","EASEMYTRIP","NAUKRI","IRFC","HUDCO",
]
NIFTY_500 = list(dict.fromkeys(NIFTY_500))  # deduplicate

# ─── Hardcoded sector map for immediate sector avg computation ────────────────
NSE_SECTOR_MAP = {
    # Banking & Finance
    "HDFCBANK":"Banking","ICICIBANK":"Banking","SBIN":"Banking","KOTAKBANK":"Banking",
    "AXISBANK":"Banking","INDUSINDBK":"Banking","BANKBARODA":"Banking","PNB":"Banking",
    "CANBK":"Banking","UNIONBANK":"Banking","IDFCFIRSTB":"Banking","FEDERALBNK":"Banking",
    "BANDHANBNK":"Banking","RBLBANK":"Banking","INDIANB":"Banking","KARURVYSYA":"Banking",
    "BAJFINANCE":"NBFC","BAJAJFINSV":"NBFC","CHOLAFIN":"NBFC","MUTHOOTFIN":"NBFC",
    "MANAPPURAM":"NBFC","SHRIRAMFIN":"NBFC","LICHSGFIN":"NBFC","CANFINHOME":"NBFC",
    "HDFCLIFE":"Insurance","SBILIFE":"Insurance","ICICIGI":"Insurance","ICICIPRULI":"Insurance",
    "LICI":"Insurance","HDFCAMC":"Asset Management","ABCAPITAL":"NBFC",
    # IT
    "TCS":"IT","INFOSYS":"IT","HCLTECH":"IT","WIPRO":"IT","TECHM":"IT",
    "LTIM":"IT","MPHASIS":"IT","COFORGE":"IT","PERSISTENT":"IT","OFSS":"IT",
    "TATAELXSI":"IT","LTTS":"IT","KPITTECH":"IT","HAPPSTMNDS":"IT","ZENSARTECH":"IT",
    # Consumer/FMCG
    "HINDUNILVR":"FMCG","ITC":"FMCG","NESTLEIND":"FMCG","BRITANNIA":"FMCG",
    "DABUR":"FMCG","MARICO":"FMCG","COLPAL":"FMCG","GODREJCP":"FMCG",
    "EMAMILTD":"FMCG","TATACONSUM":"FMCG","RADICO":"FMCG","VBL":"FMCG",
    "MCDOWELL-N":"FMCG","UBL":"FMCG","PGHH":"FMCG","GSKCONS":"FMCG",
    # Pharma
    "SUNPHARMA":"Pharma","DRREDDY":"Pharma","CIPLA":"Pharma","DIVISLAB":"Pharma",
    "TORNTPHARM":"Pharma","AUROPHARMA":"Pharma","LUPIN":"Pharma","ALKEM":"Pharma",
    "BIOCON":"Pharma","GLAND":"Pharma","NATCOPHARM":"Pharma","IPCALAB":"Pharma",
    "ABBOTINDIA":"Pharma","PFIZER":"Pharma","LAURUSLABS":"Pharma","GRANULES":"Pharma",
    # Auto
    "MARUTI":"Auto","TATAMOTORS":"Auto","BAJAJ-AUTO":"Auto","HEROMOTOCO":"Auto",
    "EICHERMOT":"Auto","TVSMOTORS":"Auto","ASHOKLEY":"Auto","APOLLOTYRE":"Auto",
    "CEATLTD":"Auto","BALKRISIND":"Auto","MOTHERSON":"Auto","SONACOMS":"Auto",
    "BOSCHLTD":"Auto","ENDURANCE":"Auto","ESCORTS":"Auto","TIINDIA":"Auto",
    # Energy & Oil
    "RELIANCE":"Energy","ONGC":"Energy","BPCL":"Energy","IOC":"Energy",
    "HINDPETRO":"Energy","OIL":"Energy","GAIL":"Energy","PETRONET":"Energy",
    "ATGL":"Energy","GUJGASLTD":"Energy","IGL":"Energy","MGL":"Energy",
    # Metals & Mining
    "TATASTEEL":"Metals","JSWSTEEL":"Metals","HINDALCO":"Metals","SAIL":"Metals",
    "NMDC":"Metals","COALINDIA":"Metals","VEDL":"Metals","HINDCOPPER":"Metals",
    "NATIONALUM":"Metals","AIAENG":"Metals","GRAPHITE":"Metals","GPIL":"Metals",
    # Cement
    "ULTRACEMCO":"Cement","AMBUJACEM":"Cement","RAMCOCEM":"Cement","DALBHARAT":"Cement",
    "JKCEMENT":"Cement","SHREECEM":"Cement","JKLAKSHMI":"Cement","HEIDELBERG":"Cement",
    # Real Estate
    "DLF":"Real Estate","GODREJPROP":"Real Estate","PRESTIGE":"Real Estate",
    "OBEROIRLTY":"Real Estate","PHOENIXLTD":"Real Estate","BRIGADE":"Real Estate",
    # Capital Goods
    "LT":"Capital Goods","SIEMENS":"Capital Goods","ABB":"Capital Goods",
    "HAL":"Capital Goods","BEL":"Capital Goods","BHEL":"Capital Goods",
    "CGPOWER":"Capital Goods","POLYCAB":"Capital Goods","HAVELLS":"Capital Goods",
    "SCHAEFFLER":"Capital Goods","TIMKEN":"Capital Goods","ELGIEQUIP":"Capital Goods",
    # Paints & Chemicals
    "ASIANPAINT":"Paints","BERGEPAINT":"Paints","KANSAINER":"Paints","INDPAINT":"Paints",
    "PIDILITIND":"Chemicals","DEEPAKNTR":"Chemicals","NAVINFLUOR":"Chemicals",
    "FLUOROCHEM":"Chemicals","SUDARSCHEM":"Chemicals","VINATIORGA":"Chemicals",
    "FINEORG":"Chemicals","NOCIL":"Chemicals","DCMSHRIRAM":"Chemicals",
    # Consumer Durables
    "TITAN":"Consumer Durables","VOLTAS":"Consumer Durables","WHIRLPOOL":"Consumer Durables",
    "CROMPTON":"Consumer Durables","DIXON":"Consumer Durables","AMBER":"Consumer Durables",
    "VGUARD":"Consumer Durables","SYMPHONY":"Consumer Durables","HAVELLS":"Consumer Durables",
    # Telecom
    "BHARTIARTL":"Telecom","INDUSTOWER":"Telecom","TATACOMM":"Telecom",
    # Retail
    "DMART":"Retail","TRENT":"Retail","SHOPERSTOP":"Retail","ZOMATO":"Retail",
    # Specialty
    "NAUKRI":"Internet","NYKAA":"Internet","POLICYBZR":"Insurance",
    "IRCTC":"Travel","INDIGO":"Aviation","SPICEJET":"Aviation",
    "PAGEIND":"Textiles","WELSPUNIND":"Textiles","TRIDENT":"Textiles",
}

def get_sector_for_symbol(symbol: str, scraped_sector: str) -> str:
    """Return best sector for a symbol, using hardcoded map as fallback."""
    if scraped_sector and scraped_sector not in ("Unknown", ""):
        return scraped_sector
    return NSE_SECTOR_MAP.get(symbol, "Unknown")


# ─── yfinance data fetch ───────────────────────────────────────────────────────
def fetch_yfinance(symbol: str) -> dict:
    """Fetch comprehensive data from Yahoo Finance."""
    try:
        ticker = yf.Ticker(f"{symbol}.NS")
        info = ticker.info
        if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
            # Try BSE suffix
            ticker = yf.Ticker(f"{symbol}.BO")
            info = ticker.info

        if not info: return {}

        # Get financials
        try:
            income_stmt = ticker.financials  # annual
            balance_sheet = ticker.balance_sheet
            cash_flow = ticker.cashflow
            quarterly_financials = ticker.quarterly_financials
        except: income_stmt = balance_sheet = cash_flow = quarterly_financials = None

        # Helper to safely get value
        def safe(key, default=None):
            v = info.get(key)
            return v if v is not None else default

        # Price data
        current_price = safe("currentPrice") or safe("regularMarketPrice")
        prev_close = safe("previousClose") or safe("regularMarketPreviousClose")
        price_change_pct = ((current_price - prev_close) / prev_close * 100) if current_price and prev_close and prev_close > 0 else None

        # Ratios
        pe = safe("trailingPE") or safe("forwardPE")
        pb = safe("priceToBook")
        roe = safe("returnOnEquity")
        roa = safe("returnOnAssets")
        de = safe("debtToEquity")
        if de: de = de / 100  # yfinance gives it as percentage
        opm = safe("operatingMargins")
        npm = safe("profitMargins")
        rev_growth = safe("revenueGrowth")
        earn_growth = safe("earningsGrowth")
        current_ratio = safe("currentRatio")
        quick_ratio = safe("quickRatio")
        dy = safe("dividendYield")
        eps = safe("trailingEps")
        beta = safe("beta")

        # Market data
        market_cap = safe("marketCap")
        w52_high = safe("fiftyTwoWeekHigh")
        w52_low = safe("fiftyTwoWeekLow")
        avg_volume = safe("averageVolume")
        ev_ebitda = safe("enterpriseToEbitda")
        ev_revenue = safe("enterpriseToRevenue")
        peg = safe("pegRatio")
        fcf = safe("freeCashflow")
        revenue = safe("totalRevenue")
        ebitda = safe("ebitda")

        # Promoter / institutional
        held_pct_insiders = safe("heldPercentInsiders")
        held_pct_institutions = safe("heldPercentInstitutions")

        # Company info
        company_name = safe("longName") or safe("shortName") or symbol
        sector = safe("sector") or safe("industry") or "Unknown"
        industry = safe("industry") or sector
        description = safe("longBusinessSummary", "")[:400] if safe("longBusinessSummary") else ""
        website = safe("website", "")
        employees = safe("fullTimeEmployees")

        # Analyst data
        rec = safe("recommendationKey", "")
        target_price = safe("targetMeanPrice")
        num_analysts = safe("numberOfAnalystOpinions")

        # Quarterly revenue/profit arrays
        quarterly_revenue = []
        quarterly_profit = []
        if quarterly_financials is not None:
            try:
                cols = quarterly_financials.columns[:8]
                if "Total Revenue" in quarterly_financials.index:
                    quarterly_revenue = [float(quarterly_financials.loc["Total Revenue", c]) / 1e7
                                        for c in cols if quarterly_financials.loc["Total Revenue", c] is not None]
                if "Net Income" in quarterly_financials.index:
                    quarterly_profit = [float(quarterly_financials.loc["Net Income", c]) / 1e7
                                       for c in cols if quarterly_financials.loc["Net Income", c] is not None]
            except: pass

        # Annual revenue/profit (5 years)
        annual_revenue = []
        annual_profit = []
        if income_stmt is not None:
            try:
                cols = income_stmt.columns[:5]
                if "Total Revenue" in income_stmt.index:
                    annual_revenue = [float(income_stmt.loc["Total Revenue", c]) / 1e7 for c in cols]
                if "Net Income" in income_stmt.index:
                    annual_profit = [float(income_stmt.loc["Net Income", c]) / 1e7 for c in cols]
            except: pass

        # ROCE computation: EBIT / Capital Employed
        roce = None
        if income_stmt is not None and balance_sheet is not None:
            try:
                ebit = income_stmt.loc["EBIT", income_stmt.columns[0]] if "EBIT" in income_stmt.index else None
                total_assets = balance_sheet.loc["Total Assets", balance_sheet.columns[0]] if "Total Assets" in balance_sheet.index else None
                current_liab = balance_sheet.loc["Current Liabilities", balance_sheet.columns[0]] if "Current Liabilities" in balance_sheet.index else None
                if ebit and total_assets and current_liab:
                    capital_employed = total_assets - current_liab
                    roce = float(ebit) / float(capital_employed) if capital_employed > 0 else None
            except: pass

        # Interest coverage
        interest_coverage = None
        if income_stmt is not None:
            try:
                ebit = income_stmt.loc["EBIT", income_stmt.columns[0]] if "EBIT" in income_stmt.index else None
                interest = income_stmt.loc["Interest Expense", income_stmt.columns[0]] if "Interest Expense" in income_stmt.index else None
                if ebit and interest and float(interest) != 0:
                    interest_coverage = abs(float(ebit) / float(interest))
            except: pass

        # Book value per share
        book_value = None
        if pb and current_price and pb > 0:
            book_value = current_price / pb

        sector = get_sector_for_symbol(symbol, sector)
        return {
            "company_name": company_name,
            "sector": sector,
            "industry": industry,
            "description": description,
            "website": website,
            "employees": employees,
            "current_price": current_price,
            "price_change_pct": price_change_pct,
            "market_cap": market_cap,
            "52w_high": w52_high,
            "52w_low": w52_low,
            "avg_volume": avg_volume,
            "pe_ratio": pe,
            "pb_ratio": pb,
            "ev_ebitda": ev_ebitda,
            "ev_revenue": ev_revenue,
            "peg_ratio": peg,
            "book_value": book_value,
            "roe": roe,
            "roa": roa,
            "roce": roce,
            "debt_to_equity": de,
            "operating_margins": opm,
            "net_margins": npm,
            "revenue_growth": rev_growth,
            "earnings_growth": earn_growth,
            "current_ratio": current_ratio,
            "quick_ratio": quick_ratio,
            "interest_coverage": interest_coverage,
            "dividend_yield": dy,
            "eps": eps,
            "beta": beta,
            "fcf": fcf,
            "revenue": revenue,
            "ebitda": ebitda,
            "promoter_holding": held_pct_insiders,
            "institutional_holding": held_pct_institutions,
            "analyst_recommendation": rec,
            "target_price": target_price,
            "num_analysts": num_analysts,
            "quarterly_revenue": quarterly_revenue[:8],
            "quarterly_profit": quarterly_profit[:8],
            "annual_revenue": annual_revenue[:5],
            "annual_profit": annual_profit[:5],
            "pros": [],
            "cons": [],
        }
    except Exception as e:
        print(f"  yfinance error {symbol}: {e}")
        return {}


def fetch_screener_fallback(symbol: str) -> dict:
    """Fallback to Screener.in scraping for stocks yfinance doesn't cover."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.screener.in/",
    })
    try:
        session.get("https://www.screener.in/", timeout=8)
        time.sleep(0.3)
    except: pass

    for suffix in ["/consolidated/", "/"]:
        try:
            url = f"https://www.screener.in/company/{symbol}{suffix}"
            r = session.get(url, timeout=12)
            if r.status_code != 200: continue
            soup = BeautifulSoup(r.text, "html.parser")
            if not soup.select_one("#top-ratios"): continue

            all_kv = {}
            for li in soup.select("li"):
                ne = li.select_one(".name"); ve = li.select_one(".number,.value")
                if ne and ve:
                    k = ne.get_text(strip=True); v = ve.get_text(strip=True)
                    if k and v: all_kv[k] = v

            def parse_num(text):
                if not text: return None
                text = str(text).strip().replace(",","").replace("₹","").replace("%","").replace("Cr.","").replace("Cr","").strip()
                if text in ("","-","—","N/A"): return None
                try: return float(text)
                except: return None

            def get(*keys):
                for k in keys:
                    if k in all_kv: return parse_num(all_kv[k])
                    for ak in all_kv:
                        if k.lower() in ak.lower(): return parse_num(all_kv[ak])
                return None

            current_price = get("Current Price")
            mc_cr = get("Market Cap")
            pe = get("Stock P/E","P/E")
            book_value = get("Book Value")
            pb = round(current_price/book_value,2) if current_price and book_value and book_value > 0 else None
            roe_raw = get("ROE"); roe = (roe_raw/100) if roe_raw else None
            roce_raw = get("ROCE"); roce = (roce_raw/100) if roce_raw else None
            de = get("Debt to equity","D/E")
            opm_raw = get("OPM"); opm = (opm_raw/100) if opm_raw else None
            dy_raw = get("Dividend Yield"); dy = (dy_raw/100) if dy_raw else None
            ph_raw = get("Promoter holding"); ph = (ph_raw/100) if ph_raw else None
            eps = get("EPS")

            hl = all_kv.get("High / Low","")
            w52h = w52l = None
            if hl and "/" in hl:
                parts = hl.replace("₹","").replace(",","").split("/")
                w52h = parse_num(parts[0]); w52l = parse_num(parts[1]) if len(parts)>1 else None

            company_name = symbol
            el = soup.select_one("h1")
            if el: company_name = el.get_text(strip=True)

            sector = "Unknown"
            for a in soup.select("a[href*='/screen/']"):
                t = a.get_text(strip=True)
                if t and 2 < len(t) < 40 and t not in ("Screener","Login","Sign Up","Home","Screen","Advanced"):
                    sector = t; break

            pros = [li.get_text(strip=True) for li in soup.select(".pros li")][:4]
            cons = [li.get_text(strip=True) for li in soup.select(".cons li")][:4]

            sector = get_sector_for_symbol(symbol, sector)
            return {
                "company_name": company_name, "sector": sector, "industry": sector,
                "description": "", "website": "", "employees": None,
                "current_price": current_price, "price_change_pct": None,
                "market_cap": mc_cr * 1e7 if mc_cr else None,
                "52w_high": w52h, "52w_low": w52l, "avg_volume": None,
                "pe_ratio": pe, "pb_ratio": pb, "ev_ebitda": None, "ev_revenue": None,
                "peg_ratio": None, "book_value": book_value,
                "roe": roe, "roa": None, "roce": roce, "debt_to_equity": de,
                "operating_margins": opm, "net_margins": None,
                "revenue_growth": None, "earnings_growth": None,
                "current_ratio": None, "quick_ratio": None, "interest_coverage": None,
                "dividend_yield": dy, "eps": eps, "beta": None, "fcf": None,
                "revenue": None, "ebitda": None,
                "promoter_holding": ph, "institutional_holding": None,
                "analyst_recommendation": None, "target_price": None, "num_analysts": None,
                "quarterly_revenue": [], "quarterly_profit": [],
                "annual_revenue": [], "annual_profit": [],
                "pros": pros, "cons": cons,
            }
        except Exception as e:
            print(f"  Screener fallback error {symbol}: {e}")
            continue
    return {}


def fetch_stock_data(symbol: str) -> dict:
    """Merge yfinance + screener data for completeness."""
    yf_data = fetch_yfinance(symbol)
    sc_data = fetch_screener_fallback(symbol)
    
    if not yf_data and not sc_data:
        return {}
    
    if not yf_data:
        sc_data["data_source"] = "screener"
        return sc_data
    
    if not sc_data:
        yf_data["data_source"] = "yfinance"
        return yf_data
    
    # Merge: yfinance is primary, screener fills gaps
    merged = dict(yf_data)
    merged["data_source"] = "merged"
    # Apply hardcoded sector as fallback
    merged["sector"] = get_sector_for_symbol(symbol, merged.get("sector", "Unknown"))
    
    # Fill ALL missing fields from screener
    for field in sc_data:
        yf_val = merged.get(field)
        sc_val = sc_data.get(field)
        if (yf_val is None or yf_val == [] or yf_val == "") and sc_val not in (None, [], ""):
            merged[field] = sc_val
    
    # Special: compute ebitda if missing
    if not merged.get("ebitda") and merged.get("revenue") and merged.get("operating_margins"):
        merged["ebitda"] = merged["revenue"] * merged["operating_margins"]
    
    # Special: compute ev_ebitda if missing  
    if not merged.get("ev_ebitda") and merged.get("market_cap") and merged.get("ebitda") and merged["ebitda"] > 0:
        merged["ev_ebitda"] = merged["market_cap"] / merged["ebitda"]
    
    # Also override sector if yfinance gave generic sector
    if sc_data.get("sector") and sc_data["sector"] != "Unknown":
        merged["sector"] = sc_data["sector"]
    
    # Use screener OPM if yfinance OPM is missing
    if not merged.get("operating_margins") and sc_data.get("operating_margins"):
        merged["operating_margins"] = sc_data["operating_margins"]
    
    return merged


# ─── Sector averages ──────────────────────────────────────────────────────────
def compute_sector_averages(cache: dict) -> dict:
    sector_data = {}
    for entry in cache.values():
        sector = entry.get("sector", "Unknown")
        if sector in ("Unknown", None): continue
        if sector not in sector_data:
            sector_data[sector] = {"pe": [], "pb": [], "roe": [], "roce": [], "opm": [], "de": [], "ev_ebitda": [], "rev_growth": [], "npm": []}
        for key, field in [("pe","pe_ratio"),("pb","pb_ratio"),("roe","roe"),("roce","roce"),
                           ("opm","operating_margins"),("de","debt_to_equity"),
                           ("ev_ebitda","ev_ebitda"),("rev_growth","revenue_growth"),("npm","net_margins")]:
            v = entry.get(field)
            if v is not None and not (isinstance(v, float) and (v != v)):  # not NaN
                sector_data[sector][key].append(v)

    averages = {}
    for sector, data in sector_data.items():
        averages[sector] = {}
        for metric, values in data.items():
            if len(values) >= 3:
                sorted_vals = sorted(values)
                n = len(sorted_vals)
                averages[sector][metric] = sorted_vals[n//2]  # median
    return averages


def get_sector_comparison(stock: dict, sector_avgs: dict) -> dict:
    symbol = stock.get("symbol", "")
    sector = stock.get("sector", "Unknown")
    # Use hardcoded map if sector is Unknown
    if sector == "Unknown" and symbol in NSE_SECTOR_MAP:
        sector = NSE_SECTOR_MAP[symbol]
    avgs = sector_avgs.get(sector, {})
    if not avgs: return {}
    result = {}
    mapping = {
        "pe_ratio": ("pe", True),
        "pb_ratio": ("pb", True),
        "roe": ("roe", False),
        "roce": ("roce", False),
        "operating_margins": ("opm", False),
        "debt_to_equity": ("de", True),
        "ev_ebitda": ("ev_ebitda", True),
        "revenue_growth": ("rev_growth", False),
        "net_margins": ("npm", False),
    }
    for stock_key, (avg_key, lower_better) in mapping.items():
        sv = stock.get(stock_key)
        av = avgs.get(avg_key)
        if sv is None or av is None or av == 0: continue
        diff_pct = ((sv - av) / abs(av)) * 100
        if lower_better:
            status = "better" if sv < av * 0.9 else ("worse" if sv > av * 1.1 else "inline")
        else:
            status = "better" if sv > av * 1.05 else ("worse" if sv < av * 0.9 else "inline")
        result[stock_key] = {
            "value": sv, "sector_avg": av,
            "diff_pct": round(diff_pct, 1), "status": status,
            "lower_better": lower_better,
        }
    return result


# ─── Sector-relative scoring (5 dimensions) ──────────────────────────────────
def score_stock(d: dict, sector_avgs: dict) -> dict:
    sector = d.get("sector", "Unknown")
    symbol = d.get("symbol", "")
    if sector == "Unknown" and symbol in NSE_SECTOR_MAP:
        sector = NSE_SECTOR_MAP[symbol]
    avgs = sector_avgs.get(sector, {})

    def pct(v): return v * 100 if v is not None else None
    def vs_sector(val, avg_key, higher_better=True, weight=1.0):
        """Score 0-100 based on how stock compares to sector median."""
        if val is None: return 0
        avg = avgs.get(avg_key)
        if avg is None or avg == 0:
            # No sector data - use absolute thresholds
            if avg_key == "roe":
                if val >= 0.25: return 85
                if val >= 0.18: return 70
                if val >= 0.12: return 50
                return 30
            elif avg_key == "roce":
                if val >= 0.25: return 85
                if val >= 0.18: return 70
                if val >= 0.12: return 50
                return 30
            elif avg_key == "opm":
                if val >= 0.25: return 85
                if val >= 0.15: return 65
                if val >= 0.08: return 45
                return 25
            elif avg_key == "de":
                if val < 0.1: return 90
                if val < 0.3: return 75
                if val < 0.7: return 50
                return 25
            elif avg_key == "pe":
                if val < 12: return 85
                if val < 20: return 65
                if val < 30: return 45
                return 25
            elif avg_key == "npm":
                if val >= 0.15: return 80
                if val >= 0.08: return 60
                return 35
            return 50  # true neutral for unknown metrics
        ratio = val / avg
        if higher_better:
            if ratio >= 2.0: return 100 * weight
            if ratio >= 1.5: return 85 * weight
            if ratio >= 1.2: return 70 * weight
            if ratio >= 1.0: return 55 * weight
            if ratio >= 0.8: return 35 * weight
            return 15 * weight
        else:  # lower is better
            if ratio <= 0.5: return 100 * weight
            if ratio <= 0.7: return 85 * weight
            if ratio <= 0.9: return 70 * weight
            if ratio <= 1.1: return 55 * weight
            if ratio <= 1.3: return 35 * weight
            return 15 * weight

    roe = d.get("roe"); roce = d.get("roce"); opm = d.get("operating_margins")
    npm = d.get("net_margins"); de = d.get("debt_to_equity")
    pe = d.get("pe_ratio"); pb = d.get("pb_ratio")
    rev_growth = d.get("revenue_growth"); earn_growth = d.get("earnings_growth")
    current_ratio = d.get("current_ratio"); ic = d.get("interest_coverage")
    fcf = d.get("fcf"); ev_ebitda = d.get("ev_ebitda")
    peg = d.get("peg_ratio"); price = d.get("current_price")
    high = d.get("52w_high"); dy = d.get("dividend_yield")
    mc = (d.get("market_cap") or 0) / 1e7

    reasons = []

    # ── 1. QUALITY (30%) ──────────────────────────────────────────────────────
    q_score = 0
    # ROE vs sector
    roe_s = vs_sector(roe, "roe", True)
    q_score += roe_s * 0.35
    if roe and pct(roe) >= 20: reasons.append(f"Strong ROE {pct(roe):.1f}%")
    elif roe and pct(roe) >= 15: reasons.append(f"Good ROE {pct(roe):.1f}%")

    # ROCE vs sector
    roce_s = vs_sector(roce, "roce", True)
    q_score += roce_s * 0.35
    if roce and pct(roce) >= 20: reasons.append(f"High ROCE {pct(roce):.1f}%")

    # OPM vs sector
    opm_s = vs_sector(opm, "opm", True)
    q_score += opm_s * 0.30
    if opm and pct(opm) >= 20: reasons.append(f"Strong margins {pct(opm):.1f}%")
    q_total = min(q_score, 100)

    # ── 2. GROWTH (25%) ───────────────────────────────────────────────────────
    g_score = 0
    g_has_data = False
    if rev_growth is not None:
        g_has_data = True
        rg_pct = pct(rev_growth)
        if rg_pct >= 25: g_score += 40; reasons.append(f"Revenue growing {rg_pct:.1f}%")
        elif rg_pct >= 15: g_score += 30; reasons.append(f"Revenue growing {rg_pct:.1f}%")
        elif rg_pct >= 8: g_score += 22
        elif rg_pct >= 0: g_score += 14
        else: g_score += 5

    if earn_growth is not None:
        g_has_data = True
        eg_pct = pct(earn_growth)
        if eg_pct >= 25: g_score += 40; reasons.append(f"Earnings growing {eg_pct:.1f}%")
        elif eg_pct >= 15: g_score += 30; reasons.append(f"Earnings growing {eg_pct:.1f}%")
        elif eg_pct >= 8: g_score += 22
        elif eg_pct >= 0: g_score += 14
        else: g_score += 5

    # If no growth data available, infer from ROE/ROCE quality
    # A company with high ROE likely has decent growth
    if not g_has_data:
        if roe and pct(roe) >= 25: g_score = 55; reasons.append("High ROE implies growth capability")
        elif roe and pct(roe) >= 18: g_score = 48
        elif roe and pct(roe) >= 12: g_score = 40
        else: g_score = 35  # neutral-ish default

    g_total = min(g_score, 100)

    # ── 3. SAFETY (20%) ───────────────────────────────────────────────────────
    s_score = 0
    s_has_data = False

    if de is not None:
        s_has_data = True
        de_s = vs_sector(de, "de", False)
        s_score += de_s * 0.40
        if de < 0.1: reasons.append("Near debt-free")
        elif de < 0.3: reasons.append("Low debt")

    if current_ratio is not None:
        s_has_data = True
        if current_ratio >= 2: s_score += 30
        elif current_ratio >= 1.5: s_score += 22
        elif current_ratio >= 1: s_score += 14
        else: s_score += 5

    if ic is not None:
        s_has_data = True
        if ic >= 5: s_score += 30
        elif ic >= 3: s_score += 22
        elif ic >= 1.5: s_score += 12
        else: s_score += 5
    elif de is not None and de < 0.1:
        s_score += 25

    # If no safety data, use pros/cons text as proxy
    if not s_has_data:
        pros_text = " ".join(d.get("pros", [])).lower()
        cons_text = " ".join(d.get("cons", [])).lower()
        if "debt free" in pros_text or "zero debt" in pros_text:
            s_score = 70; reasons.append("Debt-free (from fundamentals)")
        elif "debt" in cons_text or "leverage" in cons_text:
            s_score = 30
        else:
            s_score = 50  # neutral when no data

    s_total = min(s_score, 100)

    # ── 4. VALUE (15%) ────────────────────────────────────────────────────────
    v_score = 0
    pe_s = vs_sector(pe, "pe", False) if pe else 50
    v_score += pe_s * 0.40

    pb_s = vs_sector(pb, "pb", False) if pb else 50
    v_score += pb_s * 0.30

    if price and high and high > 0:
        pct_off = ((high - price) / high) * 100
        if pct_off >= 30: v_score += 30; reasons.append(f"{pct_off:.0f}% below 52w high")
        elif pct_off >= 15: v_score += 20
        elif pct_off >= 5: v_score += 10
        else: v_score += 5

    if pe and pe > 0 and pe < 15: reasons.append(f"Attractive P/E {pe:.1f}x")
    v_total = min(v_score, 100)

    # ── 5. MOMENTUM (10%) ─────────────────────────────────────────────────────
    m_score = 50  # neutral default
    if price and high and high > 0:
        pct_from_high = ((high - price) / high) * 100
        low = d.get("52w_low")
        if low and high > low:
            price_range_pct = ((price - low) / (high - low) * 100)
            if price_range_pct >= 80: m_score = 85
            elif price_range_pct >= 60: m_score = 70
            elif price_range_pct >= 40: m_score = 55
            elif price_range_pct >= 20: m_score = 40
            else: m_score = 28
        else:
            # Just use distance from 52w high
            if pct_from_high <= 5: m_score = 75
            elif pct_from_high <= 15: m_score = 60
            elif pct_from_high <= 30: m_score = 45
            else: m_score = 32
    m_total = min(m_score, 100)

    # ── Composite ─────────────────────────────────────────────────────────────
    composite = round(
        q_total * 0.30 +
        g_total * 0.25 +
        s_total * 0.20 +
        v_total * 0.15 +
        m_total * 0.10, 1
    )

    return {
        "composite": composite,
        "scores": {
            "quality": round(q_total),
            "growth": round(g_total),
            "safety": round(s_total),
            "value": round(v_total),
            "momentum": round(m_total),
        },
        "sub_scores": [
            {"label": "Quality", "score": round(q_total)},
            {"label": "Growth", "score": round(g_total)},
            {"label": "Safety", "score": round(s_total)},
            {"label": "Value", "score": round(v_total)},
            {"label": "Momentum", "score": round(m_total)},
        ],
        "top_reasons": list(dict.fromkeys(reasons))[:5],
        "sector_relative": True,
    }


def conviction_tier(score):
    if score >= 72: return "Strong Buy"
    if score >= 58: return "Buy"
    if score >= 42: return "Watch"
    if score >= 28: return "Neutral"
    return "Avoid"


# ─── Investor profiles ────────────────────────────────────────────────────────
INVESTOR_PROFILES = {
    "rj": {
        "name": "Rakesh Jhunjhunwala", "avatar": "RJ", "category": "Indian Legend",
        "focus": "India Growth Compounder", "color": "#f59e0b",
        "portfolio_size": 18, "sizing_style": "conviction_weighted",
        "bio": "Known as India's Warren Buffett and the 'Big Bull', Rakesh Jhunjhunwala (1960-2022) turned Rs 5,000 into over Rs 40,000 crore through a legendary 35-year career. He started trading in 1985 with borrowed money.",
        "philosophy": "Jhunjhunwala believed passionately in India's economic growth story. His mantra was 'Buy right, sit tight' — he held Titan for over 20 years and never sold.",
        "what_he_looked_for": "High ROE businesses (>20%), strong promoter conviction (>50% holding), large addressable market, India-specific growth story, reasonable valuation.",
        "what_he_avoided": "Commodity businesses, high debt companies, businesses without pricing power, promoters with poor track record.",
        "famous_investments": ["Titan Company", "Star Health Insurance", "Crisil", "Lupin", "Aptech"],
        "signature_quote": "I am bullish on India. I think we are going to have a great bull market.",
        "rebalance_style": "Held for decades. Only exited when fundamental thesis broke.",
        "description": "High ROE compounders, India growth story, high promoter conviction",
    },
    "buffett": {
        "name": "Warren Buffett", "avatar": "WB", "category": "Global Legend",
        "focus": "Quality at Fair Price", "color": "#3b82f6",
        "portfolio_size": 10, "sizing_style": "very_concentrated",
        "bio": "Warren Buffett, the Oracle of Omaha, is widely considered the greatest investor of all time. His Berkshire Hathaway has compounded at ~20% CAGR for 58 years.",
        "philosophy": "Buy wonderful businesses at fair prices and hold forever. A wonderful business has durable competitive advantages, consistent high ROE without leverage, strong management.",
        "what_he_looked_for": "ROE > 20% consistently, low debt, pricing power, brand moat, simple understandable business, honest management.",
        "what_he_avoided": "Businesses he cannot understand, highly leveraged companies, commodity businesses without pricing power.",
        "famous_investments": ["Coca-Cola", "American Express", "Apple", "GEICO", "Bank of America"],
        "signature_quote": "It is far better to buy a wonderful company at a fair price than a fair company at a wonderful price.",
        "rebalance_style": "Favourite holding period is forever.",
        "description": "Durable moat, consistent high ROE, low debt, buy below intrinsic value",
    },
    "marcellus": {
        "name": "Marcellus (Saurabh Mukherjea)", "avatar": "MC", "category": "Indian Fund",
        "focus": "Forensic Quality Only", "color": "#06b6d4",
        "portfolio_size": 12, "sizing_style": "equal_weight",
        "bio": "Saurabh Mukherjea founded Marcellus Investment Managers in 2018. His Consistent Compounders Portfolio uses forensic accounting screens to identify companies with clean books and consistently high ROCE.",
        "philosophy": "The best investments are businesses with virtually zero debt, ROCE consistently above 25%, and clean accounting. Most Indian businesses fail the forensic screen.",
        "what_he_looked_for": "Zero debt, ROCE > 25% for 10 consecutive years, clean accounting, consistent margins.",
        "what_he_avoided": "Any leverage, aggressive accounting, related-party transactions, promoter pledge.",
        "famous_investments": ["Asian Paints", "HDFC Bank", "Pidilite Industries", "Nestle India"],
        "signature_quote": "Great businesses destroy the competition slowly and surely.",
        "rebalance_style": "Annual April rebalance. Replaces bottom 2-3 performers.",
        "description": "Zero debt, very high ROCE, clean accounts, forensic quality filter",
    },
    "vijay_kedia": {
        "name": "Vijay Kedia", "avatar": "VK", "category": "Indian Legend",
        "focus": "SMILE — Niche Leaders", "color": "#8b5cf6",
        "portfolio_size": 6, "sizing_style": "very_concentrated",
        "bio": "Vijay Kedia started investing with Rs 25,000 and built a multi-hundred crore portfolio through highly concentrated bets on niche market leaders. Known for his SMILE framework.",
        "philosophy": "SMILE: Small in size, Medium in experience, Large in aspiration, Extra-large in market potential. Niche monopolies in industries most investors ignore.",
        "what_he_looked_for": "Small/mid cap niche leadership, management with 10+ years execution, large untapped addressable market, high promoter stake (>50%).",
        "what_he_avoided": "Large cap stocks, commodity businesses, companies with poor management pedigree.",
        "famous_investments": ["Atul Auto", "Aegis Logistics", "Cera Sanitaryware", "Tejas Networks"],
        "signature_quote": "If you pick the right business and right management, you do not need to time the market.",
        "rebalance_style": "Ultra long term. Holds 5-10 years.",
        "description": "SMILE framework — niche monopolies, large opportunity, high promoter stake",
    },
    "parag_parikh": {
        "name": "Parag Parikh Flexi Cap", "avatar": "PP", "category": "Indian Fund",
        "focus": "Owner-Operator Quality", "color": "#10b981",
        "portfolio_size": 22, "sizing_style": "equal_weight",
        "bio": "PPFAS manages one of India's most respected mutual funds. Known for low churn, behavioral investing approach, and willingness to hold cash when markets are overvalued.",
        "philosophy": "Invest in businesses run by owner-operators with skin in the game. Focus on pricing power, durable competitive advantages, and behavioral discipline.",
        "what_he_looked_for": "Owner-operators (>30% promoter), pricing power (OPM > 15%), low debt, consistent ROE.",
        "what_he_avoided": "Highly valued momentum stocks, businesses without pricing power, high leverage.",
        "famous_investments": ["HDFC Bank", "Bajaj Holdings", "ITC", "Coal India"],
        "signature_quote": "We buy businesses, not stocks.",
        "rebalance_style": "Semi-annual formal review. Low turnover.",
        "description": "Pricing power, owner-operator promoters, behavioral discipline",
    },
    "porinju": {
        "name": "Porinju Veliyath", "avatar": "PV", "category": "Indian Legend",
        "focus": "Smallcap Contrarian", "color": "#ec4899",
        "portfolio_size": 25, "sizing_style": "equal_weight",
        "bio": "Porinju Veliyath, founder of Equity Intelligence India, is known as the Smallcap King. Built a fund delivering exceptional returns by investing in deeply undervalued small caps.",
        "philosophy": "Find small companies that are fundamentally sound but completely ignored by institutional investors. The lack of coverage creates mispricing opportunities.",
        "what_he_looked_for": "Market cap under Rs 2,000 Cr, beaten-down prices, strong fundamentals despite temporary headwinds, honest management.",
        "what_he_avoided": "Large caps (too efficient), businesses with permanent structural problems.",
        "famous_investments": ["Geojit Financial", "Wonderla Holidays", "V-Guard Industries"],
        "signature_quote": "Markets are not efficient in the small cap space. That is where the opportunity lies.",
        "rebalance_style": "Event-driven. Exits when the turnaround thesis plays out.",
        "description": "Deep smallcap, turnaround stories, beaten-down stocks",
    },
    "ben_graham": {
        "name": "Benjamin Graham", "avatar": "BG", "category": "Global Legend",
        "focus": "Deep Value / Margin of Safety", "color": "#64748b",
        "portfolio_size": 25, "sizing_style": "equal_weight",
        "bio": "Benjamin Graham, Father of Value Investing, wrote The Intelligent Investor. Warren Buffett called him the second most influential person in his life.",
        "philosophy": "Always buy with a significant margin of safety. Never overpay. Treat stocks as ownership in real businesses. Be the rational investor when others are emotional.",
        "what_he_looked_for": "P/B below 1.5, P/E below 15, low debt, positive earnings for 10 years, dividend payments.",
        "what_he_avoided": "Speculative stocks, growth stocks at premium valuations, poor balance sheets.",
        "famous_investments": ["GEICO (bought at extreme discount)", "Northern Pipeline"],
        "signature_quote": "The margin of safety is always dependent on the price paid.",
        "rebalance_style": "Annual rebalance. Systematic rules-based approach.",
        "description": "Buy below book value, wide margin of safety, absolute value",
    },
    "peter_lynch": {
        "name": "Peter Lynch", "avatar": "PL", "category": "Global Legend",
        "focus": "GARP — Growth at Reasonable Price", "color": "#06b6d4",
        "portfolio_size": 30, "sizing_style": "equal_weight",
        "bio": "Peter Lynch managed Fidelity's Magellan Fund achieving 29.2% annual returns — the best 13-year run of any mutual fund in history.",
        "philosophy": "Invest in companies you understand from daily life. Use PEG ratio to find growth at reasonable price. A PEG below 1 means you are getting growth cheap.",
        "what_he_looked_for": "PEG ratio < 1, companies growing earnings > 20%, businesses he could explain in 2 minutes.",
        "what_he_avoided": "Businesses he did not understand, hot industries with heavy competition.",
        "famous_investments": ["Dunkin Donuts", "Taco Bell", "Subaru"],
        "signature_quote": "Invest in what you know.",
        "rebalance_style": "Quarterly review. High turnover acceptable.",
        "description": "PEG ratio focus, invest in what you know, hidden gems in boring sectors",
    },
    "charlie_munger": {
        "name": "Charlie Munger", "avatar": "CM", "category": "Global Legend",
        "focus": "Wonderful Company at Fair Price", "color": "#0ea5e9",
        "portfolio_size": 5, "sizing_style": "very_concentrated",
        "bio": "Charlie Munger, Buffett's partner at Berkshire Hathaway for 60 years, transformed Buffett from a Graham-style deep value investor to a quality compounder investor.",
        "philosophy": "A few wonderful businesses held forever beats a hundred mediocre ones traded frequently. Look for businesses with durable competitive moats and pricing power.",
        "what_he_looked_for": "ROCE > 25%, pricing power, durable moat (brand, network effect, switching costs), honest management.",
        "what_he_avoided": "Complex businesses, commodity businesses, management that speaks in jargon.",
        "famous_investments": ["BYD", "Berkshire investments alongside Buffett"],
        "signature_quote": "I have nothing to add.",
        "rebalance_style": "Ultra-long term. Very rare portfolio changes.",
        "description": "Ultra-concentrated wonderful companies, ROCE focus, hold forever",
    },
    "ashish_kacholia": {
        "name": "Ashish Kacholia", "avatar": "AK", "category": "Indian Legend",
        "focus": "Emerging Compounders", "color": "#84cc16",
        "portfolio_size": 20, "sizing_style": "equal_weight",
        "bio": "Ashish Kacholia, often called the Big Whale of smallcap investing, is known for identifying emerging compounders before they become mainstream.",
        "philosophy": "Look for scalable business models in smallcap space with high ROE, strong management, and a large runway for growth.",
        "what_he_looked_for": "Smallcap companies (Rs 500-5000 Cr), high ROE (>20%), scalable business model, good management.",
        "what_he_avoided": "Loss-making companies, high debt, promoters with integrity concerns.",
        "famous_investments": ["Wonderla Holidays", "Repco Home Finance", "Safari Industries"],
        "signature_quote": "I look for businesses that can become 10x in 7-10 years.",
        "rebalance_style": "Annual review. Replaces underperformers.",
        "description": "Smallcap quality growth, scalable businesses, emerging sector leaders",
    },
    "motilal_qglp": {
        "name": "Motilal Oswal QGLP", "avatar": "MO", "category": "Indian Fund",
        "focus": "Quality + Growth + Longevity + Price", "color": "#f97316",
        "portfolio_size": 20, "sizing_style": "conviction_weighted",
        "bio": "Motilal Oswal Asset Management applies the QGLP framework pioneered by Raamdeo Agrawal. Refined over 30 years guiding one of India's largest equity PMS businesses.",
        "philosophy": "All four QGLP pillars must be present: Quality business, Growth in earnings > 20%, Longevity of growth runway 10+ years, Price reasonable (PEG < 1.5).",
        "what_he_looked_for": "ROE > 20%, earnings growth > 20% consistently, large TAM, PEG under 1.5.",
        "what_he_avoided": "Low-quality businesses even at cheap valuations, businesses without 10-year earnings visibility.",
        "famous_investments": ["Eicher Motors", "Page Industries", "Bajaj Finance"],
        "signature_quote": "Buy right, sit tight.",
        "rebalance_style": "Annual formal rebalance.",
        "description": "All four QGLP criteria — quality, growth, longevity, price",
    },
    "dolly_khanna": {
        "name": "Dolly Khanna", "avatar": "DK", "category": "Indian Legend",
        "focus": "Cyclical Turnarounds", "color": "#f472b6",
        "portfolio_size": 25, "sizing_style": "equal_weight",
        "bio": "Dolly Khanna is one of India's most successful retail investors, known for her ability to identify cyclical businesses at turnaround points.",
        "philosophy": "Find cyclical businesses at the bottom of their cycle. Buy when the sector is hated, hold through the recovery, sell when valuations are stretched.",
        "what_he_looked_for": "Small caps under Rs 3,000 Cr, cyclical businesses at trough valuations, strong balance sheets to survive the downturn.",
        "what_he_avoided": "Large caps, businesses with poor balance sheets.",
        "famous_investments": ["Nilkamal", "Rain Industries", "Thirumalai Chemicals"],
        "signature_quote": "Buy what others are ignoring. Sell what others are chasing.",
        "rebalance_style": "Semi-annual. Exits when cyclical recovery is fully priced in.",
        "description": "Cyclical turnarounds, ignored smallcaps, beaten-down sectors",
    },
    "enam": {
        "name": "Enam / Vallabh Bhansali", "avatar": "EN", "category": "Indian Fund",
        "focus": "Forensic Long-Term Quality", "color": "#c4b5fd",
        "portfolio_size": 15, "sizing_style": "conviction_weighted",
        "bio": "Enam Securities, founded by Vallabh Bhansali and Nemish Shah, is one of India's most respected institutional brokers known for deep fundamental research.",
        "philosophy": "Management integrity is non-negotiable. Zero tolerance for governance issues. Debt-free businesses with long track records. 10+ year horizon.",
        "what_he_looked_for": "Management integrity above all, debt-free, consistent 10+ year track record, high ROCE.",
        "what_he_avoided": "Any management integrity concerns, leveraged businesses.",
        "famous_investments": ["HDFC Bank", "Infosys", "Asian Paints", "Hero Honda"],
        "signature_quote": "Management integrity is the first filter. Everything else is secondary.",
        "rebalance_style": "Very long term. Extremely low turnover.",
        "description": "Management integrity first, debt-free, forensic accounting",
    },
    "white_oak": {
        "name": "White Oak Capital", "avatar": "WO", "category": "Indian Fund",
        "focus": "Earnings Quality Growth", "color": "#86efac",
        "portfolio_size": 30, "sizing_style": "equal_weight",
        "bio": "Prashant Khemka founded White Oak Capital after a stellar career at Goldman Sachs Asset Management. Focuses on earnings quality and return on equity.",
        "philosophy": "Earnings quality is the foundation. High, sustainable ROE without leverage. Business quality drives long-term returns.",
        "what_he_looked_for": "ROE > 20% without leverage, earnings quality (cash conversion), consistent growth.",
        "what_he_avoided": "Businesses with poor earnings quality, high leverage.",
        "famous_investments": ["ICICI Bank", "Kotak Bank", "Maruti", "Titan"],
        "signature_quote": "Earnings quality separates sustainable returns from temporary ones.",
        "rebalance_style": "Annual rebalance. Equal weight approach.",
        "description": "Earnings quality, ROE without leverage, Goldman Sachs rigor",
    },
    "radhakishan_damani": {
        "name": "Radhakishan Damani", "avatar": "RKD", "category": "Indian Legend",
        "focus": "Retail & Consumer Value", "color": "#fb923c",
        "portfolio_size": 8, "sizing_style": "very_concentrated",
        "bio": "Radhakishan Damani, founder of DMart and Avenue Supermarts, is one of India's wealthiest individuals. Before DMart he was a legendary investor known for contrarian calls and deep value in the 1990s.",
        "philosophy": "Extremely concentrated bets on businesses he deeply understands. Prefers consumer-facing businesses with pricing power, everyday essential products, and low-cost operational models.",
        "what_he_looked_for": "Consumer businesses with durable competitive advantage, low-cost operators, essential products, strong cash flow, owner-operated businesses.",
        "what_he_avoided": "Capital-intensive businesses, high debt, businesses dependent on advertising, luxury goods.",
        "famous_investments": ["Avenue Supermarts (DMart)", "VST Industries", "3M India", "United Breweries"],
        "signature_quote": "Build a business where customers come back every day.",
        "rebalance_style": "Very long term. Once invested, rarely exits.",
        "description": "Consumer + retail lens, EDLP businesses, essential products, low debt",
    },
    "raamdeo_agrawal": {
        "name": "Raamdeo Agrawal", "avatar": "RA", "category": "Indian Legend",
        "focus": "QGLP — Quality Growth", "color": "#60a5fa",
        "portfolio_size": 20, "sizing_style": "conviction_weighted",
        "bio": "Raamdeo Agrawal, co-founder of Motilal Oswal Financial Services, developed the QGLP framework that has guided billions in Indian equity investment. He has compounded wealth at over 25% CAGR for over 30 years.",
        "philosophy": "QGLP: Quality of business and management, Growth in earnings over 20% for 5 years, Longevity of the growth runway 10+ years, Price that is reasonable (PEG below 1.5). All four must align.",
        "what_he_looked_for": "ROE above 20%, earnings growth above 20% for 5 years, large addressable market, honest management, PE reasonable relative to growth.",
        "what_he_avoided": "Commodity businesses, high debt, management with integrity issues, businesses with less than 5 year earnings visibility.",
        "famous_investments": ["Eicher Motors", "Page Industries", "HDFC Bank", "Infosys"],
        "signature_quote": "Wealth creation is all about owning great businesses for a long period of time.",
        "rebalance_style": "Annual formal review. Replaces slowest growers.",
        "description": "QGLP pioneer — Quality + Growth + Longevity + Price framework",
    },
    "sanjay_bakshi": {
        "name": "Sanjay Bakshi", "avatar": "SB", "category": "Indian Legend",
        "focus": "Behavioral Value Investing", "color": "#818cf8",
        "portfolio_size": 15, "sizing_style": "conviction_weighted",
        "bio": "Sanjay Bakshi is a professor at MDI Gurgaon and founder of ValueQuest Capital. A disciple of Ben Graham and Charlie Munger, he brings academic rigor to value investing.",
        "philosophy": "Combines Graham margin of safety with Munger quality-compounder approach. Heavy emphasis on behavioral finance — buy when others are irrationally fearful. Focuses on moaty businesses at temporary discounts.",
        "what_he_looked_for": "High-quality businesses at temporary discount, monopolistic characteristics, owner-operators, high ROCE, low debt.",
        "what_he_avoided": "Businesses he does not deeply understand, highly leveraged companies, businesses without durable competitive advantage.",
        "famous_investments": ["Relaxo Footwear", "Hawkins Cookers", "La Opala", "Astral Poly"],
        "signature_quote": "The best time to buy a great business is when it is being given away.",
        "rebalance_style": "Thesis-based. Patient 3-7 year holds.",
        "description": "Academic value investing, behavioral finance lens, moaty businesses at discount",
    },
    "kenneth_andrade": {
        "name": "Kenneth Andrade (Old Bridge)", "avatar": "KA", "category": "Indian Legend",
        "focus": "Asset-Light Capital Efficiency", "color": "#34d399",
        "portfolio_size": 20, "sizing_style": "equal_weight",
        "bio": "Kenneth Andrade, founder of Old Bridge Capital, is known for his contrarian asset-light investment philosophy. He ran IDFC Premier Equity Fund before starting Old Bridge, delivering exceptional returns.",
        "philosophy": "Focus on asset-light businesses with high capital efficiency. Look for companies where earnings growth does not require proportional capital investment. Contrarian — buys underperforming sectors.",
        "what_he_looked_for": "Asset-light models, high asset turnover, capital-efficient businesses, sectors at cyclical lows, ROCE improvement trend.",
        "what_he_avoided": "Capital-intensive manufacturing, businesses requiring constant capex, highly leveraged balance sheets.",
        "famous_investments": ["PI Industries", "Sudarshan Chemicals", "Aavas Financiers", "Cera Sanitaryware"],
        "signature_quote": "Asset-light businesses are the future of wealth creation.",
        "rebalance_style": "Semi-annual. Rotates out of fully valued into undervalued sectors.",
        "description": "Asset-light businesses, high capital efficiency, ROCE focus, contrarian rotation",
    },
    "chandrakant_sampat": {
        "name": "Chandrakant Sampat", "avatar": "CS", "category": "Indian Legend",
        "focus": "Original Indian Value", "color": "#a78bfa",
        "portfolio_size": 10, "sizing_style": "conviction_weighted",
        "bio": "Chandrakant Sampat (1928-2015) is considered India's original value investor, predating Buffett's fame in India. He invested in Hindustan Unilever and similar consumer monopolies decades before it became fashionable.",
        "philosophy": "Invest in businesses that sell essential products that people need regardless of economic cycles. Debt-free companies with strong brands and pricing power that compound quietly over decades.",
        "what_he_looked_for": "Debt-free balance sheets, consumer monopolies, strong brand moats, consistent dividend payers, businesses with 20+ year runway.",
        "what_he_avoided": "Leveraged businesses, commodity companies, businesses dependent on government contracts, cyclical industries.",
        "famous_investments": ["Hindustan Unilever (held 40+ years)", "Colgate-Palmolive", "Nestle India", "Infosys (early)"],
        "signature_quote": "Invest in a business that even a fool can run, because someday a fool will.",
        "rebalance_style": "Decades-long holds. Portfolio turnover near zero.",
        "description": "India original Buffett — consumer monopolies, debt-free, decades-long compounders",
    },
    "nippon_smallcap": {
        "name": "Nippon India Small Cap", "avatar": "NS", "category": "Indian Fund",
        "focus": "High Growth Small Caps", "color": "#22d3ee",
        "portfolio_size": 60, "sizing_style": "equal_weight",
        "bio": "Nippon India Small Cap Fund is one of India's largest small cap funds with over Rs 50,000 Cr AUM. It invests across the small cap spectrum with focus on growth businesses in emerging sectors.",
        "philosophy": "Diversified exposure to India's small cap growth story. Find emerging sector leaders before they become mainstream. Willing to pay higher multiples for high growth businesses.",
        "what_he_looked_for": "Small cap companies (market cap Rs 500-8000 Cr), high revenue growth above 20%, improving profitability, sector leadership potential.",
        "what_he_avoided": "Companies with too much debt, loss-making without clear path to profitability, businesses in permanently declining industries.",
        "famous_investments": ["Tube Investments", "Navin Fluorine", "Happiest Minds", "KPIT Technologies"],
        "signature_quote": "Small caps today are large caps tomorrow.",
        "rebalance_style": "Quarterly review.",
        "description": "Diversified small cap growth, emerging sector leaders, high growth businesses",
    },
    "nemish_shah": {
        "name": "Nemish Shah (Enam)", "avatar": "NSH", "category": "Indian Fund",
        "focus": "Consumer & Pharma Quality", "color": "#e879f9",
        "portfolio_size": 15, "sizing_style": "conviction_weighted",
        "bio": "Nemish Shah co-founded Enam Securities with Vallabh Bhansali. Known for deep expertise in consumer and pharmaceutical businesses. His thesis centres on businesses selling essential products with strong brand moats.",
        "philosophy": "Focus on consumer staples and pharma — businesses people need regardless of the economy. Brands with pricing power, high repeat purchase, and strong distribution networks compound quietly for decades.",
        "what_he_looked_for": "Consumer brands with pricing power, pharmaceutical businesses with strong pipelines, debt-free balance sheets, consistent dividend payers.",
        "what_he_avoided": "Capital-intensive businesses without brand moat, high debt, management with integrity concerns.",
        "famous_investments": ["Hindustan Unilever", "Nestle India", "Abbott India", "Colgate-Palmolive"],
        "signature_quote": "Consumer brands are the closest thing to a perpetual motion machine in business.",
        "rebalance_style": "Very long term holds. Decades in some cases.",
        "description": "Consumer and pharma specialist, brand moats, pricing power, debt-free",
    },
    "mirae_asset": {
        "name": "Mirae Asset India", "avatar": "MA", "category": "Indian Fund",
        "focus": "Quality Growth Large Cap", "color": "#a3e635",
        "portfolio_size": 55, "sizing_style": "market_cap_weighted",
        "bio": "Mirae Asset Investment Managers India is the Indian arm of South Korean giant Mirae Asset. Known for disciplined process-driven investing, Mirae India Equity has consistently outperformed its benchmark.",
        "philosophy": "Bottom-up stock selection focusing on quality businesses with sustainable competitive advantages. Sector leaders with consistent earnings growth and strong return ratios.",
        "what_he_looked_for": "Sector leadership, consistent earnings growth, strong ROE and ROCE, reasonable valuations, well-managed balance sheets.",
        "what_he_avoided": "Speculative businesses, high leverage, businesses without clear competitive advantage.",
        "famous_investments": ["ICICI Bank", "Infosys", "Maruti Suzuki", "Bharti Airtel", "Kotak Mahindra"],
        "signature_quote": "Quality businesses at reasonable prices outperform over time.",
        "rebalance_style": "Quarterly review. Benchmark-aware.",
        "description": "Sector leaders, quality businesses, consistent earnings growth, risk management",
    },
    "hdfc_mf": {
        "name": "HDFC Mutual Fund", "avatar": "HM", "category": "Indian Fund",
        "focus": "Value + Quality Blend", "color": "#fb923c",
        "portfolio_size": 50, "sizing_style": "conviction_weighted",
        "bio": "Under Prashant Jain (2003-2022), HDFC Equity Fund became one of India's most respected equity funds. Known for contrarian calls — buying PSU banks and infrastructure when others avoided them.",
        "philosophy": "Buy quality businesses at value prices. Be contrarian — PSU banks, infrastructure, and cyclicals have their time. Patient capital. Hold through 3-5 year down cycles if the long-term thesis is intact.",
        "what_he_looked_for": "Quality businesses at value multiples, PSU and cyclical businesses at trough valuations, consistent dividend payers.",
        "what_he_avoided": "Businesses at extreme valuations, highly leveraged companies, businesses without earnings visibility.",
        "famous_investments": ["SBI", "HDFC Bank", "Infosys", "BHEL (contrarian)", "ONGC"],
        "signature_quote": "Be contrarian. Buy when others are selling.",
        "rebalance_style": "Patient 3-5 year holds. Contrarian rebalancing.",
        "description": "Value + quality blend, contrarian at times, patient long-term capital",
    },
    "anand_rathi": {
        "name": "Anand Rathi Wealth", "avatar": "AR", "category": "Indian Fund",
        "focus": "Wealth Preservation + Growth", "color": "#fbbf24",
        "portfolio_size": 25, "sizing_style": "risk_weighted",
        "bio": "Anand Rathi Wealth is one of India's leading wealth management firms focused on HNI clients. Their approach prioritizes capital preservation alongside growth, with heavy emphasis on asset allocation.",
        "philosophy": "Wealth preservation first, growth second. Large cap bias for stability. Dividend-paying businesses for income. Portfolio construction with risk management as a central theme.",
        "what_he_looked_for": "Large cap stability (market cap above Rs 10,000 Cr), consistent dividend payers, low debt, strong corporate governance, defensive sectors.",
        "what_he_avoided": "Highly speculative smallcaps, businesses with governance issues, high leverage.",
        "famous_investments": ["HDFC Bank", "Infosys", "Reliance", "ITC", "Bajaj Finance"],
        "signature_quote": "Preserving wealth is as important as creating it.",
        "rebalance_style": "Semi-annual with asset allocation review.",
        "description": "HNI wealth management, large cap bias, capital preservation, dividend focus",
    },
    "ask_investment": {
        "name": "ASK Investment Managers", "avatar": "ASK", "category": "Indian Fund",
        "focus": "Quality Large Cap PMS", "color": "#fdba74",
        "portfolio_size": 20, "sizing_style": "conviction_weighted",
        "bio": "ASK Investment Managers is one of India's largest PMS providers with over Rs 70,000 Cr in AUM. Known for quality-focused approach and wealth preservation philosophy for HNI clients.",
        "philosophy": "Capital preservation with growth. Focus on large quality businesses with strong balance sheets. Dividend-paying companies for income. Low churn, patient approach.",
        "what_he_looked_for": "Large cap quality (above Rs 10,000 Cr market cap), consistent earnings growth, strong ROE, low debt, dividend payers, strong corporate governance.",
        "what_he_avoided": "Small caps, businesses with governance concerns, high leverage, loss-making businesses.",
        "famous_investments": ["HDFC Bank", "Bajaj Finance", "Asian Paints", "Infosys", "Kotak Bank"],
        "signature_quote": "Quality never goes out of style.",
        "rebalance_style": "Annual. Low turnover wealth management approach.",
        "description": "Quality large cap PMS, wealth preservation, consistent earnings, low leverage",
    },
    "murugappa": {
        "name": "Murugappa Group Style", "avatar": "MG", "category": "Indian Fund",
        "focus": "South India Industrial Quality", "color": "#fcd34d",
        "portfolio_size": 15, "sizing_style": "equal_weight",
        "bio": "The Murugappa Group is a 125-year-old Chennai-based conglomerate. Their investment philosophy reflects generations of industrial wealth creation — patient, conservative, quality-focused.",
        "philosophy": "Long-term industrial value creation. Manufacturing excellence, operational efficiency, conservative balance sheets. Family-run businesses with multi-generational thinking.",
        "what_he_looked_for": "Manufacturing excellence, operational efficiency, conservative balance sheets, consistent dividend history, family-managed businesses with long track records.",
        "what_he_avoided": "Speculative businesses, high leverage, businesses requiring constant external capital.",
        "famous_investments": ["Coromandel International", "Carborundum Universal", "Cholamandalam Investment", "EID Parry"],
        "signature_quote": "Build businesses that last generations.",
        "rebalance_style": "Very long term. Generational investment horizon.",
        "description": "Industrial manufacturing, conservative balance sheets, multi-generational quality",
    },
    "manish_kejriwal": {
        "name": "Manish Kejriwal (Amansa)", "avatar": "MK", "category": "Indian Legend",
        "focus": "Quality Growth PE Style", "color": "#f0abfc",
        "portfolio_size": 15, "sizing_style": "conviction_weighted",
        "bio": "Manish Kejriwal founded Amansa Capital after stints at Goldman Sachs and Temasek. He brings a private equity mindset to public market investing — long holding periods, deep business analysis.",
        "philosophy": "Invest like a PE fund in public markets. Buy stakes in high-quality businesses with long growth runways and hold for 5-10 years. Management quality and corporate governance are paramount.",
        "what_he_looked_for": "World-class management, high ROE above 20%, durable competitive moat, large addressable market, strong corporate governance.",
        "what_he_avoided": "Businesses with governance concerns, high leverage, highly competitive commoditized industries.",
        "famous_investments": ["Info Edge (Naukri)", "HDFC Life", "Asian Paints", "Pidilite Industries"],
        "signature_quote": "We invest in businesses, not stocks.",
        "rebalance_style": "Long-term 5-10 year holds. Very low portfolio turnover.",
        "description": "Private equity mindset, world-class management, 5-10 year holds",
    },
    "phil_fisher": {
        "name": "Philip Fisher", "avatar": "PF", "category": "Global Legend",
        "focus": "Scuttlebutt Growth Investor", "color": "#14b8a6",
        "portfolio_size": 12, "sizing_style": "conviction_weighted",
        "bio": "Philip Fisher wrote Common Stocks and Uncommon Profits (1958), one of the most influential investment books. His scuttlebutt method — researching companies through industry contacts — was revolutionary.",
        "philosophy": "Buy outstanding companies with superior long-term growth prospects and hold them for years. Use the scuttlebutt method to deeply understand the business. Management quality is paramount.",
        "what_he_looked_for": "Strong sales growth, high profit margins, R&D investment, excellent management, good labor relations, proprietary products.",
        "what_he_avoided": "Businesses solely focused on price competition, poor management teams, businesses without R&D investment.",
        "famous_investments": ["Motorola (held for decades)", "Texas Instruments", "Dow Chemical"],
        "signature_quote": "The stock market is filled with individuals who know the price of everything, but the value of nothing.",
        "rebalance_style": "Long-term growth holds. Exits when growth thesis breaks.",
        "description": "Outstanding growth companies, deep research, management quality paramount",
    },
    "carnelian": {
        "name": "Carnelian Asset (Vikas Khemani)", "avatar": "CA", "category": "Indian Fund",
        "focus": "Emerging Sector Leaders", "color": "#67e8f9",
        "portfolio_size": 20, "sizing_style": "equal_weight",
        "bio": "Vikas Khemani founded Carnelian Asset Management after leading Edelweiss Securities. Focuses on emerging compounders in sectors with strong tailwinds.",
        "philosophy": "Find businesses in sectors with strong structural tailwinds — defence, specialty chemicals, digital India. Companies transitioning from small to mid cap.",
        "what_he_looked_for": "Emerging sector leaders, improving margin profile, management execution, market cap Rs 500-15000 Cr.",
        "what_he_avoided": "Structurally declining industries, high leverage.",
        "famous_investments": ["KPIT Technologies", "Mas Financial", "Tanla Platforms"],
        "signature_quote": "Invest in the future, not the past.",
        "rebalance_style": "Semi-annual review.",
        "description": "Emerging compounders, structural sector tailwinds",
    },
}


def score_profile(d: dict, profile: str, sector_avgs: dict = None) -> dict:
    """Score a stock against an investor profile, using sector-relative metrics."""
    if sector_avgs is None: sector_avgs = {}
    s, r = 0, []
    sector = d.get("sector", "Unknown")
    avgs = sector_avgs.get(sector, {})

    def pct(v): return v * 100 if v is not None else None
    def vs(val, avg_key, higher_better=True):
        if val is None: return 0
        avg = avgs.get(avg_key)
        if avg is None or avg == 0: 
            # Fallback to absolute thresholds
            return None
        ratio = val / avg
        if higher_better:
            if ratio >= 1.5: return 30
            if ratio >= 1.2: return 22
            if ratio >= 1.0: return 14
            if ratio >= 0.8: return 8
            return 3
        else:
            if ratio <= 0.6: return 30
            if ratio <= 0.8: return 22
            if ratio <= 1.0: return 14
            if ratio <= 1.2: return 8
            return 3

    roe = d.get("roe"); roce = d.get("roce"); opm = d.get("operating_margins")
    dy = pct(d.get("dividend_yield")); ph = d.get("promoter_holding")
    pe = d.get("pe_ratio"); pb = d.get("pb_ratio"); de = d.get("debt_to_equity")
    mc = (d.get("market_cap") or 0) / 1e7
    price = d.get("current_price"); high = d.get("52w_high")
    rev_growth = d.get("revenue_growth"); earn_growth = d.get("earnings_growth")
    pct_off = ((high - price) / high * 100) if price and high and high > 0 else 0
    debt_free = de is not None and de < 0.2

    if profile == "rj":
        sv = vs(roe, "roe", True)
        if sv: s += sv; 
        elif roe and pct(roe) >= 20: s += 25; r.append(f"Strong ROE {pct(roe):.1f}%")
        elif roe and pct(roe) >= 15: s += 15
        sv2 = vs(roce, "roce", True)
        if sv2: s += sv2
        elif roce and pct(roce) >= 20: s += 20
        if ph and ph >= 0.5: s += 30; r.append(f"High promoter {pct(ph):.1f}%")
        elif ph and ph >= 0.35: s += 18
        if pe and 0 < pe < 35: s += 20; r.append(f"Reasonable P/E {pe:.1f}x")
        if rev_growth and pct(rev_growth) >= 15: s += 10; r.append(f"Growing {pct(rev_growth):.1f}%")

    elif profile == "buffett":
        sv = vs(roe, "roe", True)
        s += (sv or (25 if roe and pct(roe) >= 20 else 10 if roe and pct(roe) >= 15 else 0))
        if roe and pct(roe) >= 20: r.append(f"Strong ROE {pct(roe):.1f}%")
        if debt_free: s += 25; r.append("Near debt-free")
        elif de and de < 0.5: s += 15
        sv2 = vs(opm, "opm", True)
        s += (sv2 or (20 if opm and pct(opm) >= 20 else 10 if opm and pct(opm) >= 12 else 0))
        if opm and pct(opm) >= 20: r.append(f"Strong OPM {pct(opm):.1f}%")
        if pe and 0 < pe < 25: s += 20; r.append(f"Reasonable P/E {pe:.1f}x")
        elif pe and pe < 35: s += 10

    elif profile == "marcellus":
        if debt_free: s += 35; r.append("Debt-free")
        elif de and de < 0.3: s += 15
        sv = vs(roce, "roce", True)
        if sv: s += sv; 
        if roce and pct(roce) >= 25: s += 5; r.append(f"Exceptional ROCE {pct(roce):.1f}%")
        elif roce and pct(roce) >= 18: r.append(f"Strong ROCE {pct(roce):.1f}%")
        sv2 = vs(opm, "opm", True)
        s += (sv2 or 0)
        if opm and pct(opm) >= 20: r.append(f"Wide margins {pct(opm):.1f}%")
        if roe and pct(roe) >= 20: s += 15

    elif profile == "vijay_kedia":
        if 0 < mc < 5000: s += 25; r.append(f"Small/mid cap Rs {mc:.0f}Cr")
        elif mc < 20000: s += 12
        if ph and ph >= 0.5: s += 25; r.append(f"High promoter {pct(ph):.1f}%")
        elif ph and ph >= 0.35: s += 15
        sv = vs(roe, "roe", True)
        s += (sv or (20 if roe and pct(roe) >= 20 else 10))
        if roe and pct(roe) >= 20: r.append(f"High ROE {pct(roe):.1f}%")
        sv2 = vs(opm, "opm", True)
        s += (sv2 or (15 if opm and pct(opm) >= 15 else 5))

    elif profile == "parag_parikh":
        if ph and ph >= 0.45: s += 25; r.append(f"Owner-operator {pct(ph):.1f}%")
        elif ph and ph >= 0.3: s += 15
        sv = vs(opm, "opm", True)
        s += (sv or (20 if opm and pct(opm) >= 20 else 10))
        if opm and pct(opm) >= 20: r.append(f"Pricing power {pct(opm):.1f}%")
        if debt_free or (de and de < 0.5): s += 20; r.append("Conservative balance sheet")
        sv2 = vs(roe, "roe", True)
        s += (sv2 or (15 if roe and pct(roe) >= 18 else 5))

    elif profile == "ben_graham":
        if pb and 0 < pb < 1: s += 40; r.append(f"Below book P/B {pb:.2f}x")
        elif pb and pb < 1.5: s += 28; r.append(f"Near book P/B {pb:.2f}x")
        elif pb and pb < 2: s += 15
        if pe and 0 < pe < 12: s += 35; r.append(f"Deep value P/E {pe:.1f}x")
        elif pe and pe < 15: s += 22
        elif pe and pe < 20: s += 10
        if debt_free: s += 25; r.append("Graham safety")

    elif profile == "peter_lynch":
        if roe and pe and roe > 0 and pe > 0:
            peg_calc = pe / pct(roe)
            if peg_calc < 0.5: s += 40; r.append(f"Excellent PEG {peg_calc:.2f}")
            elif peg_calc < 1.0: s += 28; r.append(f"Good PEG {peg_calc:.2f}")
            elif peg_calc < 1.5: s += 15
        if rev_growth and pct(rev_growth) >= 15: s += 25; r.append(f"Growing fast {pct(rev_growth):.1f}%")
        if pe and 0 < pe < 30: s += 15

    elif profile == "charlie_munger":
        sv = vs(roce, "roce", True)
        s += (sv or (30 if roce and pct(roce) >= 25 else 10))
        if roce and pct(roce) >= 25: r.append(f"Exceptional ROCE {pct(roce):.1f}%")
        sv2 = vs(opm, "opm", True)
        s += (sv2 or (20 if opm and pct(opm) >= 25 else 8))
        if opm and pct(opm) >= 25: r.append(f"Pricing power {pct(opm):.1f}%")
        if debt_free: s += 20; r.append("Debt-free compounder")

    elif profile == "porinju":
        if 0 < mc < 2000: s += 35; r.append(f"True smallcap Rs {mc:.0f}Cr")
        elif mc < 5000: s += 18
        if pct_off >= 30: s += 25; r.append(f"Beaten down {pct_off:.0f}% off highs")
        elif pct_off >= 15: s += 12
        if pe and 0 < pe < 20: s += 25; r.append(f"Cheap P/E {pe:.1f}x")

    elif profile == "ashish_kacholia":
        if 0 < mc < 5000: s += 25; r.append(f"Smallcap Rs {mc:.0f}Cr")
        elif mc < 15000: s += 12
        sv = vs(roe, "roe", True)
        s += (sv or (20 if roe and pct(roe) >= 20 else 8))
        if roe and pct(roe) >= 20: r.append(f"High ROE {pct(roe):.1f}%")
        sv2 = vs(opm, "opm", True)
        s += (sv2 or (15 if opm and pct(opm) >= 15 else 5))
        if earn_growth and pct(earn_growth) >= 20: s += 15; r.append(f"Earnings growing {pct(earn_growth):.1f}%")

    elif profile == "motilal_qglp":
        q_met = (roe and pct(roe) >= 18) and (opm and pct(opm) >= 15)
        g_met = (rev_growth and pct(rev_growth) >= 15) or (earn_growth and pct(earn_growth) >= 15)
        p_met = pe and 0 < pe < 45
        if q_met: s += 30; r.append("Quality criterion met")
        if g_met: s += 25; r.append(f"Growth criterion met")
        if p_met: s += 25; r.append(f"Price reasonable {pe:.1f}x")
        if roce and pct(roce) >= 20: s += 20; r.append(f"ROCE {pct(roce):.1f}%")

    elif profile == "dolly_khanna":
        if 0 < mc < 3000: s += 25; r.append(f"Small cap Rs {mc:.0f}Cr")
        if pct_off >= 25: s += 25; r.append(f"Turnaround {pct_off:.0f}% off highs")
        sv = vs(roe, "roe", True)
        s += (sv or (20 if roe and pct(roe) >= 15 else 5))
        if roe and pct(roe) >= 15: r.append(f"ROE recovery {pct(roe):.1f}%")

    elif profile == "enam":
        if debt_free: s += 35; r.append("Debt-free")
        elif de and de < 0.2: s += 20
        if ph and ph >= 0.45: s += 25; r.append(f"Management alignment {pct(ph):.1f}%")
        sv = vs(roe, "roe", True)
        s += (sv or (15 if roe and pct(roe) >= 18 else 5))
        sv2 = vs(opm, "opm", True)
        s += (sv2 or (15 if opm and pct(opm) >= 15 else 5))

    elif profile == "white_oak":
        sv = vs(roe, "roe", True)
        s += (sv or (25 if roe and pct(roe) >= 22 else 10))
        if roe and pct(roe) >= 22: r.append(f"Quality ROE {pct(roe):.1f}%")
        sv2 = vs(opm, "opm", True)
        s += (sv2 or (20 if opm and pct(opm) >= 20 else 8))
        if pe and 0 < pe < 35: s += 20; r.append(f"GARP {pe:.1f}x")
        if debt_free or (de and de < 0.4): s += 20

    elif profile == "carnelian":
        if 0 < mc < 20000: s += 20; r.append(f"Emerging compounder Rs {mc:.0f}Cr")
        sv = vs(roe, "roe", True)
        s += (sv or (20 if roe and pct(roe) >= 20 else 8))
        if roe and pct(roe) >= 20: r.append(f"High ROE {pct(roe):.1f}%")
        sv2 = vs(opm, "opm", True)
        s += (sv2 or (15 if opm and pct(opm) >= 15 else 5))
        if earn_growth and pct(earn_growth) >= 20: s += 15; r.append(f"Fast growing {pct(earn_growth):.1f}%")

    elif profile == "radhakishan_damani":
        if opm and pct(opm) >= 15: s += 30; r.append(f"Consumer pricing power {pct(opm):.1f}%")
        if debt_free: s += 25; r.append("Debt-free consumer business")
        if dy and dy >= 0.02: s += 20; r.append(f"Cash return {pct(dy):.1f}%")
        if roe and pct(roe) >= 18: s += 15; r.append(f"Strong ROE {pct(roe):.1f}%")
        if mc > 5000: s += 10

    elif profile == "raamdeo_agrawal":
        q_met = (roe and pct(roe) >= 20) and (opm and pct(opm) >= 15)
        g_met = (rev_growth and pct(rev_growth) >= 15) or (earn_growth and pct(earn_growth) >= 15)
        p_met = pe and 0 < pe < 45
        l_met = ph and ph >= 0.40
        if q_met: s += 30; r.append("Quality criterion met (ROE + margins)")
        if g_met: s += 25; r.append("Growth criterion met")
        if p_met: s += 25; r.append(f"Price reasonable P/E {pe:.1f}x")
        if l_met: s += 20; r.append(f"Longevity promoter {pct(ph):.1f}%")

    elif profile == "sanjay_bakshi":
        if roe and pct(roe) >= 20: s += 25; r.append(f"Quality moat ROE {pct(roe):.1f}%")
        elif roe and pct(roe) >= 15: s += 15
        if debt_free or (de is not None and de < 0.3): s += 25; r.append("Graham safety margin")
        pct_off = ((high-price)/high*100) if price and high and high > 0 else 0
        if pct_off >= 20: s += 25; r.append(f"Behavioral mispricing {pct_off:.0f}% off highs")
        if opm and pct(opm) >= 20: s += 15; r.append(f"Wide margins {pct(opm):.1f}%")
        if pe and 0 < pe < 35: s += 10

    elif profile == "kenneth_andrade":
        if roce and pct(roce) >= 20: s += 30; r.append(f"Capital efficient ROCE {pct(roce):.1f}%")
        elif roce and pct(roce) >= 15: s += 18
        if opm and pct(opm) >= 15: s += 25; r.append(f"Asset-light margins {pct(opm):.1f}%")
        if de is not None and de < 0.3: s += 20; r.append("Low capex balance sheet")
        pct_off2 = ((high-price)/high*100) if price and high and high > 0 else 0
        if pct_off2 >= 15: s += 15; r.append(f"Contrarian entry {pct_off2:.0f}% off highs")

    elif profile == "chandrakant_sampat":
        if debt_free: s += 30; r.append("Debt-free — Sampat non-negotiable")
        if roe and pct(roe) >= 20: s += 25; r.append(f"High ROE {pct(roe):.1f}%")
        elif roe and pct(roe) >= 15: s += 15
        if opm and pct(opm) >= 20: s += 25; r.append(f"Consumer pricing power {pct(opm):.1f}%")
        elif opm and pct(opm) >= 12: s += 12
        if pe and 0 < pe < 35: s += 20

    elif profile == "nippon_smallcap":
        if 0 < mc < 8000: s += 30; r.append(f"Small cap Rs {mc:.0f}Cr")
        elif mc < 15000: s += 15
        if roe and pct(roe) >= 18: s += 25; r.append(f"High growth ROE {pct(roe):.1f}%")
        elif roe and pct(roe) >= 12: s += 15
        if opm and pct(opm) >= 15: s += 25; r.append(f"Emerging margins {pct(opm):.1f}%")
        elif opm and pct(opm) >= 8: s += 12
        if pe and 0 < pe < 50: s += 20

    elif profile == "nemish_shah":
        if debt_free: s += 30; r.append("Debt-free consumer/pharma")
        if opm and pct(opm) >= 20: s += 25; r.append(f"Pricing power OPM {pct(opm):.1f}%")
        elif opm and pct(opm) >= 12: s += 15
        if roe and pct(roe) >= 18: s += 20; r.append(f"Consistent ROE {pct(roe):.1f}%")
        if ph and ph >= 0.40: s += 15; r.append(f"Promoter alignment {pct(ph):.1f}%")
        if dy and dy >= 0.015: s += 10; r.append(f"Dividend {pct(dy):.1f}%")

    elif profile == "mirae_asset":
        if roe and pct(roe) >= 20: s += 28; r.append(f"Quality ROE {pct(roe):.1f}%")
        elif roe and pct(roe) >= 15: s += 18
        if roce and pct(roce) >= 20: s += 22; r.append(f"Strong ROCE {pct(roce):.1f}%")
        elif roce and pct(roce) >= 12: s += 12
        if opm and pct(opm) >= 18: s += 25; r.append(f"Sector leader margins {pct(opm):.1f}%")
        elif opm and pct(opm) >= 12: s += 15
        if pe and 0 < pe < 40: s += 25

    elif profile == "hdfc_mf":
        pct_off3 = ((high-price)/high*100) if price and high and high > 0 else 0
        if pct_off3 >= 20: s += 20; r.append(f"Value opportunity {pct_off3:.0f}% off highs")
        if pe and 0 < pe < 20: s += 25; r.append(f"Value P/E {pe:.1f}x")
        elif pe and pe < 30: s += 15
        if roe and pct(roe) >= 15: s += 25; r.append(f"Quality ROE {pct(roe):.1f}%")
        elif roe and pct(roe) >= 10: s += 15
        if dy and dy >= 0.02: s += 15; r.append(f"Dividend support {pct(dy):.1f}%")
        if debt_free or (de is not None and de < 0.5): s += 15

    elif profile == "anand_rathi":
        if mc > 10000: s += 20; r.append(f"Large cap safety Rs {mc:.0f}Cr")
        if dy and dy >= 0.03: s += 30; r.append(f"Strong dividend {pct(dy):.1f}%")
        elif dy and dy >= 0.02: s += 18; r.append(f"Good dividend {pct(dy):.1f}%")
        elif dy and dy >= 0.01: s += 8
        if debt_free or (de is not None and de < 0.3): s += 25; r.append("Capital preservation")
        if roe and pct(roe) >= 15: s += 15
        if pe and 0 < pe < 25: s += 10

    elif profile == "ask_investment":
        if mc > 15000: s += 20; r.append(f"Institutional quality Rs {mc:.0f}Cr")
        if roe and pct(roe) >= 18: s += 25; r.append(f"Quality ROE {pct(roe):.1f}%")
        elif roe and pct(roe) >= 12: s += 15
        if debt_free or (de is not None and de < 0.3): s += 25; r.append("Conservative balance sheet")
        if dy and dy >= 0.015: s += 15; r.append(f"Dividend {pct(dy):.1f}%")
        if opm and pct(opm) >= 15: s += 15

    elif profile == "murugappa":
        if debt_free or (de is not None and de < 0.3): s += 30; r.append("Conservative balance sheet")
        if dy and dy >= 0.02: s += 25; r.append(f"Dividend history {pct(dy):.1f}%")
        elif dy and dy >= 0.01: s += 15
        if opm and pct(opm) >= 15: s += 25; r.append(f"Manufacturing margins {pct(opm):.1f}%")
        elif opm and pct(opm) >= 10: s += 15
        if roe and pct(roe) >= 15: s += 20

    elif profile == "manish_kejriwal":
        if roe and pct(roe) >= 22: s += 30; r.append(f"PE-quality ROE {pct(roe):.1f}%")
        elif roe and pct(roe) >= 15: s += 18
        if opm and pct(opm) >= 20: s += 25; r.append(f"Quality margins {pct(opm):.1f}%")
        elif opm and pct(opm) >= 12: s += 15
        if ph and ph >= 0.45: s += 25; r.append(f"Management alignment {pct(ph):.1f}%")
        if debt_free or (de is not None and de < 0.4): s += 20

    elif profile == "phil_fisher":
        if roe and pct(roe) >= 20: s += 30; r.append(f"Superior ROE {pct(roe):.1f}%")
        elif roe and pct(roe) >= 15: s += 18
        if opm and pct(opm) >= 20: s += 25; r.append(f"Growing margins {pct(opm):.1f}%")
        elif opm and pct(opm) >= 12: s += 15
        if ph and ph >= 0.40: s += 25; r.append(f"Management aligned {pct(ph):.1f}%")
        if pe and 0 < pe < 50: s += 20
        if rev_growth and pct(rev_growth) >= 15: s += 0; r.append(f"Sales growth {pct(rev_growth):.1f}%")

    return {"score": min(s, 100), "reasons": r[:3]}


def get_matching_profiles(d: dict, sector_avgs: dict = None) -> list:
    results = []
    for pid, pdata in INVESTOR_PROFILES.items():
        res = score_profile(d, pid, sector_avgs or {})
        results.append({
            "id": pid, "name": pdata["name"], "avatar": pdata["avatar"],
            "color": pdata["color"], "score": res["score"], "reasons": res["reasons"],
        })
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:3]


def get_portfolio_allocation(profile_id: str, stocks: list, capital: float) -> dict:
    profile = INVESTOR_PROFILES.get(profile_id, {})
    sizing_style = profile.get("sizing_style", "equal_weight")
    n = len(stocks)
    if n == 0: return {"positions": []}

    if sizing_style == "very_concentrated":
        weights = [0.28, 0.20, 0.15] + [max(0.02, (1 - 0.63) / max(n - 3, 1))] * max(n - 3, 0)
    elif sizing_style == "conviction_weighted":
        scores = [s.get("profile_score", s["scoring"]["composite"]) for s in stocks]
        total = sum(scores)
        weights = [sc / total for sc in scores] if total > 0 else [1/n]*n
    else:
        weights = [1/n] * n

    total_w = sum(weights[:n])
    weights = [w / total_w for w in weights[:n]]

    positions = []
    for i, (stock, weight) in enumerate(zip(stocks, weights)):
        amount = capital * weight
        price = stock.get("current_price") or 0
        shares = int(amount / price) if price > 0 else 0
        actual_amount = shares * price if price > 0 else amount
        positions.append({
            "rank": i + 1,
            "symbol": stock["symbol"],
            "company_name": stock["company_name"],
            "sector": stock.get("sector", "Unknown"),
            "current_price": price,
            "weight_pct": round(weight * 100, 1),
            "amount": round(actual_amount),
            "shares": shares,
            "profile_score": stock.get("profile_score", stock["scoring"]["composite"]),
            "conviction": stock["conviction"],
            "why_included": (stock.get("profile_reasons") or stock["scoring"].get("top_reasons") or ["Meets profile criteria"])[:1][0],
        })

    sector_exposure = {}
    for pos in positions:
        sec = pos["sector"]
        if sec != "Unknown":
            sector_exposure[sec] = round(sector_exposure.get(sec, 0) + pos["weight_pct"], 1)

    known = {k: v for k, v in sector_exposure.items() if k != "Unknown"}
    top_sector = max(known.items(), key=lambda x: x[1])[0] if known else "Diversified"
    top_stocks = ", ".join([p["symbol"] for p in positions[:3]])

    rationale = (
        f"This portfolio is built using {profile.get('name')}'s '{profile.get('focus')}' philosophy. "
        f"Top holdings are {top_stocks}, selected because they score highest on {profile.get('name')}'s specific criteria. "
        f"Largest sector exposure is {top_sector} at {sector_exposure.get(top_sector, 0):.1f}%. "
        f"Position sizing follows {sizing_style.replace('_', ' ')} — "
        f"{'top picks get significantly larger allocations reflecting higher conviction' if sizing_style in ('very_concentrated', 'conviction_weighted') else 'equal allocation across all positions to spread risk'}."
    )

    entry_strategies = {
        "rj": "RJ believed in buying on dips aggressively. Consider entering in tranches — invest 50% now, 50% on any 10%+ market dip.",
        "buffett": "Buffett enters when he finds fair value. Add to winners at reasonable prices. Do not average down on declining businesses.",
        "marcellus": "Marcellus recommends SIP-style entry over 6-12 months. These are long-term holdings — timing matters less than selection.",
        "vijay_kedia": "Kedia builds positions slowly. Start with 25% of target allocation, add as conviction grows over 6-9 months.",
        "ben_graham": "Graham says buy below intrinsic value and sell when price reaches value. Enter only at your calculated margin of safety.",
        "peter_lynch": "Lynch invested as he found opportunities. Enter when PEG is below 1. Do not wait for the perfect entry.",
        "parag_parikh": "PPFAS holds cash for opportunities. Consider entering 70% now, keeping 30% for dips.",
    }

    return {
        "positions": positions,
        "total_stocks": n,
        "total_capital": capital,
        "total_deployed": round(sum(p["amount"] for p in positions)),
        "sector_exposure": sector_exposure,
        "portfolio_rationale": rationale,
        "entry_strategy": entry_strategies.get(profile_id, "Invest systematically over 3-6 months to average out entry prices."),
        "rebalance_note": profile.get("rebalance_style", ""),
    }



# ─── Legend Consensus Portfolio ───────────────────────────────────────────────
def score_legend_consensus(stock: dict, sector_avgs: dict) -> dict:
    """Score a stock across ALL profiles — consensus = breadth of agreement."""
    profile_ids = list(INVESTOR_PROFILES.keys())
    scores = []
    for pid in profile_ids:
        ps = score_profile(stock, pid, sector_avgs)
        scores.append({"profile_id": pid, "profile_name": INVESTOR_PROFILES[pid]["name"],
                       "score": ps["score"], "reasons": ps["reasons"]})
    scores.sort(key=lambda x: x["score"], reverse=True)

    qualifying = [s for s in scores if s["score"] >= 50]
    strong = [s for s in scores if s["score"] >= 65]
    avg_score = sum(s["score"] for s in scores) / len(scores) if scores else 0

    # Consensus score: weighted average + breadth bonus
    breadth_bonus = len(qualifying) * 2  # +2 per qualifying profile
    consensus_score = min(round(avg_score * 0.6 + breadth_bonus * 0.4), 100)

    tier = "All-Legend" if len(strong) >= 8 else "Strong Consensus" if len(qualifying) >= 5 else "Emerging Consensus" if len(qualifying) >= 3 else None

    return {
        "consensus_score": consensus_score,
        "qualifying_profiles": len(qualifying),
        "strong_profiles": len(strong),
        "tier": tier,
        "top_profiles": scores[:4],
        "all_scores": scores,
        "avg_score": round(avg_score, 1),
    }


def generate_stock_explanation(stock: dict, profile_id: str, sector_avgs: dict) -> dict:
    """Generate rich, professional explanation of why a stock was selected."""
    profile = INVESTOR_PROFILES.get(profile_id, {})
    sector = stock.get("sector", "Unknown")
    avgs = sector_avgs.get(sector, {})
    name = stock.get("company_name", stock.get("symbol", ""))
    symbol = stock.get("symbol", "")

    def pct(v): return v * 100 if v is not None else None
    def fmt_pct(v): return f"{pct(v):.1f}%" if v is not None else "N/A"
    def vs_avg(val, avg_key, higher_better=True):
        avg = avgs.get(avg_key)
        if val is None or avg is None or avg == 0: return ""
        diff = ((val - avg) / abs(avg)) * 100
        symbol_str = "↑" if (higher_better and val > avg) or (not higher_better and val < avg) else "↓"
        return f"{symbol_str} sector avg {fmt_pct(avg) if avg < 2 else f'{avg:.1f}x'}"

    roe = stock.get("roe"); roce = stock.get("roce"); opm = stock.get("operating_margins")
    pe = stock.get("pe_ratio"); pb = stock.get("pb_ratio"); de = stock.get("debt_to_equity")
    rev_g = stock.get("revenue_growth"); earn_g = stock.get("earnings_growth")
    ph = stock.get("promoter_holding"); price = stock.get("current_price")
    high = stock.get("52w_high"); mc = (stock.get("market_cap") or 0) / 1e7

    # Build qualifying metrics list
    qualifying_metrics = []

    if roe:
        qualifying_metrics.append({
            "metric": "ROE", "value": fmt_pct(roe), "sector_avg": fmt_pct(avgs.get("roe")),
            "vs_sector": vs_avg(roe, "roe", True), "learn_id": "roe",
            "explanation": f"Return on Equity of {fmt_pct(roe)} demonstrates how efficiently {name} generates profit from shareholder capital.",
            "status": "better" if avgs.get("roe") and roe > avgs["roe"] * 1.05 else "inline",
        })
    if roce:
        qualifying_metrics.append({
            "metric": "ROCE", "value": fmt_pct(roce), "sector_avg": fmt_pct(avgs.get("roce")),
            "vs_sector": vs_avg(roce, "roce", True), "learn_id": "roce",
            "explanation": f"ROCE of {fmt_pct(roce)} reflects the quality of capital deployment across the entire business, not just equity.",
            "status": "better" if avgs.get("roce") and roce > avgs["roce"] * 1.05 else "inline",
        })
    if opm:
        qualifying_metrics.append({
            "metric": "Operating Margin", "value": fmt_pct(opm), "sector_avg": fmt_pct(avgs.get("opm")),
            "vs_sector": vs_avg(opm, "opm", True), "learn_id": "operating-margins",
            "explanation": f"Operating margin of {fmt_pct(opm)} indicates the company retains {fmt_pct(opm)} of every rupee of revenue as operating profit.",
            "status": "better" if avgs.get("opm") and opm > avgs["opm"] * 1.05 else "inline",
        })
    if de is not None:
        qualifying_metrics.append({
            "metric": "Debt/Equity", "value": f"{de:.2f}x", "sector_avg": f"{avgs.get('de', 0):.2f}x" if avgs.get('de') else "N/A",
            "vs_sector": vs_avg(de, "de", False), "learn_id": "debt-equity",
            "explanation": f"Debt-to-equity of {de:.2f}x shows {'a near debt-free balance sheet' if de < 0.3 else 'moderate leverage' if de < 1 else 'significant leverage'}.",
            "status": "better" if avgs.get("de") and de < avgs["de"] * 0.9 else "inline",
        })
    if pe:
        qualifying_metrics.append({
            "metric": "P/E Ratio", "value": f"{pe:.1f}x", "sector_avg": f"{avgs.get('pe', 0):.1f}x" if avgs.get('pe') else "N/A",
            "vs_sector": vs_avg(pe, "pe", False), "learn_id": "pe-ratio",
            "explanation": f"P/E of {pe:.1f}x means investors are paying ₹{pe:.0f} for every ₹1 of annual earnings.",
            "status": "better" if avgs.get("pe") and pe < avgs["pe"] * 0.9 else "worse" if avgs.get("pe") and pe > avgs["pe"] * 1.1 else "inline",
        })
    if rev_g:
        qualifying_metrics.append({
            "metric": "Revenue Growth", "value": fmt_pct(rev_g), "sector_avg": fmt_pct(avgs.get("rev_growth")),
            "vs_sector": vs_avg(rev_g, "rev_growth", True), "learn_id": "revenue-growth",
            "explanation": f"Revenue growing at {fmt_pct(rev_g)} year-over-year demonstrates the business is expanding its top line.",
            "status": "better" if rev_g and pct(rev_g) >= 15 else "inline",
        })

    # Profile-specific full analysis paragraph
    profile_name = profile.get("name", "")
    analyses = {
        "rj": f"{name} aligns with Rakesh Jhunjhunwala's conviction-driven approach to India's growth story. With ROE of {fmt_pct(roe)}, this business demonstrates the kind of capital efficiency RJ demanded before committing capital. He specifically sought companies where promoters had significant skin in the game{f' — promoter holding at {fmt_pct(ph)} reflects this' if ph else ''}. RJ's philosophy was to find businesses riding India's long-term secular growth trends and hold them through volatility. He held Titan for over 20 years and would have applied the same patience here.",
        "buffett": f"This investment meets Warren Buffett's core criteria for what he calls a 'wonderful company.' The {fmt_pct(roe)} ROE demonstrates consistent ability to generate returns above the cost of capital — Buffett's primary quality filter. {'The near debt-free balance sheet reflects the kind of financial fortress Buffett seeks.' if de is not None and de < 0.3 else ''} Buffett evaluates whether he would be comfortable owning this business for 10 years if markets closed tomorrow. The pricing power implied by {fmt_pct(opm)} operating margins suggests a durable competitive moat.",
        "marcellus": f"{name} passes Marcellus's rigorous forensic filter — a screen that eliminates 95% of Indian listed companies. Saurabh Mukherjea's Consistent Compounders Portfolio specifically targets businesses with ROCE consistently above 25% and minimal debt. The {fmt_pct(roce)} ROCE places this firmly in what Marcellus calls 'the clean and well-lit room' of Indian businesses. Marcellus holds positions for 3-5 years minimum, relying on earnings compounding rather than multiple expansion to generate returns.",
        "ben_graham": f"From a Graham perspective, {name} presents the kind of quantitative value opportunity that the 'Father of Value Investing' sought. Graham's Intelligent Investor framework demands a margin of safety — the gap between intrinsic value and market price. {'The P/B of ' + f'{pb:.1f}x' + ' indicates the market values this business at ' + (f'{pb:.1f}x' + ' book value') if pb else ''} Graham would calculate intrinsic value based on normalised earnings power and asset values, investing only when a sufficient discount to this value exists.",
        "vijay_kedia": f"Vijay Kedia's SMILE framework — Small in size, Medium in experience, Large in aspiration, Extra-large in market potential — is the lens through which this selection must be evaluated. {'With market cap of ₹' + f'{mc:.0f}' + ' Cr, this qualifies as the small/mid cap focus Kedia demands.' if mc < 20000 else ''} Kedia specifically avoids large caps, believing the asymmetric return potential exists only in companies that can grow 10x from their current size. He would examine whether this business addresses an Indian market that is still at early stages of development.",
        "peter_lynch": f"Peter Lynch's GARP (Growth at Reasonable Price) framework evaluates {name} through the PEG ratio lens. Lynch famously said 'invest in what you know' — businesses with clear, understandable competitive advantages. {f'Revenue growth of {fmt_pct(rev_g)} demonstrates the earnings trajectory Lynch required.' if rev_g else ''} Lynch ran Fidelity Magellan to 29% annual returns by finding companies where growth was consistently underpriced by the market. He looked for boring businesses with exceptional fundamentals that institutional analysts ignored.",
        "charlie_munger": f"Charlie Munger's investment philosophy centres on what he called 'wonderful businesses at fair prices' — companies with such durable competitive advantages that they can compound capital at high rates for decades without requiring additional capital. The {fmt_pct(roce)} ROCE is the metric Munger cared about most, as it measures raw business efficiency. Munger held extraordinarily few positions, demanding that each one meet an exceptionally high bar for business quality and management integrity.",
        "parag_parikh": f"Parag Parikh Financial Advisory Services applies a behavioural finance lens to portfolio construction. PPFAS specifically seeks owner-operators — businesses where promoters have significant equity stake and think like owners, not employees. {f'The promoter holding of {fmt_pct(ph)} reflects this alignment.' if ph else ''} The fund is known for its low turnover and willingness to hold through market volatility, an approach that requires genuine conviction in the underlying business quality.",
    }

    full_analysis = analyses.get(profile_id,
        f"{name} was selected based on its strong performance against {profile_name}'s investment criteria. The key metrics that qualified this stock demonstrate the business quality this investing style demands."
    )

    return {
        "full_analysis": full_analysis,
        "qualifying_metrics": qualifying_metrics[:5],
        "one_liner": f"Selected for {fmt_pct(roe)} ROE{', ' + fmt_pct(opm) + ' OPM' if opm else ''}{', low debt' if de is not None and de < 0.3 else ''}",
    }


def generate_why_not(profile_id: str, near_misses: list, sector_avgs: dict) -> list:
    """Explain why stocks almost made it but didn't qualify."""
    results = []
    for stock in near_misses[:3]:
        name = stock.get("company_name", stock.get("symbol", ""))
        symbol = stock.get("symbol", "")
        ps = score_profile(stock, profile_id, sector_avgs)
        score = ps["score"]

        # Find the weakest metric
        roe = stock.get("roe"); roce = stock.get("roce")
        de = stock.get("debt_to_equity"); opm = stock.get("operating_margins")
        pe = stock.get("pe_ratio"); ph = stock.get("promoter_holding")

        def pct(v): return v * 100 if v else None

        reasons = []
        if profile_id == "buffett":
            if roe and pct(roe) < 15: reasons.append(f"ROE of {pct(roe):.1f}% falls below Buffett's 20% threshold for consistent capital efficiency")
            if de and de > 0.5: reasons.append(f"Debt/Equity of {de:.1f}x exceeds Buffett's preference for near debt-free balance sheets")
            if pe and pe > 35: reasons.append(f"P/E of {pe:.1f}x suggests the market has already priced in the quality premium")
        elif profile_id == "marcellus":
            if de and de > 0.3: reasons.append(f"Debt/Equity of {de:.1f}x fails Marcellus's zero-debt forensic filter")
            if roce and pct(roce) < 20: reasons.append(f"ROCE of {pct(roce):.1f}% below Marcellus's 25% minimum threshold")
        elif profile_id == "rj":
            if ph and ph < 0.35: reasons.append(f"Promoter holding of {pct(ph):.1f}% below RJ's conviction threshold")
            if roe and pct(roe) < 18: reasons.append(f"ROE of {pct(roe):.1f}% insufficient for RJ's growth compounder criteria")
        else:
            if not reasons:
                reasons.append(f"Composite score of {score}/100 did not meet the minimum threshold for this profile")

        if reasons:
            results.append({
                "symbol": symbol,
                "company_name": name,
                "score": score,
                "reason": reasons[0],
                "learn_id": "roe" if "ROE" in (reasons[0] if reasons else "") else "debt-equity" if "Debt" in (reasons[0] if reasons else "") else "roce",
            })
    return results


def build_entry(symbol, raw, sector_avgs=None):
    if sector_avgs is None: sector_avgs = {}
    # Ensure sector is set correctly
    if not raw.get("sector") or raw.get("sector") == "Unknown":
        raw["sector"] = NSE_SECTOR_MAP.get(symbol, "Unknown")
    scoring = score_stock(raw, sector_avgs)
    matching_profiles = get_matching_profiles(raw, sector_avgs)
    sector_comparison = get_sector_comparison(raw, sector_avgs)
    return {
        "symbol": symbol,
        "company_name": raw.get("company_name", symbol),
        "sector": raw.get("sector", "Unknown"),
        "industry": raw.get("industry", "Unknown"),
        "description": raw.get("description", ""),
        "website": raw.get("website", ""),
        "employees": raw.get("employees"),
        "current_price": raw.get("current_price"),
        "price_change_pct": raw.get("price_change_pct"),
        "market_cap": raw.get("market_cap"),
        "52w_high": raw.get("52w_high"),
        "52w_low": raw.get("52w_low"),
        "avg_volume": raw.get("avg_volume"),
        "pe_ratio": raw.get("pe_ratio"),
        "pb_ratio": raw.get("pb_ratio"),
        "ev_ebitda": raw.get("ev_ebitda"),
        "peg_ratio": raw.get("peg_ratio"),
        "book_value": raw.get("book_value"),
        "roe": raw.get("roe"),
        "roa": raw.get("roa"),
        "roce": raw.get("roce"),
        "debt_to_equity": raw.get("debt_to_equity"),
        "operating_margins": raw.get("operating_margins"),
        "net_margins": raw.get("net_margins"),
        "revenue_growth": raw.get("revenue_growth"),
        "earnings_growth": raw.get("earnings_growth"),
        "current_ratio": raw.get("current_ratio"),
        "quick_ratio": raw.get("quick_ratio"),
        "interest_coverage": raw.get("interest_coverage"),
        "dividend_yield": raw.get("dividend_yield"),
        "eps": raw.get("eps"),
        "beta": raw.get("beta"),
        "fcf": raw.get("fcf"),
        "promoter_holding": raw.get("promoter_holding"),
        "institutional_holding": raw.get("institutional_holding"),
        "analyst_recommendation": raw.get("analyst_recommendation"),
        "target_price": raw.get("target_price"),
        "num_analysts": raw.get("num_analysts"),
        "quarterly_revenue": raw.get("quarterly_revenue", []),
        "quarterly_profit": raw.get("quarterly_profit", []),
        "annual_revenue": raw.get("annual_revenue", []),
        "annual_profit": raw.get("annual_profit", []),
        "pros": raw.get("pros", []),
        "cons": raw.get("cons", []),
        "data_source": raw.get("data_source", "unknown"),
        "scoring": scoring,
        "conviction": conviction_tier(scoring["composite"]),
        "matching_profiles": matching_profiles,
        "sector_comparison": sector_comparison,
        "cached_at": datetime.now().isoformat(),
    }


# ─── Education content ────────────────────────────────────────────────────────
EDUCATION_CONTENT = {
    "metrics": [
        {
            "id": "pe-ratio", "title": "Price to Earnings (P/E) Ratio",
            "category": "metrics", "difficulty": "beginner", "read_time": 2,
            "summary": "How much you pay for every rupee of profit a company earns.",
            "content": "The P/E ratio tells you how expensive a stock is relative to its earnings. If a company earns Rs 10 per share and the stock costs Rs 200, the P/E is 20x — you are paying 20 rupees for every 1 rupee of annual profit.\n\nA lower P/E generally means the stock is cheaper. But cheap is not always good — a low P/E can mean a business is declining.\n\nIn India, the Nifty 50 average P/E is around 20-22x in normal times. Consumer companies like Nestle trade at 70-80x because investors expect consistent growth for decades. PSU banks trade at 5-8x because growth is slower.\n\nThe key insight: always compare P/E to the company's own history AND to sector peers. A pharma company at P/E 30x might be cheap while a bank at P/E 15x might be expensive — it depends on the sector norm.",
            "example_stock": "NESTLEIND",
            "example_text": "Nestle India trades at ~70x P/E because it has grown earnings consistently for 30 years. Investors pay a premium for that predictability.",
            "watch_out": "A very low P/E can be a value trap — the market might be pricing in declining earnings ahead.",
            "related": ["pb-ratio", "peg-ratio", "ev-ebitda"],
        },
        {
            "id": "roe", "title": "Return on Equity (ROE)",
            "category": "metrics", "difficulty": "beginner", "read_time": 2,
            "summary": "How efficiently a company uses shareholder money to generate profit.",
            "content": "ROE measures how much profit a company generates from the money shareholders have invested. If shareholders put in Rs 100 and the company earns Rs 20 profit, ROE is 20%.\n\nROE above 20% is generally excellent. It means the company is a money-making machine — for every Rs 100 invested, it generates Rs 20 of profit every year.\n\nWarren Buffett specifically looks for companies with consistently high ROE without excessive debt. Companies like Asian Paints and HDFC Bank have maintained 20%+ ROE for decades — this is rare and extremely valuable.\n\nImportant: high ROE achieved through high debt is dangerous. A company borrowing heavily can artificially inflate ROE. Always check debt levels alongside ROE.",
            "example_stock": "ASIANPAINT",
            "example_text": "Asian Paints has maintained ROE above 25% for over 15 years with virtually zero debt — a hallmark of genuine business quality.",
            "watch_out": "ROE inflated by debt (high D/E ratio) is misleading. Always check ROCE alongside ROE.",
            "related": ["roce", "debt-equity", "return-on-assets"],
        },
        {
            "id": "roce", "title": "Return on Capital Employed (ROCE)",
            "category": "metrics", "difficulty": "intermediate", "read_time": 2,
            "summary": "The purest measure of how well a business uses all its capital.",
            "content": "ROCE is considered a better quality measure than ROE because it accounts for ALL capital — both equity and debt. It answers: for every rupee the business uses (from any source), how much profit does it generate?\n\nROCE above 20% consistently is the hallmark of truly great businesses. Marcellus Investment's entire strategy is built around finding companies with ROCE above 25% for 10 consecutive years.\n\nThe difference between ROE and ROCE: ROE can be gamed by taking on debt. ROCE cannot be faked — it measures raw business efficiency regardless of financing structure.\n\nCharlie Munger once said: show me a business with 25% ROCE sustained over 20 years, and I will show you a business that has a real competitive moat.",
            "example_stock": "PIDILITIND",
            "example_text": "Pidilite (Fevicol) has maintained ROCE above 30% for decades — because its brand moat allows pricing power with minimal capital reinvestment.",
            "watch_out": "Capital-intensive businesses like steel and cement will naturally have lower ROCE. Always compare within the same sector.",
            "related": ["roe", "operating-margins", "moat"],
        },
        {
            "id": "debt-equity", "title": "Debt to Equity Ratio",
            "category": "metrics", "difficulty": "beginner", "read_time": 2,
            "summary": "How much debt a company has compared to shareholder funds.",
            "content": "The D/E ratio compares total debt to shareholders equity. A D/E of 0.5 means the company has Rs 50 of debt for every Rs 100 of shareholder money.\n\nDebt is not always bad — for infrastructure companies and banks, leverage is part of the business model. But for consumer and technology companies, a clean balance sheet (D/E below 0.3) is a strong quality signal.\n\nThe biggest Indian business failures in the last decade — IL&FS, DHFL, Reliance Communications — all had one thing in common: extreme leverage.\n\nChandrakant Sampat, India's original value investor, made debt-free balance sheets his single non-negotiable criterion. He believed that debt-free companies could survive any downturn and emerge stronger.",
            "example_stock": "HDFCBANK",
            "example_text": "HDFC Bank carries significant debt (it is a bank — that is the business model), but manages it with exceptional discipline. For banks, look at NPAs and Capital Adequacy instead of D/E.",
            "watch_out": "Zero debt is not always optimal — some debt can improve returns. The question is whether the business generates returns above its cost of debt.",
            "related": ["roe", "interest-coverage", "current-ratio"],
        },
        {
            "id": "operating-margins", "title": "Operating Profit Margin (OPM)",
            "category": "metrics", "difficulty": "beginner", "read_time": 2,
            "summary": "What percentage of revenue becomes operating profit.",
            "content": "Operating margin tells you how much profit a business keeps from its revenues after paying all operating costs (but before interest and taxes).\n\nA 20% OPM means for every Rs 100 in revenue, Rs 20 is operating profit. The remaining Rs 80 went to raw materials, employees, rent, and other costs.\n\nHigh and stable operating margins indicate pricing power — the company can charge what it wants without customers switching. Nestle India, Asian Paints, and Pidilite consistently maintain 20%+ OPM because of their brand strength.\n\nImproving margins over time is a very bullish signal — it means the business is scaling efficiently or gaining pricing power.",
            "example_stock": "BRITANNIA",
            "example_text": "Britannia increased OPM from 5% in 2015 to over 15% by 2022 — a margin expansion story that created enormous shareholder value.",
            "watch_out": "Compare margins within sectors. A 5% margin is great for a commodity trader but terrible for a software company.",
            "related": ["roe", "roce", "revenue-growth"],
        },
        {
            "id": "pb-ratio", "title": "Price to Book (P/B) Ratio",
            "category": "metrics", "difficulty": "intermediate", "read_time": 2,
            "summary": "What premium the market charges over the company's net assets.",
            "content": "Book value is what shareholders would theoretically get if the company sold all its assets and paid all its debts today. P/B compares the market price to this book value.\n\nP/B below 1 means the market values the company less than its net assets — often a signal of deep value or serious business problems.\n\nBenjamin Graham specifically looked for stocks trading below 1.5x book value as part of his margin of safety framework.\n\nFor asset-heavy businesses like banks and manufacturing, P/B is meaningful. For software companies with few physical assets, P/B is less relevant — their value lies in intellectual property and people, not balance sheet assets.",
            "example_stock": "SBIN",
            "example_text": "SBI has historically traded between 0.8x and 1.5x book value — reflecting investor uncertainty about NPAs. When PSU banks trade below book, it has historically been a good entry point.",
            "watch_out": "A low P/B can mean the assets are impaired (loans that won't be repaid, inventory that won't be sold). The quality of assets matters as much as the price.",
            "related": ["pe-ratio", "graham-number", "margin-of-safety"],
        },
        {
            "id": "peg-ratio", "title": "PEG Ratio",
            "category": "metrics", "difficulty": "intermediate", "read_time": 2,
            "summary": "P/E ratio adjusted for growth — finds growth stocks at reasonable prices.",
            "content": "The PEG ratio was popularized by Peter Lynch. It divides the P/E ratio by the earnings growth rate to find growth stocks that are not overvalued.\n\nPEG = P/E divided by Earnings Growth Rate\n\nA PEG below 1 means you are paying less than the growth justifies — Lynch considered this the sweet spot. A PEG above 2 means you are paying a significant premium for expected growth.\n\nExample: A stock with P/E of 30x growing earnings at 35% per year has a PEG of 0.86 — reasonable. A stock with P/E of 50x growing at 15% has a PEG of 3.3 — expensive.\n\nLynch used this to find companies like Dunkin Donuts and Taco Bell early — boring businesses with consistent growth that nobody was excited about.",
            "example_stock": "BAJFINANCE",
            "example_text": "Bajaj Finance historically traded at high P/E multiples that seemed expensive, but its consistently high earnings growth kept PEG reasonable.",
            "watch_out": "PEG relies on growth estimates which can be wrong. Be conservative with growth assumptions.",
            "related": ["pe-ratio", "earnings-growth", "peter-lynch"],
        },
        {
            "id": "ev-ebitda", "title": "EV/EBITDA",
            "category": "metrics", "difficulty": "advanced", "read_time": 3,
            "summary": "Enterprise value relative to operating earnings — the professional's valuation metric.",
            "content": "EV/EBITDA is widely used by professional investors and investment bankers because it is capital-structure neutral — it does not matter if the company is funded by debt or equity.\n\nEV (Enterprise Value) = Market Cap + Total Debt - Cash. This represents the true cost of buying the whole business.\n\nEBITDA = Earnings Before Interest, Tax, Depreciation and Amortization. A proxy for operating cash generation.\n\nEV/EBITDA below 10x is generally considered cheap, above 20x expensive — but varies hugely by sector and growth rate.\n\nWhy better than P/E: P/E can be distorted by interest costs and tax structures. EV/EBITDA cuts through these to show the underlying business value.",
            "example_stock": "TATAMOTORS",
            "example_text": "Auto companies with high debt can look cheap on P/E but expensive on EV/EBITDA once debt is accounted for. EV/EBITDA gives the honest picture.",
            "watch_out": "EBITDA ignores capex requirements. For capital-intensive businesses, EV/FCF (Free Cash Flow) is even better.",
            "related": ["pe-ratio", "free-cash-flow", "enterprise-value"],
        },
        {
            "id": "dividend-yield", "title": "Dividend Yield",
            "category": "metrics", "difficulty": "beginner", "read_time": 2,
            "summary": "Annual cash returned to shareholders as a percentage of stock price.",
            "content": "Dividend yield measures the annual dividend payment as a percentage of the current stock price. A Rs 200 stock paying Rs 10 annual dividend has a 5% yield.\n\nHigh dividend yield stocks are favored by income investors — retirees and conservative investors who need regular cash flow.\n\nBut yield chasing can be dangerous. A very high yield (above 6-7%) sometimes signals that investors expect the dividend to be cut — the stock price has fallen because of business problems.\n\nThe best dividend stocks are ones that consistently grow their dividend over time — companies like ITC, Coal India, and Power Grid have done this for years.",
            "example_stock": "COALINDIA",
            "example_text": "Coal India has maintained dividend yields of 5-8% for years, making it a favourite of income investors despite questions about long-term coal demand.",
            "watch_out": "A dividend yield that looks abnormally high is often a warning sign — check if the company can sustain the payout from its free cash flow.",
            "related": ["free-cash-flow", "payout-ratio", "income-investing"],
        },
    ],
    "strategies": [
        {
            "id": "value-investing", "title": "Value Investing — Buy What Others Ignore",
            "category": "strategies", "difficulty": "beginner", "read_time": 4,
            "summary": "The art of buying good businesses at prices below what they are actually worth.",
            "content": "Value investing was invented by Benjamin Graham and perfected by Warren Buffett. The core idea is simple: stocks are not just ticker symbols — they represent ownership in real businesses. And like any asset, businesses can be bought cheaply or expensively.\n\nThe market is not always rational. Fear causes prices to drop below intrinsic value. Greed causes prices to rise above it. Value investors profit from this irrationality by buying when others are fearful and selling when others are greedy.\n\nIn India, the best value opportunities have historically come during market crashes (2008, 2020), sector downturns (IT in 2001, pharma in 2016), and company-specific bad news that turns out to be temporary.\n\nRamesh Damani famously bought VST Industries (cigarettes) and Aptech when they were deeply out of favour. Both went on to deliver multibagger returns.\n\nKey principles:\n1. Always buy with a margin of safety — pay less than intrinsic value\n2. Think like a business owner, not a trader\n3. Be patient — value takes time to be recognized\n4. Distinguish between temporary problems and permanent ones",
            "related": ["pe-ratio", "pb-ratio", "margin-of-safety"],
        },
        {
            "id": "quality-investing", "title": "Quality Investing — Great Businesses at Fair Prices",
            "category": "strategies", "difficulty": "intermediate", "read_time": 4,
            "summary": "Finding businesses with durable competitive advantages and holding them for decades.",
            "content": "Quality investing evolved from value investing. While Graham looked for cheap businesses, Buffett (influenced by Charlie Munger) evolved to paying fair prices for genuinely great businesses.\n\nThe insight: a great business at a fair price is better than a mediocre business at a cheap price. Compounding works best when the underlying business is excellent.\n\nWhat makes a quality business in India?\n- Consistent high ROCE (above 20%) for 10+ years\n- Pricing power — can raise prices without losing customers\n- Low debt — does not need external capital to grow\n- Strong management with integrity and long tenure\n- Large addressable market with long growth runway\n\nMarcellus Investment's CCP (Consistent Compounders Portfolio) is built entirely on quality investing principles. Their universe of stocks that pass all their filters is surprisingly small — fewer than 30 companies in all of India.",
            "related": ["roce", "moat", "marcellus"],
        },
        {
            "id": "growth-investing", "title": "Growth Investing — Riding the Earnings Tide",
            "category": "strategies", "difficulty": "intermediate", "read_time": 3,
            "summary": "Investing in companies growing faster than the market and holding through the growth phase.",
            "content": "Growth investors focus on businesses growing revenue and earnings significantly faster than the market. They are willing to pay premium valuations (high P/E) because fast compounding justifies higher prices.\n\nThe key metric for growth investors is earnings growth rate. Peter Lynch looked for companies growing earnings at 20-25% per year with PEG ratios below 1.\n\nIn India, the biggest growth stories of the last decade include Bajaj Finance (NBFC growth), HDFC Bank (banking penetration), Asian Paints (urbanization), and recently Zomato/Nykaa (digital consumption).\n\nThe risk: growth can disappoint. A company priced for 30% growth trading at 50x P/E that delivers only 15% growth will see its stock fall sharply — the multiple compresses AND earnings disappoint.",
            "related": ["peg-ratio", "earnings-growth", "peter-lynch"],
        },
        {
            "id": "moat", "title": "Competitive Moats — What Protects a Business",
            "category": "strategies", "difficulty": "intermediate", "read_time": 4,
            "summary": "Why some businesses can earn high returns indefinitely while others cannot.",
            "content": "Warren Buffett popularized the concept of the economic moat — a durable competitive advantage that protects a business from competitors, just like a castle moat protects from invaders.\n\nThe 5 types of moats:\n\n1. Brand moat: Customers pay premium because they trust the brand. Fevicol (Pidilite) — no contractor will risk using a cheaper alternative because failure is too costly.\n\n2. Switching costs: Once adopted, it is painful to switch. Tally accounting software — millions of businesses have years of data in Tally, making migration expensive.\n\n3. Network effects: More users make the product more valuable. NSE — more traders attract more liquidity, which attracts more traders.\n\n4. Cost advantage: Structurally lower costs than competitors. DMart — EDLP model, owned stores, no frills, passes savings to customers.\n\n5. Regulatory moat: Government licences or approvals protect the business. CAMS — processes 70% of mutual fund transactions in India because of SEBI approvals.",
            "related": ["quality-investing", "roce", "buffett"],
        },
    ],
    "beginners": [
        {
            "id": "what-is-a-stock", "title": "What is a Stock?",
            "category": "beginners", "difficulty": "beginner", "read_time": 2,
            "summary": "Owning a stock means owning a small piece of a real business.",
            "content": "When you buy a share of Reliance Industries, you become a part-owner of one of India's largest businesses — its refineries, retail stores, Jio network, and everything else.\n\nA stock is not just a price on a screen. It represents real ownership in a real business with real assets, employees, customers, and profits.\n\nCompanies issue shares to raise money from the public. In return, shareholders own a proportional part of the business and share in its profits (through dividends) and growth (through rising stock price).\n\nThe NSE (National Stock Exchange) and BSE (Bombay Stock Exchange) are the marketplaces where these shares are bought and sold every day.\n\nWhy stocks beat other investments over time: businesses generate real economic value. A good business earns returns on capital that exceed inflation. Over 20-30 years, owning great businesses is the most powerful way to build wealth.",
            "related": ["market-cap", "how-markets-work", "getting-started"],
        },
        {
            "id": "market-cap", "title": "What is Market Capitalisation?",
            "category": "beginners", "difficulty": "beginner", "read_time": 2,
            "summary": "The total value the market places on a company.",
            "content": "Market capitalisation (market cap) is simply the total value of all shares of a company.\n\nMarket Cap = Share Price multiplied by Total Number of Shares\n\nIf Reliance has 1,350 crore shares and the price is Rs 2,800, the market cap is Rs 37,80,000 crore — or about Rs 37.8 lakh crore.\n\nIn India, companies are broadly classified by market cap:\n- Large Cap: Top 100 companies by market cap (above Rs 20,000 Cr)\n- Mid Cap: Companies ranked 101-250 (Rs 5,000-20,000 Cr)\n- Small Cap: Companies ranked below 250 (below Rs 5,000 Cr)\n\nSmall cap stocks can grow faster (more room to grow) but are riskier (less stable, less liquid). Large caps are safer but can be slower movers.",
            "related": ["what-is-a-stock", "large-mid-small-cap", "liquidity"],
        },
        {
            "id": "how-to-read-annual-report", "title": "How to Read an Annual Report in 10 Minutes",
            "category": "beginners", "difficulty": "intermediate", "read_time": 5,
            "summary": "The 5 things you must check in every annual report before investing.",
            "content": "Every listed company in India must publish an annual report. Most retail investors never read them. This is your edge.\n\n1. The MD's Letter to Shareholders (5 minutes): Read what the management is saying about the business, challenges, and outlook. Is the tone honest? Are they acknowledging problems or just celebrating wins?\n\n2. The P&L Statement: Is revenue growing? Are margins expanding or contracting? Is profit growing faster than revenue (good) or slower (bad)?\n\n3. The Balance Sheet: Is debt increasing every year? Is cash building up? Are receivables growing faster than revenue (warning sign)?\n\n4. The Cash Flow Statement: The most honest financial statement. Is the company actually collecting cash from its operations? A company can show accounting profits while being cash flow negative — always check.\n\n5. Related Party Transactions: Are there large transactions with promoter-owned companies? This is how money gets siphoned out. Keep this small.\n\nBonus: The auditor's notes — any qualifications in the audit report are serious warning signs.",
            "related": ["financial-statements", "red-flags", "promoter-holding"],
        },
    ],
}


# ─── Cache functions ──────────────────────────────────────────────────────────
def save_cache():
    try:
        with _cache_lock:
            data = {"cache_time": _cache_time.isoformat() if _cache_time else None, "stocks": _cache}
        with open(CACHE_FILE, "w") as f: json.dump(data, f)
        with open(SECTOR_CACHE_FILE, "w") as f: json.dump(_sector_averages, f)
        print(f"Saved {len(_cache)} stocks to disk")
    except Exception as e: print(f"Save failed: {e}")


def load_cache():
    global _cache, _cache_time, _sector_averages
    try:
        if not os.path.exists(CACHE_FILE): return False
        with open(CACHE_FILE, "r") as f: data = json.load(f)
        stocks = data.get("stocks", {}); ct = data.get("cache_time")
        if not stocks: return False
        with _cache_lock:
            _cache = stocks
            _cache_time = datetime.fromisoformat(ct) if ct else datetime.now()
        if os.path.exists(SECTOR_CACHE_FILE):
            with open(SECTOR_CACHE_FILE, "r") as f: _sector_averages = json.load(f)
        age_h = (datetime.now() - _cache_time).total_seconds() / 3600
        print(f"Loaded cache: {len(stocks)} stocks, {age_h:.1f}h old")
        return True
    except Exception as e: print(f"Load failed: {e}"); return False


def refresh_cache():
    global _cache, _cache_time, _is_refreshing, _refresh_progress, _sector_averages
    if _is_refreshing: return
    _is_refreshing = True
    universe = NIFTY_500
    _refresh_progress = {"done": 0, "total": len(universe)}
    print(f"\nCache refresh — {len(universe)} stocks via yfinance\n")

    new_cache = {}
    for i, symbol in enumerate(universe):
        try:
            print(f"  [{i+1}/{len(universe)}] {symbol}...", end=" ", flush=True)
            raw = fetch_stock_data(symbol)
            if raw and raw.get("current_price"):
                entry = build_entry(symbol, raw, _sector_averages)
                new_cache[symbol] = entry
                print(f"✓ score={entry['scoring']['composite']:.0f} [{raw.get('data_source','?')}]")
            else:
                print("✗ no data")
            _refresh_progress["done"] = i + 1

            if (i + 1) % 30 == 0 and new_cache:
                with _cache_lock:
                    _cache.update(new_cache)
                    _cache_time = datetime.now()
                avgs = compute_sector_averages(new_cache)
                with _cache_lock: _sector_averages = avgs
                save_cache()

            time.sleep(0.5)  # yfinance is faster than scraping
        except Exception as e:
            print(f"✗ {e}"); _refresh_progress["done"] = i + 1; time.sleep(1)

    # Final sector averages
    sector_avgs = compute_sector_averages(new_cache)
    # Recompute all entries with final sector averages
    for sym in new_cache:
        new_cache[sym]["sector_comparison"] = get_sector_comparison(new_cache[sym], sector_avgs)
        new_cache[sym]["scoring"] = score_stock(new_cache[sym], sector_avgs)
        new_cache[sym]["conviction"] = conviction_tier(new_cache[sym]["scoring"]["composite"])
        new_cache[sym]["matching_profiles"] = get_matching_profiles(new_cache[sym], sector_avgs)

    with _cache_lock:
        _cache = new_cache
        _cache_time = datetime.now()
        _sector_averages = sector_avgs

    save_cache()
    print(f"\nCache complete: {len(new_cache)} stocks\n")
    _is_refreshing = False


@app.on_event("startup")
async def startup():
    global _sector_averages
    loaded = load_cache()
    if loaded:
        age_h = (datetime.now() - _cache_time).total_seconds() / 3600
        # Apply hardcoded sectors to cached stocks first
        updated = 0
        with _cache_lock:
            for sym, stock in _cache.items():
                if stock.get("sector", "Unknown") == "Unknown" and sym in NSE_SECTOR_MAP:
                    stock["sector"] = NSE_SECTOR_MAP[sym]
                    updated += 1
        if updated: print(f"Applied hardcoded sectors to {updated} stocks")
        # Always recompute sector averages
        with _cache_lock:
            avgs = compute_sector_averages(_cache)
        with _cache_lock:
            _sector_averages = avgs
        print(f"Computed sector averages: {len(_sector_averages)} sectors")
        # Rebuild if stale or missing merged data
        sample = list(_cache.values())[:5] if _cache else []
        needs_rebuild = age_h > 8 or any(s.get("data_source") not in ("merged","yfinance") for s in sample)
        if needs_rebuild:
            print(f"Cache rebuild needed (age={age_h:.1f}h)")
            threading.Thread(target=refresh_cache, daemon=True).start()
        else:
            print(f"Cache fresh ({age_h:.1f}h, {len(_sector_averages)} sectors indexed)")
    else:
        threading.Thread(target=refresh_cache, daemon=True).start()


# ─── Routes ───────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "app": "stocks.ai", "version": "12.0.0",
        "cached_stocks": len(_cache), "refreshing": _is_refreshing,
        "progress": f"{_refresh_progress['done']}/{_refresh_progress['total']}",
        "cache_age": str(datetime.now() - _cache_time).split(".")[0] if _cache_time else "warming",
        "profiles": len(INVESTOR_PROFILES),
        "sectors_indexed": len(_sector_averages),
    }

@app.get("/api/cache/status")
def cache_status():
    return {
        "ready": len(_cache) > 0, "count": len(_cache),
        "refreshing": _is_refreshing, "progress": _refresh_progress,
        "last_updated": _cache_time.isoformat() if _cache_time else None,
    }

@app.get("/api/cache/refresh")
def trigger_refresh(bg: BackgroundTasks):
    if _is_refreshing: return {"message": "Already refreshing"}
    bg.add_task(refresh_cache)
    return {"message": "Refresh started"}

@app.get("/api/profiles")
def get_profiles():
    return {"profiles": INVESTOR_PROFILES, "count": len(INVESTOR_PROFILES)}

@app.get("/api/education")
def get_education(category: Optional[str] = None):
    all_content = []
    for cat, items in EDUCATION_CONTENT.items():
        for item in items:
            if not category or item["category"] == category:
                all_content.append({k: v for k, v in item.items() if k != "content"})
    return {"content": all_content, "categories": list(EDUCATION_CONTENT.keys())}

@app.get("/api/education/{content_id}")
def get_education_item(content_id: str):
    for cat, items in EDUCATION_CONTENT.items():
        for item in items:
            if item["id"] == content_id:
                return item
    raise HTTPException(404, f"Content '{content_id}' not found")

@app.get("/api/sector-averages")
def sector_averages():
    global _sector_averages
    # If empty, recompute on the fly
    if not _sector_averages and _cache:
        with _cache_lock:
            avgs = compute_sector_averages(_cache)
        with _cache_lock:
            _sector_averages = avgs
        print(f"On-demand sector avg computation: {len(_sector_averages)} sectors")
    return {"sectors": _sector_averages, "count": len(_sector_averages)}

@app.get("/api/symbols")
def get_symbols():
    """Fast endpoint returning all cached symbols for autocomplete."""
    with _cache_lock:
        symbols = [
            {
                "symbol": v["symbol"],
                "name": v["company_name"],
                "sector": v.get("sector", "Unknown"),
            }
            for v in _cache.values()
            if v.get("symbol")
        ]
    # Also include the full universe even if not cached yet
    universe_symbols = [{"symbol": s, "name": s, "sector": ""} for s in NIFTY_500 if s not in {x["symbol"] for x in symbols}]
    return {"symbols": symbols + universe_symbols, "count": len(symbols) + len(universe_symbols)}

@app.get("/api/stock/{symbol}")
def get_stock(symbol: str):
    symbol = symbol.upper().strip()
    with _cache_lock:
        if symbol in _cache: return _cache[symbol]
    raw = fetch_stock_data(symbol)
    if not raw or not raw.get("current_price"):
        raise HTTPException(404, f"Could not find {symbol}")
    with _cache_lock: avgs = dict(_sector_averages)
    entry = build_entry(symbol, raw, avgs)
    with _cache_lock: _cache[symbol] = entry
    return entry

@app.get("/api/screen")
def screen(
    min_score: float = Query(40),
    sector: Optional[str] = Query(None),
    conviction: Optional[str] = Query(None),
    profile: Optional[str] = Query(None),
    limit: int = Query(30, le=100),
    min_market_cap: Optional[float] = Query(None),
    max_pe: Optional[float] = Query(None),
    min_roe: Optional[float] = Query(None),
):
    with _cache_lock: stocks = list(_cache.values())
    if not stocks:
        done = _refresh_progress.get("done", 0); total = _refresh_progress.get("total", 0)
        return {"count": 0, "stocks": [], "warming": True,
                "message": f"Loading... {done}/{total} done. Try again shortly."}
    results = []
    for s in stocks:
        if s["scoring"]["composite"] < min_score: continue
        if conviction and conviction.lower() not in s["conviction"].lower(): continue
        if sector and sector.lower() not in (s.get("sector") or "").lower(): continue
        if min_market_cap and (s.get("market_cap") or 0) < min_market_cap * 1e7: continue
        if max_pe and s.get("pe_ratio") and s["pe_ratio"] > max_pe: continue
        if min_roe and s.get("roe") and s["roe"] * 100 < min_roe: continue
        if profile:
            with _cache_lock: avgs = dict(_sector_averages)
            ps = score_profile(s, profile, avgs)
            if ps["score"] < 35: continue
            s = dict(s); s["profile_score"] = ps["score"]; s["profile_reasons"] = ps["reasons"]
        results.append(s)
    results.sort(key=lambda x: x.get("profile_score", x["scoring"]["composite"]), reverse=True)
    return {
        "count": len(results), "stocks": results[:limit],
        "total_cached": len(stocks),
        "cache_age": str(datetime.now() - _cache_time).split(".")[0] if _cache_time else "unknown",
    }

@app.get("/api/watchlist")
def watchlist(symbols: str = Query(...)):
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()][:20]
    results, missing = [], []
    with _cache_lock: cached = dict(_cache)
    for sym in symbol_list:
        if sym in cached: results.append(cached[sym])
        else: missing.append(sym)
    with _cache_lock: avgs = dict(_sector_averages)
    for sym in missing:
        try:
            raw = fetch_stock_data(sym)
            if raw and raw.get("current_price"):
                entry = build_entry(sym, raw, avgs)
                with _cache_lock: _cache[sym] = entry
                results.append(entry)
            time.sleep(0.3)
        except Exception as e: print(f"Error {sym}: {e}")
    results.sort(key=lambda x: x["scoring"]["composite"], reverse=True)
    return {"count": len(results), "stocks": results}

@app.get("/api/market/pulse")
def market_pulse():
    nifty_pe = fetch_nifty_pe()
    market = get_market_valuation(nifty_pe)
    with _cache_lock:
        stocks = list(_cache.values())
    if not stocks:
        return {"nifty_pe": nifty_pe, "market": market, "strong_buys": [], "near_lows": [], "top_sectors": [], "total_indexed": 0}
    strong_buys = sorted(
        [s for s in stocks if s["conviction"] in ("Strong Buy", "Buy")],
        key=lambda x: x["scoring"]["composite"], reverse=True
    )[:6]
    near_lows = []
    for s in stocks:
        price = s.get("current_price"); low = s.get("52w_low"); high = s.get("52w_high")
        if price and low and high and high > low:
            pct_from_low = ((price - low) / (high - low)) * 100
            if pct_from_low < 25:
                near_lows.append({**s, "pct_from_low": round(pct_from_low, 1)})
    near_lows = sorted(near_lows, key=lambda x: x["scoring"]["composite"], reverse=True)[:5]
    sector_counts = {}
    for s in stocks:
        sec = s.get("sector", "Unknown")
        if sec != "Unknown": sector_counts[sec] = sector_counts.get(sec, 0) + 1
    top_sectors = sorted(sector_counts.items(), key=lambda x: x[1], reverse=True)[:6]
    return {
        "nifty_pe": nifty_pe,
        "market": market,
        "strong_buys": [{"symbol": s["symbol"], "company_name": s["company_name"],
                         "score": s["scoring"]["composite"], "sector": s.get("sector"), "conviction": s["conviction"]} for s in strong_buys],
        "near_lows": [{"symbol": s["symbol"], "company_name": s["company_name"],
                       "pct_from_low": s["pct_from_low"], "score": s["scoring"]["composite"]} for s in near_lows],
        "top_sectors": [{"sector": s[0], "count": s[1]} for s in top_sectors],
        "total_indexed": len(stocks),
        "last_updated": _cache_time.isoformat() if _cache_time else None,
    }


@app.post("/api/portfolio/build")
def build_portfolio_endpoint(
    profile_id: str = Query(...),
    capital: float = Query(...),
    limit: int = Query(None),
    mode: str = Query("single"),
):
    nifty_pe = fetch_nifty_pe()

    if mode == "consensus":
        return build_consensus_portfolio_fn(capital, nifty_pe, limit)

    if profile_id not in INVESTOR_PROFILES:
        raise HTTPException(400, f"Unknown profile: {profile_id}")

    try:
        asset_alloc = compute_asset_allocation(profile_id, capital, nifty_pe)
    except Exception as e:
        print(f"Asset allocation error: {e}")
        asset_alloc = {
            "allocation_pct": {"equity": 70, "gold": 10, "debt": 15, "cash": 5},
            "allocation_amt": {"equity": int(capital*0.7), "gold": int(capital*0.1), "debt": int(capital*0.15), "cash": int(capital*0.05)},
            "equity_capital": int(capital * 0.7),
            "nifty_pe": 22.0, "market_valuation": {"zone": "Fair Value", "color": "#2563eb", "description": "Market at historical average."},
            "logic": "Balanced allocation based on profile philosophy.",
            "instruments": {"gold": "Sovereign Gold Bond", "debt": "Liquid Fund", "cash": "Savings Account"},
            "rebalance_triggers": []
        }
    equity_capital = asset_alloc["equity_capital"]
    profile = INVESTOR_PROFILES[profile_id]
    target_n = limit or profile.get("portfolio_size", 15)

    with _cache_lock: stocks = list(_cache.values())
    if not stocks: raise HTTPException(503, "Cache not ready. Try again in a few minutes.")
    with _cache_lock: avgs = dict(_sector_averages)

    scored = []
    for s in stocks:
        ps = score_profile(s, profile_id, avgs)
        if ps["score"] >= 25:  # Lower threshold - let more stocks through
            s = dict(s); s["profile_score"] = ps["score"]; s["profile_reasons"] = ps["reasons"]
            scored.append(s)
    scored.sort(key=lambda x: x["profile_score"], reverse=True)
    top = scored[:target_n]
    near_misses = scored[target_n:target_n+6]
    if not top: raise HTTPException(404, "No stocks meet this profile criteria")

    portfolio = get_portfolio_allocation(profile_id, top, equity_capital)

    for pos in portfolio["positions"]:
        try:
            stock_data = next((s for s in top if s["symbol"] == pos["symbol"]), {})
            explanation = generate_stock_explanation(stock_data, profile_id, avgs)
            pos["full_analysis"] = explanation.get("full_analysis", "")
            pos["qualifying_metrics"] = explanation.get("qualifying_metrics", [])
            pos["one_liner"] = explanation.get("one_liner", "")
        except Exception as e:
            print(f"Explanation error for {pos.get('symbol')}: {e}")
            pos["full_analysis"] = f"Selected based on {INVESTOR_PROFILES.get(profile_id, {}).get('name', profile_id)} criteria."
            pos["qualifying_metrics"] = []
            pos["one_liner"] = pos.get("why_included", "")

    try:
        why_not = generate_why_not(profile_id, near_misses, avgs)
    except Exception as e:
        print(f"Why-not error: {e}")
        why_not = []

    portfolio.update({
        "profile_id": profile_id, "profile_name": profile["name"],
        "profile_philosophy": profile["philosophy"], "profile_bio": profile["bio"],
        "capital_input": capital, "equity_capital": equity_capital,
        "asset_allocation": asset_alloc, "why_not": why_not,
        "generated_at": datetime.now().isoformat(), "mode": "single",
    })
    return portfolio


def build_consensus_portfolio_fn(capital: float, nifty_pe: float, limit: int = None) -> dict:
    asset_alloc = compute_asset_allocation("parag_parikh", capital, nifty_pe)
    equity_capital = asset_alloc["equity_capital"]
    with _cache_lock: stocks = list(_cache.values())
    with _cache_lock: avgs = dict(_sector_averages)

    consensus_scored = []
    for s in stocks:
        cs = score_legend_consensus(s, avgs)
        if cs["tier"]:
            s = dict(s); s["consensus_score"] = cs["consensus_score"]
            s["consensus_data"] = cs; s["profile_score"] = cs["consensus_score"]
            consensus_scored.append(s)
    consensus_scored.sort(key=lambda x: x["consensus_score"], reverse=True)
    top = consensus_scored[:limit or 20]
    if not top: raise HTTPException(404, "Not enough consensus stocks found")

    total_q = sum(s["consensus_data"]["qualifying_profiles"] for s in top)
    weights = [s["consensus_data"]["qualifying_profiles"] / total_q for s in top]
    total_w = sum(weights)
    weights = [w / total_w for w in weights]

    positions = []
    for i, (stock, weight) in enumerate(zip(top, weights)):
        price = stock.get("current_price") or 0
        shares = int(equity_capital * weight / price) if price > 0 else 0
        amount = shares * price if price > 0 else equity_capital * weight
        cs_data = stock["consensus_data"]
        explanation = generate_stock_explanation(stock, "buffett", avgs)
        positions.append({
            "rank": i+1, "symbol": stock["symbol"], "company_name": stock["company_name"],
            "sector": stock.get("sector","Unknown"), "current_price": price,
            "weight_pct": round(weight*100,1), "amount": round(amount), "shares": shares,
            "profile_score": stock["consensus_score"], "consensus_tier": cs_data["tier"],
            "qualifying_profiles": cs_data["qualifying_profiles"],
            "top_agreeing_profiles": [{"name": p["profile_name"], "score": p["score"]} for p in cs_data["top_profiles"][:3]],
            "conviction": stock["conviction"],
            "why_included": f"{cs_data['qualifying_profiles']} legendary investors agree on this stock",
            "full_analysis": f"This stock achieves rare multi-profile consensus across {cs_data['qualifying_profiles']} legendary investor frameworks with an average score of {cs_data['avg_score']:.0f}/100. The profiles rating it highest are {', '.join(p['profile_name'] for p in cs_data['top_profiles'][:2])}. Multi-profile consensus is significant because it means the stock simultaneously satisfies value (Graham), quality (Buffett/Marcellus), and growth (RJ/Lynch) criteria — an extremely rare combination in Indian markets.",
            "qualifying_metrics": explanation["qualifying_metrics"][:4],
            "one_liner": explanation["one_liner"],
        })

    sector_exposure = {}
    for pos in positions:
        sec = pos["sector"]
        if sec != "Unknown": sector_exposure[sec] = round(sector_exposure.get(sec,0)+pos["weight_pct"],1)

    return {
        "positions": positions, "total_stocks": len(positions),
        "total_capital": capital, "equity_capital": equity_capital,
        "total_deployed": round(sum(p["amount"] for p in positions)),
        "sector_exposure": sector_exposure, "asset_allocation": asset_alloc,
        "portfolio_rationale": f"This Legend Consensus portfolio selects stocks where multiple legendary investors independently agree. Position sizing is weighted by consensus breadth — broader agreement earns larger allocation. These are the rarest, highest-conviction opportunities in Indian markets.",
        "entry_strategy": "Enter systematically over 3-6 months to average entry prices. The consensus approach reduces single-style risk.",
        "rebalance_note": "Quarterly review. Replace stocks dropping below 3-profile consensus. Add new consensus entrants.",
        "why_not": [], "profile_id": "consensus", "profile_name": "Legend Consensus",
        "profile_philosophy": "The intersection of all legendary investor philosophies — stocks that simultaneously pass value, quality, and growth filters.",
        "profile_bio": "A meta-strategy finding common ground between 14 legendary investors.",
        "capital_input": capital, "generated_at": datetime.now().isoformat(), "mode": "consensus",
    }


