from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from datetime import datetime
import threading
import time
import json
import os
import re
import requests
from bs4 import BeautifulSoup

app = FastAPI(title="stocks.ai API", version="10.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CACHE_FILE = "stock_cache.json"

_cache = {}
_cache_time = None
_cache_lock = threading.Lock()
_is_refreshing = False
_refresh_progress = {"done": 0, "total": 0}

# ─── Full Universe: NSE + BSE ─────────────────────────────────────────────────────
# Screener.in covers both NSE and BSE stocks with the same symbol format
STOCK_UNIVERSE = list(dict.fromkeys([
    # ── Nifty 50 ──
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
    # ── Nifty Next 50 ──
    "ADANIENT", "ADANIGREEN", "ADANIPOWER", "AMBUJACEM", "BAJAJHLDNG",
    "BANKBARODA", "BERGEPAINT", "BEL", "BPCL", "CANBK",
    "CHOLAFIN", "COLPAL", "DLF", "GAIL", "GODREJCP",
    "GRASIM", "HAL", "HDFCAMC", "ICICIGI", "ICICIPRULI",
    "INDUSTOWER", "INDIGO", "IOC", "IRCTC", "JINDALSTEL",
    "LICI", "LTIM", "LUPIN", "MCDOWELL-N", "NHPC",
    "NMDC", "OFSS", "OIL", "PAGEIND", "PERSISTENT",
    "PETRONET", "PFC", "PIIND", "PNB", "RECLTD",
    "SAIL", "SHRIRAMFIN", "SIEMENS", "TATAPOWER", "TRENT",
    "VBL", "UNITDSPR", "NYKAA", "ZOMATO", "PAYTM",
    # ── Nifty Midcap 150 ──
    "ABCAPITAL", "ALKEM", "APOLLOTYRE", "ASHOKLEY", "ASTRAL",
    "AUROPHARMA", "BALKRISIND", "BANDHANBNK", "BIOCON", "CAMS",
    "CANFINHOME", "CARBORUNIV", "COFORGE", "CONCOR", "CROMPTON",
    "CUMMINSIND", "DEEPAKNTR", "DIXON", "ESCORTS", "EXIDEIND",
    "FEDERALBNK", "FORTIS", "GLENMARK", "GODREJIND", "GODREJPROP",
    "GRANULES", "GSPL", "HINDPETRO", "HONAUT", "IDFCFIRSTB",
    "IEX", "INDHOTEL", "INDIANB", "INDPAINT", "ISEC",
    "JKCEMENT", "JUBLFOOD", "KAJARIACER", "KANSAINER", "LICHSGFIN",
    "LINDEINDIA", "LTF", "LTTS", "MANAPPURAM", "MAXHEALTH",
    "MCX", "MFSL", "MPHASIS", "MRF", "MUTHOOTFIN",
    "NATCOPHARM", "NAUKRI", "OBEROIRLTY", "PFIZER", "PHOENIX",
    "PRESTIGE", "RADICO", "RAMCOCEM", "RELAXO", "RITES",
    "ROUTE", "SBICARD", "SBILIFE", "SCHAEFFLER", "SKFINDIA",
    "SONACOMS", "SRF", "SUNDARMFIN", "SUNDRMFAST", "SUPREMEIND",
    "SYNGENE", "TATACHEM", "TATACOMM", "TATAELXSI", "TVSMOTORS",
    "UBL", "UNIONBANK", "VGUARD", "VOLTAS", "WHIRLPOOL",
    # ── Nifty Smallcap 250 (selected) ──
    "AAVAS", "AFFLE", "AJANTPHARM", "AKZOINDIA", "ALEMBICLTD",
    "AMBER", "ANGELONE", "APTUS", "ASTRALLTD", "ATGL",
    "AVANTIFEED", "BALAMINES", "BASF", "BAYERCROP", "CDSL",
    "CENTURYPLY", "CERA", "CGPOWER", "CHAMBLFERT", "CLEAN",
    "CREDITACC", "DALBHARAT", "DCMSHRIRAM", "DELHIVERY", "DEVYANI",
    "DOMS", "EASEMYTRIP", "ELGIEQUIP", "EMAMILTD", "ENDURANCE",
    "ERIS", "FINEORG", "FINPIPE", "FLUOROCHEM", "GAEL",
    "GALAXYSURF", "GICRE", "GLAND", "GNFC", "GREENPANEL",
    "GRINDWELL", "GUJGASLTD", "HBLPOWER", "HIKAL", "HOMEFIRST",
    "HUDCO", "INDIAMART", "INDIGOPNTS", "INTELLECT", "IPCALAB",
    "IRB", "IRFC", "JBCHEPHARM", "JKPAPER", "JSWENERGY",
    "JUSTDIAL", "KAVVERITEL", "KPITTECH", "KRBL", "LALPATHLAB",
    "LAURUSLABS", "MAPMYINDIA", "METROBRAND", "NAUKRI", "NBCC",
    "NLCINDIA", "OLECTRA", "PGHH", "POLICYBZR", "PRINCEPIPE",
    "RAJESHEXPO", "RKFORGE", "ROSSARI", "SAFARI", "SEQUENT",
    "SHYAMMETL", "SOLARA", "STARHEALTH", "SUVENPHAR", "TANLA",
    "TATAINVEST", "TCNSBRANDS", "THYROCARE", "TTKPRESTIG", "UCOBANK",
    "UNOAUTO", "UTIAMC", "VIJAYA", "VINCOPPER", "ZEEL",
    # ── BSE-listed stocks not on NSE (BSE 500 additions) ──
    "ABBOTINDIA", "ACCELYA", "AIAENG", "AKZOINDIA", "AMARAJABAT",
    "ANANTRAJ", "ANSALAPI", "APOLLOHOSP", "ARCHIDPLY", "ARSHIYA",
    "ASAHIINDIA", "ASTRAZEN", "ATGL", "ATUL", "BAJAJCON",
    "BAJAJELEC", "BAJAJHIND", "BALAXI", "BALPHARMA", "BANSWRASA",
    "BARDOD", "BCLIND", "BDAL", "BEML", "BFINVEST",
    "BGRENERGY", "BHAGERIA", "BHANDARI", "BHARATFORG", "BHARATRAS",
    "BHEL", "BORORENEW", "BOSCHLTD", "CAMPUS", "CAPLIPOINT",
    "CASTROLIND", "CEATLTD", "CENTRALBK", "CENTURYTEX", "CHEMCON",
    "CHEMPLASTS", "CIGNITITEC", "CINEVISTA", "COCHINSHIP", "COFFEDAY",
    "COLGATE", "COMPTAADV", "CONFIPET", "CONTROLPR", "COROMANDEL",
    "CRAFTSMAN", "CRISIL", "DATAMATICS", "DBREALTY", "DEEPAKFERT",
    "DELTACORP", "DHANISVCS", "DHANUKA", "DRHORN", "DYNPRO",
    "EDELWEISS", "ELECTCAST", "EMKAY", "ENPRO", "EPIGRAL",
    "EQUITASBNK", "EROSMEDIA", "ESABINDIA", "ESCORTS", "EXICOM",
    "FAIRCHEM", "FIEMIND", "FINEORG", "FINPIPE", "FORTIS",
    "FSL", "GABRIEL", "GALAXYSURF", "GARFIBRES", "GATEWAY",
    "GENESYS", "GHCL", "GILLETTE", "GIPCL", "GMMPFAUDLR",
    "GNFC", "GODHA", "GODREJAGRO", "GPIL", "GRAPHITE",
    "GREENPANEL", "GRINDWELL", "GSFC", "GSKCONS", "GTLINFRA",
    "GULFOILLUB", "HAPPSTMNDS", "HARDWYN", "HDFCBANK", "HERITGFOOD",
    "HIKAL", "HINDCOPPER", "HINDMOTORS", "HINDOILEXP", "HONAUT",
    "HPCL", "IBREALEST", "ICIL", "IDBI", "IDFC",
    "IFBIND", "IIFL", "IMFA", "INDIACEM", "INDSWFTLAB",
    "INFIBEAM", "INGERRAND", "INOXWIND", "INSECTICID", "INTENTECH",
    "IOB", "ISGEC", "ITI", "J&KBANK", "JAGRAN",
    "JAMNAAUTO", "JAYAGROGN", "JBMA", "JETAIRWAYS", "JKIL",
    "JKLAKSHMI", "JKPAPER", "JKTYRE", "JMFINANCIL", "JOINDRE",
    "JUBLINGREA", "JUNIPERH", "KANSAINER", "KARURVYSYA", "KCP",
    "KDDL", "KESORAMIND", "KFINTECH", "KILITCH", "KIMS",
    "KINGFA", "KITEX", "KNRCON", "KOLTEPATIL", "KPRMILL",
    "KRBL", "KREBSBIO", "KRISHANA", "KSENG", "KTKBANK",
    "KUANTUM", "LAOPALA", "LATENTVIEW", "LAXMIMACH", "LLOYDSENGG",
    "LMWLTD", "LOKESHM", "LORDSCHLO", "LUPIN", "LUXIND",
    "LYKALABS", "MAHINDCIE", "MAHLIFE", "MAHSCOOTER", "MASFIN",
    "MATRIMONY", "MAXESTATES", "MAYURUNIQ", "MEDANTA", "MIDHANI",
    "MINDACORP", "MIRZAINT", "MMTC", "MOLDTKPAC", "MONARCH",
    "MOTHERSON", "MPSLTD", "MRPL", "MSTCLTD", "NAGAFERT",
    "NATHBIOGEN", "NAVINFLUOR", "NETWORK18", "NFL", "NGIL",
    "NIITLTD", "NILE", "NILKAMAL", "NIPPOBATRY", "NLC",
    "NOCIL", "NRBBEARING", "NTPC", "NUCLEUS", "OCCL",
    "OLECTRA", "OMAXE", "ONMOBILE", "ORIENTELEC", "ORISSAMINE",
    "PAEL", "PANACEABIO", "PARBATI", "PARSVNATH", "PATELENG",
    "PATINTLOG", "PDSL", "PENIND", "PERSISTENT", "PGHL",
    "PHOENIXLTD", "PILANIINVS", "PIONEEREMB", "PLASTIBLEN", "POCL",
    "POKARNA", "POLYPLEX", "POLYMED", "POONAWALLA", "PRICOLLTD",
    "PRIMESECU", "PRINCEPIPE", "PRITIKAUTO", "PVRINOX", "QUESS",
    "RAILTEL", "RAIN", "RAJRATAN", "RALLIS", "RAMASTEEL",
    "RAMCOIND", "RATEGAIN", "RAYMOND", "RBLBANK", "REDINGTON",
    "REPCOHOME", "RESPONIND", "RPOWER", "RVNL", "SAFARI",
    "SAGARCEM", "SAKSOFT", "SALZERELEC", "SANDHAR", "SANGHIIND",
    "SANWARIA", "SARDAEN", "SAREGAMA", "SBICARD", "SEQUENT",
    "SHAREINDIA", "SHILPAMED", "SHIVALIK", "SHOPERSTOP", "SHRIRAMEPC",
    "SHYAMMETL", "SIGACHI", "SIGNATURE", "SINTERCOM", "SKIPPER",
    "SNOWMAN", "SOLARA", "SOMANYCERA", "SPANDANA", "SPARC",
    "SPECIALITY", "SPICEJET", "SPORTKING", "SPSINFRA", "SREEL",
    "STCINDIA", "STERTOOLS", "STYLAM", "SUBROS", "SUDARSCHEM",
    "SUMICHEM", "SUNCLAYLTD", "SUNDARAM", "SUNFLAG", "SUNPHARMA",
    "SUPRIYA", "SUVENPHAR", "SWSOLAR", "SYMPHONY", "SYNCOMF",
    "TAINWALA", "TAJ", "TALBROAUTO", "TANLA", "TASTYBIT",
    "TATAINVEST", "TCIEXP", "TCNSBRANDS", "TEJASNET", "TEXMOPIPES",
    "TFCILTD", "THANGAMAYL", "THYROCARE", "TIINDIA", "TIMKEN",
    "TINPLATE", "TIPSINDLTD", "TITAGARH", "TMILL", "TORNTPOWER",
    "TPLPLASTEH", "TREJHARA", "TREEHOUSE", "TRIDENT", "TRIVENI",
    "TTKPRESTIG", "TTML", "TVTODAY", "UCOBANK", "UFLEX",
    "UJJIVAN", "ULTRACEMCO", "UNIENTER", "UNIONBANK", "UNIPARTS",
    "UNITECH", "UNOMINDA", "UTIAMC", "UTTAMSUGAR", "VGUARD",
    "VINATIORGA", "VINDHYATEL", "VINNY", "VIPIND", "VIPULLTD",
    "VISAKAIND", "VISHNU", "VOLTAMP", "VRLLOG", "VSTIND",
    "VSTLTD", "WABCOINDIA", "WELCORP", "WELSPUNIND", "WENDT",
    "WESTLIFE", "WIPROELTD", "WONDERLA", "XCHANGING", "YAARI",
    "YATHARTH", "ZENSARTECH", "ZENTEC", "ZFCVINDIA", "ZODIACLOTH",
]))

SCREENER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.screener.in/",
}

