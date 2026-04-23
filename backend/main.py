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
import csv
import io

app = FastAPI(title="stocks.ai API", version="11.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CACHE_FILE = "stock_cache.json"
SECTOR_CACHE_FILE = "sector_cache.json"

_cache = {}
_cache_time = None
_cache_lock = threading.Lock()
_is_refreshing = False
_refresh_progress = {"done": 0, "total": 0}
_sector_averages = {}

# ─── Fetch NSE symbol list automatically ─────────────────────────────────────────
def fetch_nse_symbols() -> list:
    """Download complete NSE equity list and return symbols."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.nseindia.com/",
        }
        session = requests.Session()
        session.headers.update(headers)
        session.get("https://www.nseindia.com", timeout=10)
        time.sleep(1)
        r = session.get(
            "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv",
            timeout=30
        )
        if r.status_code == 200:
            reader = csv.DictReader(io.StringIO(r.text))
            symbols = []
            for row in reader:
                sym = row.get("SYMBOL", "").strip()
                series = row.get("SERIES", "").strip()
                if sym and series == "EQ":  # Only equity, not derivatives
                    symbols.append(sym)
            print(f"✓ Fetched {len(symbols)} NSE symbols")
            return symbols
        else:
            print(f"✗ NSE CSV fetch failed: {r.status_code}")
            return []
    except Exception as e:
        print(f"✗ NSE symbol fetch error: {e}")
        return []


# Fallback hardcoded Nifty 500 if NSE fetch fails
FALLBACK_UNIVERSE = [
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
    "COROMANDEL","CRISIL","DATAMATICS","DEEPAKFERT","EDELWEISS","EMKAY","EPIGRAL",
    "EQUITASBNK","ESABINDIA","GABRIEL","GILLETTE","GIPCL","GMMPFAUDLR","GPIL",
    "GRAPHITE","GSKCONS","GULFOILLUB","HAPPSTMNDS","HINDCOPPER","HPCL","IDBI",
    "IFBIND","IIFL","INDIACEM","INFIBEAM","INGERRAND","INOXWIND","INSECTICID",
    "ISGEC","ITI","JAMNAAUTO","JKIL","JKLAKSHMI","JKPAPER","JKTYRE","JMFINANCIL",
    "KARURVYSYA","KFINTECH","KIMS","KNRCON","KOLTEPATIL","KPRMILL","KRBL","LAOPALA",
    "LATENTVIEW","LAXMIMACH","LLOYDSENGG","LUXIND","MAHINDCIE","MASFIN","MATRIMONY",
    "MAYURUNIQ","MINDACORP","MMTC","MOLDTKPAC","MOTHERSON","MRPL","NAVINFLUOR",
    "NETWORK18","NFL","NIITLTD","NILKAMAL","NOCIL","NUCLEUS","OMAXE","ORIENTELEC",
    "PANACEABIO","PATELENG","PATINTLOG","PENIND","PGHL","PHOENIXLTD","PILANIINVS",
    "PLASTIBLEN","POKARNA","POLYPLEX","POLYMED","POONAWALLA","PRICOLLTD","PVRINOX",
    "QUESS","RAILTEL","RAIN","RALLIS","RAYMOND","RBLBANK","REDINGTON","REPCOHOME",
    "RVNL","SAGARCEM","SAKSOFT","SANDHAR","SANGHIIND","SAREGAMA","SEQUENT",
    "SHAREINDIA","SHILPAMED","SHOPERSTOP","SHYAMMETL","SIGACHI","SKIPPER","SNOWMAN",
    "SOLARA","SPANDANA","SPARC","SPICEJET","STYLAM","SUBROS","SUDARSCHEM","SUMICHEM",
    "SUNDARAM","SUNFLAG","SUPRIYA","SWSOLAR","SYMPHONY","TALBROAUTO","TCIEXP",
    "TCNSBRANDS","TEJASNET","TIINDIA","TIMKEN","TINPLATE","TIPSINDLTD","TITAGARH",
    "TORNTPOWER","TRIDENT","TRIVENI","TTML","UCOBANK","UFLEX","UJJIVAN","UNIPARTS",
    "UNOMINDA","UTTAMSUGAR","VINDHYATEL","VIPIND","VISAKAIND","VOLTAMP","VRLLOG",
    "VSTIND","WABCOINDIA","WELCORP","WELSPUNIND","WESTLIFE","WONDERLA","ZENSARTECH",
]

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
                ne = li.select_one(".name"); ve = li.select_one(".number,.value")
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
            ph_raw = get("Promoter holding","Promoter Holding")
            promoter_holding = (ph_raw/100) if ph_raw is not None else None
            pledge_raw = get("Pledge percentage","Promoter pledge")
            pledge = (pledge_raw/100) if pledge_raw is not None else None

            company_name = symbol
            for sel in ["h1.margin-0","h1"]:
                el = soup.select_one(sel)
                if el: company_name = el.get_text(strip=True); break

            sector = "Unknown"
            for a in soup.select("a[href*='/screen/']"):
                t = a.get_text(strip=True)
                if t and 2 < len(t) < 40 and t not in ("Screener","Login","Sign Up","Home","Screen","Advanced"): sector = t; break
            if sector == "Unknown":
                for sel in [".company-info a", ".breadcrumb a", ".sector a", "span.sector"]:
                    el = soup.select_one(sel)
                    if el:
                        t = el.get_text(strip=True)
                        if t and 2 < len(t) < 40: sector = t; break
            if sector == "Unknown":
                m = re.search(r"Sector[:\s]+([A-Za-z &/]+)\n", soup.get_text())
                if m: sector = m.group(1).strip()

            # Quarterly data — last 4 quarters revenue
            quarterly_revenue = []
            quarterly_profit = []
            for table in soup.select("table"):
                headers_row = table.select("thead th")
                if not headers_row: continue
                header_text = " ".join(h.get_text(strip=True) for h in headers_row)
                if "Sales" in header_text or "Revenue" in header_text:
                    rows = table.select("tbody tr")
                    for row in rows[:8]:
                        cells = row.select("td")
                        if cells:
                            label = cells[0].get_text(strip=True)
                            if "Sales" in label or "Revenue" in label:
                                vals = [parse_number(c.get_text(strip=True)) for c in cells[1:5]]
                                quarterly_revenue = [v for v in vals if v is not None]
                            if "Net Profit" in label or "Profit" in label:
                                vals = [parse_number(c.get_text(strip=True)) for c in cells[1:5]]
                                quarterly_profit = [v for v in vals if v is not None]

            pros = [li.get_text(strip=True) for li in soup.select(".pros li")][:4]
            cons = [li.get_text(strip=True) for li in soup.select(".cons li")][:4]

            result = {
                "company_name": company_name, "sector": sector,
                "current_price": current_price, "market_cap": market_cap,
                "pe_ratio": pe, "pb_ratio": pb, "book_value": book_value,
                "roe": roe, "roce": roce, "debt_to_equity": de,
                "operating_margins": opm, "gross_margins": opm,
                "dividend_yield": dy, "52w_high": w52_high, "52w_low": w52_low,
                "eps": eps, "promoter_holding": promoter_holding,
                "promoter_pledge": pledge,
                "quarterly_revenue": quarterly_revenue,
                "quarterly_profit": quarterly_profit,
                "pros": pros, "cons": cons,
            }
            if not result.get("pe_ratio") and not result.get("current_price"): continue
            return result
        except Exception as e:
            print(f"  Screener error {symbol}: {e}"); continue
    return {}


# ─── Sector averages computation ─────────────────────────────────────────────────
def compute_sector_averages(cache: dict) -> dict:
    """Compute average metrics per sector from cached data."""
    sector_data = {}
    for entry in cache.values():
        sector = entry.get("sector", "Unknown")
        if sector == "Unknown": continue
        if sector not in sector_data:
            sector_data[sector] = {"pe": [], "pb": [], "roe": [], "roce": [], "opm": [], "de": []}
        if entry.get("pe_ratio"): sector_data[sector]["pe"].append(entry["pe_ratio"])
        if entry.get("pb_ratio"): sector_data[sector]["pb"].append(entry["pb_ratio"])
        if entry.get("roe"): sector_data[sector]["roe"].append(entry["roe"])
        if entry.get("roce"): sector_data[sector]["roce"].append(entry["roce"])
        if entry.get("operating_margins"): sector_data[sector]["opm"].append(entry["operating_margins"])
        if entry.get("debt_to_equity"): sector_data[sector]["de"].append(entry["debt_to_equity"])

    averages = {}
    for sector, data in sector_data.items():
        averages[sector] = {}
        for metric, values in data.items():
            if values:
                sorted_vals = sorted(values)
                # Use median to avoid outlier skew
                n = len(sorted_vals)
                averages[sector][metric] = sorted_vals[n//2]
    return averages


# ─── All Investor Profiles ────────────────────────────────────────────────────────
INVESTOR_PROFILES = {
    # ── Indian Legends ──
    "rj": {
        "name": "Rakesh Jhunjhunwala", "avatar": "🐂", "category": "Indian Legend",
        "focus": "India Growth Compounder", "color": "#f59e0b",
        "portfolio_size": 18, "sizing_style": "conviction_weighted",
        "bio": "Known as India's Warren Buffett and the 'Big Bull', Rakesh Jhunjhunwala (1960-2022) turned ₹5,000 into over ₹40,000 crore through a legendary 35-year career. He started trading in 1985 with borrowed money and built one of India's most celebrated investment track records.",
        "philosophy": "Jhunjhunwala believed passionately in India's economic growth story. He invested in businesses that would benefit from India's rising middle class, consumption boom, and infrastructure growth. His mantra was 'Buy right, sit tight' — he held Titan for over 20 years.",
        "what_he_looked_for": "High ROE businesses (>20%), strong promoter conviction (>50% holding), large addressable market, India-specific growth story, reasonable valuation. He preferred businesses with pricing power and brand moats.",
        "what_he_avoided": "Commodity businesses, high debt companies, businesses without pricing power, promoters with poor track record or pledged shares.",
        "famous_investments": ["Titan Company (bought at ₹3, held to ₹3000+)", "Star Health Insurance", "Crisil", "Lupin", "Aptech", "Nazara Technologies"],
        "signature_quote": "I am bullish on India. I think we are going to have a great bull market.",
        "rebalance_style": "Held for decades. Only exited when fundamental thesis broke. Annual review.",
        "description": "High ROE compounders, India growth story, high promoter conviction, buy on dips",
    },
    "ramesh_damani": {
        "name": "Ramesh Damani", "avatar": "🎯", "category": "Indian Legend",
        "focus": "Contrarian Deep Value", "color": "#ef4444",
        "portfolio_size": 12, "sizing_style": "equal_weight",
        "bio": "Ramesh Damani is a BSE member and veteran investor who has been investing in Indian markets since 1989. Known for his contrarian calls and ability to find value in out-of-favour sectors, he is one of India's most respected market voices.",
        "philosophy": "Damani is a classic contrarian — he buys when everyone is selling and sells when everyone is buying. He looks for sectors that are temporarily out of favour due to cyclical headwinds but have strong long-term fundamentals.",
        "what_he_looked_for": "Stocks trading well below historical valuations, sectors at cyclical lows, management with strong track record, dividend-paying businesses, companies with significant margin of safety.",
        "what_he_avoided": "Momentum stocks, businesses at peak valuations, highly leveraged companies, businesses where he couldn't understand the long-term thesis.",
        "famous_investments": ["VST Industries", "Aptech", "CRISIL", "MPS Ltd", "Delta Corp"],
        "signature_quote": "In the short run the market is a voting machine but in the long run it is a weighing machine.",
        "rebalance_style": "Thesis-based. Holds 5-7 years until the contrarian thesis plays out.",
        "description": "Deep value, contrarian, out-of-favour sectors, 5-7 year patience",
    },
    "vijay_kedia": {
        "name": "Vijay Kedia", "avatar": "💡", "category": "Indian Legend",
        "focus": "SMILE — Niche Leaders", "color": "#8b5cf6",
        "portfolio_size": 6, "sizing_style": "very_concentrated",
        "bio": "Vijay Kedia started investing with ₹25,000 and has built a multi-hundred crore portfolio through highly concentrated bets on niche market leaders. Known for his SMILE framework and willingness to hold stocks for a decade or more.",
        "philosophy": "Kedia's SMILE framework: Small in size (of the company), Medium in experience (management), Large in aspiration, Extra-large in market potential. He looks for niche monopolies in industries most investors ignore.",
        "what_he_looked_for": "Small/mid cap companies with niche leadership, management with 10+ years of execution history, large untapped addressable market, high promoter stake (>50%), improving ROE trend.",
        "what_he_avoided": "Large cap stocks (too expensive for the upside), commodity businesses, companies with poor management pedigree, stocks where he couldn't see a 5-10x in 5-7 years.",
        "famous_investments": ["Atul Auto", "Aegis Logistics", "Cera Sanitaryware", "Tejas Networks", "Vaibhav Global"],
        "signature_quote": "If you pick the right business and right management, you don't need to time the market.",
        "rebalance_style": "Ultra long term. Holds 5-10 years. Checks portfolio once a quarter.",
        "description": "SMILE framework — small/mid cap niche monopolies, large opportunity, great management",
    },
    "porinju": {
        "name": "Porinju Veliyath", "avatar": "🔍", "category": "Indian Legend",
        "focus": "Smallcap Contrarian", "color": "#ec4899",
        "portfolio_size": 25, "sizing_style": "equal_weight",
        "bio": "Porinju Veliyath, founder of Equity Intelligence India, is known as the 'Smallcap King'. Starting as a sub-broker, he built a fund that delivered exceptional returns by investing in deeply undervalued small caps ignored by institutions.",
        "philosophy": "Find small companies that are fundamentally sound but completely ignored by institutional investors. The lack of institutional coverage creates mispricing opportunities. Buy when the company is in trouble for temporary reasons, not structural ones.",
        "what_he_looked_for": "Market cap under ₹2,000 Cr, beaten-down prices (30%+ off highs), strong business fundamentals despite temporary headwinds, honest management, low institutional ownership.",
        "what_he_avoided": "Large caps (too efficient, no alpha), businesses with permanent structural problems, managements with integrity issues.",
        "famous_investments": ["Geojit Financial", "Wonderla Holidays", "V-Guard Industries", "Kitex Garments"],
        "signature_quote": "Markets are not efficient in the small cap space. That's where the opportunity lies.",
        "rebalance_style": "Event-driven. Exits when the turnaround thesis plays out or breaks.",
        "description": "Deep smallcap, turnaround stories, beaten-down stocks ignored by institutions",
    },
    "ashish_kacholia": {
        "name": "Ashish Kacholia", "avatar": "🚀", "category": "Indian Legend",
        "focus": "Emerging Compounders", "color": "#84cc16",
        "portfolio_size": 20, "sizing_style": "equal_weight",
        "bio": "Ashish Kacholia, often called the 'Big Whale' of smallcap investing, is known for identifying emerging compounders before they become mainstream. He has a remarkable track record of finding multi-baggers in the smallcap space.",
        "philosophy": "Look for scalable business models in smallcap space with high ROE, strong management, and a large runway for growth. The best investments are businesses that can grow 10x in revenues while maintaining or improving margins.",
        "what_he_looked_for": "Smallcap companies (₹500-5000 Cr), high ROE (>20%), scalable business model, good management with track record, improving margins, low debt.",
        "what_he_avoided": "Loss-making companies, businesses without clear path to profitability, high debt companies, promoters with integrity concerns.",
        "famous_investments": ["Wonderla Holidays", "Repco Home Finance", "Garware Technical Fibres", "Safari Industries", "Praveg"],
        "signature_quote": "I look for businesses that can become 10x in 7-10 years.",
        "rebalance_style": "Annual review. Replaces underperformers with better opportunities.",
        "description": "Smallcap quality growth, scalable businesses, emerging sector leaders",
    },
    "dolly_khanna": {
        "name": "Dolly Khanna", "avatar": "💎", "category": "Indian Legend",
        "focus": "Cyclical Turnarounds", "color": "#f472b6",
        "portfolio_size": 25, "sizing_style": "equal_weight",
        "bio": "Dolly Khanna is one of India's most successful retail investors, managing investments alongside her husband Rajiv Khanna. Known for her ability to identify cyclical businesses at turnaround points, she has consistently found multi-baggers in sectors others ignore.",
        "philosophy": "Find cyclical businesses at the bottom of their cycle. Buy when the sector is hated, hold through the recovery, sell when valuations are stretched. Focus on under-the-radar small caps with strong fundamentals.",
        "what_he_looked_for": "Small caps under ₹3,000 Cr, cyclical businesses at trough valuations, sectors out of favour, strong balance sheets to survive the downturn, improving operational metrics.",
        "what_he_avoided": "Large caps, businesses with poor balance sheets that might not survive the cycle, management with integrity issues.",
        "famous_investments": ["Nilkamal", "Rain Industries", "Thirumalai Chemicals", "PPAP Automotive", "Tinna Rubber"],
        "signature_quote": "Buy what others are ignoring. Sell what others are chasing.",
        "rebalance_style": "Semi-annual. Exits when cyclical recovery is fully priced in.",
        "description": "Under-the-radar cyclicals, turnaround stories, ignored smallcaps with pricing power",
    },
    "chandrakant_sampat": {
        "name": "Chandrakant Sampat", "avatar": "📜", "category": "Indian Legend",
        "focus": "Original Indian Value", "color": "#a78bfa",
        "portfolio_size": 10, "sizing_style": "conviction_weighted",
        "bio": "Chandrakant Sampat (1928-2015) is considered India's original value investor, predating even Buffett's fame in India. He invested in Hindustan Unilever and similar consumer monopolies decades before it became fashionable. A true pioneer of long-term value investing in India.",
        "philosophy": "Invest in businesses that sell essential products/services that people need regardless of economic cycles. Debt-free companies with strong brands and pricing power that compound quietly over decades.",
        "what_he_looked_for": "Debt-free balance sheets, consumer monopolies, strong brand moats, consistent dividend payers, businesses with 20+ year runway, high ROE without leverage.",
        "what_he_avoided": "Leveraged businesses, commodity companies, businesses dependent on government contracts, cyclical industries.",
        "famous_investments": ["Hindustan Unilever (held for 40+ years)", "Colgate-Palmolive", "Nestle India", "Infosys (early investor)"],
        "signature_quote": "Invest in a business that even a fool can run, because someday a fool will.",
        "rebalance_style": "Decades-long holds. Portfolio turnover near zero.",
        "description": "India's original Buffett — consumer monopolies, debt-free, decades-long compounders",
    },
    "radhakishan_damani": {
        "name": "Radhakishan Damani", "avatar": "🛒", "category": "Indian Legend",
        "focus": "Retail & Consumer Value", "color": "#fb923c",
        "portfolio_size": 8, "sizing_style": "very_concentrated",
        "bio": "Radhakishan Damani, founder of DMart and Avenue Supermarts, is one of India's wealthiest individuals. Before DMart, he was a legendary investor known for his contrarian calls and deep value approach in the 1990s and 2000s.",
        "philosophy": "Extremely concentrated bets on businesses he deeply understands. Prefers consumer-facing businesses with pricing power, everyday essential products, and low-cost operational models. DMart itself embodies his philosophy — EDLP (Every Day Low Price).",
        "what_he_looked_for": "Consumer businesses with durable competitive advantage, low-cost operators, essential products, strong cash flow generation, owner-operated businesses.",
        "what_he_avoided": "Capital-intensive businesses, high debt, businesses dependent on advertising for survival, luxury goods.",
        "famous_investments": ["Avenue Supermarts (DMart)", "VST Industries", "3M India", "United Breweries"],
        "signature_quote": "Build a business where customers come back every day.",
        "rebalance_style": "Very long term. Once invested, rarely exits.",
        "description": "Consumer + retail lens, EDLP businesses, essential products, low debt",
    },
    "raamdeo_agrawal": {
        "name": "Raamdeo Agrawal", "avatar": "📋", "category": "Indian Legend",
        "focus": "QGLP — Quality Growth", "color": "#60a5fa",
        "portfolio_size": 20, "sizing_style": "conviction_weighted",
        "bio": "Raamdeo Agrawal, co-founder of Motilal Oswal Financial Services, developed the QGLP framework that has guided billions in Indian equity investment. A chartered accountant turned investor, he has compounded wealth at >25% CAGR for over 30 years.",
        "philosophy": "QGLP: Quality of business and management, Growth in earnings (>20% for 5+ years), Longevity of the growth runway (10+ years), Price that is reasonable (PEG < 1.5). All four must align.",
        "what_he_looked_for": "ROE > 20%, earnings growth > 20% for 5 years, large addressable market, honest management with track record, PE reasonable relative to growth.",
        "what_he_avoided": "Commodity businesses, high debt, management with integrity issues, businesses with < 5 year earnings visibility.",
        "famous_investments": ["Eicher Motors", "Page Industries", "HDFC Bank", "Infosys"],
        "signature_quote": "Wealth creation is all about owning great businesses for a long period of time.",
        "rebalance_style": "Annual formal review. Replaces slowest growers.",
        "description": "QGLP pioneer — Quality + Growth + Longevity + Price framework",
    },
    "sanjay_bakshi": {
        "name": "Sanjay Bakshi", "avatar": "🎓", "category": "Indian Legend",
        "focus": "Behavioral Value Investing", "color": "#818cf8",
        "portfolio_size": 15, "sizing_style": "conviction_weighted",
        "bio": "Sanjay Bakshi is a professor at MDI Gurgaon and founder of ValueQuest Capital. A disciple of Ben Graham and Charlie Munger, he brings academic rigor to value investing and is known for his deep research approach.",
        "philosophy": "Combines Graham's margin of safety with Munger's quality-compounder approach. Heavy emphasis on behavioral finance — buy when others are irrationally fearful. Focuses on 'moaty' businesses trading at discount due to temporary problems.",
        "what_he_looked_for": "High-quality businesses at temporary discount, monopolistic characteristics, owner-operators, high ROCE, low debt, businesses benefiting from behavioral mispricing.",
        "what_he_avoided": "Businesses he doesn't deeply understand, highly leveraged companies, businesses without durable competitive advantage.",
        "famous_investments": ["Relaxo Footwear", "Hawkins Cookers", "La Opala", "Astral Poly"],
        "signature_quote": "The best time to buy a great business is when it's being given away.",
        "rebalance_style": "Thesis-based. Patient 3-7 year holds.",
        "description": "Academic value investing, behavioral finance lens, moaty businesses at temporary discount",
    },
    "kenneth_andrade": {
        "name": "Kenneth Andrade (Old Bridge)", "avatar": "🌉", "category": "Indian Legend",
        "focus": "Asset-Light Capital Efficiency", "color": "#34d399",
        "portfolio_size": 20, "sizing_style": "equal_weight",
        "bio": "Kenneth Andrade, founder of Old Bridge Capital, is known for his contrarian, asset-light investment philosophy. He ran IDFC Premier Equity Fund before starting Old Bridge, delivering exceptional returns.",
        "philosophy": "Focus on asset-light businesses with high capital efficiency. Avoid capital-intensive businesses. Look for companies where earnings growth doesn't require proportional capital investment. Contrarian — buys underperforming sectors.",
        "what_he_looked_for": "Asset-light models, high asset turnover, capital-efficient businesses, sectors at cyclical lows, ROCE improvement trend.",
        "what_he_avoided": "Capital-intensive manufacturing, businesses requiring constant capex, highly leveraged balance sheets.",
        "famous_investments": ["PI Industries", "Sudarshan Chemicals", "Aavas Financiers", "Cera Sanitaryware"],
        "signature_quote": "Asset-light businesses are the future of wealth creation.",
        "rebalance_style": "Semi-annual. Rotates out of fully valued into undervalued sectors.",
        "description": "Asset-light businesses, high capital efficiency, ROCE focus, contrarian sector rotation",
    },
    "manish_kejriwal": {
        "name": "Manish Kejriwal (Amansa Capital)", "avatar": "🌐", "category": "Indian Legend",
        "focus": "Quality Growth PE Style", "color": "#f0abfc",
        "portfolio_size": 15, "sizing_style": "conviction_weighted",
        "bio": "Manish Kejriwal founded Amansa Capital after stints at Goldman Sachs and Temasek. He brings a private equity mindset to public market investing — long holding periods, deep business analysis, focus on quality compounders.",
        "philosophy": "Invest like a PE fund in public markets. Buy stakes in high-quality businesses with long growth runways and hold for 5-10 years. Management quality and corporate governance are paramount.",
        "what_he_looked_for": "World-class management, high ROE (>20%), durable competitive moat, large addressable market, strong corporate governance, consistent capital allocation.",
        "what_he_avoided": "Businesses with governance concerns, high leverage, businesses in highly competitive commoditized industries.",
        "famous_investments": ["Info Edge (Naukri)", "HDFC Life", "Asian Paints", "Pidilite Industries"],
        "signature_quote": "We invest in businesses, not stocks.",
        "rebalance_style": "Long-term 5-10 year holds. Very low portfolio turnover.",
        "description": "Private equity mindset in public markets, world-class management, 5-10 year holds",
    },
    # ── Global Legends ──
    "buffett": {
        "name": "Warren Buffett", "avatar": "🧠", "category": "Global Legend",
        "focus": "Quality at Fair Price", "color": "#3b82f6",
        "portfolio_size": 10, "sizing_style": "very_concentrated",
        "bio": "Warren Buffett, the 'Oracle of Omaha', is widely considered the greatest investor of all time. Starting with Graham's deep value approach, he evolved to buying wonderful businesses at fair prices under Charlie Munger's influence. His Berkshire Hathaway has compounded at ~20% CAGR for 58 years.",
        "philosophy": "Buy wonderful businesses at fair prices and hold forever. A wonderful business has durable competitive advantages (moats), consistent high ROE without leverage, strong management, and generates free cash flow. Price matters but quality matters more.",
        "what_he_looked_for": "ROE > 20% consistently, low debt, pricing power, brand moat, simple understandable business, honest management, free cash flow generation.",
        "what_he_avoided": "Businesses he can't understand, highly leveraged companies, commodity businesses without pricing power, businesses requiring constant capital reinvestment.",
        "famous_investments": ["Coca-Cola (1988)", "American Express", "Apple", "GEICO", "Bank of America"],
        "signature_quote": "It's far better to buy a wonderful company at a fair price than a fair company at a wonderful price.",
        "rebalance_style": "Favourite holding period is forever. Rarely sells.",
        "description": "Durable moat, consistent high ROE, low debt, buy below intrinsic value",
    },
    "peter_lynch": {
        "name": "Peter Lynch", "avatar": "📈", "category": "Global Legend",
        "focus": "GARP — Growth at Reasonable Price", "color": "#06b6d4",
        "portfolio_size": 30, "sizing_style": "equal_weight",
        "bio": "Peter Lynch managed Fidelity's Magellan Fund from 1977-1990, achieving 29.2% annual returns — the best 13-year run of any mutual fund in history. He popularized the concept of 'invest in what you know' and the PEG ratio.",
        "philosophy": "Invest in companies you understand from daily life. Use PEG ratio (PE/Growth) to find growth at reasonable price. A PEG below 1 means you're getting growth cheap. Diversify widely in stocks you've thoroughly researched.",
        "what_he_looked_for": "PEG ratio < 1, companies growing earnings > 20%, businesses he could explain in 2 minutes, under-followed companies, turnaround stories.",
        "what_he_avoided": "Businesses he didn't understand, 'hot' industries with heavy competition, companies with too much debt.",
        "famous_investments": ["Dunkin' Donuts", "Taco Bell", "Subaru", "La Quinta Motor Inns"],
        "signature_quote": "Invest in what you know.",
        "rebalance_style": "Quarterly review as fund manager. For personal portfolio, annual.",
        "description": "PEG ratio focus, invest in what you know, hidden gems in boring sectors",
    },
    "ben_graham": {
        "name": "Benjamin Graham", "avatar": "⚖️", "category": "Global Legend",
        "focus": "Deep Value / Margin of Safety", "color": "#64748b",
        "portfolio_size": 25, "sizing_style": "equal_weight",
        "bio": "Benjamin Graham, the 'Father of Value Investing', wrote The Intelligent Investor and Security Analysis — the bibles of value investing. Warren Buffett called him the second most influential person in his life after his father. Graham survived the 1929 crash and developed a systematic approach to finding undervalued stocks.",
        "philosophy": "Always buy with a significant margin of safety — the gap between intrinsic value and price. Never overpay. Treat stocks as ownership in real businesses. Be the rational investor when others are emotional.",
        "what_he_looked_for": "P/B below 1.5, P/E below 15, low debt, positive earnings for 10 years, dividend payments, working capital > long-term debt.",
        "what_he_avoided": "Speculative stocks, growth stocks at premium valuations, businesses with poor balance sheets.",
        "famous_investments": ["GEICO (bought at extreme discount)", "Northern Pipeline (net-net)"],
        "signature_quote": "The margin of safety is always dependent on the price paid.",
        "rebalance_style": "Annual rebalance. Systematic rules-based approach.",
        "description": "Buy below book value, wide margin of safety, net-net stocks, absolute value",
    },
    "charlie_munger": {
        "name": "Charlie Munger", "avatar": "🦁", "category": "Global Legend",
        "focus": "Wonderful Company at Fair Price", "color": "#0ea5e9",
        "portfolio_size": 5, "sizing_style": "very_concentrated",
        "bio": "Charlie Munger, Buffett's partner at Berkshire Hathaway for 60 years, was perhaps the most intellectually rigorous investor of his generation. He transformed Buffett from a Graham-style deep value investor to a quality compounder investor. He managed Daily Journal Corporation's portfolio well into his 90s.",
        "philosophy": "A few wonderful businesses held forever beats a hundred mediocre ones traded frequently. Look for businesses with durable competitive moats, pricing power, and high ROCE. Use mental models from multiple disciplines to avoid errors.",
        "what_he_looked_for": "ROCE > 25%, pricing power, durable moat (brand, network effect, switching costs), honest management, simple business.",
        "what_he_avoided": "Complex businesses, commodity businesses, management that speaks in jargon, highly leveraged balance sheets.",
        "famous_investments": ["BYD (personal portfolio)", "Berkshire Hathaway investments alongside Buffett"],
        "signature_quote": "I have nothing to add.",
        "rebalance_style": "Ultra-long term. Very rare portfolio changes.",
        "description": "Ultra-concentrated wonderful companies, ROCE focus, hold forever",
    },
    "phil_fisher": {
        "name": "Philip Fisher", "avatar": "🔭", "category": "Global Legend",
        "focus": "Scuttlebutt Growth Investor", "color": "#14b8a6",
        "portfolio_size": 12, "sizing_style": "conviction_weighted",
        "bio": "Philip Fisher wrote Common Stocks and Uncommon Profits (1958), one of the most influential investment books ever written. His scuttlebutt method — researching companies through industry contacts, suppliers, customers, and competitors — was revolutionary. Warren Buffett said he was '85% Graham and 15% Fisher'.",
        "philosophy": "Buy outstanding companies with superior long-term growth prospects and hold them for years. Use the scuttlebutt method to deeply understand the business. Management quality is paramount.",
        "what_he_looked_for": "Strong sales growth, high profit margins, R&D investment, excellent management, good labor relations, proprietary products or services.",
        "what_he_avoided": "Businesses solely focused on price competition, poor management teams, businesses without R&D investment.",
        "famous_investments": ["Motorola (held for decades)", "Texas Instruments", "Dow Chemical"],
        "signature_quote": "The stock market is filled with individuals who know the price of everything, but the value of nothing.",
        "rebalance_style": "Long-term growth holds. Exits when growth thesis breaks.",
        "description": "Outstanding growth companies, deep research scuttlebutt method, management quality",
    },
    # ── Indian Fund Houses ──
    "parag_parikh": {
        "name": "Parag Parikh Flexi Cap", "avatar": "🌍", "category": "Indian Fund",
        "focus": "Owner-Operator Quality", "color": "#10b981",
        "portfolio_size": 22, "sizing_style": "equal_weight",
        "bio": "Parag Parikh Financial Advisory Services (PPFAS) manages one of India's most respected mutual funds. Founded by the late Parag Parikh, the fund is known for its low churn, behavioral investing approach, and willingness to hold cash when markets are overvalued.",
        "philosophy": "Invest in businesses run by owner-operators with skin in the game. Focus on pricing power, durable competitive advantages, and behavioral discipline — avoid getting caught in market euphoria. Hold cash when valuations are stretched.",
        "what_he_looked_for": "Owner-operators (>30% promoter holding), pricing power (OPM > 15%), low debt, consistent ROE, global comparable businesses, behavioral discipline.",
        "what_he_avoided": "Highly valued momentum stocks, businesses without pricing power, high leverage, frequent management changes.",
        "famous_investments": ["HDFC Bank", "Bajaj Holdings", "ITC", "Coal India", "Alphabet (global)"],
        "signature_quote": "We buy businesses, not stocks.",
        "rebalance_style": "Semi-annual formal review. Low turnover fund.",
        "description": "Pricing power, owner-operator promoters, low churn, behavioral discipline",
    },
    "marcellus": {
        "name": "Marcellus Investment (Saurabh Mukherjea)", "avatar": "🔬", "category": "Indian Fund",
        "focus": "Forensic Quality Only", "color": "#06b6d4",
        "portfolio_size": 12, "sizing_style": "equal_weight",
        "bio": "Saurabh Mukherjea founded Marcellus Investment Managers in 2018 after leading Ambit Capital's research. His Consistent Compounders Portfolio (CCP) uses forensic accounting screens to identify companies with clean books and consistently high ROCE.",
        "philosophy": "The best investments are businesses with virtually zero debt, ROCE consistently above 25%, and clean accounting. Most Indian businesses fail the forensic screen. The ones that pass tend to compound for decades.",
        "what_he_looked_for": "Zero/near-zero debt, ROCE > 25% for 10 consecutive years, clean accounting (no aggressive revenue recognition), consistent margins, low working capital cycle.",
        "what_he_avoided": "Any leverage, aggressive accounting practices, businesses with related-party transactions, promoter pledge.",
        "famous_investments": ["Asian Paints", "HDFC Bank", "Pidilite Industries", "Nestle India", "Bajaj Finance"],
        "signature_quote": "Great businesses destroy the competition slowly and surely.",
        "rebalance_style": "Annual April rebalance. Replaces bottom 2-3 performers.",
        "description": "Zero debt, very high ROCE, clean accounts, forensic quality filter",
    },
    "motilal_qglp": {
        "name": "Motilal Oswal QGLP", "avatar": "📊", "category": "Indian Fund",
        "focus": "Quality + Growth + Longevity + Price", "color": "#f97316",
        "portfolio_size": 20, "sizing_style": "conviction_weighted",
        "bio": "Motilal Oswal Asset Management applies the QGLP framework pioneered by Raamdeo Agrawal. The framework has been refined over 30 years and guides one of India's largest equity PMS businesses.",
        "philosophy": "All four QGLP pillars must be present: Quality business with strong moat, Growth in earnings > 20% for 5 years, Longevity of growth runway (10+ years still ahead), Price that is reasonable relative to growth (PEG < 1.5).",
        "what_he_looked_for": "ROE > 20%, earnings growth > 20% consistently, large TAM with 10+ year runway, management with execution track record, PEG ratio under 1.5.",
        "what_he_avoided": "Low-quality businesses even at cheap valuations, good businesses at unreasonable prices, businesses without 10-year earnings visibility.",
        "famous_investments": ["Eicher Motors", "Page Industries", "Bajaj Finance", "Avenue Supermarts"],
        "signature_quote": "Buy right, sit tight.",
        "rebalance_style": "Annual formal rebalance. Disciplined process.",
        "description": "All four QGLP criteria must be met — quality, growth, longevity, price",
    },
    "nippon_smallcap": {
        "name": "Nippon India Small Cap", "avatar": "🌱", "category": "Indian Fund",
        "focus": "High Growth Small Caps", "color": "#22d3ee",
        "portfolio_size": 60, "sizing_style": "equal_weight",
        "bio": "Nippon India Small Cap Fund is one of India's largest small cap funds with over ₹50,000 Cr AUM. It invests across the small cap spectrum with a focus on growth businesses in emerging sectors.",
        "philosophy": "Diversified exposure to India's small cap growth story. Find emerging sector leaders before they become mainstream. Willing to pay higher multiples for high growth businesses. Wide diversification reduces individual stock risk.",
        "what_he_looked_for": "Small cap companies (market cap ₹500-8000 Cr), high revenue growth (>20%), improving profitability, sector leadership potential, scalable business models.",
        "what_he_avoided": "Companies with too much debt, loss-making businesses without clear path to profitability, businesses in permanently declining industries.",
        "famous_investments": ["Tube Investments", "Navin Fluorine", "Happiest Minds", "KPIT Technologies"],
        "signature_quote": "Small caps today are large caps tomorrow.",
        "rebalance_style": "Quarterly review with high turnover due to fund flows.",
        "description": "Diversified small cap growth, emerging sector leaders, high growth businesses",
    },
    "mirae_asset": {
        "name": "Mirae Asset India", "avatar": "🏆", "category": "Indian Fund",
        "focus": "Quality Growth Large Cap", "color": "#a3e635",
        "portfolio_size": 55, "sizing_style": "market_cap_weighted",
        "bio": "Mirae Asset Investment Managers India is the Indian arm of South Korean giant Mirae Asset. Known for disciplined, process-driven investing, Mirae India Equity has consistently outperformed its benchmark.",
        "philosophy": "Bottom-up stock selection focusing on quality businesses with sustainable competitive advantages. Sector leaders with consistent earnings growth and strong return ratios. Risk management is central to the process.",
        "what_he_looked_for": "Sector leadership, consistent earnings growth, strong ROE and ROCE, reasonable valuations, well-managed balance sheets.",
        "what_he_avoided": "Speculative businesses, high leverage, businesses without clear competitive advantage.",
        "famous_investments": ["ICICI Bank", "Infosys", "Maruti Suzuki", "Bharti Airtel", "Kotak Mahindra"],
        "signature_quote": "Quality businesses at reasonable prices outperform over time.",
        "rebalance_style": "Quarterly review. Benchmark-aware.",
        "description": "Sector leaders, quality businesses, consistent earnings growth, risk management",
    },
    "hdfc_mf": {
        "name": "HDFC Mutual Fund (Prashant Jain Era)", "avatar": "🏦", "category": "Indian Fund",
        "focus": "Value + Quality Blend", "color": "#fb923c",
        "portfolio_size": 50, "sizing_style": "conviction_weighted",
        "bio": "Under Prashant Jain (2003-2022), HDFC Equity Fund became one of India's most respected equity funds. Known for contrarian calls — buying public sector banks and infrastructure when others avoided them — Jain delivered exceptional long-term returns through a blend of value and quality.",
        "philosophy": "Buy quality businesses at value prices. Don't hesitate to be contrarian — PSU banks, infrastructure, and cyclicals have their time. Patient capital. Hold through 3-5 year down cycles if the long-term thesis is intact.",
        "what_he_looked_for": "Quality businesses at value multiples, PSU/cyclical businesses at trough valuations, consistent dividend payers, businesses with strong management.",
        "what_he_avoided": "Businesses at extreme valuations, highly leveraged companies, businesses without earnings visibility.",
        "famous_investments": ["SBI", "HDFC Bank", "Infosys", "BHEL (contrarian)", "ONGC"],
        "signature_quote": "Be contrarian. Buy when others are selling.",
        "rebalance_style": "Patient 3-5 year holds. Contrarian rebalancing.",
        "description": "Value + quality blend, contrarian at times, patient long-term capital",
    },
    "anand_rathi": {
        "name": "Anand Rathi Wealth", "avatar": "⚡", "category": "Indian Fund",
        "focus": "Wealth Preservation + Growth", "color": "#fbbf24",
        "portfolio_size": 25, "sizing_style": "risk_weighted",
        "bio": "Anand Rathi Wealth is one of India's leading wealth management firms, focused on HNI and ultra-HNI clients. Their investment approach prioritizes capital preservation alongside growth, with heavy emphasis on asset allocation.",
        "philosophy": "Wealth preservation first, growth second. Large cap bias for stability. Dividend-paying businesses for income. Portfolio construction with risk management as a central theme. Asset allocation across equity, debt, and alternatives.",
        "what_he_looked_for": "Large cap stability (market cap > ₹10,000 Cr), consistent dividend payers, low debt, strong corporate governance, defensive sectors.",
        "what_he_avoided": "Highly speculative smallcaps, businesses with governance issues, high leverage.",
        "famous_investments": ["HDFC Bank", "Infosys", "Reliance", "ITC", "Bajaj Finance"],
        "signature_quote": "Preserving wealth is as important as creating it.",
        "rebalance_style": "Semi-annual with asset allocation review.",
        "description": "HNI wealth management, large cap bias, capital preservation, dividend focus",
    },
    "white_oak": {
        "name": "White Oak Capital (Prashant Khemka)", "avatar": "🌳", "category": "Indian Fund",
        "focus": "Earnings Quality Growth", "color": "#86efac",
        "portfolio_size": 30, "sizing_style": "equal_weight",
        "bio": "Prashant Khemka founded White Oak Capital after a stellar career at Goldman Sachs Asset Management where he managed India equity. White Oak focuses on a rigorous bottom-up approach emphasizing earnings quality and return on equity.",
        "philosophy": "Earnings quality is the foundation. High, sustainable ROE without leverage. Business quality drives long-term returns. GARP approach — willing to pay for growth but not at any price.",
        "what_he_looked_for": "ROE > 20% without leverage, earnings quality (cash conversion), consistent growth, reasonable valuation (PEG < 1.5), strong management.",
        "what_he_avoided": "Businesses with poor earnings quality, high leverage, businesses where ROE depends on leverage not operational excellence.",
        "famous_investments": ["ICICI Bank", "Kotak Bank", "Maruti", "Titan", "Asian Paints"],
        "signature_quote": "Earnings quality separates sustainable returns from temporary ones.",
        "rebalance_style": "Annual rebalance. Equal weight approach.",
        "description": "Earnings quality, ROE without leverage, GARP approach, Goldman Sachs rigor",
    },
    "enam": {
        "name": "Enam Securities / Vallabh Bhansali", "avatar": "🛡️", "category": "Indian Fund",
        "focus": "Forensic Long-Term Quality", "color": "#c4b5fd",
        "portfolio_size": 15, "sizing_style": "conviction_weighted",
        "bio": "Enam Securities, founded by Vallabh Bhansali and Nemish Shah, is one of India's most respected institutional brokers and investors. Known for deep fundamental research and integrity-first approach, Enam's investment calls have created generational wealth for clients.",
        "philosophy": "Management integrity is non-negotiable. Zero tolerance for governance issues. Debt-free businesses with long track records. 10+ year investment horizon. Research everything before investing — no shortcuts.",
        "what_he_looked_for": "Management integrity above all, debt-free or near-debt-free, consistent 10+ year track record, high ROCE, businesses with pricing power, long-term earnings visibility.",
        "what_he_avoided": "Any management integrity concerns, leveraged businesses, businesses dependent on government approvals, short-term trading.",
        "famous_investments": ["HDFC Bank", "Infosys", "Asian Paints", "Hero Honda (early)"],
        "signature_quote": "Management integrity is the first filter. Everything else is secondary.",
        "rebalance_style": "Very long term. Extremely low turnover.",
        "description": "Management integrity first, debt-free, forensic accounting, 10+ year horizon",
    },
    "nemish_shah": {
        "name": "Nemish Shah (Enam Co-Founder)", "avatar": "🎯", "category": "Indian Fund",
        "focus": "Consumer & Pharma Quality", "color": "#e879f9",
        "portfolio_size": 15, "sizing_style": "conviction_weighted",
        "bio": "Nemish Shah co-founded Enam Securities with Vallabh Bhansali and is known for his deep expertise in consumer and pharmaceutical businesses. His investment thesis centres on businesses selling essential products with strong brand moats.",
        "philosophy": "Focus on consumer staples and pharma — businesses people need regardless of the economy. Brands with pricing power, high repeat purchase, and strong distribution networks compound quietly for decades.",
        "what_he_looked_for": "Consumer brands with pricing power, pharmaceutical businesses with strong product pipelines, high repeat purchase businesses, debt-free balance sheets, consistent dividend payers.",
        "what_he_avoided": "Capital-intensive businesses, businesses without brand moat, high debt, management with integrity concerns.",
        "famous_investments": ["Hindustan Unilever", "Nestle India", "Abbott India", "Colgate-Palmolive"],
        "signature_quote": "Consumer brands are the closest thing to a perpetual motion machine in business.",
        "rebalance_style": "Very long term holds. Decades in some cases.",
        "description": "Consumer & pharma specialist, brand moats, pricing power, debt-free",
    },
    "ask_investment": {
        "name": "ASK Investment Managers", "avatar": "💰", "category": "Indian Fund",
        "focus": "Quality Large Cap PMS", "color": "#fdba74",
        "portfolio_size": 20, "sizing_style": "conviction_weighted",
        "bio": "ASK Investment Managers is one of India's largest PMS providers with over ₹70,000 Cr in AUM. Known for their quality-focused approach and wealth preservation philosophy for HNI clients.",
        "philosophy": "Capital preservation with growth. Focus on large, quality businesses with strong balance sheets. Dividend-paying companies for income. Low churn, patient approach. Strong risk management framework.",
        "what_he_looked_for": "Large cap quality (>₹10,000 Cr market cap), consistent earnings growth, strong ROE, low debt, dividend payers, strong corporate governance.",
        "what_he_avoided": "Small caps, businesses with governance concerns, high leverage, loss-making businesses.",
        "famous_investments": ["HDFC Bank", "Bajaj Finance", "Asian Paints", "Infosys", "Kotak Bank"],
        "signature_quote": "Quality never goes out of style.",
        "rebalance_style": "Annual. Low turnover wealth management approach.",
        "description": "Quality large cap PMS, wealth preservation, consistent earnings, low leverage",
    },
    "carnelian": {
        "name": "Carnelian Asset (Vikas Khemani)", "avatar": "💫", "category": "Indian Fund",
        "focus": "Emerging Sector Leaders", "color": "#67e8f9",
        "portfolio_size": 20, "sizing_style": "equal_weight",
        "bio": "Vikas Khemani founded Carnelian Asset Management after leading Edelweiss Securities. His philosophy centres on identifying emerging compounders — businesses in sectors with strong tailwinds before they become mainstream.",
        "philosophy": "Find businesses in sectors with strong structural tailwinds — defence, specialty chemicals, digital India, healthcare. Look for companies transitioning from small to mid cap that will benefit from sector re-rating.",
        "what_he_looked_for": "Emerging sector leaders in structural growth industries, improving margin profile, management with execution track record, high promoter holding, market cap ₹500-15,000 Cr.",
        "what_he_avoided": "Businesses in structurally declining industries, high leverage, management without track record.",
        "famous_investments": ["KPIT Technologies", "Mas Financial", "Tanla Platforms", "Affle India"],
        "signature_quote": "Invest in the future, not the past.",
        "rebalance_style": "Semi-annual review. Adds to winners, exits underperformers.",
        "description": "Emerging compounders, structural sector tailwinds, transitioning small to mid cap",
    },
    "murugappa": {
        "name": "Murugappa Group Style", "avatar": "🏭", "category": "Indian Fund",
        "focus": "South India Industrial Quality", "color": "#fcd34d",
        "portfolio_size": 15, "sizing_style": "equal_weight",
        "bio": "The Murugappa Group is a 125-year-old Chennai-based conglomerate with businesses in fertilizers, engineering, finance, and consumer products. Their investment philosophy reflects generations of industrial wealth creation — patient, conservative, quality-focused.",
        "philosophy": "Long-term industrial value creation. Manufacturing excellence, operational efficiency, conservative balance sheets. Family-run businesses with multi-generational thinking. South India's values of conservatism, hard work, and reinvestment.",
        "what_he_looked_for": "Manufacturing excellence, operational efficiency, conservative balance sheets (low debt), consistent dividend history, family-managed businesses with long track records, dividend growth.",
        "what_he_avoided": "Speculative businesses, high leverage, businesses requiring constant external capital, short-term focus.",
        "famous_investments": ["Coromandel International", "Carborundum Universal", "Cholamandalam Investment", "EID Parry"],
        "signature_quote": "Build businesses that last generations.",
        "rebalance_style": "Very long term. Generational investment horizon.",
        "description": "Industrial manufacturing, conservative balance sheets, multi-generational quality",
    },
}


# ─── Portfolio sizing logic per profile ──────────────────────────────────────────
def get_portfolio_allocation(profile_id: str, stocks: list, capital: float) -> dict:
    """Generate position-sized portfolio for a given investor profile."""
    profile = INVESTOR_PROFILES.get(profile_id, {})
    sizing_style = profile.get("sizing_style", "equal_weight")
    n = len(stocks)
    if n == 0: return {"positions": [], "summary": ""}

    allocations = []

    if sizing_style == "very_concentrated":
        # Top stock 25-30%, second 20%, rest equal
        weights = []
        if n >= 1: weights.append(0.28)
        if n >= 2: weights.append(0.20)
        if n >= 3: weights.append(0.15)
        remaining = 1.0 - sum(weights)
        rest = n - len(weights)
        for _ in range(rest):
            weights.append(remaining / rest if rest > 0 else 0)

    elif sizing_style == "conviction_weighted":
        # Weight by score — higher score = larger position
        scores = [s.get("profile_score", s["scoring"]["composite"]) for s in stocks]
        total_score = sum(scores)
        weights = [sc/total_score for sc in scores] if total_score > 0 else [1/n]*n

    elif sizing_style == "risk_weighted":
        # Larger caps get larger weights
        mcs = [s.get("market_cap") or 1e10 for s in stocks]
        total_mc = sum(mcs)
        weights = [mc/total_mc for mc in mcs]

    elif sizing_style == "market_cap_weighted":
        mcs = [s.get("market_cap") or 1e10 for s in stocks]
        total_mc = sum(mcs)
        weights = [mc/total_mc for mc in mcs]

    else:  # equal_weight
        weights = [1/n] * n

    # Normalize weights to sum to 1
    total_w = sum(weights[:n])
    weights = [w/total_w for w in weights[:n]]

    for i, (stock, weight) in enumerate(zip(stocks, weights)):
        amount = capital * weight
        price = stock.get("current_price") or 0
        shares = int(amount / price) if price > 0 else 0
        actual_amount = shares * price if price > 0 else amount

        allocations.append({
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
            "top_reason": stock.get("profile_reasons", stock["scoring"].get("top_reasons", []))[:1],
            "why_included": generate_stock_rationale(stock, profile_id),
        })

    # Sector breakdown
    sector_exposure = {}
    for pos in allocations:
        sec = pos["sector"]
        sector_exposure[sec] = sector_exposure.get(sec, 0) + pos["weight_pct"]

    return {
        "positions": allocations,
        "total_stocks": n,
        "total_capital": capital,
        "total_deployed": round(sum(p["amount"] for p in allocations)),
        "sector_exposure": sector_exposure,
        "portfolio_rationale": generate_portfolio_rationale(profile_id, allocations, sector_exposure),
        "entry_strategy": get_entry_strategy(profile_id),
        "rebalance_note": profile.get("rebalance_style", ""),
    }


def generate_stock_rationale(stock: dict, profile_id: str) -> str:
    """Generate a human-readable explanation for why this stock was picked."""
    reasons = stock.get("profile_reasons", stock["scoring"].get("top_reasons", []))
    if reasons:
        return f"Selected because: {'. '.join(reasons[:2])}"
    return f"Passes {INVESTOR_PROFILES.get(profile_id, {}).get('name', profile_id)} screening criteria"


def generate_portfolio_rationale(profile_id: str, positions: list, sector_exposure: dict) -> str:
    profile = INVESTOR_PROFILES.get(profile_id, {})
    known = {k:v for k,v in sector_exposure.items() if k != "Unknown"}
    top_sector = max(known.items(), key=lambda x: x[1])[0] if known else (max(sector_exposure.items(), key=lambda x: x[1])[0] if sector_exposure else "Diversified")
    top_stocks = ", ".join([p["symbol"] for p in positions[:3]])
    return (
        f"This portfolio is constructed using {profile.get('name', profile_id)}'s '{profile.get('focus', '')}' philosophy. "
        f"The top holdings are {top_stocks} which scored highest on {profile.get('name', profile_id)}'s key criteria. "
        f"Largest sector exposure is {top_sector} at {sector_exposure.get(top_sector, 0):.1f}%. "
        f"Position sizing follows {profile.get('sizing_style', 'equal weight').replace('_', ' ')} approach — "
        f"{'higher conviction positions get larger allocations' if profile.get('sizing_style') == 'conviction_weighted' else 'equal allocation across all positions to diversify risk'}."
    )


def get_entry_strategy(profile_id: str) -> str:
    strategies = {
        "rj": "RJ believed in buying on dips aggressively. Consider entering positions in tranches — invest 50% now, 50% on any 10%+ market dip.",
        "buffett": "Buffett enters when he finds fair value. Don't average down on declining businesses, but add to winners at reasonable prices.",
        "ramesh_damani": "Damani is patient. These are contrarian picks — they may fall further before recovering. Enter in 3 tranches over 3-6 months.",
        "vijay_kedia": "Kedia builds positions slowly. Start with 25% of target allocation, add as conviction grows. Don't rush.",
        "ben_graham": "Graham says buy below intrinsic value and sell when price reaches value. Set target prices and enter only below them.",
        "marcellus": "Marcellus recommends SIP-style entry over 6-12 months. These are long-term holdings — timing is less critical than selection.",
        "peter_lynch": "Lynch invested as he found opportunities. Enter when PEG is below 1. Don't wait for the 'perfect' entry.",
        "parag_parikh": "PPFAS holds cash for opportunities. Consider entering 70% now and keeping 30% for dips.",
    }
    return strategies.get(profile_id, "Invest systematically over 3-6 months to average out entry prices. Market timing is less important than business quality.")


# ─── Profile scoring ──────────────────────────────────────────────────────────────
def score_profile(d: dict, profile: str) -> dict:
    s, r = 0, []
    def pct(v): return v*100 if v is not None else None
    roe=pct(d.get("roe")); roce=pct(d.get("roce")); opm=pct(d.get("operating_margins"))
    dy=pct(d.get("dividend_yield")); ph=pct(d.get("promoter_holding"))
    pe=d.get("pe_ratio"); pb=d.get("pb_ratio"); de=d.get("debt_to_equity")
    mc=d.get("market_cap") or 0; mc_cr=mc/1e7
    price=d.get("current_price"); high=d.get("52w_high")
    pros_cons=" ".join(d.get("pros",[])+d.get("cons",[]))
    debt_free=(de is not None and de<0.2) or "debt free" in pros_cons.lower()
    pct_off=((high-price)/high*100) if price and high and high>0 else 0

    if profile=="rj":
        if roe and roe>=25: s+=30;r.append(f"Exceptional ROE {roe:.1f}%")
        elif roe and roe>=18: s+=20;r.append(f"Strong ROE {roe:.1f}%")
        elif roe and roe>=12: s+=10
        if roce and roce>=25: s+=20;r.append(f"High ROCE {roce:.1f}%")
        elif roce and roce>=15: s+=12
        if ph and ph>=50: s+=30;r.append(f"High promoter conviction {ph:.1f}%")
        elif ph and ph>=35: s+=15
        if pe and 0<pe<35: s+=20;r.append(f"Growth at fair price P/E {pe:.1f}x")
    elif profile=="ramesh_damani":
        if pct_off>=40: s+=35;r.append(f"Deep discount {pct_off:.0f}% off highs")
        elif pct_off>=25: s+=22;r.append(f"Significant discount {pct_off:.0f}% off highs")
        elif pct_off>=15: s+=12
        if pe and 0<pe<12: s+=30;r.append(f"Deep value P/E {pe:.1f}x")
        elif pe and pe<18: s+=18
        if pb and 0<pb<1.5: s+=20;r.append(f"Near book P/B {pb:.1f}x")
        elif pb and pb<2.5: s+=10
        if roe and roe>=12: s+=15
    elif profile=="vijay_kedia":
        if 0<mc_cr<5000: s+=25;r.append(f"Small/Mid cap ₹{mc_cr:.0f}Cr")
        elif mc_cr<20000: s+=12
        if ph and ph>=50: s+=25;r.append(f"Promoter conviction {ph:.1f}%")
        elif ph and ph>=35: s+=15
        if roe and roe>=20: s+=25;r.append(f"High ROE {roe:.1f}%")
        elif roe and roe>=15: s+=15
        if opm and opm>=15: s+=25;r.append(f"Good margins {opm:.1f}%")
        elif opm and opm>=10: s+=12
    elif profile=="porinju":
        if 0<mc_cr<2000: s+=35;r.append(f"True smallcap ₹{mc_cr:.0f}Cr")
        elif mc_cr<5000: s+=18
        if pct_off>=30: s+=25;r.append(f"Beaten down {pct_off:.0f}% off highs")
        elif pct_off>=15: s+=12
        if pe and 0<pe<20: s+=25;r.append(f"Cheap P/E {pe:.1f}x")
        elif pe and pe<35: s+=10
        if roe and roe>=12: s+=15
    elif profile=="ashish_kacholia":
        if 0<mc_cr<5000: s+=25;r.append(f"Smallcap ₹{mc_cr:.0f}Cr")
        elif mc_cr<15000: s+=12
        if roe and roe>=20: s+=25;r.append(f"High ROE {roe:.1f}%")
        elif roe and roe>=15: s+=15
        if opm and opm>=15: s+=25;r.append(f"Good margins {opm:.1f}%")
        elif opm and opm>=10: s+=15
        if pe and 0<pe<40: s+=15
        if ph and ph>=40: s+=10
    elif profile=="dolly_khanna":
        if 0<mc_cr<3000: s+=25;r.append(f"Under-radar ₹{mc_cr:.0f}Cr")
        if pct_off>=25: s+=25;r.append(f"Turnaround candidate {pct_off:.0f}% off highs")
        if roe and roe>=15: s+=25;r.append(f"ROE recovery {roe:.1f}%")
        if opm and opm>=10: s+=15
        if de is not None and de<0.5: s+=10
    elif profile=="chandrakant_sampat":
        if debt_free: s+=30;r.append("Debt-free")
        if roe and roe>=20: s+=25;r.append(f"High ROE {roe:.1f}%")
        elif roe and roe>=15: s+=15
        if opm and opm>=20: s+=25;r.append(f"Pricing power {opm:.1f}%")
        elif opm and opm>=12: s+=12
        if pe and 0<pe<35: s+=20
    elif profile=="radhakishan_damani":
        if opm and opm>=15: s+=30;r.append(f"Consumer pricing power {opm:.1f}%")
        if debt_free: s+=25;r.append("Debt-free consumer")
        if dy and dy>=2: s+=20;r.append(f"Cash return {dy:.1f}%")
        if roe and roe>=18: s+=15
        if mc_cr>5000: s+=10
    elif profile=="raamdeo_agrawal":
        q_met=(roe and roe>=20) and (opm and opm>=15)
        g_met=roce and roce>=20
        p_met=pe and 0<pe<45
        l_met=ph and ph>=40
        if q_met: s+=30;r.append("Quality ✓")
        if g_met: s+=25;r.append(f"Growth ✓ ROCE {roce:.1f}%")
        if p_met: s+=25;r.append(f"Price ✓ P/E {pe:.1f}x")
        if l_met: s+=20;r.append(f"Longevity ✓ promoter {ph:.1f}%")
    elif profile=="sanjay_bakshi":
        if roe and roe>=20: s+=25;r.append(f"Quality moat ROE {roe:.1f}%")
        elif roe and roe>=15: s+=15
        if debt_free or (de is not None and de<0.3): s+=25;r.append("Graham safety margin")
        if pct_off>=20: s+=25;r.append(f"Behavioral mispricing {pct_off:.0f}% off highs")
        if opm and opm>=20: s+=15
        if pe and 0<pe<35: s+=10
    elif profile=="kenneth_andrade":
        if roce and roce>=20: s+=30;r.append(f"Capital efficient ROCE {roce:.1f}%")
        elif roce and roce>=15: s+=18
        if opm and opm>=15: s+=25;r.append(f"Asset-light margins {opm:.1f}%")
        if de is not None and de<0.3: s+=20;r.append("Low capex balance sheet")
        if pct_off>=15: s+=15;r.append(f"Contrarian entry {pct_off:.0f}% off highs")
        if roe and roe>=15: s+=10
    elif profile=="manish_kejriwal":
        if roe and roe>=22: s+=30;r.append(f"PE-quality ROE {roe:.1f}%")
        elif roe and roe>=15: s+=18
        if opm and opm>=20: s+=25;r.append(f"Quality margins {opm:.1f}%")
        elif opm and opm>=12: s+=15
        if ph and ph>=45: s+=25;r.append(f"Management alignment {ph:.1f}%")
        if debt_free or (de is not None and de<0.4): s+=20
    elif profile=="buffett":
        if roe and roe>=20: s+=25;r.append(f"Strong ROE {roe:.1f}%")
        elif roe and roe>=15: s+=15
        if debt_free: s+=25;r.append("Near debt-free")
        elif de is not None and de<0.5: s+=15
        if opm and opm>=20: s+=25;r.append(f"Strong OPM {opm:.1f}%")
        elif opm and opm>=12: s+=15
        if pe and 0<pe<25: s+=25;r.append(f"Reasonable P/E {pe:.1f}x")
        elif pe and pe<35: s+=10
    elif profile=="peter_lynch":
        if roe and pe and roe>0 and pe>0:
            peg=pe/roe
            if peg<0.5: s+=40;r.append(f"Excellent PEG {peg:.2f}")
            elif peg<1.0: s+=28;r.append(f"Good PEG {peg:.2f}")
            elif peg<1.5: s+=15
        if roe and roe>=15: s+=25;r.append(f"Growth ROE {roe:.1f}%")
        elif roe and roe>=10: s+=15
        if pe and 0<pe<30: s+=20
        if 0<mc_cr<10000: s+=15;r.append("Lynch sweet spot size")
    elif profile=="ben_graham":
        if pb and 0<pb<1: s+=40;r.append(f"Below book P/B {pb:.2f}x")
        elif pb and pb<1.5: s+=28;r.append(f"Near book P/B {pb:.2f}x")
        elif pb and pb<2: s+=15
        if pe and 0<pe<12: s+=35;r.append(f"Deep value P/E {pe:.1f}x")
        elif pe and pe<15: s+=22
        elif pe and pe<20: s+=10
        if debt_free: s+=25;r.append("Graham safety")
        elif de is not None and de<0.3: s+=15
    elif profile=="charlie_munger":
        if roce and roce>=30: s+=35;r.append(f"Exceptional ROCE {roce:.1f}%")
        elif roce and roce>=22: s+=22
        elif roce and roce>=15: s+=12
        if opm and opm>=25: s+=25;r.append(f"Pricing power {opm:.1f}%")
        elif opm and opm>=15: s+=15
        if debt_free: s+=20;r.append("Debt-free compounder")
        elif de is not None and de<0.3: s+=12
        if pe and 0<pe<40: s+=20
    elif profile=="phil_fisher":
        if roe and roe>=20: s+=30;r.append(f"Superior ROE {roe:.1f}%")
        elif roe and roe>=15: s+=18
        if opm and opm>=20: s+=25;r.append(f"Growing margins {opm:.1f}%")
        elif opm and opm>=12: s+=15
        if ph and ph>=40: s+=25;r.append(f"Management aligned {ph:.1f}%")
        if pe and 0<pe<50: s+=20
    elif profile=="parag_parikh":
        if ph and ph>=45: s+=25;r.append(f"Owner-operator {ph:.1f}%")
        elif ph and ph>=30: s+=15
        if opm and opm>=20: s+=25;r.append(f"Pricing power {opm:.1f}%")
        elif opm and opm>=12: s+=15
        if debt_free or (de is not None and de<0.5): s+=20
        if roe and roe>=18: s+=20;r.append(f"Consistent ROE {roe:.1f}%")
        elif roe and roe>=12: s+=10
        if pe and 0<pe<40: s+=10
    elif profile=="marcellus":
        if debt_free: s+=35;r.append("Debt-free — must-have")
        elif de is not None and de<0.3: s+=15
        if roce and roce>=25: s+=35;r.append(f"Exceptional ROCE {roce:.1f}%")
        elif roce and roce>=18: s+=20
        if opm and opm>=20: s+=20;r.append(f"Consistent margins {opm:.1f}%")
        elif opm and opm>=12: s+=10
        if roe and roe>=20: s+=10
    elif profile in ("motilal_qglp","raamdeo_agrawal"):
        q_met=(roe and roe>=18) and (opm and opm>=15)
        g_met=roce and roce>=20
        p_met=pe and 0<pe<45
        l_met=ph and ph>=40
        if q_met: s+=30;r.append("Quality ✓ (ROE + margins)")
        if g_met: s+=25;r.append(f"Growth ✓ ROCE {roce:.1f}%")
        if p_met: s+=25;r.append(f"Price ✓ P/E {pe:.1f}x")
        if l_met: s+=20;r.append(f"Longevity ✓ promoter {ph:.1f}%")
    elif profile=="nippon_smallcap":
        if 0<mc_cr<8000: s+=30;r.append(f"Small cap ₹{mc_cr:.0f}Cr")
        elif mc_cr<15000: s+=15
        if roe and roe>=18: s+=25;r.append(f"High growth ROE {roe:.1f}%")
        elif roe and roe>=12: s+=15
        if opm and opm>=15: s+=25;r.append(f"Emerging margins {opm:.1f}%")
        elif opm and opm>=8: s+=12
        if pe and 0<pe<50: s+=20
    elif profile=="mirae_asset":
        if roe and roe>=20: s+=28;r.append(f"Quality ROE {roe:.1f}%")
        elif roe and roe>=15: s+=18
        if roce and roce>=20: s+=22;r.append(f"Strong ROCE {roce:.1f}%")
        elif roce and roce>=12: s+=12
        if opm and opm>=18: s+=25;r.append(f"Sector leader margins {opm:.1f}%")
        elif opm and opm>=12: s+=15
        if pe and 0<pe<40: s+=25
    elif profile=="hdfc_mf":
        if pct_off>=20: s+=20;r.append(f"Value opportunity {pct_off:.0f}% off highs")
        if pe and 0<pe<20: s+=25;r.append(f"Value P/E {pe:.1f}x")
        elif pe and pe<30: s+=15
        if roe and roe>=15: s+=25;r.append(f"Quality ROE {roe:.1f}%")
        elif roe and roe>=10: s+=15
        if dy and dy>=2: s+=15;r.append(f"Dividend {dy:.1f}%")
        if debt_free or (de is not None and de<0.5): s+=15
    elif profile=="anand_rathi":
        if mc_cr>10000: s+=20;r.append(f"Large cap safety ₹{mc_cr:.0f}Cr")
        if dy and dy>=3: s+=30;r.append(f"Strong dividend {dy:.1f}%")
        elif dy and dy>=2: s+=18
        elif dy and dy>=1: s+=8
        if debt_free or (de is not None and de<0.3): s+=25;r.append("Capital preservation")
        if roe and roe>=15: s+=15
        if pe and 0<pe<25: s+=10
    elif profile=="white_oak":
        if roe and roe>=22: s+=30;r.append(f"Earnings quality ROE {roe:.1f}%")
        elif roe and roe>=15: s+=18
        if opm and opm>=20: s+=25;r.append(f"Quality margins {opm:.1f}%")
        elif opm and opm>=12: s+=15
        if pe and 0<pe<35: s+=25
        if debt_free or (de is not None and de<0.4): s+=20
    elif profile in ("enam","nemish_shah"):
        if debt_free: s+=35;r.append("Debt-free — top criterion")
        elif de is not None and de<0.2: s+=20
        if ph and ph>=45: s+=25;r.append(f"Management alignment {ph:.1f}%")
        elif ph and ph>=30: s+=15
        if roe and roe>=18: s+=20;r.append(f"Consistent ROE {roe:.1f}%")
        elif roe and roe>=12: s+=12
        if opm and opm>=15: s+=20;r.append(f"Sustainable margins {opm:.1f}%")
    elif profile=="ask_investment":
        if mc_cr>15000: s+=20;r.append(f"Institutional quality ₹{mc_cr:.0f}Cr")
        if roe and roe>=18: s+=25;r.append(f"Quality ROE {roe:.1f}%")
        elif roe and roe>=12: s+=15
        if debt_free or (de is not None and de<0.3): s+=25
        if dy and dy>=1.5: s+=15;r.append(f"Dividend {dy:.1f}%")
        if opm and opm>=15: s+=15
    elif profile=="carnelian":
        if 0<mc_cr<20000: s+=20;r.append(f"Emerging compounder ₹{mc_cr:.0f}Cr")
        if roe and roe>=20: s+=25;r.append(f"High ROE {roe:.1f}%")
        elif roe and roe>=15: s+=15
        if opm and opm>=15: s+=25;r.append(f"Expanding margins {opm:.1f}%")
        elif opm and opm>=10: s+=12
        if ph and ph>=45: s+=20;r.append(f"Promoter conviction {ph:.1f}%")
        elif ph and ph>=30: s+=10
        if pe and 0<pe<45: s+=10
    elif profile=="murugappa":
        if debt_free or (de is not None and de<0.3): s+=30;r.append("Conservative balance sheet")
        if dy and dy>=2: s+=25;r.append(f"Dividend history {dy:.1f}%")
        elif dy and dy>=1: s+=15
        if opm and opm>=15: s+=25;r.append(f"Manufacturing margins {opm:.1f}%")
        elif opm and opm>=10: s+=15
        if roe and roe>=15: s+=20
        if mc_cr>2000: s+=0

    return {"score": min(s, 100), "reasons": r[:3]}


def get_matching_profiles(d: dict) -> list:
    results = []
    for pid in INVESTOR_PROFILES:
        res = score_profile(d, pid)
        results.append({
            "id": pid,
            "name": INVESTOR_PROFILES[pid]["name"],
            "avatar": INVESTOR_PROFILES[pid]["avatar"],
            "score": res["score"],
            "reasons": res["reasons"],
        })
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:3]


# ─── Standard scoring ─────────────────────────────────────────────────────────────
def to_pct(val): return val*100 if val is not None else None

def score_buffett_std(d):
    s,r=0,[]
    roe=to_pct(d.get("roe"))
    pc_text=" ".join(d.get("pros",[])+d.get("cons",[]))
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

def get_sector_comparison(stock: dict, sector_avgs: dict) -> dict:
    """Return sector average comparison for each metric."""
    sector = stock.get("sector","Unknown")
    avgs = sector_avgs.get(sector,{})
    if not avgs: return {}
    result = {}
    metrics = {
        "pe_ratio":"pe","pb_ratio":"pb","roe":"roe",
        "roce":"roce","operating_margins":"opm","debt_to_equity":"de"
    }
    for stock_key, avg_key in metrics.items():
        stock_val = stock.get(stock_key)
        avg_val = avgs.get(avg_key)
        if stock_val is not None and avg_val is not None and avg_val != 0:
            diff_pct = ((stock_val - avg_val) / abs(avg_val)) * 100
            # For debt and PE, lower is better
            lower_is_better = stock_key in ("pe_ratio","debt_to_equity","pb_ratio")
            if lower_is_better:
                status = "better" if stock_val < avg_val else ("worse" if stock_val > avg_val*1.1 else "inline")
            else:
                status = "better" if stock_val > avg_val*1.05 else ("worse" if stock_val < avg_val*0.9 else "inline")
            result[stock_key] = {
                "value": stock_val,
                "sector_avg": avg_val,
                "diff_pct": round(diff_pct, 1),
                "status": status,
            }
    return result

def build_entry(symbol, raw):
    scoring=compute_score(raw)
    matching_profiles=get_matching_profiles(raw)
    with _cache_lock:
        sec_avgs = dict(_sector_averages)
    sector_comparison = get_sector_comparison(raw, sec_avgs)
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
        "promoter_pledge":raw.get("promoter_pledge"),
        "eps":raw.get("eps"),
        "quarterly_revenue":raw.get("quarterly_revenue",[]),
        "quarterly_profit":raw.get("quarterly_profit",[]),
        "pros":raw.get("pros",[]),
        "cons":raw.get("cons",[]),
        "scoring":scoring,
        "conviction":conviction_tier(scoring["composite"]),
        "matching_profiles":matching_profiles,
        "sector_comparison":sector_comparison,
        "cached_at":datetime.now().isoformat(),
        "source":"screener.in",
    }


# ─── Disk cache ───────────────────────────────────────────────────────────────────
def save_cache_to_disk():
    try:
        with _cache_lock:
            data={"cache_time":_cache_time.isoformat() if _cache_time else None,"stocks":_cache}
        with open(CACHE_FILE,"w") as f: json.dump(data,f)
        # Save sector averages
        with open(SECTOR_CACHE_FILE,"w") as f: json.dump(_sector_averages,f)
        print(f"✓ Saved {len(_cache)} stocks to disk")
    except Exception as e: print(f"✗ Save failed: {e}")

def load_cache_from_disk():
    global _cache,_cache_time,_sector_averages
    try:
        if not os.path.exists(CACHE_FILE): return False
        with open(CACHE_FILE,"r") as f: data=json.load(f)
        stocks=data.get("stocks",{}); ct=data.get("cache_time")
        if not stocks: return False
        with _cache_lock:
            _cache=stocks
            _cache_time=datetime.fromisoformat(ct) if ct else datetime.now()
        if os.path.exists(SECTOR_CACHE_FILE):
            with open(SECTOR_CACHE_FILE,"r") as f:
                _sector_averages=json.load(f)
        age_h=(datetime.now()-_cache_time).total_seconds()/3600
        print(f"✓ Loaded disk cache: {len(stocks)} stocks, {age_h:.1f}h old")
        return True
    except Exception as e: print(f"✗ Load failed: {e}"); return False


# ─── Cache refresh ────────────────────────────────────────────────────────────────
def refresh_cache():
    global _cache,_cache_time,_is_refreshing,_refresh_progress,_sector_averages
    if _is_refreshing: return
    _is_refreshing=True

    # Try to fetch NSE symbols, fallback to hardcoded list
    nse_symbols = fetch_nse_symbols()
    universe = nse_symbols if len(nse_symbols) > 100 else FALLBACK_UNIVERSE
    # Limit to first 600 for free tier — prioritize by being in fallback list
    if len(universe) > 600:
        priority = set(FALLBACK_UNIVERSE)
        sorted_universe = [s for s in universe if s in priority] + [s for s in universe if s not in priority]
        universe = sorted_universe[:600]

    _refresh_progress={"done":0,"total":len(universe)}
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Cache refresh — {len(universe)} stocks (NSE auto-fetched)\n")

    new_cache={}
    for i,symbol in enumerate(universe):
        try:
            print(f"  [{i+1}/{len(universe)}] {symbol}...",end=" ",flush=True)
            raw=fetch_screener(symbol)
            if raw and (raw.get("pe_ratio") or raw.get("current_price")):
                # Build entry without sector comparison first (avgs not ready)
                scoring=compute_score(raw)
                matching_profiles=get_matching_profiles(raw)
                entry={
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
                    "promoter_pledge":raw.get("promoter_pledge"),
                    "eps":raw.get("eps"),
                    "quarterly_revenue":raw.get("quarterly_revenue",[]),
                    "quarterly_profit":raw.get("quarterly_profit",[]),
                    "pros":raw.get("pros",[]),
                    "cons":raw.get("cons",[]),
                    "scoring":scoring,
                    "conviction":conviction_tier(scoring["composite"]),
                    "matching_profiles":matching_profiles,
                    "sector_comparison":{},
                    "cached_at":datetime.now().isoformat(),
                    "source":"screener.in",
                }
                new_cache[symbol]=entry
                roe_d=f"{to_pct(raw.get('roe')):.1f}%" if raw.get("roe") else "-"
                opm_d=f"{to_pct(raw.get('operating_margins')):.1f}%" if raw.get("operating_margins") else "-"
                print(f"✓ score={scoring['composite']} ROE={roe_d} OPM={opm_d}")
            else:
                print("✗ no data")
            _refresh_progress["done"]=i+1

            # Intermediate save every 50
            if (i+1)%50==0 and new_cache:
                with _cache_lock: _cache.update(new_cache); _cache_time=datetime.now()
                # Compute sector averages from what we have
                avgs=compute_sector_averages(new_cache)
                with _cache_lock: _sector_averages=avgs
                save_cache_to_disk()

            time.sleep(2)
        except Exception as e:
            print(f"✗ {e}"); _refresh_progress["done"]=i+1; time.sleep(2)

    # Final sector averages computation
    sector_avgs = compute_sector_averages(new_cache)

    # Add sector comparisons to all entries
    for sym in new_cache:
        new_cache[sym]["sector_comparison"] = get_sector_comparison(new_cache[sym], sector_avgs)

    with _cache_lock:
        _cache=new_cache; _cache_time=datetime.now()
        _sector_averages=sector_avgs

    save_cache_to_disk()
    print(f"\n✓ Cache complete: {len(new_cache)} stocks at {_cache_time.strftime('%H:%M:%S')}\n")
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
            # Compute sector avgs if missing
            if not _sector_averages:
                with _cache_lock: avgs=compute_sector_averages(_cache)
                with _cache_lock: _sector_averages=avgs
    else:
        threading.Thread(target=refresh_cache,daemon=True).start()


# ─── Routes ──────────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "app":"stocks.ai","version":"11.0.0",
        "cached_stocks":len(_cache),"refreshing":_is_refreshing,
        "refresh_progress":f"{_refresh_progress['done']}/{_refresh_progress['total']}" if _is_refreshing else "idle",
        "cache_age":str(datetime.now()-_cache_time).split(".")[0] if _cache_time else "warming up",
        "investor_profiles":len(INVESTOR_PROFILES),
        "sectors_indexed":len(_sector_averages),
    }

@app.get("/api/cache/status")
def cache_status():
    return {
        "ready":len(_cache)>0,"count":len(_cache),
        "refreshing":_is_refreshing,"progress":_refresh_progress,
        "last_updated":_cache_time.isoformat() if _cache_time else None,
    }

@app.get("/api/cache/refresh")
def trigger_refresh(background_tasks:BackgroundTasks):
    if _is_refreshing: return {"message":"Already refreshing"}
    background_tasks.add_task(refresh_cache)
    return {"message":"Refresh started"}

@app.get("/api/profiles")
def get_profiles():
    return {"profiles":INVESTOR_PROFILES,"count":len(INVESTOR_PROFILES)}

@app.get("/api/sector-averages")
def get_sector_averages():
    return {"sectors":_sector_averages}

@app.get("/api/stock/{symbol}")
def get_stock(symbol:str):
    symbol=symbol.upper().strip()
    with _cache_lock:
        if symbol in _cache: return _cache[symbol]
    raw=fetch_screener(symbol)
    if not raw: raise HTTPException(404,f"Could not find {symbol}")
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
        done=_refresh_progress.get("done",0); total=_refresh_progress.get("total",0)
        return {"count":0,"stocks":[],"warming":True,
                "message":f"Loading... {done}/{total} done. Try again shortly."}
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
    return {
        "count":len(results),"stocks":results[:limit],
        "total_cached":len(stocks),
        "cache_age":str(datetime.now()-_cache_time).split(".")[0] if _cache_time else "unknown",
    }

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

@app.post("/api/portfolio/build")
def build_portfolio(
    profile_id:str=Query(...),
    capital:float=Query(...,description="Total capital in INR"),
    limit:int=Query(None),
):
    if profile_id not in INVESTOR_PROFILES:
        raise HTTPException(400,f"Unknown profile: {profile_id}")
    profile=INVESTOR_PROFILES[profile_id]
    target_n=limit or profile.get("portfolio_size",15)

    with _cache_lock: stocks=list(_cache.values())
    if not stocks:
        raise HTTPException(503,"Cache not ready yet. Try again in a few minutes.")

    # Score all stocks for this profile
    scored=[]
    for s in stocks:
        ps=score_profile(s,profile_id)
        if ps["score"]>=40:
            s=dict(s); s["profile_score"]=ps["score"]; s["profile_reasons"]=ps["reasons"]
            scored.append(s)

    scored.sort(key=lambda x:x["profile_score"],reverse=True)
    top_stocks=scored[:target_n]

    if not top_stocks:
        raise HTTPException(404,"No stocks found matching this profile's criteria")

    portfolio=get_portfolio_allocation(profile_id,top_stocks,capital)
    portfolio["profile_id"]=profile_id
    portfolio["profile_name"]=profile["name"]
    portfolio["profile_philosophy"]=profile["philosophy"]
    portfolio["profile_bio"]=profile["bio"]
    portfolio["capital_input"]=capital
    portfolio["generated_at"]=datetime.now().isoformat()

    return portfolio

@app.get("/api/debug/{symbol}")
def debug_stock(symbol:str):
    raw=fetch_screener(symbol.upper())
    return {"symbol":symbol.upper(),"raw":raw}