def parse_number(text):
    if not text: return None
    text = str(text).strip().replace(",","").replace("₹","").replace("%","").replace("Cr.","").replace("Cr","").strip()
    if text in ("","-","—","N/A"): return None
    if "/" in text: text = text.split("/")[0].strip()
    try: return float(text)
    except: return None


def fetch_screener(symbol: str) -> dict:
    session = requests.Session()
    session.headers.update(SCREENER_HEADERS)
    try: session.get("https://www.screener.in/", timeout=8); time.sleep(0.3)
    except: pass

    for suffix in ["/consolidated/", "/"]:
        try:
            url = f"https://www.screener.in/company/{symbol}{suffix}"
            r = session.get(url, timeout=12)
            if r.status_code in (404, 403): continue
            if r.status_code != 200: continue
            soup = BeautifulSoup(r.text, "html.parser")
            if not soup.select_one("#top-ratios"): continue

            all_kv = {}
            for li in soup.select("li"):
                ne = li.select_one(".name"); ve = li.select_one(".number, .value")
                if ne and ve:
                    k = ne.get_text(strip=True); v = ve.get_text(strip=True)
                    if k and v: all_kv[k] = v
            for tr in soup.select("table tr"):
                cells = tr.select("td")
                if len(cells) >= 2:
                    k = cells[0].get_text(strip=True); v = cells[1].get_text(strip=True)
                    if k and v: all_kv[k] = v

            def get(*keys):
                for k in keys:
                    if k in all_kv: return parse_number(all_kv[k])
                    for ak in all_kv:
                        if k.lower() in ak.lower(): return parse_number(all_kv[ak])
                return None

            current_price = get("Current Price")
            mc_cr = get("Market Cap")
            market_cap = mc_cr * 1e7 if mc_cr else None
            pe = get("Stock P/E","P/E")
            book_value = get("Book Value")
            pb = round(current_price/book_value,2) if current_price and book_value and book_value > 0 else None
            roe_raw = get("ROE","Return on equity"); roe = (roe_raw/100) if roe_raw is not None else None
            roce_raw = get("ROCE"); roce = (roce_raw/100) if roce_raw is not None else None
            de = get("Debt to equity","D/E")
            opm_raw = get("OPM","Operating Profit Margin")
            opm = (opm_raw/100) if opm_raw is not None else None
            if opm is None:
                m = re.search(r'OPM[^\d]*(\d+\.?\d*)%', soup.get_text())
                if m: opm = float(m.group(1))/100
            dy_raw = get("Dividend Yield"); dy = (dy_raw/100) if dy_raw is not None else None
            hl_text = all_kv.get("High / Low","")
            w52_high = w52_low = None
            if hl_text and "/" in hl_text:
                parts = hl_text.replace("₹","").replace(",","").split("/")
                w52_high = parse_number(parts[0])
                w52_low = parse_number(parts[1]) if len(parts)>1 else None
            eps = get("EPS")
            ph_raw = get("Promoter holding","Promoter Holding"); promoter_holding = (ph_raw/100) if ph_raw is not None else None

            company_name = symbol
            for sel in ["h1.margin-0","h1"]:
                el = soup.select_one(sel)
                if el: company_name = el.get_text(strip=True); break

            sector = "Unknown"
            for a in soup.select("a[href*='/screen/']"):
                t = a.get_text(strip=True)
                if t and 2 < len(t) < 40: sector = t; break

            pros = [li.get_text(strip=True) for li in soup.select(".pros li")][:3]
            cons = [li.get_text(strip=True) for li in soup.select(".cons li")][:3]

            result = {
                "company_name": company_name, "sector": sector,
                "current_price": current_price, "market_cap": market_cap,
                "pe_ratio": pe, "pb_ratio": pb, "book_value": book_value,
                "roe": roe, "roce": roce, "debt_to_equity": de,
                "operating_margins": opm, "gross_margins": opm,
                "dividend_yield": dy, "52w_high": w52_high, "52w_low": w52_low,
                "eps": eps, "promoter_holding": promoter_holding,
                "pros": pros, "cons": cons,
            }
            if not result.get("pe_ratio") and not result.get("current_price"): continue
            return result
        except Exception as e:
            print(f"  Screener error {symbol}: {e}"); continue
    return {}


# ─── ALL Investor Profiles ────────────────────────────────────────────────────────
INVESTOR_PROFILES = {
    # ── Indian Legends ──
    "rj": {
        "name": "Rakesh Jhunjhunwala", "avatar": "🐂",
        "focus": "India Growth Compounder", "category": "Indian Legend",
        "description": "High ROE compounders, India growth story, high promoter conviction, buy on dips",
        "color": "#f59e0b",
    },
    "ramesh_damani": {
        "name": "Ramesh Damani", "avatar": "🎯",
        "focus": "Contrarian Deep Value", "category": "Indian Legend",
        "description": "Deep value, contrarian, out-of-favour sectors, 5-7 year patience",
        "color": "#ef4444",
    },
    "vijay_kedia": {
        "name": "Vijay Kedia", "avatar": "💡",
        "focus": "SMILE — Niche Leaders", "category": "Indian Legend",
        "description": "Small/Mid cap niche monopolies, large opportunity, great management, high promoter holding",
        "color": "#8b5cf6",
    },
    "porinju": {
        "name": "Porinju Veliyath", "avatar": "🔍",
        "focus": "Smallcap Contrarian", "category": "Indian Legend",
        "description": "Deep smallcap, turnaround stories, beaten-down stocks ignored by institutions",
        "color": "#ec4899",
    },
    "ashish_kacholia": {
        "name": "Ashish Kacholia", "avatar": "🚀",
        "focus": "Emerging Compounders", "category": "Indian Legend",
        "description": "Smallcap quality growth, scalable businesses, emerging sector leaders",
        "color": "#84cc16",
    },
    "dolly_khanna": {
        "name": "Dolly Khanna", "avatar": "💎",
        "focus": "Cyclical Turnarounds", "category": "Indian Legend",
        "description": "Under-the-radar cyclicals, turnaround stories, ignored smallcaps with pricing power",
        "color": "#f472b6",
    },
    "chandrakant_sampat": {
        "name": "Chandrakant Sampat", "avatar": "📜",
        "focus": "Original Indian Value", "category": "Indian Legend",
        "description": "India's original Buffett — consumer monopolies, debt-free, decades-long compounders",
        "color": "#a78bfa",
    },
    # ── Global Legends ──
    "buffett": {
        "name": "Warren Buffett", "avatar": "🧠",
        "focus": "Quality at Fair Price", "category": "Global Legend",
        "description": "Durable moat, consistent high ROE, debt-free balance sheet, buy below intrinsic value",
        "color": "#3b82f6",
    },
    "peter_lynch": {
        "name": "Peter Lynch", "avatar": "📈",
        "focus": "GARP — Growth at Reasonable Price", "category": "Global Legend",
        "description": "PEG ratio focus, invest in what you know, hidden gems in boring sectors",
        "color": "#06b6d4",
    },
    "ben_graham": {
        "name": "Benjamin Graham", "avatar": "⚖️",
        "focus": "Deep Value / Margin of Safety", "category": "Global Legend",
        "description": "Buy below book value, wide margin of safety, net-net stocks, absolute value",
        "color": "#64748b",
    },
    "charlie_munger": {
        "name": "Charlie Munger", "avatar": "🦁",
        "focus": "Wonderful Company at Fair Price", "category": "Global Legend",
        "description": "High ROCE compounders, pricing power, avoid commodity businesses, hold forever",
        "color": "#0ea5e9",
    },
    "phil_fisher": {
        "name": "Philip Fisher", "avatar": "🔭",
        "focus": "Scuttlebutt Growth Investor", "category": "Global Legend",
        "description": "Long-term growth, R&D investment, superior management, strong sales growth",
        "color": "#14b8a6",
    },
    # ── Indian Fund Houses ──
    "parag_parikh": {
        "name": "Parag Parikh Flexi Cap", "avatar": "🌍",
        "focus": "Owner-Operator Quality", "category": "Indian Fund",
        "description": "Pricing power, owner-operator promoters, low churn, behavioural discipline",
        "color": "#10b981",
    },
    "marcellus": {
        "name": "Marcellus (Saurabh Mukherjea)", "avatar": "🔬",
        "focus": "Forensic Quality Only", "category": "Indian Fund",
        "description": "Zero debt, very high ROCE, clean accounts, consistent compounders, no leverage",
        "color": "#06b6d4",
    },
    "motilal_qglp": {
        "name": "Motilal Oswal QGLP", "avatar": "📊",
        "focus": "Quality + Growth + Longevity + Price", "category": "Indian Fund",
        "description": "All four QGLP criteria must be met — quality business, growing earnings, long runway, fair price",
        "color": "#f97316",
    },
    "nippon_smallcap": {
        "name": "Nippon India Small Cap", "avatar": "🌱",
        "focus": "High Growth Small Caps", "category": "Indian Fund",
        "description": "Emerging sector leaders, high revenue growth, small/mid market cap, willing to pay for growth",
        "color": "#22d3ee",
    },
    "mirae_asset": {
        "name": "Mirae Asset India", "avatar": "🏆",
        "focus": "Quality Growth Large Cap", "category": "Indian Fund",
        "description": "Quality businesses with sustainable growth, sector leaders, strong return ratios",
        "color": "#a3e635",
    },
    "hdfc_mf": {
        "name": "HDFC Mutual Fund", "avatar": "🏦",
        "focus": "Value + Quality Blend", "category": "Indian Fund",
        "description": "Prashant Jain style — value + quality mix, contrarian at times, long-term patient capital",
        "color": "#fb923c",
    },
    "anand_rathi": {
        "name": "Anand Rathi Wealth", "avatar": "⚡",
        "focus": "Wealth Preservation + Growth", "category": "Indian Fund",
        "description": "HNI wealth management style — large cap bias, dividend payers, capital preservation focus",
        "color": "#fbbf24",
    },
    "white_oak": {
        "name": "White Oak Capital (Prashant Khemka)", "avatar": "🌳",
        "focus": "Earnings Quality Growth", "category": "Indian Fund",
        "description": "Ex-Goldman Sachs — earnings quality, return on equity, growth at reasonable price",
        "color": "#86efac",
    },
    "enam": {
        "name": "Enam / Vallabh Bhansali", "avatar": "🛡️",
        "focus": "Forensic + Long Term", "category": "Indian Fund",
        "description": "Management integrity above all, avoid leverage, forensic accounting, 10+ year horizon",
        "color": "#c4b5fd",
    },
    "ask_investment": {
        "name": "ASK Investment Managers", "avatar": "💰",
        "focus": "Quality Large Cap PMS", "category": "Indian Fund",
        "description": "Capital preservation + growth, quality businesses, low debt, consistent dividend payers",
        "color": "#fdba74",
    },
    "carnelian": {
        "name": "Carnelian Asset (Vikas Khemani)", "avatar": "💫",
        "focus": "Emerging Sector Leaders", "category": "Indian Fund",
        "description": "Emerging compounders, sector tailwinds, management quality, 5-7 year horizon",
        "color": "#67e8f9",
    },
}


# ─── Profile scoring logic ────────────────────────────────────────────────────────
def score_profile(d: dict, profile: str) -> dict:
    s, r = 0, []
    def pct(v): return v*100 if v is not None else None
    roe = pct(d.get("roe")); roce = pct(d.get("roce")); opm = pct(d.get("operating_margins"))
    dy = pct(d.get("dividend_yield")); ph = pct(d.get("promoter_holding"))
    pe = d.get("pe_ratio"); pb = d.get("pb_ratio"); de = d.get("debt_to_equity")
    mc = d.get("market_cap") or 0; mc_cr = mc/1e7
    price = d.get("current_price"); high = d.get("52w_high")
    pros_cons = " ".join(d.get("pros",[]) + d.get("cons",[]))
    debt_free = (de is not None and de < 0.2) or "debt free" in pros_cons.lower()
    pct_off_high = ((high-price)/high*100) if price and high and high > 0 else 0

    if profile == "rj":
        if roe and roe >= 25: s+=30; r.append(f"Exceptional ROE {roe:.1f}%")
        elif roe and roe >= 18: s+=20; r.append(f"Strong ROE {roe:.1f}%")
        elif roe and roe >= 12: s+=10
        if roce and roce >= 25: s+=20; r.append(f"High ROCE {roce:.1f}%")
        elif roce and roce >= 15: s+=12
        if ph and ph >= 50: s+=30; r.append(f"High promoter conviction {ph:.1f}%")
        elif ph and ph >= 35: s+=15
        if pe and 0<pe<35: s+=20; r.append(f"Growth at fair price P/E {pe:.1f}x")

    elif profile == "ramesh_damani":
        if pct_off_high >= 40: s+=35; r.append(f"Deep discount {pct_off_high:.0f}% off highs")
        elif pct_off_high >= 25: s+=22; r.append(f"Significant discount {pct_off_high:.0f}% off highs")
        elif pct_off_high >= 15: s+=12
        if pe and 0<pe<12: s+=30; r.append(f"Deep value P/E {pe:.1f}x")
        elif pe and pe<18: s+=18; r.append(f"Value P/E {pe:.1f}x")
        if pb and 0<pb<1.5: s+=20; r.append(f"Near/below book P/B {pb:.1f}x")
        elif pb and pb<2.5: s+=10
        if roe and roe>=12: s+=15; r.append(f"ROE {roe:.1f}%")

    elif profile == "vijay_kedia":
        if 0 < mc_cr < 5000: s+=25; r.append(f"Small/Mid cap ₹{mc_cr:.0f}Cr")
        elif mc_cr < 20000: s+=12
        if ph and ph>=50: s+=25; r.append(f"Promoter conviction {ph:.1f}%")
        elif ph and ph>=35: s+=15
        if roe and roe>=20: s+=25; r.append(f"High ROE {roe:.1f}%")
        elif roe and roe>=15: s+=15
        if opm and opm>=15: s+=25; r.append(f"Good margins {opm:.1f}%")
        elif opm and opm>=10: s+=12

    elif profile == "porinju":
        if 0 < mc_cr < 2000: s+=35; r.append(f"True smallcap ₹{mc_cr:.0f}Cr")
        elif mc_cr < 5000: s+=18; r.append(f"Small cap ₹{mc_cr:.0f}Cr")
        if pct_off_high >= 30: s+=25; r.append(f"Beaten down {pct_off_high:.0f}% off highs")
        elif pct_off_high >= 15: s+=12
        if pe and 0<pe<20: s+=25; r.append(f"Cheap P/E {pe:.1f}x")
        elif pe and pe<35: s+=10
        if roe and roe>=12: s+=15

    elif profile == "ashish_kacholia":
        if 0 < mc_cr < 5000: s+=25; r.append(f"Smallcap focus ₹{mc_cr:.0f}Cr")
        elif mc_cr < 15000: s+=12
        if roe and roe>=20: s+=25; r.append(f"High ROE {roe:.1f}%")
        elif roe and roe>=15: s+=15
        if opm and opm>=15: s+=25; r.append(f"Good margins {opm:.1f}%")
        elif opm and opm>=10: s+=15
        if pe and 0<pe<40: s+=15
        if ph and ph>=40: s+=10; r.append(f"Promoter skin in game {ph:.1f}%")

    elif profile == "dolly_khanna":
        # Cyclical turnarounds, under-the-radar
        if 0 < mc_cr < 3000: s+=25; r.append(f"Under-the-radar smallcap ₹{mc_cr:.0f}Cr")
        if pct_off_high >= 25: s+=25; r.append(f"Turnaround candidate {pct_off_high:.0f}% off highs")
        if roe and roe>=15: s+=25; r.append(f"ROE recovery {roe:.1f}%")
        if opm and opm>=10: s+=15
        if de is not None and de<0.5: s+=10; r.append("Manageable debt")

    elif profile == "chandrakant_sampat":
        # Consumer monopolies, debt-free, decades-long compounders
        if debt_free: s+=30; r.append("Debt-free — Sampat's #1 criterion")
        if roe and roe>=20: s+=25; r.append(f"High ROE {roe:.1f}%")
        elif roe and roe>=15: s+=15
        if opm and opm>=20: s+=25; r.append(f"Consumer pricing power {opm:.1f}%")
        elif opm and opm>=12: s+=12
        if pe and 0<pe<35: s+=20; r.append(f"Reasonable P/E {pe:.1f}x")

    elif profile == "buffett":
        if roe and roe>=20: s+=25; r.append(f"Strong ROE {roe:.1f}%")
        elif roe and roe>=15: s+=15
        if debt_free: s+=25; r.append("Near debt-free")
        elif de is not None and de<0.5: s+=15; r.append("Low debt")
        if opm and opm>=20: s+=25; r.append(f"Strong OPM {opm:.1f}%")
        elif opm and opm>=12: s+=15
        if pe and 0<pe<25: s+=25; r.append(f"Reasonable P/E {pe:.1f}x")
        elif pe and pe<35: s+=10

    elif profile == "peter_lynch":
        # PEG ratio focus
        if roe and pe and roe>0 and pe>0:
            peg = pe/roe
            if peg < 0.5: s+=40; r.append(f"Excellent PEG {peg:.2f}")
            elif peg < 1.0: s+=28; r.append(f"Good PEG {peg:.2f}")
            elif peg < 1.5: s+=15; r.append(f"Acceptable PEG {peg:.2f}")
        if roe and roe>=15: s+=25; r.append(f"Growth indicator ROE {roe:.1f}%")
        elif roe and roe>=10: s+=15
        if pe and 0<pe<30: s+=20
        if 0 < mc_cr < 10000: s+=15; r.append("Mid/small cap — Lynch's sweet spot")

    elif profile == "ben_graham":
        if pb and 0<pb<1: s+=40; r.append(f"Below book value P/B {pb:.2f}x")
        elif pb and pb<1.5: s+=28; r.append(f"Near book P/B {pb:.2f}x")
        elif pb and pb<2: s+=15
        if pe and 0<pe<12: s+=35; r.append(f"Deep value P/E {pe:.1f}x")
        elif pe and pe<15: s+=22
        elif pe and pe<20: s+=10
        if debt_free: s+=25; r.append("No debt — Graham safety")
        elif de is not None and de<0.3: s+=15

    elif profile == "charlie_munger":
        # Wonderful company at fair price — ROCE focus
        if roce and roce>=30: s+=35; r.append(f"Exceptional ROCE {roce:.1f}%")
        elif roce and roce>=22: s+=22; r.append(f"Strong ROCE {roce:.1f}%")
        elif roce and roce>=15: s+=12
        if opm and opm>=25: s+=25; r.append(f"Pricing power OPM {opm:.1f}%")
        elif opm and opm>=15: s+=15
        if debt_free: s+=20; r.append("Debt-free compounder")
        elif de is not None and de<0.3: s+=12
        if pe and 0<pe<40: s+=20; r.append(f"Fair price P/E {pe:.1f}x")

    elif profile == "phil_fisher":
        # Growth, R&D, sales growth
        if roe and roe>=20: s+=30; r.append(f"Superior returns ROE {roe:.1f}%")
        elif roe and roe>=15: s+=18
        if opm and opm>=20: s+=25; r.append(f"Growing margins {opm:.1f}%")
        elif opm and opm>=12: s+=15
        if ph and ph>=40: s+=25; r.append(f"Management alignment {ph:.1f}%")
        if pe and 0<pe<50: s+=20; r.append(f"Growth valuation P/E {pe:.1f}x")

    elif profile == "parag_parikh":
        if ph and ph>=45: s+=25; r.append(f"Owner-operator {ph:.1f}%")
        elif ph and ph>=30: s+=15
        if opm and opm>=20: s+=25; r.append(f"Pricing power OPM {opm:.1f}%")
        elif opm and opm>=12: s+=15
        if debt_free or (de is not None and de<0.5): s+=20; r.append("Conservative balance sheet")
        if roe and roe>=18: s+=20; r.append(f"Consistent ROE {roe:.1f}%")
        elif roe and roe>=12: s+=10
        if pe and 0<pe<40: s+=10

    elif profile == "marcellus":
        if debt_free: s+=35; r.append("Debt-free — Marcellus must-have")
        elif de is not None and de<0.3: s+=15
        if roce and roce>=25: s+=35; r.append(f"Exceptional ROCE {roce:.1f}%")
        elif roce and roce>=18: s+=20; r.append(f"Strong ROCE {roce:.1f}%")
        if opm and opm>=20: s+=20; r.append(f"Consistent margins {opm:.1f}%")
        elif opm and opm>=12: s+=10
        if roe and roe>=20: s+=10

    elif profile == "motilal_qglp":
        q_met = (roe and roe>=18) and (opm and opm>=15)
        g_met = roce and roce>=20
        p_met = pe and 0<pe<45
        l_met = ph and ph>=40
        if q_met: s+=30; r.append("Quality criterion ✓ (ROE + margins)")
        if g_met: s+=25; r.append(f"Growth criterion ✓ ROCE {roce:.1f}%")
        if p_met: s+=25; r.append(f"Price criterion ✓ P/E {pe:.1f}x")
        if l_met: s+=20; r.append(f"Longevity ✓ promoter {ph:.1f}%")

    elif profile == "nippon_smallcap":
        if 0 < mc_cr < 8000: s+=30; r.append(f"Small cap universe ₹{mc_cr:.0f}Cr")
        elif mc_cr < 15000: s+=15
        if roe and roe>=18: s+=25; r.append(f"High growth ROE {roe:.1f}%")
        elif roe and roe>=12: s+=15
        if opm and opm>=15: s+=25; r.append(f"Emerging margins {opm:.1f}%")
        elif opm and opm>=8: s+=12
        if pe and 0<pe<50: s+=20; r.append(f"Growth premium P/E {pe:.1f}x")

    elif profile == "mirae_asset":
        if roe and roe>=20: s+=28; r.append(f"Quality return ROE {roe:.1f}%")
        elif roe and roe>=15: s+=18
        if roce and roce>=20: s+=22; r.append(f"Strong ROCE {roce:.1f}%")
        elif roce and roce>=12: s+=12
        if opm and opm>=18: s+=25; r.append(f"Sector leader margins {opm:.1f}%")
        elif opm and opm>=12: s+=15
        if pe and 0<pe<40: s+=25; r.append(f"Reasonable valuation {pe:.1f}x")

    elif profile == "hdfc_mf":
        # Value + quality blend
        if pct_off_high >= 20: s+=20; r.append(f"Value opportunity {pct_off_high:.0f}% off highs")
        if pe and 0<pe<20: s+=25; r.append(f"Value zone P/E {pe:.1f}x")
        elif pe and pe<30: s+=15
        if roe and roe>=15: s+=25; r.append(f"Quality return ROE {roe:.1f}%")
        elif roe and roe>=10: s+=15
        if dy and dy>=2: s+=15; r.append(f"Dividend support {dy:.1f}%")
        if debt_free or (de is not None and de<0.5): s+=15; r.append("Conservative balance sheet")

    elif profile == "anand_rathi":
        # Capital preservation, large cap, dividend
        if mc_cr > 10000: s+=20; r.append(f"Large cap safety ₹{mc_cr:.0f}Cr")
        if dy and dy>=3: s+=30; r.append(f"Strong dividend {dy:.1f}%")
        elif dy and dy>=2: s+=18; r.append(f"Good dividend {dy:.1f}%")
        elif dy and dy>=1: s+=8
        if debt_free or (de is not None and de<0.3): s+=25; r.append("Capital preservation — low debt")
        if roe and roe>=15: s+=15; r.append(f"Steady ROE {roe:.1f}%")
        if pe and 0<pe<25: s+=10

    elif profile == "white_oak":
        # Earnings quality, ROE, growth at reasonable price
        if roe and roe>=22: s+=30; r.append(f"Earnings quality ROE {roe:.1f}%")
        elif roe and roe>=15: s+=18
        if opm and opm>=20: s+=25; r.append(f"Quality margins {opm:.1f}%")
        elif opm and opm>=12: s+=15
        if pe and 0<pe<35: s+=25; r.append(f"GARP valuation {pe:.1f}x")
        if debt_free or (de is not None and de<0.4): s+=20; r.append("Clean balance sheet")

    elif profile == "enam":
        # Management integrity, no leverage, long term
        if debt_free: s+=35; r.append("No debt — Enam's top criterion")
        elif de is not None and de<0.2: s+=20
        if ph and ph>=45: s+=25; r.append(f"Management alignment {ph:.1f}%")
        elif ph and ph>=30: s+=15
        if roe and roe>=18: s+=20; r.append(f"Consistent ROE {roe:.1f}%")
        elif roe and roe>=12: s+=12
        if opm and opm>=15: s+=20; r.append(f"Sustainable margins {opm:.1f}%")

    elif profile == "ask_investment":
        # Quality large cap PMS
        if mc_cr > 15000: s+=20; r.append(f"Institutional quality ₹{mc_cr:.0f}Cr")
        if roe and roe>=18: s+=25; r.append(f"Quality ROE {roe:.1f}%")
        elif roe and roe>=12: s+=15
        if debt_free or (de is not None and de<0.3): s+=25; r.append("Conservative balance sheet")
        if dy and dy>=1.5: s+=15; r.append(f"Dividend paying {dy:.1f}%")
        if opm and opm>=15: s+=15; r.append(f"Quality margins {opm:.1f}%")

    elif profile == "carnelian":
        # Emerging compounders, sector tailwinds
        if 0 < mc_cr < 20000: s+=20; r.append(f"Emerging compounder ₹{mc_cr:.0f}Cr")
        if roe and roe>=20: s+=25; r.append(f"High ROE {roe:.1f}%")
        elif roe and roe>=15: s+=15
        if opm and opm>=15: s+=25; r.append(f"Expanding margins {opm:.1f}%")
        elif opm and opm>=10: s+=12
        if ph and ph>=45: s+=20; r.append(f"Promoter conviction {ph:.1f}%")
        elif ph and ph>=30: s+=10
        if pe and 0<pe<45: s+=10

    return {"score": min(s, 100), "reasons": r[:3]}


def get_matching_profiles(d: dict) -> list:
    results = []
    for pid in INVESTOR_PROFILES:
        res = score_profile(d, pid)
        results.append({"id": pid, "name": INVESTOR_PROFILES[pid]["name"],
                        "avatar": INVESTOR_PROFILES[pid]["avatar"],
                        "score": res["score"], "reasons": res["reasons"]})
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:3]


# ─── Standard composite scoring ──────────────────────────────────────────────────
def to_pct(val): return val*100 if val is not None else None

def score_buffett_std(d):
    s,r=0,[]
    roe=to_pct(d.get("roe")); pc=d.get("pros",[])+d.get("cons",[])
    pc_text=" ".join(pc)
    if roe:
        if roe>=25: s+=28;r.append(f"Exceptional ROE {roe:.1f}%")
        elif roe>=18: s+=20;r.append(f"Strong ROE {roe:.1f}%")
        elif roe>=12: s+=12
        elif roe>=8: s+=5
    de=d.get("debt_to_equity")
    if de is not None:
        if de<0.1: s+=25;r.append("Virtually debt-free")
        elif de<0.3: s+=20;r.append("Near debt-free")
        elif de<0.5: s+=14
        elif de<1.0: s+=6
    elif "debt free" in pc_text.lower(): s+=20;r.append("Debt-free")
    opm=to_pct(d.get("operating_margins"))
    if opm:
        if opm>=30: s+=25;r.append(f"Excellent OPM {opm:.1f}%")
        elif opm>=20: s+=18
        elif opm>=12: s+=10
        elif opm>=6: s+=4
    pe=d.get("pe_ratio")
    if pe and pe>0:
        if pe<12: s+=22;r.append(f"Very cheap P/E {pe:.1f}x")
        elif pe<20: s+=16;r.append(f"Reasonable P/E {pe:.1f}x")
        elif pe<30: s+=8
        elif pe<45: s+=3
    return {"score":min(s,100),"reasons":r,"label":"Buffett"}

def score_rj_std(d):
    s,r=0,[]
    roe=to_pct(d.get("roe")); roce=to_pct(d.get("roce"))
    if roe:
        if roe>=30: s+=30;r.append(f"Exceptional ROE {roe:.1f}%")
        elif roe>=22: s+=22
        elif roe>=15: s+=14
        elif roe>=10: s+=6
    if roce:
        if roce>=30: s+=20;r.append(f"Excellent ROCE {roce:.1f}%")
        elif roce>=20: s+=14
        elif roce>=12: s+=7
    pe=d.get("pe_ratio")
    if pe and pe>0:
        if pe<15: s+=20;r.append(f"Attractive P/E {pe:.1f}x")
        elif pe<25: s+=14
        elif pe<40: s+=6
    ph=to_pct(d.get("promoter_holding"))
    if ph:
        if ph>=60: s+=30;r.append(f"Very high promoter {ph:.1f}%")
        elif ph>=50: s+=22;r.append(f"High promoter {ph:.1f}%")
        elif ph>=35: s+=12
    return {"score":min(s,100),"reasons":r,"label":"RJ Style"}

def score_quality_std(d):
    s,r=0,[]
    opm=to_pct(d.get("operating_margins")); roce=to_pct(d.get("roce"))
    dy=to_pct(d.get("dividend_yield")); de=d.get("debt_to_equity")
    pc_text=" ".join(d.get("pros",[])+d.get("cons",[]))
    if opm:
        if opm>=30: s+=30;r.append(f"Wide moat OPM {opm:.1f}%")
        elif opm>=20: s+=22
        elif opm>=12: s+=12
        elif opm>=6: s+=5
    if roce:
        if roce>=30: s+=28;r.append(f"Exceptional ROCE {roce:.1f}%")
        elif roce>=20: s+=20
        elif roce>=12: s+=10
        elif roce>=8: s+=4
    if dy:
        if dy>=4: s+=22;r.append(f"High dividend {dy:.1f}%")
        elif dy>=2: s+=14
        elif dy>=1: s+=7
    if de is not None and de<0.3: s+=20;r.append("Fortress balance sheet")
    elif de is None and "debt free" in pc_text.lower(): s+=18;r.append("Debt-free")
    return {"score":min(s,100),"reasons":r,"label":"Quality/MF"}

def score_value_std(d):
    s,r=0,[]
    pb=d.get("pb_ratio"); pe=d.get("pe_ratio")
    price=d.get("current_price"); high=d.get("52w_high")
    if pb and pb>0:
        if pb<1: s+=40;r.append(f"Below book P/B {pb:.2f}x")
        elif pb<2: s+=28;r.append(f"Near book P/B {pb:.2f}x")
        elif pb<4: s+=16
        elif pb<8: s+=6
        elif pb<15: s+=2
    if pe and pe>0:
        if pe<10: s+=35;r.append(f"Deep value P/E {pe:.1f}x")
        elif pe<15: s+=25
        elif pe<22: s+=15
        elif pe<30: s+=7
        elif pe<40: s+=2
    if price and high and high>0:
        pct_off=((high-price)/high)*100
        if pct_off>=35: s+=25;r.append(f"{pct_off:.0f}% below 52w high")
        elif pct_off>=20: s+=16
        elif pct_off>=10: s+=8
        elif pct_off>=5: s+=3
    return {"score":min(s,100),"reasons":r,"label":"Graham Value"}

def compute_score(d):
    b=score_buffett_std(d); rj=score_rj_std(d); q=score_quality_std(d); v=score_value_std(d)
    composite=round(b["score"]*0.30+rj["score"]*0.30+q["score"]*0.25+v["score"]*0.15,1)
    reasons=b["reasons"]+rj["reasons"]+q["reasons"]+v["reasons"]
    return {
        "composite":composite,
        "scores":{"buffett":b["score"],"rj_style":rj["score"],"quality":q["score"],"value":v["score"]},
        "top_reasons":reasons[:5],
        "sub_scores":[b,rj,q,v],
    }

def conviction_tier(score):
    if score>=70: return "Strong Buy"
    if score>=55: return "Buy"
    if score>=40: return "Watch"
    if score>=25: return "Neutral"
    return "Avoid"

def build_entry(symbol, raw):
    scoring=compute_score(raw)
    matching_profiles=get_matching_profiles(raw)
    return {
        "symbol":symbol,
        "company_name":raw.get("company_name",symbol),
        "sector":raw.get("sector","Unknown"),
        "current_price":raw.get("current_price"),
        "market_cap":raw.get("market_cap"),
        "52w_high":raw.get("52w_high"),
        "52w_low":raw.get("52w_low"),
        "pe_ratio":raw.get("pe_ratio"),
        "pb_ratio":raw.get("pb_ratio"),
        "book_value":raw.get("book_value"),
        "roe":raw.get("roe"),
        "roce":raw.get("roce"),
        "debt_to_equity":raw.get("debt_to_equity"),
        "operating_margins":raw.get("operating_margins"),
        "dividend_yield":raw.get("dividend_yield"),
        "promoter_holding":raw.get("promoter_holding"),
        "eps":raw.get("eps"),
        "pros":raw.get("pros",[]),
        "cons":raw.get("cons",[]),
        "scoring":scoring,
        "conviction":conviction_tier(scoring["composite"]),
        "matching_profiles":matching_profiles,
        "cached_at":datetime.now().isoformat(),
        "source":"screener.in",
    }


# ─── Disk cache ───────────────────────────────────────────────────────────────────
def save_cache_to_disk():
    try:
        with _cache_lock:
            data={"cache_time":_cache_time.isoformat() if _cache_time else None,"stocks":_cache}
        with open(CACHE_FILE,"w") as f: json.dump(data,f)
        print(f"✓ Saved to disk: {len(_cache)} stocks")
    except Exception as e: print(f"✗ Save failed: {e}")

def load_cache_from_disk():
    global _cache,_cache_time
    try:
        if not os.path.exists(CACHE_FILE): print("No disk cache, building fresh"); return False
        with open(CACHE_FILE,"r") as f: data=json.load(f)
        stocks=data.get("stocks",{}); ct=data.get("cache_time")
        if not stocks: return False
        with _cache_lock:
            _cache=stocks
            _cache_time=datetime.fromisoformat(ct) if ct else datetime.now()
        age_h=(datetime.now()-_cache_time).total_seconds()/3600
        print(f"✓ Loaded disk cache: {len(stocks)} stocks, {age_h:.1f}h old")
        return True
    except Exception as e: print(f"✗ Load failed: {e}"); return False


# ─── Cache refresh ────────────────────────────────────────────────────────────────
def refresh_cache():
    global _cache,_cache_time,_is_refreshing,_refresh_progress
    if _is_refreshing: return
    _is_refreshing=True
    _refresh_progress={"done":0,"total":len(STOCK_UNIVERSE)}
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Cache refresh — {len(STOCK_UNIVERSE)} stocks (NSE+BSE)\n")
    new_cache={}
    for i,symbol in enumerate(STOCK_UNIVERSE):
        try:
            print(f"  [{i+1}/{len(STOCK_UNIVERSE)}] {symbol}...",end=" ",flush=True)
            raw=fetch_screener(symbol)
            if raw and (raw.get("pe_ratio") or raw.get("current_price")):
                entry=build_entry(symbol,raw)
                new_cache[symbol]=entry
                roe_d=f"{to_pct(raw.get('roe')):.1f}%" if raw.get("roe") else "-"
                opm_d=f"{to_pct(raw.get('operating_margins')):.1f}%" if raw.get("operating_margins") else "-"
                top_p=entry["matching_profiles"][0]["name"] if entry["matching_profiles"] else "-"
                print(f"✓ score={entry['scoring']['composite']} ROE={roe_d} OPM={opm_d} → {top_p}")
            else:
                print("✗ no data")
            _refresh_progress["done"]=i+1
            # Save every 50 stocks
            if (i+1)%50==0 and new_cache:
                with _cache_lock: _cache.update(new_cache); _cache_time=datetime.now()
                save_cache_to_disk()
            time.sleep(2)
        except Exception as e:
            print(f"✗ {e}"); _refresh_progress["done"]=i+1; time.sleep(2)
    with _cache_lock: _cache=new_cache; _cache_time=datetime.now()
    save_cache_to_disk()
    print(f"\n✓ Cache complete: {len(new_cache)}/{len(STOCK_UNIVERSE)} at {_cache_time.strftime('%H:%M:%S')}\n")
    _is_refreshing=False


@app.on_event("startup")
async def startup():
    loaded=load_cache_from_disk()
    if loaded:
        age_h=(datetime.now()-_cache_time).total_seconds()/3600
        if age_h>12:
            print("Cache stale, refreshing in background...")
            threading.Thread(target=refresh_cache,daemon=True).start()
        else:
            print(f"Cache fresh ({age_h:.1f}h old)")
    else:
        threading.Thread(target=refresh_cache,daemon=True).start()


# ─── Routes ──────────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "app":"stocks.ai by relentless ais","version":"10.0.0",
        "cached_stocks":len(_cache),"refreshing":_is_refreshing,
        "refresh_progress":f"{_refresh_progress['done']}/{_refresh_progress['total']}" if _is_refreshing else "idle",
        "cache_age":str(datetime.now()-_cache_time).split(".")[0] if _cache_time else "warming up",
        "universe_size":len(STOCK_UNIVERSE),
        "investor_profiles":len(INVESTOR_PROFILES),
    }

@app.get("/api/cache/status")
def cache_status():
    return {"ready":len(_cache)>0,"count":len(_cache),"refreshing":_is_refreshing,
            "progress":_refresh_progress,"last_updated":_cache_time.isoformat() if _cache_time else None}

@app.get("/api/cache/refresh")
def trigger_refresh(background_tasks:BackgroundTasks):
    if _is_refreshing: return {"message":"Already refreshing","progress":_refresh_progress}
    background_tasks.add_task(refresh_cache)
    return {"message":"Refresh started"}

@app.get("/api/profiles")
def get_profiles():
    return {"profiles":INVESTOR_PROFILES,"count":len(INVESTOR_PROFILES)}

@app.get("/api/stock/{symbol}")
def get_stock(symbol:str):
    symbol=symbol.upper().strip()
    with _cache_lock:
        if symbol in _cache: return _cache[symbol]
    raw=fetch_screener(symbol)
    if not raw: raise HTTPException(404,f"Could not find {symbol} on Screener.in")
    entry=build_entry(symbol,raw)
    with _cache_lock: _cache[symbol]=entry
    return entry

@app.get("/api/screen")
def screen(
    min_score:float=Query(40),
    sector:Optional[str]=Query(None),
    conviction:Optional[str]=Query(None),
    profile:Optional[str]=Query(None),
    limit:int=Query(30,le=100),
):
    with _cache_lock: stocks=list(_cache.values())
    if not stocks:
        done=_refresh_progress.get("done",0); total=_refresh_progress.get("total",len(STOCK_UNIVERSE))
        return {"count":0,"stocks":[],"warming":True,"message":f"Loading... {done}/{total} done. Try again shortly."}
    results=[]
    for s in stocks:
        if s["scoring"]["composite"]<min_score: continue
        if conviction and conviction.lower() not in s["conviction"].lower(): continue
        if sector and sector.lower() not in (s.get("sector") or "").lower(): continue
        if profile:
            ps=score_profile(s,profile)
            if ps["score"]<35: continue
            s=dict(s); s["profile_score"]=ps["score"]; s["profile_reasons"]=ps["reasons"]
        results.append(s)
    results.sort(key=lambda x:x.get("profile_score",x["scoring"]["composite"]),reverse=True)
    return {"count":len(results),"stocks":results[:limit],"total_cached":len(stocks),
            "universe_size":len(STOCK_UNIVERSE),
            "cache_age":str(datetime.now()-_cache_time).split(".")[0] if _cache_time else "unknown"}

@app.get("/api/watchlist")
def watchlist(symbols:str=Query(...)):
    symbol_list=[s.strip().upper() for s in symbols.split(",") if s.strip()][:20]
    results,missing=[],[]
    with _cache_lock: cached=dict(_cache)
    for sym in symbol_list:
        if sym in cached: results.append(cached[sym])
        else: missing.append(sym)
    for sym in missing:
        try:
            raw=fetch_screener(sym)
            if raw:
                entry=build_entry(sym,raw)
                with _cache_lock: _cache[sym]=entry
                results.append(entry)
            time.sleep(2)
        except Exception as e: print(f"Error {sym}: {e}")
    results.sort(key=lambda x:x["scoring"]["composite"],reverse=True)
    return {"count":len(results),"stocks":results}

@app.get("/api/debug/{symbol}")
def debug_stock(symbol:str):
    raw=fetch_screener(symbol.upper())
    return {"symbol":symbol.upper(),"raw":raw}
