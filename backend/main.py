from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import threading, time, json, os, re, requests
from bs4 import BeautifulSoup

app = FastAPI(title="stocks.ai API", version="13.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

CACHE_FILE = "stock_cache.json"
SECTOR_CACHE_FILE = "sector_cache.json"
_cache = {}
_cache_time = None
_cache_lock = threading.Lock()
_is_refreshing = False
_refresh_progress = {"done": 0, "total": 0}
_sector_averages = {}
_nifty_pe_cache = {"pe": None, "fetched_at": None}

def fetch_nifty_pe() -> float:
    global _nifty_pe_cache
    if _nifty_pe_cache["pe"] and _nifty_pe_cache["fetched_at"]:
        if (datetime.now() - _nifty_pe_cache["fetched_at"]).total_seconds() < 14400:
            return _nifty_pe_cache["pe"]
    try:
        r = requests.get("https://www.screener.in/company/NIFTY/", timeout=8,
                         headers={"User-Agent":"Mozilla/5.0"})
        m = re.search(r"P/E[^\d]*?(\d{2,3}\.?\d*)", r.text)
        if m:
            pe = float(m.group(1))
            if 8 < pe < 60:
                _nifty_pe_cache = {"pe": round(pe,1), "fetched_at": datetime.now()}
                return round(pe,1)
    except: pass
    return 22.0

def get_market_valuation(pe: float) -> dict:
    if pe < 15: return {"zone":"Deep Value","color":"#16a34a","description":"Market historically cheap. Aggressive equity allocation justified.","equity_modifier":1.15}
    if pe < 18: return {"zone":"Undervalued","color":"#65a30d","description":"Below historical average. Good time to be fully invested.","equity_modifier":1.08}
    if pe < 22: return {"zone":"Fair Value","color":"#2563eb","description":"At historical average. Maintain base allocation.","equity_modifier":1.0}
    if pe < 26: return {"zone":"Slightly Expensive","color":"#d97706","description":"Above historical average. Trim equity slightly, build cash.","equity_modifier":0.90}
    if pe < 30: return {"zone":"Expensive","color":"#ea580c","description":"Significantly overvalued. Reduce equity, increase safety assets.","equity_modifier":0.80}
    return {"zone":"Bubble Territory","color":"#dc2626","description":"Extreme overvaluation. Only highest-conviction positions justified.","equity_modifier":0.65}

NSE_SECTOR_MAP = {
    "HDFCBANK":"Banking","ICICIBANK":"Banking","SBIN":"Banking","KOTAKBANK":"Banking",
    "AXISBANK":"Banking","INDUSINDBK":"Banking","BANKBARODA":"Banking","PNB":"Banking",
    "CANBK":"Banking","UNIONBANK":"Banking","IDFCFIRSTB":"Banking","FEDERALBNK":"Banking",
    "BANDHANBNK":"Banking","RBLBANK":"Banking","INDIANB":"Banking","KARURVYSYA":"Banking",
    "DCBBANK":"Banking","SOUTHBANK":"Banking","UJJIVAN":"Banking","CENTRALBK":"Banking",
    "BAJFINANCE":"NBFC","BAJAJFINSV":"NBFC","CHOLAFIN":"NBFC","MUTHOOTFIN":"NBFC",
    "MANAPPURAM":"NBFC","SHRIRAMFIN":"NBFC","LICHSGFIN":"NBFC","CANFINHOME":"NBFC",
    "ABCAPITAL":"NBFC","POONAWALLA":"NBFC","CREDITACC":"NBFC","AAVAS":"NBFC",
    "HOMEFIRST":"NBFC","APTUS":"NBFC","MASFIN":"NBFC","SPANDANA":"NBFC","IIFL":"NBFC",
    "HDFCLIFE":"Insurance","SBILIFE":"Insurance","ICICIGI":"Insurance","ICICIPRULI":"Insurance",
    "LICI":"Insurance","STARHEALTH":"Insurance","GICRE":"Insurance","NIACL":"Insurance",
    "HDFCAMC":"Asset Management","CAMS":"Asset Management","ISEC":"Asset Management",
    "ANGELONE":"Asset Management","KFINTECH":"Asset Management","CDSL":"Asset Management",
    "MCX":"Asset Management","UTIAMC":"Asset Management",
    "TCS":"IT","INFOSYS":"IT","HCLTECH":"IT","WIPRO":"IT","TECHM":"IT",
    "LTIM":"IT","MPHASIS":"IT","COFORGE":"IT","PERSISTENT":"IT","OFSS":"IT",
    "TATAELXSI":"IT","LTTS":"IT","KPITTECH":"IT","HAPPSTMNDS":"IT","ZENSARTECH":"IT",
    "INTELLECT":"IT","MASTEK":"IT","BSOFT":"IT","SAKSOFT":"IT","LATENTVIEW":"IT",
    "TANLA":"IT","NUCLEUS":"IT","NIITLTD":"IT",
    "HINDUNILVR":"FMCG","ITC":"FMCG","NESTLEIND":"FMCG","BRITANNIA":"FMCG",
    "DABUR":"FMCG","MARICO":"FMCG","COLPAL":"FMCG","GODREJCP":"FMCG",
    "EMAMILTD":"FMCG","TATACONSUM":"FMCG","VBL":"FMCG","MCDOWELL-N":"FMCG",
    "UBL":"FMCG","PGHH":"FMCG","GILLETTE":"FMCG","RADICO":"FMCG",
    "JYOTHYLAB":"FMCG","BAJAJCON":"FMCG","VSTIND":"FMCG","GSKCONS":"FMCG",
    "SUNPHARMA":"Pharma","DRREDDY":"Pharma","CIPLA":"Pharma","DIVISLAB":"Pharma",
    "TORNTPHARM":"Pharma","AUROPHARMA":"Pharma","LUPIN":"Pharma","ALKEM":"Pharma",
    "BIOCON":"Pharma","GLAND":"Pharma","NATCOPHARM":"Pharma","IPCALAB":"Pharma",
    "ABBOTINDIA":"Pharma","PFIZER":"Pharma","LAURUSLABS":"Pharma","GRANULES":"Pharma",
    "AJANTPHARM":"Pharma","ERIS":"Pharma","JBCHEPHARM":"Pharma","SYNGENE":"Pharma",
    "LALPATHLAB":"Pharma","METROPOLIS":"Pharma","THYROCARE":"Pharma","SPARC":"Pharma",
    "POLYMED":"Pharma","SHILPAMED":"Pharma","SEQUENT":"Pharma",
    "MARUTI":"Auto","TATAMOTORS":"Auto","BAJAJ-AUTO":"Auto","HEROMOTOCO":"Auto",
    "EICHERMOT":"Auto","TVSMOTORS":"Auto","ASHOKLEY":"Auto","APOLLOTYRE":"Auto",
    "CEATLTD":"Auto","BALKRISIND":"Auto","MOTHERSON":"Auto","SONACOMS":"Auto",
    "BOSCHLTD":"Auto","ENDURANCE":"Auto","ESCORTS":"Auto","TIINDIA":"Auto",
    "GABRIEL":"Auto","JAMNAAUTO":"Auto","SUBROS":"Auto","MINDACORP":"Auto",
    "WABCOINDIA":"Auto","TALBROAUTO":"Auto","MAHINDCIE":"Auto","SANDHAR":"Auto",
    "RELIANCE":"Energy","ONGC":"Energy","BPCL":"Energy","IOC":"Energy",
    "HINDPETRO":"Energy","OIL":"Energy","GAIL":"Energy","PETRONET":"Energy",
    "ATGL":"Energy","GUJGASLTD":"Energy","IGL":"Energy","MGL":"Energy","MRPL":"Energy",
    "TATASTEEL":"Metals","JSWSTEEL":"Metals","HINDALCO":"Metals","SAIL":"Metals",
    "NMDC":"Metals","COALINDIA":"Metals","HINDCOPPER":"Metals","GPIL":"Metals",
    "WELCORP":"Metals","GRAPHITE":"Metals","TINPLATE":"Metals",
    "ULTRACEMCO":"Cement","AMBUJACEM":"Cement","RAMCOCEM":"Cement","DALBHARAT":"Cement",
    "JKCEMENT":"Cement","SHREECEM":"Cement","JKLAKSHMI":"Cement","SAGARCEM":"Cement",
    "DLF":"Real Estate","GODREJPROP":"Real Estate","PRESTIGE":"Real Estate",
    "OBEROIRLTY":"Real Estate","PHOENIXLTD":"Real Estate","BRIGADE":"Real Estate",
    "SOBHA":"Real Estate","KOLTEPATIL":"Real Estate","MAHLIFE":"Real Estate",
    "LT":"Capital Goods","SIEMENS":"Capital Goods","ABB":"Capital Goods",
    "BEL":"Capital Goods","BHEL":"Capital Goods","CGPOWER":"Capital Goods",
    "POLYCAB":"Capital Goods","HAVELLS":"Capital Goods","SCHAEFFLER":"Capital Goods",
    "TIMKEN":"Capital Goods","ELGIEQUIP":"Capital Goods","CUMMINSIND":"Capital Goods",
    "THERMAX":"Capital Goods","KSB":"Capital Goods","GRINDWELL":"Capital Goods",
    "ESABINDIA":"Capital Goods","INGERRAND":"Capital Goods","SKIPPER":"Capital Goods",
    "ASIANPAINT":"Paints","BERGEPAINT":"Paints","KANSAINER":"Paints","INDPAINT":"Paints",
    "PIDILITIND":"Chemicals","DEEPAKNTR":"Chemicals","NAVINFLUOR":"Chemicals",
    "FLUOROCHEM":"Chemicals","SUDARSCHEM":"Chemicals","VINATIORGA":"Chemicals",
    "FINEORG":"Chemicals","NOCIL":"Chemicals","DCMSHRIRAM":"Chemicals",
    "ATUL":"Chemicals","GNFC":"Chemicals","CHAMBLFERT":"Chemicals",
    "DEEPAKFERT":"Chemicals","COROMANDEL":"Chemicals","RALLIS":"Chemicals",
    "ROSSARI":"Chemicals","EPIGRAL":"Chemicals","HIKAL":"Chemicals",
    "TITAN":"Consumer Durables","VOLTAS":"Consumer Durables","WHIRLPOOL":"Consumer Durables",
    "CROMPTON":"Consumer Durables","DIXON":"Consumer Durables","AMBER":"Consumer Durables",
    "VGUARD":"Consumer Durables","SYMPHONY":"Consumer Durables","KAJARIACER":"Consumer Durables",
    "TTKPRESTIG":"Consumer Durables","CERA":"Consumer Durables","RELAXO":"Consumer Durables",
    "NILKAMAL":"Consumer Durables","SAFARI":"Consumer Durables","BAJAJELEC":"Consumer Durables",
    "CENTURYPLY":"Consumer Durables","GREENPANEL":"Consumer Durables","LAOPALA":"Consumer Durables",
    "PAGEIND":"Textiles","WELSPUNIND":"Textiles","TRIDENT":"Textiles","KPRMILL":"Textiles",
    "RAYMOND":"Textiles","CENTURYTEX":"Textiles",
    "BHARTIARTL":"Telecom","INDUSTOWER":"Telecom","TATACOMM":"Telecom","TEJASNET":"Telecom",
    "DMART":"Retail","TRENT":"Retail","SHOPERSTOP":"Retail","METROBRAND":"Retail",
    "WESTLIFE":"Retail","DEVYANI":"Retail","JUBLFOOD":"Retail",
    "NAUKRI":"Internet","ZOMATO":"Internet","NYKAA":"Internet","POLICYBZR":"Internet",
    "MAPMYINDIA":"Internet","INDIAMART":"Internet","JUSTDIAL":"Internet","MATRIMONY":"Internet",
    "IRCTC":"Travel","INDIGO":"Aviation","INDHOTEL":"Travel","WONDERLA":"Travel",
    "EASEMYTRIP":"Travel","PVRINOX":"Entertainment","SAREGAMA":"Entertainment",
    "IRFC":"Infra Finance","HUDCO":"Infra Finance","RECLTD":"Infra Finance","PFC":"Infra Finance",
    "SBICARD":"Fintech","RVNL":"Infrastructure","NBCC":"Infrastructure","RAILTEL":"Infrastructure",
    "NHPC":"Power","NTPC":"Power","POWERGRID":"Power","TATAPOWER":"Power",
    "JSWENERGY":"Power","TORNTPOWER":"Power","CESC":"Power",
    "ADANIPORTS":"Logistics","CONCOR":"Logistics","TCIEXP":"Logistics","VRLLOG":"Logistics",
    "HAL":"Defence","MTAR":"Defence","CASTROLIND":"Lubricants","GULFOILLUB":"Lubricants",
}

def sector_for(symbol: str, scraped: str = "Unknown") -> str:
    if scraped and scraped not in ("Unknown","",None): return scraped
    return NSE_SECTOR_MAP.get(symbol.upper(),"Unknown")

NIFTY_500 = list(dict.fromkeys([
    "RELIANCE","TCS","HDFCBANK","BHARTIARTL","ICICIBANK","INFOSYS","HINDUNILVR",
    "ITC","LT","KOTAKBANK","HCLTECH","AXISBANK","BAJFINANCE","MARUTI","SUNPHARMA",
    "TITAN","ULTRACEMCO","ASIANPAINT","NESTLEIND","WIPRO","TECHM","ONGC","POWERGRID",
    "NTPC","TATAMOTORS","BAJAJFINSV","ADANIPORTS","COALINDIA","BRITANNIA","CIPLA",
    "DRREDDY","EICHERMOT","HEROMOTOCO","HINDALCO","INDUSINDBK","JSWSTEEL","DIVISLAB",
    "SBIN","TATASTEEL","APOLLOHOSP","PIDILITIND","TATACONSUM","DMART","HAVELLS",
    "POLYCAB","TORNTPHARM","MARICO","DABUR","HDFCLIFE","BAJAJ-AUTO","AMBUJACEM",
    "BANKBARODA","BERGEPAINT","BEL","BPCL","CANBK","CHOLAFIN","COLPAL","DLF",
    "GAIL","GODREJCP","GRASIM","HAL","HDFCAMC","ICICIGI","ICICIPRULI","INDUSTOWER",
    "INDIGO","IOC","IRCTC","LICI","LTIM","LUPIN","MCDOWELL-N","NHPC","NMDC",
    "OFSS","OIL","PAGEIND","PERSISTENT","PETRONET","PFC","PNB","RECLTD","SAIL",
    "SHRIRAMFIN","SIEMENS","TATAPOWER","TRENT","VBL","ZOMATO","ABCAPITAL","ALKEM",
    "APOLLOTYRE","ASHOKLEY","ASTRAL","AUROPHARMA","BALKRISIND","BANDHANBNK","BIOCON",
    "CAMS","CANFINHOME","COFORGE","CONCOR","CROMPTON","CUMMINSIND","DEEPAKNTR",
    "DIXON","ESCORTS","EXIDEIND","FEDERALBNK","FORTIS","GLENMARK","GODREJPROP",
    "GRANULES","IDFCFIRSTB","INDHOTEL","INDIANB","ISEC","JKCEMENT","JUBLFOOD",
    "KAJARIACER","KANSAINER","LICHSGFIN","LTTS","MANAPPURAM","MAXHEALTH","MCX",
    "MPHASIS","MRF","MUTHOOTFIN","NATCOPHARM","NAUKRI","OBEROIRLTY","PFIZER",
    "PHOENIXLTD","PRESTIGE","RADICO","RAMCOCEM","RELAXO","SBICARD","SBILIFE",
    "SCHAEFFLER","SONACOMS","SRF","SUNDARMFIN","SUPREMEIND","SYNGENE","TATACHEM",
    "TATACOMM","TATAELXSI","TVSMOTORS","UBL","UNIONBANK","VGUARD","VOLTAS",
    "WHIRLPOOL","AAVAS","AFFLE","AJANTPHARM","AMBER","ANGELONE","APTUS","ATGL",
    "CDSL","CENTURYPLY","CERA","CGPOWER","CHAMBLFERT","CREDITACC","DALBHARAT",
    "DCMSHRIRAM","DEEPAKFERT","DEVYANI","ELGIEQUIP","EMAMILTD","ENDURANCE","ERIS",
    "FINEORG","FLUOROCHEM","GICRE","GLAND","GNFC","GREENPANEL","GRINDWELL",
    "GUJGASLTD","HAPPSTMNDS","HIKAL","HOMEFIRST","HUDCO","INDIAMART","INTELLECT",
    "IPCALAB","IRFC","JBCHEPHARM","JSWENERGY","JUSTDIAL","KPITTECH","LALPATHLAB",
    "LAOPALA","LATENTVIEW","LAURUSLABS","MAPMYINDIA","METROBRAND","NBCC","NILKAMAL",
    "NOCIL","NYKAA","PGHH","POLICYBZR","POONAWALLA","PVRINOX","RAILTEL","RAIN",
    "RALLIS","RAYMOND","RBLBANK","RVNL","SAGARCEM","SAKSOFT","SANDHAR","SAREGAMA",
    "SHILPAMED","SHOPERSTOP","SOLARA","SPANDANA","SPARC","SUBROS","SUDARSCHEM",
    "SYMPHONY","TANLA","TCIEXP","TEJASNET","THYROCARE","TIINDIA","TIMKEN","TINPLATE",
    "TORNTPOWER","TRIDENT","UJJIVAN","UTIAMC","VINATIORGA","VRLLOG","WABCOINDIA",
    "WELCORP","WELSPUNIND","WESTLIFE","WONDERLA","ZENSARTECH","EASEMYTRIP",
    "CASTROLIND","GULFOILLUB","GRAPHITE","HINDCOPPER","GPIL","ABBOTINDIA","AIAENG",
    "ATUL","BAJAJELEC","BEML","BHARATFORG","BOSCHLTD","CEATLTD","CENTRALBK",
    "CENTURYTEX","COROMANDEL","CRISIL","EQUITASBNK","ESABINDIA","GABRIEL","GILLETTE",
    "GSKCONS","HPCL","IIFL","INGERRAND","ISGEC","JAMNAAUTO","JKIL","JKLAKSHMI",
    "JKTYRE","KARURVYSYA","KFINTECH","KIMS","KRBL","LAXMIMACH","LUXIND","MASFIN",
    "MATRIMONY","MAYURUNIQ","MOLDTKPAC","MOTHERSON","MRPL","NAVINFLUOR","SKIPPER",
    "ROSSARI","EPIGRAL","MTAR","MGL","IGL","TRENT","JUBLFOOD","DEVYANI","CAMPUS",
    "MINDACORP","HAPPSTMNDS","BSOFT","NIITLTD","NETWORK18","KNRCON",
]))

# ═══════════════════════════════════════════════════════════════════════════════
# SCREENER.IN SCRAPER — Gets ALL fields including OPM, NPM, D/E, Current Ratio
# ═══════════════════════════════════════════════════════════════════════════════
def fetch_screener(symbol: str) -> dict:
    session = requests.Session()
    session.headers.update({
        "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language":"en-US,en;q=0.9","Referer":"https://www.screener.in/",
    })
    try: session.get("https://www.screener.in/",timeout=6)
    except: pass

    def pn(text):
        if not text: return None
        t = str(text).strip().replace(",","").replace("₹","").replace("%","").replace("Cr.","").replace("Cr","").replace("x","").strip()
        if t in ("","-","—","N/A","--","NA","\xa0"): return None
        try: return float(t.split()[0])
        except: return None

    for suffix in ["/consolidated/","/"]:
        try:
            r = session.get(f"https://www.screener.in/company/{symbol}{suffix}",timeout=15)
            if r.status_code in (404,403,429): continue
            if r.status_code != 200: continue
            soup = BeautifulSoup(r.text,"html.parser")
            if not soup.select_one("#top-ratios"): continue

            kv = {}
            for li in soup.select("#top-ratios li"):
                n = li.select_one(".name"); v = li.select_one(".number,.nowrap,.value")
                if n and v: kv[n.get_text(strip=True)] = v.get_text(strip=True)

            for section in soup.select("section"):
                for row in section.select("table tbody tr"):
                    cells = row.select("td,th")
                    if len(cells) < 2: continue
                    rn = cells[0].get_text(strip=True)
                    if not rn or len(rn) > 70: continue
                    for c in cells[1:]:
                        v = c.get_text(strip=True)
                        if v and v not in ("-","—","","--"):
                            kv[rn] = v; break

            def get(*keys):
                for k in keys:
                    if k in kv: return pn(kv[k])
                    for ak in kv:
                        if k.lower() == ak.lower() or (k.lower() in ak.lower() and len(ak) < len(k)+25):
                            v = pn(kv[ak])
                            if v is not None: return v
                return None

            price     = get("Current Price")
            mc_cr     = get("Market Cap")
            pe        = get("Stock P/E","P/E")
            bv        = get("Book Value")
            pb        = round(price/bv,2) if price and bv and bv>0 else None
            roe_r     = get("ROE","Return on equity","Return on Equity")
            roe       = roe_r/100 if roe_r else None
            roce_r    = get("ROCE","Return on capital employed","Return on Capital Employed")
            roce      = roce_r/100 if roce_r else None
            opm_r     = get("OPM","OPM %","Operating Profit Margin","Operating profit margin")
            if not opm_r:
                op = get("Operating Profit","EBIT","PBDIT")
                sal = get("Sales","Revenue","Net Sales")
                if op and sal and sal>0: opm_r = op/sal*100
            opm       = opm_r/100 if opm_r else None
            npm_r     = get("Net Profit %","Net profit margin","NPM","Profit after tax %","PAT %")
            if not npm_r:
                pat = get("Net Profit","Profit after tax","PAT")
                sal2 = get("Sales","Revenue","Net Sales")
                if pat and sal2 and sal2>0: npm_r = pat/sal2*100
            npm       = npm_r/100 if npm_r else None
            de        = get("Debt to equity","Debt / Equity","D/E Ratio","Debt to Equity")
            cr        = get("Current Ratio","Current ratio")
            dy_r      = get("Dividend Yield","Div. Yield","Dividend yield")
            dy        = dy_r/100 if dy_r else None
            ph_r      = get("Promoter holding","Promoter Holding","Promoter")
            ph        = ph_r/100 if ph_r else None
            pledge_r  = get("Pledge %","Pledged percentage","Pledged %")
            pledge    = pledge_r/100 if pledge_r else None
            eps       = get("EPS","EPS (TTM)","Earnings per Share")
            ic        = get("Interest Coverage","Interest coverage")
            sales_raw = get("Sales","Revenue","Net Sales","Total Revenue")
            revenue   = sales_raw*1e7 if sales_raw else None
            op_raw    = get("Operating Profit","EBIT","PBDIT","PBIT")
            ebitda    = op_raw*1e7 if op_raw else (revenue*opm if revenue and opm else None)
            ev_ebitda = round((mc_cr*1e7)/ebitda,1) if mc_cr and ebitda and ebitda>0 else None
            fcf_r     = get("Free Cash Flow","FCF")
            fcf       = fcf_r*1e7 if fcf_r else None

            hl = kv.get("High / Low","")
            w52h = w52l = None
            if "/" in hl:
                parts = hl.replace("₹","").replace(",","").split("/")
                w52h = pn(parts[0]); w52l = pn(parts[1]) if len(parts)>1 else None

            name = symbol
            for sel in ["h1.margin-0","h1",".company-name"]:
                el = soup.select_one(sel)
                if el:
                    t = el.get_text(strip=True)
                    if t and 2<len(t)<100: name=t; break

            sect = "Unknown"
            for a in soup.select("a[href*='/screen/']"):
                t = a.get_text(strip=True)
                if t and 2<len(t)<50 and t not in ("Screener","Login","Sign Up","Home","Screen","Advanced","Export","Back"):
                    sect=t; break

            pros = [li.get_text(strip=True) for li in soup.select(".pros li,#top-pros li")][:5]
            cons = [li.get_text(strip=True) for li in soup.select(".cons li,#top-cons li")][:5]

            q_rev=[]; q_pat=[]
            for sec in soup.select("section"):
                h2=sec.find(["h2","h3"])
                if not h2: continue
                title=h2.get_text(strip=True).lower()
                if "quarterly" in title or "results" in title:
                    for row in sec.select("table tbody tr"):
                        cells=row.select("td")
                        if not cells: continue
                        lbl=cells[0].get_text(strip=True).lower()
                        if "sales" in lbl or "revenue" in lbl:
                            q_rev=[pn(c.get_text()) for c in cells[1:9]]
                            q_rev=[v for v in q_rev if v is not None]
                        if "net profit" in lbl or "profit after" in lbl:
                            q_pat=[pn(c.get_text()) for c in cells[1:9]]
                            q_pat=[v for v in q_pat if v is not None]

            if not price and not pe: continue
            return {
                "company_name":name,"sector":sector_for(symbol,sect),"industry":sect,
                "description":"","website":"","employees":None,
                "current_price":price,"price_change_pct":None,
                "market_cap":mc_cr*1e7 if mc_cr else None,
                "52w_high":w52h,"52w_low":w52l,"avg_volume":None,
                "pe_ratio":pe,"pb_ratio":pb,"ev_ebitda":ev_ebitda,"ev_revenue":None,
                "peg_ratio":None,"book_value":bv,
                "roe":roe,"roa":None,"roce":roce,"debt_to_equity":de,
                "operating_margins":opm,"net_margins":npm,
                "revenue_growth":None,"earnings_growth":None,
                "current_ratio":cr,"quick_ratio":None,"interest_coverage":ic,
                "dividend_yield":dy,"eps":eps,"beta":None,
                "revenue":revenue,"ebitda":ebitda,"fcf":fcf,
                "promoter_holding":ph,"promoter_pledge":pledge,"institutional_holding":None,
                "analyst_recommendation":None,"target_price":None,"num_analysts":None,
                "quarterly_revenue":q_rev[:8],"quarterly_profit":q_pat[:8],
                "annual_revenue":[],"annual_profit":[],
                "pros":pros,"cons":cons,"data_source":"screener",
            }
        except Exception as e:
            print(f"  screener {symbol}: {e}"); continue
    return {}


# ═══════════════════════════════════════════════════════════════════════════════
# SECTOR AVERAGES — computed from cached stocks using medians
# ═══════════════════════════════════════════════════════════════════════════════
def compute_sector_averages(cache: dict) -> dict:
    data = {}
    for sym,s in cache.items():
        sec = s.get("sector","Unknown")
        if sec in ("Unknown","",None): sec = sector_for(sym,"Unknown")
        if sec in ("Unknown","",None): continue
        if sec not in data: data[sec]={k:[] for k in ["pe","pb","roe","roce","opm","npm","de","cr","ev_ebitda"]}
        for k,f in [("pe","pe_ratio"),("pb","pb_ratio"),("roe","roe"),("roce","roce"),
                    ("opm","operating_margins"),("npm","net_margins"),("de","debt_to_equity"),
                    ("cr","current_ratio"),("ev_ebitda","ev_ebitda")]:
            v = s.get(f)
            if v is not None and isinstance(v,(int,float)) and v==v and not (v!=v):
                data[sec][k].append(v)
    result = {}
    for sec,metrics in data.items():
        result[sec]={}
        for k,vals in metrics.items():
            if len(vals)>=2:
                sv=sorted(vals); n=len(sv)
                result[sec][k]=sv[n//2]  # median
    return result

def get_sector_comp(stock: dict, avgs: dict) -> dict:
    sym = stock.get("symbol","")
    sec = stock.get("sector","Unknown")
    if sec in ("Unknown","",None): sec = sector_for(sym,"Unknown")
    sa = avgs.get(sec,{})
    if not sa: return {}
    result = {}
    for sf,ak,lb in [("pe_ratio","pe",True),("pb_ratio","pb",True),
                     ("roe","roe",False),("roce","roce",False),
                     ("operating_margins","opm",False),("net_margins","npm",False),
                     ("debt_to_equity","de",True),("current_ratio","cr",False),
                     ("ev_ebitda","ev_ebitda",True)]:
        sv=stock.get(sf); av=sa.get(ak)
        if sv is None or av is None or av==0: continue
        diff=((sv-av)/abs(av))*100
        if lb: status="better" if sv<av*0.9 else ("worse" if sv>av*1.1 else "inline")
        else:  status="better" if sv>av*1.05 else ("worse" if sv<av*0.9 else "inline")
        result[sf]={"value":sv,"sector_avg":round(av,3),"diff_pct":round(diff,1),"status":status,"lower_better":lb}
    return result

# ═══════════════════════════════════════════════════════════════════════════════
# SCORING — 5 dimensions, sector-relative with absolute fallbacks
# ═══════════════════════════════════════════════════════════════════════════════
def ath(val, thresholds, hi=True):
    if val is None: return None
    if hi:
        for t,s in thresholds:
            if val>=t: return s
        return thresholds[-1][1]
    else:
        for t,s in thresholds:
            if val<=t: return s
        return thresholds[-1][1]

def score_stock(d: dict, avgs: dict) -> dict:
    sym=d.get("symbol",""); sec=d.get("sector","Unknown")
    if sec in ("Unknown","",None): sec=sector_for(sym,"Unknown")
    sa=avgs.get(sec,{})

    def p(v): return v*100 if v is not None else None
    def vs(val,key,hi=True):
        if val is None: return None
        avg=sa.get(key)
        if not avg or avg==0: return None
        r=val/avg
        if hi:
            if r>=2.0: return 95
            if r>=1.5: return 82
            if r>=1.2: return 68
            if r>=1.0: return 54
            if r>=0.8: return 38
            return 20
        else:
            if r<=0.4: return 95
            if r<=0.6: return 82
            if r<=0.8: return 68
            if r<=1.0: return 54
            if r<=1.3: return 38
            return 20

    roe=d.get("roe"); roce=d.get("roce"); opm=d.get("operating_margins")
    npm=d.get("net_margins"); de=d.get("debt_to_equity"); cr=d.get("current_ratio")
    pe=d.get("pe_ratio"); pb=d.get("pb_ratio"); rev_g=d.get("revenue_growth")
    earn_g=d.get("earnings_growth"); price=d.get("current_price")
    high=d.get("52w_high"); low=d.get("52w_low"); ic=d.get("interest_coverage")
    reasons=[]

    # QUALITY (30%)
    q_parts=[]; q_weights=[]
    if roe is not None:
        s=vs(roe,"roe",True) or ath(p(roe),[(30,95),(25,85),(20,72),(15,58),(10,40),(5,25)])
        q_parts.append(s); q_weights.append(0.40)
        if p(roe)>=25: reasons.append(f"Exceptional ROE {p(roe):.1f}%")
        elif p(roe)>=18: reasons.append(f"Strong ROE {p(roe):.1f}%")
    if roce is not None:
        s=vs(roce,"roce",True) or ath(p(roce),[(30,95),(25,85),(20,72),(15,58),(10,40)])
        q_parts.append(s); q_weights.append(0.35)
        if p(roce)>=25: reasons.append(f"Exceptional ROCE {p(roce):.1f}%")
        elif p(roce)>=18: reasons.append(f"High ROCE {p(roce):.1f}%")
    if opm is not None:
        s=vs(opm,"opm",True) or ath(p(opm),[(30,90),(20,75),(15,60),(8,42),(3,25)])
        q_parts.append(s); q_weights.append(0.25)
        if p(opm)>=25: reasons.append(f"Wide margins OPM {p(opm):.1f}%")
        elif p(opm)>=15: reasons.append(f"Strong margins OPM {p(opm):.1f}%")
    elif npm is not None:
        s=vs(npm,"npm",True) or ath(p(npm),[(20,85),(12,68),(8,52),(4,35)])
        q_parts.append(s); q_weights.append(0.25)
    if not q_parts: Q=45
    else:
        tw=sum(q_weights[:len(q_parts)])
        Q=min(sum(q_parts[i]*q_weights[i] for i in range(len(q_parts)))/tw,100)

    # GROWTH (25%)
    g_parts=[]
    if rev_g is not None:
        rg=p(rev_g)
        if rg>=30: g_parts.append(95); reasons.append(f"Revenue surging {rg:.1f}%")
        elif rg>=20: g_parts.append(82); reasons.append(f"Revenue growing {rg:.1f}%")
        elif rg>=12: g_parts.append(65)
        elif rg>=5: g_parts.append(48)
        elif rg>=0: g_parts.append(32)
        else: g_parts.append(15)
    if earn_g is not None:
        eg=p(earn_g)
        if eg>=30: g_parts.append(95); reasons.append(f"Earnings surging {eg:.1f}%")
        elif eg>=20: g_parts.append(82)
        elif eg>=10: g_parts.append(65)
        elif eg>=0: g_parts.append(40)
        else: g_parts.append(15)
    if not g_parts:
        if roe and p(roe)>=25: G=62; reasons.append("High ROE signals reinvestment capacity")
        elif roe and p(roe)>=18: G=52
        else: G=40
    else: G=min(sum(g_parts)/len(g_parts),100)

    # SAFETY (20%)
    s_parts=[]
    if de is not None:
        s2=vs(de,"de",False) or ath(de,[(0,95),(0.1,90),(0.3,75),(0.7,55),(1.5,35),(3,18)],hi=False)
        s_parts.append(s2)
        if de<0.1: reasons.append("Near debt-free")
        elif de<0.3: reasons.append(f"Low debt D/E {de:.2f}x")
    if cr is not None:
        if cr>=2.5: s_parts.append(88)
        elif cr>=2.0: s_parts.append(75)
        elif cr>=1.5: s_parts.append(60)
        elif cr>=1.0: s_parts.append(42)
        else: s_parts.append(18)
    if ic is not None:
        if ic>=8: s_parts.append(90)
        elif ic>=5: s_parts.append(75)
        elif ic>=3: s_parts.append(55)
        elif ic>=1.5: s_parts.append(35)
        else: s_parts.append(15)
    if not s_parts:
        pros_t=" ".join(d.get("pros",[])).lower(); cons_t=" ".join(d.get("cons",[])).lower()
        if "debt free" in pros_t or "zero debt" in pros_t: S=75; reasons.append("Debt-free")
        elif "debt" in cons_t or "leverage" in cons_t: S=28
        elif roce and p(roce)>20: S=58
        else: S=45
    else: S=min(sum(s_parts)/len(s_parts),100)

    # VALUE (15%)
    v_parts=[]
    if pe and pe>0:
        s3=vs(pe,"pe",False) or ath(pe,[(0,90),(10,80),(15,68),(20,55),(30,40),(50,22),(100,10)],hi=False)
        v_parts.append(s3)
        if pe<15: reasons.append(f"Attractive P/E {pe:.1f}x")
    if pb and pb>0:
        s4=vs(pb,"pb",False) or ath(pb,[(0,90),(1,80),(1.5,68),(3,50),(5,35),(10,20)],hi=False)
        v_parts.append(s4)
    if price and high and high>0:
        pf=((high-price)/high)*100
        if pf>=40: v_parts.append(85); reasons.append(f"{pf:.0f}% below 52W high")
        elif pf>=25: v_parts.append(70)
        elif pf>=10: v_parts.append(55)
        else: v_parts.append(35)
    V=min(sum(v_parts)/len(v_parts),100) if v_parts else 45

    # MOMENTUM (10%)
    if price and high and high>0 and low and high>low:
        pos=((price-low)/(high-low))*100
        if pos>=80: M=85
        elif pos>=60: M=70
        elif pos>=40: M=55
        elif pos>=20: M=40
        else: M=25
    elif price and high and high>0:
        pf2=((high-price)/high)*100
        M=max(20,80-pf2*1.5)
    else: M=45

    def cl(x): return max(0,min(100,round(x)))
    Q=cl(Q); G=cl(G); S=cl(S); V=cl(V); M=cl(M)
    comp=cl(Q*0.30+G*0.25+S*0.20+V*0.15+M*0.10)
    return {
        "composite":comp,
        "scores":{"quality":Q,"growth":G,"safety":S,"value":V,"momentum":M},
        "sub_scores":[
            {"label":"Quality","score":Q,"weight":"30%"},{"label":"Growth","score":G,"weight":"25%"},
            {"label":"Safety","score":S,"weight":"20%"},{"label":"Value","score":V,"weight":"15%"},
            {"label":"Momentum","score":M,"weight":"10%"},
        ],
        "top_reasons":list(dict.fromkeys(reasons))[:5],
        "sector":sec,"sector_relative":bool(sa),
    }

def conviction(score):
    if score>=72: return "Strong Buy"
    if score>=58: return "Buy"
    if score>=42: return "Watch"
    if score>=28: return "Neutral"
    return "Avoid"


# ═══════════════════════════════════════════════════════════════════════════════
# 29 INVESTOR PROFILES — Deep researched criteria
# ═══════════════════════════════════════════════════════════════════════════════
INVESTOR_PROFILES = {
    "rj":{"name":"Rakesh Jhunjhunwala","avatar":"RJ","category":"Indian Legend","focus":"India Growth Compounder","color":"#f59e0b","portfolio_size":15,"sizing_style":"conviction_weighted","bio":"India's Warren Buffett. Turned ₹5,000 into ₹40,000+ crore in 35 years. Passionate bull on India's long-term growth story.","philosophy":"'Give your investments time to mature. Be patient for the world to discover your gems.' Stay fully invested in India's growth. Entry barriers + large TAM + honest management.","exact_criteria":{"market_cap_min_cr":5000,"revenue_growth_min_pct":10,"roce_min_pct":15,"roe_min_pct":15,"de_max":0.5,"opm_min_pct":15,"promoter_min_pct":50},"what_he_looked_for":"Market cap >₹5,000 Cr, Revenue growth >10% CAGR, ROCE >15%, ROE >15%, D/E <0.5, OPM >15%, Promoter >50%, P/E below sector average. Strong cash reserves. Entry barriers. India-specific growth runway.","what_he_avoided":"Capital-scarce businesses, high debt, poor corporate governance, businesses without pricing power.","famous_investments":["Titan Company","Crisil","Lupin","Star Health","Metro Brands"],"signature_quote":"'I am bullish on India. The Indian economy will be a $10 trillion economy by 2030.'","rebalance_style":"Decades-long holds. Sold only when fundamental thesis broke or PE unsustainable."},
    "vijay_kedia":{"name":"Vijay Kedia","avatar":"VK","category":"Indian Legend","focus":"SMILE — Small Cap Monopolies","color":"#8b5cf6","portfolio_size":8,"sizing_style":"very_concentrated","bio":"Started with ₹25,000 borrowed from his father. Built a ₹1,500+ crore portfolio. Famous for 160x returns on Atul Auto and Cera Sanitaryware.","philosophy":"SMILE: Small in size (<₹5,000 Cr), Medium experience (10-15yr management), Large aspiration (fire in belly), Extra-large market potential (low share in massive TAM). Bet on the jockey, not the horse.","exact_criteria":{"market_cap_max_cr":5000,"management_experience_min_years":10,"large_tam":True,"low_market_share":True,"honest_management":True},"what_he_looked_for":"Market cap <₹5,000 Cr. Management 10-15 years experience. Low market share in large industry. Honest promoters. Scalable model. Does NOT rely on complex financial ratios — bets on management quality.","what_he_avoided":"Large cap stocks (too efficient), businesses already discovered by institutions, sectors with intense competition.","famous_investments":["Atul Auto (₹5→₹800, 160x)","Cera Sanitaryware (₹30→₹4800, 160x)","Aegis Logistics","TAC Infosec"],"signature_quote":"'Bet on the jockey, not the horse. If the management is good, the company can navigate even difficult situations.'","rebalance_style":"Ultra long term — 10 to 20 year holds. Never sold on small dips."},
    "porinju":{"name":"Porinju Veliyath","avatar":"PV","category":"Indian Legend","focus":"Smallcap Contrarian Turnarounds","color":"#ec4899","portfolio_size":25,"sizing_style":"equal_weight","bio":"The Smallcap King. Founder of Equity Intelligence India. Built fortune finding deeply undervalued small caps ignored by institutions.","philosophy":"Institutional exclusion creates systematic mispricing in small caps. Find beaten-down quality at distressed prices. The lack of coverage is the opportunity.","exact_criteria":{"market_cap_max_cr":2000,"beaten_down_pct":30,"strong_fundamentals":True,"honest_management":True},"what_he_looked_for":"Market cap under ₹2,000 Cr. 30-50% beaten down from highs. Strong historical fundamentals despite temporary problems. Honest management.","what_he_avoided":"Large caps (too efficient), businesses with permanent structural decline, promoters with integrity issues.","famous_investments":["Geojit Financial","Wonderla Holidays","V-Guard Industries"],"signature_quote":"'Markets are not efficient in the small cap space. That is exactly where the opportunity lies for patient investors.'","rebalance_style":"Event-driven. Exits when turnaround thesis plays out."},
    "ashish_kacholia":{"name":"Ashish Kacholia","avatar":"AK","category":"Indian Legend","focus":"Emerging Quality Compounders","color":"#84cc16","portfolio_size":20,"sizing_style":"equal_weight","bio":"Called the Big Whale of smallcap investing. Identifies emerging compounders before mainstream discovery. Known for exceptional due diligence.","philosophy":"Look for scalable business models in smallcap space with high ROE, strong management execution, and large growth runway. Buy before institutional discovery.","exact_criteria":{"market_cap_max_cr":15000,"roe_min_pct":20,"scalable_model":True,"earnings_growth_min_pct":20},"what_he_looked_for":"Smallcap companies ₹500-15,000 Cr, ROE >20%, scalable business, excellent management, earnings growing 20%+.","what_he_avoided":"Loss-making companies, high debt, promoters with integrity concerns, businesses without competitive advantage.","famous_investments":["Wonderla Holidays","Repco Home Finance","Safari Industries","Genus Power"],"signature_quote":"'I look for businesses that can become 10x in 7-10 years. The business model must be scalable.'","rebalance_style":"Annual review. Replaces underperformers, adds to winners."},
    "dolly_khanna":{"name":"Dolly Khanna","avatar":"DK","category":"Indian Legend","focus":"Cyclical Turnarounds & Deep Value","color":"#f472b6","portfolio_size":25,"sizing_style":"equal_weight","bio":"One of India's most successful retail investors. Specialises in cyclical businesses at turnaround points, holding through the recovery cycle.","philosophy":"Find cyclical businesses at the absolute bottom of their cycle. Buy when the sector is universally hated. Hold through the recovery. Sell when valuations stretch.","exact_criteria":{"market_cap_max_cr":3000,"at_cyclical_low":True,"pe_below_sector":True},"what_he_looked_for":"Small caps under ₹3,000 Cr. Cyclical businesses at trough valuations. Strong enough balance sheet to survive the downturn.","what_he_avoided":"Large caps, businesses with poor balance sheets that can't survive cyclical downturns.","famous_investments":["Nilkamal","Rain Industries","Thirumalai Chemicals","PPAP Automotive"],"signature_quote":"'Buy what others are ignoring. Sell what others are chasing.'","rebalance_style":"Semi-annual. Exits when cyclical recovery fully priced in."},
    "chandrakant_sampat":{"name":"Chandrakant Sampat","avatar":"CS","category":"Indian Legend","focus":"India's Original Value Investor","color":"#a78bfa","portfolio_size":10,"sizing_style":"conviction_weighted","bio":"(1928-2015) India's original value investor. Bought Hindustan Unilever and held for 40+ years. His singular criterion: zero debt.","philosophy":"Invest in businesses selling essential products people need regardless of economic cycles. Zero tolerance for debt. Brands with pricing power compound quietly for decades.","exact_criteria":{"debt_free":True,"de_max":0.1,"consumer_monopoly":True,"strong_brand":True,"essential_products":True},"what_he_looked_for":"Debt-free balance sheets (NON-NEGOTIABLE). Consumer monopolies. Strong brand moats. Essential products (FMCG, pharma). Consistent dividend payers. 20+ year runway.","what_he_avoided":"Leveraged businesses, commodity companies, government-dependent businesses, cyclical industries.","famous_investments":["Hindustan Unilever (held 40+ years)","Colgate-Palmolive","Nestle India"],"signature_quote":"'Invest in a business that even a fool can run, because someday a fool will.'","rebalance_style":"Decades-long holds. Portfolio turnover near zero."},
    "radhakishan_damani":{"name":"Radhakishan Damani","avatar":"RKD","category":"Indian Legend","focus":"Retail & Consumer Value","color":"#fb923c","portfolio_size":8,"sizing_style":"very_concentrated","bio":"Founder of DMart. Legendary investor known for contrarian calls. Philosophy: own businesses you deeply understand.","philosophy":"Extremely concentrated bets on businesses he understands completely. Consumer-facing, essential products, pricing power, low-cost operational model.","exact_criteria":{"consumer_business":True,"opm_min_pct":15,"de_max":0.3,"cash_generating":True},"what_he_looked_for":"Consumer businesses with durable competitive advantage. Low-cost operators. Essential products. Strong cash generation. Owner-operated businesses.","what_he_avoided":"Capital-intensive businesses, high debt, businesses dependent on advertising spend, luxury goods.","famous_investments":["DMart/Avenue Supermarts","VST Industries","3M India","United Breweries"],"signature_quote":"'Build a business where customers come back every single day.'","rebalance_style":"Very long term. Rarely exits once invested."},
    "raamdeo_agrawal":{"name":"Raamdeo Agrawal","avatar":"RA","category":"Indian Legend","focus":"QGLP — Quality Growth Longevity Price","color":"#60a5fa","portfolio_size":20,"sizing_style":"conviction_weighted","bio":"Co-founder of Motilal Oswal. Developed the QGLP framework. Compounded wealth at 25%+ CAGR for 30+ years.","philosophy":"All four QGLP pillars must align: Quality business, Growth in earnings >20%, Longevity of growth runway 10+ years, Price reasonable (PEG <1.5).","exact_criteria":{"roe_min_pct":20,"earnings_growth_min_pct":20,"peg_max":1.5,"pe_max":50},"what_he_looked_for":"ROE >20%, Earnings growth >20% for 5 years, Large addressable market, Honest management, PE reasonable relative to growth (PEG <1.5). All four QGLP criteria must be met.","what_he_avoided":"Commodity businesses, high debt, management integrity issues, businesses without 5-year earnings visibility.","famous_investments":["Eicher Motors","Page Industries","HDFC Bank","Infosys"],"signature_quote":"'Wealth creation is all about owning great businesses for a long period of time.'","rebalance_style":"Annual formal review. Replaces slowest growing stocks."},
    "sanjay_bakshi":{"name":"Sanjay Bakshi","avatar":"SB","category":"Indian Legend","focus":"Behavioral Value + Moat Investing","color":"#818cf8","portfolio_size":15,"sizing_style":"conviction_weighted","bio":"Professor at MDI Gurgaon and founder of ValueQuest Capital. Combines Graham's margin of safety with Munger's quality approach and behavioral finance.","philosophy":"Buy high-quality businesses at temporary discounts caused by irrational market behavior. Monopolistic characteristics. Owner-operators. High ROCE.","exact_criteria":{"roce_min_pct":20,"de_max":0.5,"moat":True,"owner_operator":True,"temporary_discount":True},"what_he_looked_for":"High-quality businesses at 20%+ temporary discount. Monopolistic characteristics. Owner-operators with >40% promoter holding. High ROCE. Low debt.","what_he_avoided":"Businesses he doesn't deeply understand, highly leveraged companies, businesses without durable moat.","famous_investments":["Relaxo Footwear","Hawkins Cookers","La Opala","Astral Poly"],"signature_quote":"'The best time to buy a great business is when it is temporarily given away by the market.'","rebalance_style":"Thesis-based. Patient 3-7 year holds."},
    "kenneth_andrade":{"name":"Kenneth Andrade (Old Bridge)","avatar":"KA","category":"Indian Legend","focus":"Asset-Light Capital Efficiency","color":"#34d399","portfolio_size":20,"sizing_style":"equal_weight","bio":"Founder of Old Bridge Capital. Known for contrarian asset-light investment philosophy. Ran IDFC Premier Equity Fund with exceptional returns.","philosophy":"Focus on asset-light businesses with high capital efficiency. Earnings growth without proportional capital investment. Contrarian — buys underperforming sectors at cyclical lows.","exact_criteria":{"roce_min_pct":15,"asset_light":True,"contrarian":True},"what_he_looked_for":"Asset-light models, high asset turnover, capital-efficient businesses, sectors at cyclical lows, improving ROCE trend.","what_he_avoided":"Capital-intensive manufacturing, businesses requiring constant capex, highly leveraged balance sheets.","famous_investments":["PI Industries","Sudarshan Chemicals","Aavas Financiers","Cera Sanitaryware"],"signature_quote":"'Asset-light businesses are the future of wealth creation in India.'","rebalance_style":"Semi-annual. Rotates from fully-valued to undervalued sectors."},
    "manish_kejriwal":{"name":"Manish Kejriwal (Amansa)","avatar":"MK","category":"Indian Legend","focus":"PE Mindset in Public Markets","color":"#f0abfc","portfolio_size":15,"sizing_style":"conviction_weighted","bio":"Founder of Amansa Capital after Goldman Sachs and Temasek. Brings private equity discipline — deep due diligence, long holding periods, world-class management focus.","philosophy":"Invest like a PE fund in public markets. World-class management, durable moats, long growth runways. Hold for 5-10 years. Corporate governance is paramount.","exact_criteria":{"roe_min_pct":20,"opm_min_pct":20,"promoter_min_pct":40,"de_max":0.5},"what_he_looked_for":"World-class management, ROE >20%, strong competitive moat, large addressable market, strong corporate governance.","what_he_avoided":"Businesses with governance concerns, high leverage, highly competitive commoditized industries.","famous_investments":["Info Edge (Naukri)","HDFC Life","Asian Paints","Pidilite Industries"],"signature_quote":"'We invest in businesses, not stocks. The stock price will follow the business quality.'","rebalance_style":"Long-term 5-10 year holds. Very low portfolio turnover."},
    "buffett":{"name":"Warren Buffett","avatar":"WB","category":"Global Legend","focus":"Wonderful Companies at Fair Prices","color":"#3b82f6","portfolio_size":10,"sizing_style":"very_concentrated","bio":"Oracle of Omaha. Compounded Berkshire Hathaway at ~20% CAGR for 58 years. The greatest investor in history.","philosophy":"Buy wonderful businesses at fair prices and hold forever. Wonderful = durable competitive advantage + consistent high ROE without leverage + pricing power + honest management.","exact_criteria":{"roe_min_pct":20,"de_max":0.5,"opm_min_pct":15,"pe_max":35,"consistent_earnings":True},"what_he_looked_for":"ROE >20% consistently without leverage. D/E <0.5. OPM >15% (pricing power). P/E <35x. Business understandable in 5 minutes. Honest management with long tenure.","what_he_avoided":"Businesses he cannot understand, highly leveraged companies, commodity businesses without pricing power.","famous_investments":["Coca-Cola","American Express","Apple","GEICO","Bank of America"],"signature_quote":"'It is far better to buy a wonderful company at a fair price than a fair company at a wonderful price.'","rebalance_style":"Favourite holding period is forever."},
    "ben_graham":{"name":"Benjamin Graham","avatar":"BG","category":"Global Legend","focus":"Deep Value — Margin of Safety","color":"#64748b","portfolio_size":25,"sizing_style":"equal_weight","bio":"Father of Value Investing. Wrote The Intelligent Investor. Warren Buffett's teacher. Created modern security analysis.","philosophy":"Always buy with a significant margin of safety — the gap between intrinsic value and market price. Never overpay. Treat stocks as ownership in real businesses.","exact_criteria":{"pb_max":1.5,"pe_max":15,"de_max":0.5,"current_ratio_min":2.0,"dividend_payer":True},"what_he_looked_for":"P/B below 1.5x. P/E below 15x. D/E below 0.5. Positive earnings for 5+ years. Dividend payments. Current ratio above 2x.","what_he_avoided":"Speculative stocks, growth stocks at premium valuations, poor balance sheets.","famous_investments":["GEICO (bought at extreme discount)","Northern Pipeline"],"signature_quote":"'The margin of safety is always dependent on the price paid. It can be large at one price, small at another, and nonexistent at a third.'","rebalance_style":"Annual rebalance. Systematic rules-based approach."},
    "peter_lynch":{"name":"Peter Lynch","avatar":"PL","category":"Global Legend","focus":"GARP — Growth at Reasonable Price","color":"#06b6d4","portfolio_size":30,"sizing_style":"equal_weight","bio":"Managed Fidelity Magellan Fund achieving 29.2% annual returns — best 13-year run of any mutual fund in history.","philosophy":"Use PEG ratio to find growth at reasonable price. PEG below 1 = you are getting growth cheap. Invest in companies you understand from daily life.","exact_criteria":{"peg_max":1.0,"earnings_growth_min_pct":15,"pe_max":50},"what_he_looked_for":"PEG ratio <1.0 (ideally <0.5). Earnings growth >15-20%. Companies he could explain in 2 minutes. Boring industries with exceptional fundamentals.","what_he_avoided":"Businesses he did not understand, hot industries with heavy competition.","famous_investments":["Dunkin Donuts","Taco Bell","Subaru","La Quinta Motor Inns"],"signature_quote":"'Invest in what you know. The real key to making money in stocks is not to get scared out of them.'","rebalance_style":"Quarterly review. High turnover acceptable when PEG changes."},
    "charlie_munger":{"name":"Charlie Munger","avatar":"CM","category":"Global Legend","focus":"Wonderful Businesses — Pricing Power","color":"#0ea5e9","portfolio_size":5,"sizing_style":"very_concentrated","bio":"Buffett's partner for 60 years. Transformed Buffett from Graham-style deep value to quality compounder investing.","philosophy":"A few wonderful businesses held forever beats a hundred mediocre ones traded frequently. ROCE is the ultimate quality test. Pricing power is the ultimate moat indicator.","exact_criteria":{"roce_min_pct":25,"opm_min_pct":25,"de_max":0.3,"pricing_power":True},"what_he_looked_for":"ROCE >25% (non-negotiable). OPM >25% (pricing power). Near debt-free. Durable competitive moat. Management that allocates capital brilliantly.","what_he_avoided":"Complex businesses, commodity businesses, management that speaks in jargon.","famous_investments":["BYD","Berkshire investments alongside Buffett"],"signature_quote":"'Show me the incentive and I will show you the outcome.'","rebalance_style":"Ultra-long term. Very rare portfolio changes."},
    "phil_fisher":{"name":"Philip Fisher","avatar":"PF","category":"Global Legend","focus":"Outstanding Growth — Scuttlebutt Research","color":"#14b8a6","portfolio_size":12,"sizing_style":"conviction_weighted","bio":"Wrote Common Stocks and Uncommon Profits (1958). Scuttlebutt research method revolutionised equity research.","philosophy":"Buy outstanding companies with superior long-term growth prospects and hold for years. Research through industry contacts, customers, competitors, suppliers. Management quality is paramount.","exact_criteria":{"sales_growth_min_pct":15,"opm_expanding":True,"management_quality":True,"promoter_min_pct":35},"what_he_looked_for":"Strong and sustained sales growth >15%. Expanding profit margins. Excellent management with R&D commitment. Proprietary products or services. Good labour relations.","what_he_avoided":"Businesses solely focused on price competition, poor management teams, businesses without proprietary advantages.","famous_investments":["Motorola (held for decades)","Texas Instruments","Dow Chemical"],"signature_quote":"'The stock market is filled with individuals who know the price of everything, but the value of nothing.'","rebalance_style":"Long-term growth holds. Exits when growth thesis permanently breaks."},
    "parag_parikh":{"name":"Parag Parikh Flexi Cap","avatar":"PP","category":"Indian Fund","focus":"Owner-Operator Quality + Behavioral Discipline","color":"#10b981","portfolio_size":22,"sizing_style":"equal_weight","bio":"PPFAS manages one of India's most respected mutual funds. Known for ultra-low churn, behavioural investing approach, and willingness to hold cash when markets are overvalued.","philosophy":"Invest in businesses run by owner-operators with real skin in the game. Focus on pricing power, durable competitive advantages, and behavioural discipline. Hold cash when nothing is cheap.","exact_criteria":{"promoter_min_pct":30,"opm_min_pct":15,"de_max":0.7,"roe_min_pct":15,"pe_max":45},"what_he_looked_for":"Owner-operators (promoter >30%). Pricing power (OPM >15%). Low debt. Consistent ROE >15%. Reasonable PE <45x. Global quality companies alongside Indian.","what_he_avoided":"Highly valued momentum stocks, businesses without pricing power, high leverage.","famous_investments":["HDFC Bank","Bajaj Holdings","ITC","Coal India","Google (global)"],"signature_quote":"'We buy businesses, not stocks. Price is what you pay, value is what you get.'","rebalance_style":"Semi-annual formal review. Very low turnover."},
    "marcellus":{"name":"Marcellus (Saurabh Mukherjea)","avatar":"MC","category":"Indian Fund","focus":"Consistent Compounders — Forensic Quality","color":"#06b6d4","portfolio_size":12,"sizing_style":"equal_weight","bio":"Founded Marcellus in 2018. CCP strategy uses forensic accounting screens to find companies with clean books and consistently high ROCE. 12-15 stocks maximum.","philosophy":"ROCE >15% (CCP targets >25-40%) for 10 consecutive years. Revenue growth >10% CAGR for 10 years. Near-zero debt. 12 forensic accounting ratios. Low churn.","exact_criteria":{"roce_min_pct":15,"revenue_growth_min_pct":10,"de_max":0.3,"clean_accounting":True,"free_cash_flow_positive":True},"what_he_looked_for":"ROCE >15% for 10 consecutive years (CCP often >40%). Revenue growth >10% CAGR for 10 years. Near-zero debt. Clean accounting (12 forensic ratios). Zero promoter pledge. Free cash flow generation.","what_he_avoided":"Any leverage, aggressive accounting, related-party transactions, promoter pledge.","famous_investments":["Asian Paints","HDFC Bank","Pidilite Industries","Nestle India","TCS"],"signature_quote":"'Great businesses destroy the competition slowly and surely, and without making any noise.'","rebalance_style":"Annual April rebalance. Replaces bottom 2-3 performers."},
    "motilal_qglp":{"name":"Motilal Oswal QGLP","avatar":"MO","category":"Indian Fund","focus":"Quality + Growth + Longevity + Price","color":"#f97316","portfolio_size":20,"sizing_style":"conviction_weighted","bio":"Motilal Oswal Asset Management applies QGLP framework pioneered by Raamdeo Agrawal. Refined over 30 years.","philosophy":"All four QGLP pillars must be present simultaneously. Quality business, Growth in earnings >20%, Longevity of growth runway 10+ years, Price reasonable (PEG <1.5).","exact_criteria":{"roe_min_pct":20,"earnings_growth_min_pct":20,"peg_max":1.5,"pe_max":50},"what_he_looked_for":"ROE >20%, Earnings growth >20% consistently, Large total addressable market, PEG under 1.5.","what_he_avoided":"Low-quality businesses even at cheap valuations, businesses without 10-year earnings visibility.","famous_investments":["Eicher Motors","Page Industries","Bajaj Finance"],"signature_quote":"'Buy right, sit tight.'","rebalance_style":"Annual formal rebalance."},
    "nippon_smallcap":{"name":"Nippon India Small Cap","avatar":"NS","category":"Indian Fund","focus":"High Growth Small Caps","color":"#22d3ee","portfolio_size":60,"sizing_style":"equal_weight","bio":"One of India's largest small cap funds with over ₹50,000 Cr AUM. Invests across small caps with focus on growth businesses in emerging sectors.","philosophy":"Diversified exposure to India's small cap growth story. Find emerging sector leaders before mainstream discovery. Willing to pay higher multiples for high growth.","exact_criteria":{"market_cap_max_cr":8000,"revenue_growth_min_pct":15,"roe_min_pct":15,"pe_max":60},"what_he_looked_for":"Small cap companies (₹500-8,000 Cr). Revenue growth >20%. Improving profitability. Sector leadership potential.","what_he_avoided":"Loss-making without path to profitability, too much debt, permanently declining industries.","famous_investments":["Tube Investments","Navin Fluorine","Happiest Minds","KPIT Technologies"],"signature_quote":"'Small caps today are large caps tomorrow.'","rebalance_style":"Quarterly review."},
    "mirae_asset":{"name":"Mirae Asset India","avatar":"MA","category":"Indian Fund","focus":"Quality Growth — Sector Leaders","color":"#a3e635","portfolio_size":55,"sizing_style":"market_cap_weighted","bio":"Mirae Asset India applies Korean rigor to Indian equity. Known for disciplined, process-driven investing.","philosophy":"Bottom-up stock selection focusing on quality businesses with sustainable competitive advantages. Sector leaders with consistent earnings growth and strong return ratios.","exact_criteria":{"roe_min_pct":15,"roce_min_pct":15,"earnings_growth_min_pct":12,"pe_max":45},"what_he_looked_for":"Sector leadership. Consistent earnings growth. Strong ROE and ROCE. Reasonable valuations. Well-managed balance sheets.","what_he_avoided":"Speculative businesses, high leverage, businesses without competitive advantage.","famous_investments":["ICICI Bank","Infosys","Maruti Suzuki","Bharti Airtel","Kotak Mahindra"],"signature_quote":"'Quality businesses at reasonable prices outperform over any market cycle.'","rebalance_style":"Quarterly review. Benchmark-aware."},
    "hdfc_mf":{"name":"HDFC Mutual Fund (Prashant Jain era)","avatar":"HM","category":"Indian Fund","focus":"Value + Quality — Contrarian","color":"#fb923c","portfolio_size":50,"sizing_style":"conviction_weighted","bio":"Under Prashant Jain (2003-2022), HDFC Equity Fund became India's most respected equity fund. Famous for contrarian calls on PSU banks and infrastructure.","philosophy":"Buy quality businesses at value prices. Be contrarian. PSU banks, infrastructure, and cyclicals have their time. Patient capital. Hold through 3-5 year down cycles.","exact_criteria":{"pe_max":20,"roe_min_pct":12,"de_max":1.5,"dividend_yield_min_pct":2},"what_he_looked_for":"Quality businesses at value multiples (PE <20x). PSU and cyclical businesses at trough valuations. Consistent dividend payers. Willing to be 3 years early.","what_he_avoided":"Businesses at extreme valuations, highly leveraged, businesses without earnings visibility.","famous_investments":["SBI","HDFC Bank","Infosys","BHEL (contrarian)","ONGC"],"signature_quote":"'Be contrarian. Buy when others are selling in panic.'","rebalance_style":"Patient 3-5 year holds. Contrarian rebalancing."},
    "enam":{"name":"Enam / Vallabh Bhansali","avatar":"EN","category":"Indian Fund","focus":"Forensic Long-Term Quality","color":"#c4b5fd","portfolio_size":15,"sizing_style":"conviction_weighted","bio":"Enam Securities, founded by Vallabh Bhansali and Nemish Shah, is one of India's most respected institutional brokers known for deep fundamental research.","philosophy":"Management integrity is non-negotiable. Zero tolerance for governance issues. Debt-free businesses with long track records. 10+ year horizon.","exact_criteria":{"de_max":0.1,"management_integrity":True,"track_record_years":10,"roe_min_pct":18},"what_he_looked_for":"Management integrity above all. Debt-free businesses. Consistent 10+ year track record. High ROCE. Pricing power.","what_he_avoided":"Any management integrity concerns, leveraged businesses.","famous_investments":["HDFC Bank","Infosys","Asian Paints","Hero Honda"],"signature_quote":"'Management integrity is the first filter. Everything else is secondary.'","rebalance_style":"Very long term. Extremely low turnover."},
    "nemish_shah":{"name":"Nemish Shah","avatar":"NSH","category":"Indian Fund","focus":"Consumer & Pharma Quality","color":"#e879f9","portfolio_size":15,"sizing_style":"conviction_weighted","bio":"Co-founded Enam Securities. Deep expertise in consumer and pharmaceutical businesses with decades-long holding horizons.","philosophy":"Consumer staples and pharma — businesses people need regardless of the economy. Brands with pricing power and high repeat purchase compound quietly for decades.","exact_criteria":{"de_max":0.2,"opm_min_pct":18,"roe_min_pct":18,"dividend_payer":True},"what_he_looked_for":"Consumer brands with pricing power. Pharmaceutical businesses with strong pipelines. Debt-free balance sheets. Consistent dividend payers.","what_he_avoided":"Capital-intensive businesses without brand moat, high debt, management integrity concerns.","famous_investments":["Hindustan Unilever","Nestle India","Abbott India","Colgate-Palmolive"],"signature_quote":"'Consumer brands are the closest thing to a perpetual motion machine in business.'","rebalance_style":"Very long term holds. Decades in some cases."},
    "white_oak":{"name":"White Oak Capital (Prashant Khemka)","avatar":"WO","category":"Indian Fund","focus":"Earnings Quality + ROE without Leverage","color":"#34d399","portfolio_size":30,"sizing_style":"equal_weight","bio":"Founded White Oak Capital after Goldman Sachs Asset Management. Focus on earnings quality and return on equity without leverage.","philosophy":"Earnings quality is the foundation. High, sustainable ROE without leverage. Business quality drives long-term returns. Goldman Sachs rigour applied to Indian markets.","exact_criteria":{"roe_min_pct":20,"de_max":0.5,"earnings_quality":True,"pe_max":40},"what_he_looked_for":"ROE >20% without leverage. High earnings quality (cash conversion). Consistent growth. Reasonable valuations.","what_he_avoided":"Businesses with poor earnings quality, high leverage.","famous_investments":["ICICI Bank","Kotak Bank","Maruti","Titan"],"signature_quote":"'Earnings quality separates sustainable returns from temporary ones.'","rebalance_style":"Annual rebalance. Equal weight approach."},
    "carnelian":{"name":"Carnelian Asset (Vikas Khemani)","avatar":"CA","category":"Indian Fund","focus":"Emerging Compounders — Structural Sectors","color":"#67e8f9","portfolio_size":20,"sizing_style":"equal_weight","bio":"Founded Carnelian Asset Management after leading Edelweiss Securities. Focuses on emerging compounders in sectors with strong structural tailwinds.","philosophy":"Find businesses in sectors with strong structural tailwinds — defence, specialty chemicals, digital India, PLI beneficiaries. Companies transitioning from small to mid cap.","exact_criteria":{"market_cap_max_cr":20000,"roe_min_pct":18,"earnings_growth_min_pct":20,"opm_min_pct":12},"what_he_looked_for":"Emerging sector leaders in structural growth sectors. Improving margin profile. Management execution track record. Market cap ₹500-20,000 Cr.","what_he_avoided":"Structurally declining industries, high leverage.","famous_investments":["KPIT Technologies","Mas Financial","Tanla Platforms"],"signature_quote":"'Invest in the future, not the past. Structural tailwinds are as important as the business itself.'","rebalance_style":"Semi-annual review."},
    "anand_rathi":{"name":"Anand Rathi Wealth","avatar":"AR","category":"Indian Fund","focus":"HNI Wealth Preservation + Growth","color":"#fbbf24","portfolio_size":25,"sizing_style":"risk_weighted","bio":"One of India's leading wealth management firms. Approach prioritises capital preservation alongside growth with heavy emphasis on asset allocation.","philosophy":"Wealth preservation first, growth second. Large cap bias for stability. Dividend-paying businesses for income. Risk management as central theme.","exact_criteria":{"market_cap_min_cr":10000,"de_max":0.5,"dividend_yield_min_pct":2,"roe_min_pct":12},"what_he_looked_for":"Large cap stability (>₹10,000 Cr). Consistent dividend payers (>2% yield). Low debt. Strong corporate governance. Defensive sectors.","what_he_avoided":"Highly speculative smallcaps, governance issues, high leverage.","famous_investments":["HDFC Bank","Infosys","Reliance","ITC","Bajaj Finance"],"signature_quote":"'Preserving wealth is as important as creating it.'","rebalance_style":"Semi-annual with asset allocation review."},
    "ask_investment":{"name":"ASK Investment Managers","avatar":"ASK","category":"Indian Fund","focus":"Quality Large Cap PMS","color":"#fdba74","portfolio_size":20,"sizing_style":"conviction_weighted","bio":"One of India's largest PMS providers with over ₹70,000 Cr AUM. Known for quality-focused wealth preservation philosophy for HNI clients.","philosophy":"Capital preservation with growth. Focus on large quality businesses. Low churn, patient approach. Management quality is the cornerstone.","exact_criteria":{"market_cap_min_cr":15000,"roe_min_pct":18,"de_max":0.4,"pe_max":40},"what_he_looked_for":"Large cap quality (>₹15,000 Cr). Consistent earnings growth. Strong ROE. Low debt. Dividend payers. Strong corporate governance.","what_he_avoided":"Small caps, governance concerns, high leverage, loss-making businesses.","famous_investments":["HDFC Bank","Bajaj Finance","Asian Paints","Infosys","Kotak Bank"],"signature_quote":"'Quality never goes out of style.'","rebalance_style":"Annual. Low turnover wealth management approach."},
    "murugappa":{"name":"Murugappa Group Style","avatar":"MG","category":"Indian Fund","focus":"Conservative Industrial Quality","color":"#fcd34d","portfolio_size":15,"sizing_style":"equal_weight","bio":"The Murugappa Group is a 125-year-old Chennai-based conglomerate. Investment philosophy reflects generations of industrial wealth creation — patient, conservative, quality-focused.","philosophy":"Long-term industrial value creation. Manufacturing excellence. Conservative balance sheets. Consistent dividend history. Multi-generational thinking.","exact_criteria":{"de_max":0.5,"dividend_yield_min_pct":2,"opm_min_pct":12,"roe_min_pct":12},"what_he_looked_for":"Manufacturing excellence. Operational efficiency. Conservative balance sheets. Consistent dividend history. Family-managed businesses with long track records.","what_he_avoided":"Speculative businesses, high leverage, businesses requiring constant external capital.","famous_investments":["Coromandel International","Carborundum Universal","Cholamandalam","EID Parry"],"signature_quote":"'Build businesses that last generations.'","rebalance_style":"Very long term. Generational investment horizon."},
}


# ═══════════════════════════════════════════════════════════════════════════════
# PROFILE SCORING — Precise criteria, NOT generic
# ═══════════════════════════════════════════════════════════════════════════════
def score_profile(d: dict, pid: str, avgs: dict) -> dict:
    s=0; r=[]
    sym=d.get("symbol",""); sec=d.get("sector","Unknown")
    if sec in ("Unknown","",None): sec=sector_for(sym,"Unknown")
    sa=avgs.get(sec,{})
    def p(v): return v*100 if v is not None else None
    def vc(val,key,hi=True):
        if val is None: return 0
        avg=sa.get(key)
        if not avg or avg==0: return 0
        ratio=val/avg
        if hi:
            if ratio>=1.5: return 30
            if ratio>=1.2: return 22
            if ratio>=1.0: return 16
            if ratio>=0.8: return 10
            return 4
        else:
            if ratio<=0.5: return 30
            if ratio<=0.7: return 22
            if ratio<=0.9: return 16
            if ratio<=1.1: return 10
            return 4
    roe=d.get("roe"); roce=d.get("roce"); opm=d.get("operating_margins")
    de=d.get("debt_to_equity"); cr=d.get("current_ratio"); pe=d.get("pe_ratio")
    pb=d.get("pb_ratio"); ph=d.get("promoter_holding"); pledge=d.get("promoter_pledge",0) or 0
    rev_g=d.get("revenue_growth"); earn_g=d.get("earnings_growth")
    dy=d.get("dividend_yield"); price=d.get("current_price"); high=d.get("52w_high")
    mc=(d.get("market_cap") or 0)/1e7
    debt_free=de is not None and de<0.15
    pct_off=((high-price)/high*100) if price and high and high>0 else 0
    pledge_ok=pledge<0.10

    if pid=="rj":
        if mc>=5000: s+=15; r.append(f"Mid/Large cap ₹{mc:.0f}Cr ✓ (RJ min ₹5,000 Cr)")
        elif mc>=2000: s+=8
        if roe and p(roe)>=15: s+=15+vc(roe,"roe",True); r.append(f"ROE {p(roe):.1f}% ≥ 15% RJ threshold")
        if roce and p(roce)>=15: s+=15+vc(roce,"roce",True); r.append(f"ROCE {p(roce):.1f}% ≥ 15% RJ threshold")
        if de is not None and de<0.5: s+=15; r.append("D/E <0.5 — RJ criterion ✓")
        if opm and p(opm)>=15: s+=15+vc(opm,"opm",True); r.append(f"OPM {p(opm):.1f}% ≥ 15% ✓")
        if ph and ph>=0.50: s+=20; r.append(f"Promoter {p(ph):.1f}% >50% — RJ requirement ✓")
        elif ph and ph>=0.40: s+=12; r.append(f"Promoter {p(ph):.1f}%")
        if pe and sa.get("pe") and pe<sa["pe"]: s+=10; r.append("P/E below sector avg — RJ entry signal")
    elif pid=="vijay_kedia":
        if mc<=1000: s+=30; r.append(f"Small cap ₹{mc:.0f}Cr — SMILE S criterion ✓")
        elif mc<=5000: s+=20; r.append(f"Mid-small cap ₹{mc:.0f}Cr")
        if ph and ph>=0.50: s+=20; r.append(f"Promoter {p(ph):.1f}% — jockey aligned ✓")
        elif ph and ph>=0.35: s+=12
        if pledge_ok and ph and ph>=0.35: s+=10; r.append("No pledge — management conviction ✓")
        if roe and p(roe)>=15: s+=15+vc(roe,"roe",True)
        if opm and p(opm)>=12: s+=10+vc(opm,"opm",True)
        if pe and 0<pe<40: s+=10; r.append(f"Reasonable P/E {pe:.1f}x")
    elif pid=="porinju":
        if mc<=2000: s+=30; r.append(f"True smallcap ₹{mc:.0f}Cr — Porinju territory ✓")
        elif mc<=5000: s+=15
        if pct_off>=40: s+=25; r.append(f"Beaten down {pct_off:.0f}% off 52W high — opportunity")
        elif pct_off>=25: s+=15; r.append(f"{pct_off:.0f}% below 52W high")
        if pe and 0<pe<15: s+=20; r.append(f"Deep value P/E {pe:.1f}x")
        elif pe and pe<25: s+=10
        if roe and p(roe)>=12: s+=15+vc(roe,"roe",True)
        if de is None or de<1.0: s+=10
    elif pid=="ashish_kacholia":
        if mc<=5000: s+=25; r.append(f"Smallcap ₹{mc:.0f}Cr ✓")
        elif mc<=15000: s+=15; r.append(f"Mid cap ₹{mc:.0f}Cr")
        if roe and p(roe)>=20: s+=25+vc(roe,"roe",True); r.append(f"High ROE {p(roe):.1f}% ✓")
        elif roe and p(roe)>=15: s+=15
        if earn_g and p(earn_g)>=20: s+=20; r.append(f"Earnings growing {p(earn_g):.1f}% ✓")
        elif earn_g and p(earn_g)>=12: s+=12
        if opm and p(opm)>=15: s+=15+vc(opm,"opm",True)
        if pe and 0<pe<50: s+=10
    elif pid=="dolly_khanna":
        if mc<=3000: s+=25; r.append(f"Small cap ₹{mc:.0f}Cr — Dolly's zone ✓")
        elif mc<=7000: s+=12
        if pct_off>=30: s+=25; r.append(f"Cyclical opportunity {pct_off:.0f}% off highs")
        elif pct_off>=15: s+=15
        if roe and p(roe)>=12: s+=20+vc(roe,"roe",True); r.append(f"ROE recovery signal {p(roe):.1f}%")
        if de is not None and de<0.7: s+=15
        if pe and 0<pe<20: s+=15; r.append(f"Cheap P/E {pe:.1f}x")
    elif pid=="chandrakant_sampat":
        if debt_free: s+=35; r.append("Debt-free — Sampat's NON-NEGOTIABLE criterion ✓")
        elif de and de<0.1: s+=25; r.append("Near debt-free ✓")
        if roe and p(roe)>=20: s+=25; r.append(f"High ROE {p(roe):.1f}%")
        elif roe and p(roe)>=15: s+=15
        if opm and p(opm)>=20: s+=25; r.append(f"Consumer pricing power OPM {p(opm):.1f}%")
        elif opm and p(opm)>=12: s+=12
        if pe and 0<pe<40: s+=15
    elif pid=="radhakishan_damani":
        if opm and p(opm)>=15: s+=30; r.append(f"Consumer pricing power OPM {p(opm):.1f}%")
        elif opm and p(opm)>=10: s+=18
        if de is not None and de<0.3: s+=25; r.append("Conservative balance sheet ✓")
        if dy and p(dy)>=2: s+=15; r.append(f"Cash return {p(dy):.1f}% yield")
        if roe and p(roe)>=18: s+=20; r.append(f"Strong ROE {p(roe):.1f}%")
        elif roe and p(roe)>=12: s+=12
        if mc>=5000: s+=10
    elif pid=="raamdeo_agrawal":
        q_met=roe and p(roe)>=20; g_met=(earn_g and p(earn_g)>=20) or (rev_g and p(rev_g)>=15); p_met=pe and 0<pe<50
        if q_met: s+=30; r.append(f"Q: ROE {p(roe):.1f}%≥20% ✓")
        if g_met: s+=30; r.append("G: Growth criterion met (>20%) ✓")
        if p_met: s+=20; r.append(f"P: Reasonable P/E {pe:.1f}x ✓")
        if roce and p(roce)>=20: s+=20; r.append(f"ROCE {p(roce):.1f}%")
    elif pid=="sanjay_bakshi":
        if roce and p(roce)>=20: s+=25+vc(roce,"roce",True); r.append(f"Quality ROCE {p(roce):.1f}%")
        elif roce and p(roce)>=15: s+=15
        if debt_free or (de and de<0.3): s+=20; r.append("Graham safety margin ✓")
        if pct_off>=20: s+=25; r.append(f"Behavioral mispricing {pct_off:.0f}% off highs")
        elif pct_off>=10: s+=12
        if ph and ph>=0.40: s+=15; r.append(f"Owner-operator {p(ph):.1f}%")
        if opm and p(opm)>=20: s+=15; r.append(f"Wide margins OPM {p(opm):.1f}%")
    elif pid=="kenneth_andrade":
        if roce and p(roce)>=20: s+=30+vc(roce,"roce",True); r.append(f"Capital efficient ROCE {p(roce):.1f}%")
        elif roce and p(roce)>=15: s+=18
        if opm and p(opm)>=15: s+=25+vc(opm,"opm",True); r.append(f"Asset-light margins {p(opm):.1f}%")
        if de is not None and de<0.3: s+=20; r.append("Low capex model ✓")
        if pct_off>=15: s+=15; r.append(f"Contrarian entry {pct_off:.0f}% off highs")
    elif pid=="manish_kejriwal":
        if roe and p(roe)>=20: s+=25+vc(roe,"roe",True); r.append(f"PE-quality ROE {p(roe):.1f}%")
        elif roe and p(roe)>=15: s+=15
        if opm and p(opm)>=20: s+=25+vc(opm,"opm",True); r.append(f"Quality margins {p(opm):.1f}%")
        if ph and ph>=0.45: s+=25; r.append(f"Management aligned {p(ph):.1f}%")
        elif ph and ph>=0.30: s+=15
        if debt_free or (de and de<0.4): s+=15
        if pledge_ok: s+=10
    elif pid=="buffett":
        if roe and p(roe)>=20: s+=25+vc(roe,"roe",True); r.append(f"Buffett-grade ROE {p(roe):.1f}% ✓")
        elif roe and p(roe)>=15: s+=15
        if de is not None and de<0.5: s+=20; r.append("Conservative balance sheet ✓")
        if opm and p(opm)>=15: s+=20+vc(opm,"opm",True); r.append(f"Pricing power OPM {p(opm):.1f}% ✓")
        elif opm and p(opm)>=10: s+=10
        if pe and 0<pe<35: s+=20; r.append(f"Reasonable P/E {pe:.1f}x for the quality ✓")
        elif pe and pe<50: s+=8
    elif pid=="ben_graham":
        if pb and pb<1.0: s+=40; r.append(f"Below book P/B {pb:.2f}x — Graham ideal ✓")
        elif pb and pb<1.5: s+=28; r.append(f"Near book P/B {pb:.2f}x ✓")
        elif pb and pb<2.0: s+=14
        if pe and 0<pe<12: s+=30; r.append(f"Deep value P/E {pe:.1f}x — Graham zone ✓")
        elif pe and pe<15: s+=20; r.append(f"Value P/E {pe:.1f}x ✓")
        elif pe and pe<20: s+=8
        if cr and cr>=2.0: s+=20; r.append(f"Current ratio {cr:.1f}x — Graham safety ✓")
        if dy and p(dy)>=1: s+=10; r.append(f"Dividend payer {p(dy):.1f}%")
        if de is not None and de<0.5: s+=10
    elif pid=="peter_lynch":
        peg_calc=None
        if roe and pe and p(roe)>0: peg_calc=pe/p(roe)
        if peg_calc and peg_calc<0.5: s+=40; r.append(f"Excellent PEG ~{peg_calc:.2f} ✓")
        elif peg_calc and peg_calc<1.0: s+=28; r.append(f"Good PEG ~{peg_calc:.2f} ✓")
        elif peg_calc and peg_calc<1.5: s+=15
        if earn_g and p(earn_g)>=20: s+=25; r.append(f"Lynch growth signal {p(earn_g):.1f}% ✓")
        elif earn_g and p(earn_g)>=15: s+=15
        elif rev_g and p(rev_g)>=15: s+=12
        if pe and 0<pe<30: s+=15; r.append(f"Reasonable P/E {pe:.1f}x")
    elif pid=="charlie_munger":
        if roce and p(roce)>=25: s+=35+vc(roce,"roce",True); r.append(f"Munger-grade ROCE {p(roce):.1f}% ✓")
        elif roce and p(roce)>=20: s+=20
        elif roce and p(roce)>=15: s+=10
        if opm and p(opm)>=25: s+=30+vc(opm,"opm",True); r.append(f"Pricing power OPM {p(opm):.1f}% ✓")
        elif opm and p(opm)>=20: s+=18
        if debt_free: s+=25; r.append("Debt-free compounder — Munger approved ✓")
        elif de and de<0.2: s+=15
    elif pid=="phil_fisher":
        if roe and p(roe)>=20: s+=25+vc(roe,"roe",True); r.append(f"Superior ROE {p(roe):.1f}%")
        elif roe and p(roe)>=15: s+=15
        if opm and p(opm)>=18: s+=25+vc(opm,"opm",True); r.append(f"Expanding margins {p(opm):.1f}%")
        if ph and ph>=0.40: s+=20; r.append(f"Management aligned {p(ph):.1f}%")
        if rev_g and p(rev_g)>=15: s+=20; r.append(f"Sales growth {p(rev_g):.1f}%")
        elif rev_g and p(rev_g)>=10: s+=12
        if pe and 0<pe<50: s+=10
    elif pid=="parag_parikh":
        if ph and ph>=0.50: s+=25; r.append(f"Strong owner-operator {p(ph):.1f}%")
        elif ph and ph>=0.35: s+=18; r.append(f"Owner-operator {p(ph):.1f}%")
        elif ph and ph>=0.25: s+=10
        if opm and p(opm)>=15: s+=20+vc(opm,"opm",True); r.append(f"Pricing power {p(opm):.1f}%")
        elif opm and p(opm)>=10: s+=10
        if de is not None and de<0.7: s+=15; r.append("Conservative balance sheet")
        if roe and p(roe)>=15: s+=20+vc(roe,"roe",True)
        if pe and 0<pe<50: s+=10
        if pledge_ok: s+=10
    elif pid=="marcellus":
        if debt_free: s+=30; r.append("Debt-free — Marcellus essential criterion ✓")
        elif de and de<0.1: s+=22; r.append("Near debt-free ✓")
        elif de and de<0.3: s+=10
        if roce and p(roce)>=25: s+=30+vc(roce,"roce",True); r.append(f"Exceptional ROCE {p(roce):.1f}% — CCP quality ✓")
        elif roce and p(roce)>=15: s+=18; r.append(f"Strong ROCE {p(roce):.1f}%")
        if roe and p(roe)>=20: s+=15+vc(roe,"roe",True)
        if opm and p(opm)>=18: s+=15; r.append(f"Wide margins {p(opm):.1f}%")
        if pledge==0: s+=10; r.append("Zero promoter pledge — forensic positive ✓")
    elif pid=="motilal_qglp":
        q_ok=roe and p(roe)>=20; g_ok=earn_g and p(earn_g)>=20; p_ok=pe and 0<pe<50
        if q_ok: s+=28; r.append(f"Quality: ROE {p(roe):.1f}% ✓")
        if g_ok: s+=28; r.append(f"Growth: Earnings {p(earn_g):.1f}% ✓")
        if p_ok: s+=22; r.append(f"Price: P/E {pe:.1f}x ✓")
        if roce and p(roce)>=20: s+=22; r.append(f"ROCE {p(roce):.1f}%")
    elif pid=="nippon_smallcap":
        if mc<=2000: s+=28; r.append(f"Small cap ₹{mc:.0f}Cr ✓")
        elif mc<=5000: s+=20; r.append(f"Small-mid cap ₹{mc:.0f}Cr")
        elif mc<=8000: s+=12
        if roe and p(roe)>=15: s+=22+vc(roe,"roe",True); r.append(f"Growth ROE {p(roe):.1f}%")
        elif roe and p(roe)>=12: s+=12
        if earn_g and p(earn_g)>=20: s+=25; r.append(f"High growth {p(earn_g):.1f}%")
        elif earn_g and p(earn_g)>=12: s+=15
        if pe and 0<pe<60: s+=15
        if opm and p(opm)>=10: s+=10
    elif pid=="mirae_asset":
        if roe and p(roe)>=15: s+=25+vc(roe,"roe",True); r.append(f"Quality ROE {p(roe):.1f}%")
        if roce and p(roce)>=15: s+=22+vc(roce,"roce",True); r.append(f"Strong ROCE {p(roce):.1f}%")
        if opm and p(opm)>=15: s+=20+vc(opm,"opm",True); r.append(f"Sector leader margins {p(opm):.1f}%")
        if pe and 0<pe<45: s+=15; r.append(f"Reasonable P/E {pe:.1f}x")
        if mc>=5000: s+=10
    elif pid=="hdfc_mf":
        if pe and 0<pe<15: s+=28; r.append(f"Deep value P/E {pe:.1f}x — HDFC MF style ✓")
        elif pe and pe<20: s+=20; r.append(f"Value P/E {pe:.1f}x")
        if roe and p(roe)>=12: s+=22+vc(roe,"roe",True); r.append(f"Quality ROE {p(roe):.1f}%")
        if dy and p(dy)>=2: s+=18; r.append(f"Dividend support {p(dy):.1f}%")
        if de is not None and de<0.7: s+=15
        if pct_off>=20: s+=17; r.append(f"Contrarian opportunity {pct_off:.0f}% off highs")
    elif pid=="enam":
        if debt_free: s+=32; r.append("Debt-free — Enam non-negotiable ✓")
        elif de and de<0.1: s+=20
        if ph and ph>=0.50: s+=25; r.append(f"Management alignment {p(ph):.1f}%")
        elif ph and ph>=0.35: s+=15
        if roe and p(roe)>=18: s+=22+vc(roe,"roe",True)
        if opm and p(opm)>=15: s+=15+vc(opm,"opm",True)
        if pledge==0: s+=10; r.append("Zero pledge — integrity signal ✓")
    elif pid=="nemish_shah":
        if debt_free or (de and de<0.2): s+=28; r.append("Debt-free consumer/pharma quality ✓")
        if opm and p(opm)>=18: s+=25+vc(opm,"opm",True); r.append(f"Pricing power OPM {p(opm):.1f}%")
        elif opm and p(opm)>=12: s+=15
        if roe and p(roe)>=18: s+=22+vc(roe,"roe",True)
        if ph and ph>=0.40: s+=15
        if dy and p(dy)>=1.5: s+=10; r.append(f"Dividend {p(dy):.1f}%")
    elif pid=="white_oak":
        if roe and p(roe)>=20: s+=28+vc(roe,"roe",True); r.append(f"Quality ROE {p(roe):.1f}%")
        elif roe and p(roe)>=15: s+=18
        if de is not None and de<0.5: s+=22; r.append("ROE without excessive leverage ✓")
        if opm and p(opm)>=18: s+=22+vc(opm,"opm",True)
        if pe and 0<pe<40: s+=18
        if mc>=5000: s+=10
    elif pid=="carnelian":
        if mc<=20000 and mc>=500: s+=18; r.append(f"Emerging compounder ₹{mc:.0f}Cr")
        if roe and p(roe)>=18: s+=22+vc(roe,"roe",True); r.append(f"High ROE {p(roe):.1f}%")
        if earn_g and p(earn_g)>=20: s+=22; r.append(f"Fast growing {p(earn_g):.1f}%")
        elif earn_g and p(earn_g)>=12: s+=12
        if opm and p(opm)>=12: s+=18+vc(opm,"opm",True)
        if pe and 0<pe<55: s+=12
    elif pid=="anand_rathi":
        if mc>=10000: s+=20; r.append(f"Large cap stability ₹{mc:.0f}Cr ✓")
        if dy and p(dy)>=3: s+=30; r.append(f"Strong dividend {p(dy):.1f}%")
        elif dy and p(dy)>=2: s+=20; r.append(f"Good dividend {p(dy):.1f}%")
        elif dy and p(dy)>=1: s+=10
        if de is not None and de<0.5: s+=22; r.append("Capital preservation balance sheet ✓")
        if roe and p(roe)>=12: s+=18
        if pe and 0<pe<25: s+=10
    elif pid=="ask_investment":
        if mc>=15000: s+=18; r.append(f"Institutional quality ₹{mc:.0f}Cr ✓")
        if roe and p(roe)>=18: s+=25+vc(roe,"roe",True); r.append(f"Quality ROE {p(roe):.1f}%")
        elif roe and p(roe)>=12: s+=15
        if de is not None and de<0.4: s+=22; r.append("Conservative balance sheet ✓")
        if dy and p(dy)>=1.5: s+=15
        if opm and p(opm)>=15: s+=15
        if pledge_ok: s+=10
    elif pid=="murugappa":
        if de is not None and de<0.5: s+=28; r.append("Conservative balance sheet ✓")
        if dy and p(dy)>=2: s+=22; r.append(f"Dividend history {p(dy):.1f}%")
        elif dy and p(dy)>=1: s+=12
        if opm and p(opm)>=12: s+=22+vc(opm,"opm",True); r.append(f"Manufacturing margins {p(opm):.1f}%")
        if roe and p(roe)>=12: s+=18+vc(roe,"roe",True)
        if mc>=1000: s+=10
    else:
        if roe and p(roe)>=18: s+=30
        if de is not None and de<0.5: s+=20
        if opm and p(opm)>=15: s+=25
        if pe and 0<pe<35: s+=25

    return {"score":min(s,100),"reasons":r[:3]}


# ═══════════════════════════════════════════════════════════════════════════════
# ASSET ALLOCATION — Profile-specific, PE-adjusted
# ═══════════════════════════════════════════════════════════════════════════════
PROFILE_ALLOCATION = {
    "rj":{"base":{"equity":92,"gold":0,"debt":3,"cash":5},"pe_sensitive":False,
          "logic":"RJ stayed fully invested through all cycles. Maximum equity — he never tried to time the market.","instruments":{"gold":"N/A","debt":"Liquid Fund","cash":"SIP reserve — buy dips"}},
    "vijay_kedia":{"base":{"equity":95,"gold":0,"debt":0,"cash":5},"pe_sensitive":False,
          "logic":"Kedia stays almost fully invested. 5% cash is just for opportunistic additions when conviction stocks dip.","instruments":{"gold":"N/A","debt":"N/A","cash":"Reserve for adding to existing positions"}},
    "porinju":{"base":{"equity":90,"gold":0,"debt":5,"cash":5},"pe_sensitive":False,
          "logic":"Porinju stays fully invested in smallcaps — he times the business, not the market.","instruments":{"gold":"N/A","debt":"Liquid Fund","cash":"Opportunity fund for beaten-down situations"}},
    "ashish_kacholia":{"base":{"equity":88,"gold":0,"debt":5,"cash":7},"pe_sensitive":False,
          "logic":"Kacholia stays largely invested. Small cash reserve for new opportunities as they emerge.","instruments":{"gold":"N/A","debt":"Liquid Fund","cash":"New opportunity reserve"}},
    "dolly_khanna":{"base":{"equity":85,"gold":0,"debt":5,"cash":10},"pe_sensitive":False,
          "logic":"Dolly keeps 10% cash to deploy into beaten-down cyclicals when sectors bottom out.","instruments":{"gold":"N/A","debt":"Liquid Fund","cash":"Cyclical opportunity fund"}},
    "chandrakant_sampat":{"base":{"equity":75,"gold":5,"debt":15,"cash":5},"pe_sensitive":True,
          "logic":"Sampat preferred conservative allocation. Debt for safety, gold as wealth preservation, equity only in truly exceptional debt-free businesses.","instruments":{"gold":"Sovereign Gold Bond","debt":"Government Securities","cash":"Emergency reserve"}},
    "radhakishan_damani":{"base":{"equity":85,"gold":0,"debt":10,"cash":5},"pe_sensitive":False,
          "logic":"RKD concentrated in his best ideas. Very focused portfolio with long holds.","instruments":{"gold":"N/A","debt":"Short Duration Debt","cash":"Opportunistic reserve"}},
    "raamdeo_agrawal":{"base":{"equity":85,"gold":5,"debt":5,"cash":5},"pe_sensitive":True,
          "logic":"QGLP framework targets high-quality high-growth stocks — stays invested. Small gold allocation for portfolio balance.","instruments":{"gold":"Sovereign Gold Bond","debt":"Liquid Fund","cash":"QGLP opportunity fund"}},
    "sanjay_bakshi":{"base":{"equity":80,"gold":0,"debt":10,"cash":10},"pe_sensitive":True,
          "logic":"Bakshi keeps 10% cash specifically for behavioral mispricing opportunities — great businesses temporarily beaten down.","instruments":{"gold":"N/A","debt":"Short Duration Debt","cash":"Behavioral opportunity fund — deploy only at >20% discount to intrinsic value"}},
    "kenneth_andrade":{"base":{"equity":82,"gold":0,"debt":8,"cash":10},"pe_sensitive":True,
          "logic":"Kenneth keeps cash to rotate into sectors at cyclical lows — a core part of his contrarian approach.","instruments":{"gold":"N/A","debt":"Liquid Fund","cash":"Sector rotation fund"}},
    "manish_kejriwal":{"base":{"equity":85,"gold":0,"debt":10,"cash":5},"pe_sensitive":True,
          "logic":"PE-style investing requires patience. Small cash reserve for the exceptional opportunity that meets all criteria.","instruments":{"gold":"N/A","debt":"Short Duration Debt","cash":"High-conviction opportunity reserve"}},
    "buffett":{"base":{"equity":70,"gold":5,"debt":10,"cash":15},"pe_sensitive":True,
          "logic":"Buffett is famous for holding cash. 'Cash is like oxygen — you don't notice it when you have it, but when you don't, it's the only thing you notice.' Berkshire holds 20%+ cash waiting for the fat pitch.","instruments":{"gold":"Sovereign Gold Bond","debt":"Short Duration Debt Fund","cash":"Buffett's dry powder — deploy only for genuine bargains at 25%+ margin of safety"}},
    "ben_graham":{"base":{"equity":50,"gold":0,"debt":40,"cash":10},"pe_sensitive":True,
          "logic":"Graham's timeless rule: never less than 25% or more than 75% in stocks. Move between these bounds based on market valuation. At Nifty PE >25, equity should be at the lower bound.","instruments":{"gold":"N/A","debt":"Medium Duration Bond Fund","cash":"Margin of safety reserve — deploy when P/B drops below 1.5x"}},
    "peter_lynch":{"base":{"equity":85,"gold":0,"debt":5,"cash":10},"pe_sensitive":True,
          "logic":"Lynch was fully invested as a fund manager. For personal portfolios, keep 85% invested and 10% cash for PEG <0.5 opportunities.","instruments":{"gold":"N/A","debt":"Liquid Fund","cash":"PEG opportunity fund — deploy when you find PEG <0.5"}},
    "charlie_munger":{"base":{"equity":82,"gold":0,"debt":3,"cash":15},"pe_sensitive":True,
          "logic":"Munger concentrated in 5 exceptional businesses. Kept 15% cash for the rare extraordinary opportunity. 'Opportunity cost is the only real cost.'","instruments":{"gold":"N/A","debt":"T-Bills equivalent","cash":"Waiting for the exceptional — Munger deployed only at very high conviction"}},
    "phil_fisher":{"base":{"equity":88,"gold":0,"debt":5,"cash":7},"pe_sensitive":True,
          "logic":"Fisher stayed heavily invested in outstanding companies. Small cash reserve for adding to existing positions during dips.","instruments":{"gold":"N/A","debt":"Liquid Fund","cash":"Reserve for adding to best holdings on market weakness"}},
    "parag_parikh":{"base":{"equity":65,"gold":10,"debt":15,"cash":10},"pe_sensitive":True,
          "logic":"PPFAS actively manages allocation. Fund holds ~20% cash+debt when markets are expensive. Gold is essential insurance against currency debasement. Deployed aggressively in March 2020 crash.","instruments":{"gold":"Sovereign Gold Bond (SGB) — 2.5% tax-free interest + gold upside","debt":"Liquid Fund or Short Duration","cash":"Deployed aggressively when Nifty PE drops below 16x"}},
    "marcellus":{"base":{"equity":95,"gold":0,"debt":0,"cash":5},"pe_sensitive":False,
          "logic":"Marcellus is always fully invested. Mukherjea believes their 12-15 stocks outperform any cash position at any market valuation. No market timing ever.","instruments":{"gold":"N/A","debt":"N/A","cash":"Transaction reserve only"}},
    "motilal_qglp":{"base":{"equity":85,"gold":5,"debt":5,"cash":5},"pe_sensitive":True,
          "logic":"QGLP stays invested — great growth businesses outperform even at stretched valuations. Small allocation to gold and debt for balance.","instruments":{"gold":"Sovereign Gold Bond","debt":"Liquid Fund","cash":"QGLP addition fund"}},
    "nippon_smallcap":{"base":{"equity":90,"gold":0,"debt":5,"cash":5},"pe_sensitive":False,
          "logic":"Smallcap fund — stays fully invested as timing is impossible in this segment. Diversification is the risk management tool.","instruments":{"gold":"N/A","debt":"Liquid Fund","cash":"New opportunity reserve"}},
    "mirae_asset":{"base":{"equity":80,"gold":5,"debt":10,"cash":5},"pe_sensitive":True,
          "logic":"Quality-focused fund with benchmark awareness. Slightly conservative allocation with gold for stability.","instruments":{"gold":"Sovereign Gold Bond","debt":"Short Duration Debt","cash":"Rebalancing reserve"}},
    "hdfc_mf":{"base":{"equity":70,"gold":5,"debt":15,"cash":10},"pe_sensitive":True,
          "logic":"Prashant Jain kept 10-15% cash to deploy into contrarian opportunities. 'Being 3 years early is the same as being wrong — but you need cash to stay in the game.'","instruments":{"gold":"Sovereign Gold Bond","debt":"Medium Duration Bond Fund","cash":"Contrarian opportunity fund — deploy into beaten-down quality sectors"}},
    "enam":{"base":{"equity":80,"gold":5,"debt":10,"cash":5},"pe_sensitive":True,
          "logic":"Enam's long-term approach keeps most capital in proven businesses. Small gold allocation for wealth preservation.","instruments":{"gold":"Sovereign Gold Bond","debt":"Government Securities","cash":"Reserve for integrity-positive opportunities"}},
    "nemish_shah":{"base":{"equity":80,"gold":5,"debt":12,"cash":3},"pe_sensitive":True,
          "logic":"Consumer/pharma focus provides natural defensiveness. Conservative allocation with strong dividend income component.","instruments":{"gold":"Sovereign Gold Bond","debt":"Medium Duration Bond Fund","cash":"Dividend reinvestment fund"}},
    "white_oak":{"base":{"equity":78,"gold":5,"debt":12,"cash":5},"pe_sensitive":True,
          "logic":"Goldman Sachs-style discipline. Balanced allocation with emphasis on earnings quality stocks.","instruments":{"gold":"Sovereign Gold Bond","debt":"Short Duration Debt","cash":"Quality opportunity fund"}},
    "carnelian":{"base":{"equity":85,"gold":0,"debt":5,"cash":10},"pe_sensitive":True,
          "logic":"Structural sector focus requires staying invested through cycles. Cash for new structural themes as they emerge.","instruments":{"gold":"N/A","debt":"Liquid Fund","cash":"Structural theme opportunity fund"}},
    "anand_rathi":{"base":{"equity":55,"gold":10,"debt":25,"cash":10},"pe_sensitive":True,
          "logic":"HNI wealth management — capital preservation first. Heavy debt allocation for income. Gold for inflation protection. Conservative equity bias.","instruments":{"gold":"Sovereign Gold Bond (SGB) + Gold ETF","debt":"AAA-rated bond funds + FD","cash":"Liquid fund for tactical opportunities"}},
    "ask_investment":{"base":{"equity":65,"gold":8,"debt":20,"cash":7},"pe_sensitive":True,
          "logic":"PMS approach for HNIs — conservative allocation, quality large caps, regular income from dividends. Wealth preservation as primary objective.","instruments":{"gold":"Sovereign Gold Bond","debt":"Medium Duration Bond Fund + AAA FDs","cash":"Liquid Fund"}},
    "murugappa":{"base":{"equity":60,"gold":8,"debt":22,"cash":10},"pe_sensitive":True,
          "logic":"Multi-generational approach — moderate equity, strong debt for income, gold for family wealth preservation. Think in decades, not years.","instruments":{"gold":"Physical Gold + Sovereign Gold Bond","debt":"Government Securities + Corporate Bonds","cash":"Fixed Deposit for emergency + opportunity"}},
    "default":{"base":{"equity":70,"gold":8,"debt":12,"cash":10},"pe_sensitive":True,
          "logic":"Balanced allocation adjusted for current market valuation.","instruments":{"gold":"Sovereign Gold Bond","debt":"Short Duration Debt Fund","cash":"Opportunity reserve"}},
}

def compute_allocation(pid: str, capital: float, npe: float) -> dict:
    cfg=PROFILE_ALLOCATION.get(pid,PROFILE_ALLOCATION["default"])
    base=dict(cfg["base"]); mv=get_market_valuation(npe)
    if cfg["pe_sensitive"]:
        mod=mv["equity_modifier"]; old_eq=base["equity"]; new_eq=round(old_eq*mod)
        new_eq=max(min(new_eq,95),25); diff=old_eq-new_eq; base["equity"]=new_eq
        base["cash"]=base.get("cash",0)+diff
    total=sum(base.values())
    pct={k:round(v/total*100,1) for k,v in base.items()}
    amt={k:round(v/100*capital) for k,v in pct.items()}
    return {
        "allocation_pct":pct,"allocation_amt":amt,"equity_capital":amt["equity"],
        "nifty_pe":npe,"market_valuation":mv,"logic":cfg["logic"],
        "instruments":cfg["instruments"],
        "rebalance_triggers":[
            "If Nifty PE drops below 16x — shift 10% from cash/debt to equity",
            "If Nifty PE rises above 28x — reduce equity by 15%, park in debt",
            "Rebalance annually or when any asset class drifts >5% from target",
        ],
    }

def get_matching_profiles(stock: dict, avgs: dict) -> list:
    results=[]
    for pid in INVESTOR_PROFILES:
        ps=score_profile(stock,pid,avgs)
        p=INVESTOR_PROFILES[pid]
        results.append({"id":pid,"name":p["name"],"avatar":p["avatar"],"color":p["color"],"score":ps["score"],"reasons":ps["reasons"]})
    results.sort(key=lambda x:x["score"],reverse=True)
    return results[:3]

def get_portfolio_allocation(pid: str, stocks: list, equity_capital: float) -> dict:
    profile=INVESTOR_PROFILES.get(pid,{}); style=profile.get("sizing_style","equal_weight"); n=len(stocks)
    if n==0: return {"positions":[]}
    if style=="very_concentrated":
        raw=[0.30,0.22,0.16,0.10,0.08]+[0.04]*(n-5)
    elif style=="conviction_weighted":
        scores=[s.get("profile_score",50) for s in stocks]; total=sum(scores) or n
        raw=[sc/total for sc in scores]
    elif style=="market_cap_weighted":
        mcs=[max((s.get("market_cap") or 1e10),1) for s in stocks]; total=sum(mcs)
        raw=[mc/total for mc in mcs]
    else:
        raw=[1/n]*n
    tw=sum(raw[:n]); weights=[w/tw for w in raw[:n]]
    positions=[]
    for i,(stock,w) in enumerate(zip(stocks,weights)):
        price=stock.get("current_price") or 0; amt=equity_capital*w
        shares=int(amt/price) if price>0 else 0; actual=shares*price if price>0 else amt
        positions.append({
            "rank":i+1,"symbol":stock["symbol"],"company_name":stock["company_name"],
            "sector":stock.get("sector","Unknown"),"current_price":price,
            "weight_pct":round(w*100,1),"amount":round(actual),"shares":shares,
            "profile_score":stock.get("profile_score",0),"conviction":stock.get("conviction","Watch"),
            "profile_reasons":stock.get("profile_reasons",[]),"why_included":"","full_analysis":"",
            "qualifying_metrics":[],"one_liner":"",
        })
    se={}
    for pos in positions:
        sec=pos["sector"]
        if sec!="Unknown": se[sec]=round(se.get(sec,0)+pos["weight_pct"],1)
    return {
        "positions":positions,"total_stocks":n,"total_capital":equity_capital,
        "total_deployed":round(sum(p["amount"] for p in positions)),
        "sector_exposure":se,
        "portfolio_rationale":f"Portfolio built using {profile.get('name','')}'s '{profile.get('focus','')}' philosophy. {profile.get('philosophy','')[:200]}",
        "entry_strategy":"Invest systematically over 3-6 months to average entry prices. Never invest the full amount in a single day.",
        "rebalance_note":"Review annually. Replace stocks where the investment thesis has fundamentally changed. Stay disciplined to the profile's core criteria.",
    }

def explain_stock(stock: dict, pid: str, avgs: dict) -> dict:
    name=stock.get("company_name",stock.get("symbol","")); sym=stock.get("symbol","")
    sec=stock.get("sector","Unknown")
    if sec in ("Unknown","",None): sec=sector_for(sym,"Unknown")
    sa=avgs.get(sec,{}); p_info=INVESTOR_PROFILES.get(pid,{})
    def fp(v): return f"{v*100:.1f}%" if v is not None else "N/A"
    def fn(v,d=1): return f"{v:.{d}f}" if v is not None else "N/A"
    roe=stock.get("roe"); roce=stock.get("roce"); opm=stock.get("operating_margins")
    de=stock.get("debt_to_equity"); ph=stock.get("promoter_holding"); pe=stock.get("pe_ratio")
    mc=(stock.get("market_cap") or 0)/1e7; cr=stock.get("current_ratio")
    pb=stock.get("pb_ratio"); pct_off=((stock.get("52w_high",0)-(stock.get("current_price") or 0))/(stock.get("52w_high") or 1)*100) if stock.get("52w_high") else 0
    qm=[]
    if roe: qm.append({"metric":"ROE","value":fp(roe),"sector_avg":fp(sa.get("roe")) if sa.get("roe") else "N/A","status":"better" if sa.get("roe") and roe>sa["roe"]*1.05 else ("worse" if sa.get("roe") and roe<sa["roe"]*0.90 else "inline"),"learn_id":"roe","explanation":f"ROE of {fp(roe)} means {name} generates ₹{roe*100:.0f} of profit for every ₹100 of shareholder capital — {'above' if sa.get('roe') and roe>sa['roe'] else 'in line with'} the {sec} sector average of {fp(sa.get('roe'))}."})
    if roce: qm.append({"metric":"ROCE","value":fp(roce),"sector_avg":fp(sa.get("roce")) if sa.get("roce") else "N/A","status":"better" if sa.get("roce") and roce>sa["roce"]*1.05 else ("worse" if sa.get("roce") and roce<sa["roce"]*0.90 else "inline"),"learn_id":"roce","explanation":f"ROCE of {fp(roce)} reflects capital deployment quality across the entire business — sector average is {fp(sa.get('roce'))}."})
    if opm: qm.append({"metric":"OPM","value":fp(opm),"sector_avg":fp(sa.get("opm")) if sa.get("opm") else "N/A","status":"better" if sa.get("opm") and opm>sa["opm"]*1.05 else ("worse" if sa.get("opm") and opm<sa["opm"]*0.90 else "inline"),"learn_id":"operating-margins","explanation":f"Operating margin of {fp(opm)} means {name} retains {fp(opm)} of every rupee of revenue — sector average is {fp(sa.get('opm'))}."})
    if de is not None: qm.append({"metric":"D/E","value":f"{de:.2f}x","sector_avg":f"{sa['de']:.2f}x" if sa.get("de") else "N/A","status":"better" if de<0.3 else ("inline" if de<0.7 else "worse"),"learn_id":"debt-equity","explanation":f"D/E of {de:.2f}x indicates {'near debt-free balance sheet' if de<0.2 else 'moderate leverage' if de<0.8 else 'significant leverage'}. Sector avg: {fn(sa.get('de'),2)+'x' if sa.get('de') else 'N/A'}."})
    if pe: qm.append({"metric":"P/E","value":f"{pe:.1f}x","sector_avg":f"{sa['pe']:.1f}x" if sa.get("pe") else "N/A","status":"better" if sa.get("pe") and pe<sa["pe"]*0.9 else ("worse" if sa.get("pe") and pe>sa["pe"]*1.1 else "inline"),"learn_id":"pe-ratio","explanation":f"P/E of {pe:.1f}x vs sector average of {fn(sa.get('pe'),1)+'x' if sa.get('pe') else 'N/A'} — {'cheap relative to sector' if sa.get('pe') and pe<sa['pe']*0.85 else 'at a premium to sector' if sa.get('pe') and pe>sa['pe']*1.15 else 'in line with sector'}."})
    if ph: qm.append({"metric":"Promoter","value":fp(ph),"sector_avg":"N/A","status":"better" if ph>=0.50 else ("inline" if ph>=0.35 else "worse"),"learn_id":"promoter-holding","explanation":f"Promoter holding of {fp(ph)} means founders hold {'a majority stake — strong alignment' if ph>=0.51 else 'a significant stake'} with minority shareholders."})
    analyses={
        "rj":f"{name} evaluated against RJ's exact criteria: Market cap {fn(mc,0)}Cr {'✓ ≥₹5,000 Cr' if mc>=5000 else '✗ below RJ minimum'}, ROCE {fp(roce)} {'✓ ≥15%' if roce and roce*100>=15 else '✗'}, ROE {fp(roe)} {'✓ ≥15%' if roe and roe*100>=15 else '✗'}, D/E {fn(de,2)+'x' if de else 'N/A'} {'✓ <0.5' if de and de<0.5 else '✗'}, OPM {fp(opm)} {'✓ ≥15%' if opm and opm*100>=15 else '✗'}, Promoter {fp(ph)} {'✓ >50%' if ph and ph>=0.50 else '✗'}. RJ held Titan for 20+ years and Crisil for 15 years — the same patience would apply here if fundamentals hold.",
        "buffett":f"{name} evaluated against Buffett's exact criteria: ROE {fp(roe)} {'✓ ≥20%' if roe and roe*100>=20 else '✗ below 20% threshold'}, D/E {fn(de,2)+'x' if de else 'N/A'} {'✓ <0.5' if de and de<0.5 else '✗'}, OPM {fp(opm)} {'✓ ≥15% pricing power' if opm and opm*100>=15 else '✗'}, P/E {fn(pe,1)+'x' if pe else 'N/A'} {'✓ <35x' if pe and pe<35 else '✗'}. Buffett would ask: 'Can I understand this business in 5 minutes? Does it have a durable moat? Would I own it for 10 years if markets closed?'",
        "marcellus":f"{name} evaluated against Marcellus's forensic criteria: ROCE {fp(roce)} {'✓ above 15% minimum' if roce and roce*100>=15 else '✗'} (CCP typically seeks >25%), D/E {fn(de,2)+'x' if de else 'N/A'} {'✓ near-zero debt' if de and de<0.2 else '⚠ has leverage Marcellus would question'}, Promoter pledge {'✓ clean' if stock.get('promoter_pledge',0)==0 else '⚠ pledge exists'}. Marcellus holds 12-15 stocks max and rebalances annually in April.",
        "ben_graham":f"{name} against Graham's exact screens: P/B {fn(pb,2)+'x' if pb else 'N/A'} {'✓ <1.5x' if pb and pb<1.5 else '✗ above 1.5x limit'}, P/E {fn(pe,1)+'x' if pe else 'N/A'} {'✓ <15x deep value' if pe and pe<15 else '✗ above 15x threshold'}, Current ratio {fn(cr,1)+'x' if cr else 'N/A'} {'✓ ≥2x' if cr and cr>=2 else '✗'}. Graham demanded buying significantly below intrinsic value — the margin of safety is the cornerstone of his entire philosophy.",
        "vijay_kedia":f"Vijay Kedia's SMILE framework for {name}: S (Small) — {fn(mc,0)}Cr market cap {'✓ small enough for SMILE' if mc<=5000 else '✗ larger than Kedia targets'}, M (Medium experience) — proxied by management track record, L (Large aspiration) — {'shown through expansion trajectory' if opm else 'unclear'}, E (Extra-large TAM) — {sec} sector potential. Kedia does NOT rely on complex ratios — he bets on the jockey (management), not the horse. Promoter holding {fp(ph)} {'reflects strong conviction' if ph and ph>=0.50 else 'is moderate'}.",
        "charlie_munger":f"{name} against Munger's non-negotiable criteria: ROCE {fp(roce)} {'✓ ≥25% Munger threshold' if roce and roce*100>=25 else '✗ below 25%'}, OPM {fp(opm)} {'✓ ≥25% pricing power' if opm and opm*100>=25 else '✗ below 25%'}, Debt status {'✓ near debt-free' if de and de<0.2 else '✗ has leverage Munger dislikes'}. Munger concentrated in just 5 businesses. He would only include this if ROCE and pricing power both clearly pass.",
    }
    para=analyses.get(pid,f"{name} selected based on {p_info.get('name','this profile')}'s investment criteria. ROE {fp(roe)}, ROCE {fp(roce)}, OPM {fp(opm)}, D/E {fn(de,2)+'x' if de else 'N/A'}, Promoter {fp(ph)}. {'Strong qualifier' if len([m for m in qm if m.get('status')=='better'])>=2 else 'Partial qualifier'} for this profile.")
    ps=score_profile(stock,pid,avgs)
    return {"full_analysis":para,"qualifying_metrics":qm[:6],"one_liner":", ".join(ps["reasons"][:2]) if ps["reasons"] else fp(roe)+" ROE"}

def why_not_list(pid: str, near_misses: list, avgs: dict) -> list:
    results=[]
    for stock in near_misses[:4]:
        name=stock.get("company_name",stock.get("symbol","")); sym=stock.get("symbol","")
        ps=score_profile(stock,pid,avgs)
        def p(v): return v*100 if v is not None else None
        roe=stock.get("roe"); de=stock.get("debt_to_equity"); pe=stock.get("pe_ratio")
        roce=stock.get("roce"); opm=stock.get("operating_margins"); ph=stock.get("promoter_holding")
        mc=(stock.get("market_cap") or 0)/1e7; pb=stock.get("pb_ratio"); cr=stock.get("current_ratio")
        reasons=[]
        if pid in ("rj","buffett","manish_kejriwal","white_oak","raamdeo_agrawal","motilal_qglp"):
            if roe and p(roe)<20: reasons.append(f"ROE of {p(roe):.1f}% below the 20% quality threshold this profile demands")
            if de and de>0.5: reasons.append(f"D/E of {de:.2f}x exceeds the conservative balance sheet requirement of this profile")
        if pid=="marcellus":
            if de and de>0.2: reasons.append(f"D/E of {de:.2f}x fails Marcellus's near-zero debt requirement")
            if roce and p(roce)<15: reasons.append(f"ROCE of {p(roce):.1f}% below the 15% consistency threshold Marcellus demands")
        if pid in ("chandrakant_sampat","enam"):
            if de and de>0.15: reasons.append(f"D/E of {de:.2f}x — debt-free is a non-negotiable criterion for this profile")
        if pid in ("vijay_kedia","porinju","ashish_kacholia","nippon_smallcap"):
            if mc>15000: reasons.append(f"Market cap of ₹{mc:.0f}Cr too large for this small-cap focused profile")
        if pid=="ben_graham":
            if pb and pb>2: reasons.append(f"P/B of {pb:.2f}x above Graham's strict 1.5x limit")
            if pe and pe>20: reasons.append(f"P/E of {pe:.1f}x above Graham's 15x threshold")
        if pid=="charlie_munger":
            if roce and p(roce)<25: reasons.append(f"ROCE of {p(roce):.1f}% below Munger's non-negotiable 25% threshold")
            if opm and p(opm)<25: reasons.append(f"OPM of {p(opm):.1f}% below Munger's 25% pricing power requirement")
        if not reasons: reasons.append(f"Composite profile score of {ps['score']}/100 did not clear the minimum threshold for inclusion")
        learn_id="roe" if any("ROE" in r for r in reasons) else "debt-equity" if any("D/E" in r or "debt" in r.lower() for r in reasons) else "pe-ratio"
        results.append({"symbol":sym,"company_name":name,"score":ps["score"],"reason":reasons[0],"learn_id":learn_id})
    return results

def score_consensus(stock: dict, avgs: dict) -> dict:
    scores=[]
    for pid in INVESTOR_PROFILES:
        ps=score_profile(stock,pid,avgs)
        scores.append({"profile_id":pid,"profile_name":INVESTOR_PROFILES[pid]["name"],"score":ps["score"],"reasons":ps["reasons"]})
    scores.sort(key=lambda x:x["score"],reverse=True)
    qualifying=[s for s in scores if s["score"]>=40]; strong=[s for s in scores if s["score"]>=60]
    avg=sum(s["score"] for s in scores)/len(scores) if scores else 0
    breadth=len(qualifying)*2.5; consensus=min(round(avg*0.55+breadth*0.45),100)
    tier="All-Legend" if len(strong)>=8 else ("Strong Consensus" if len(qualifying)>=5 else ("Emerging Consensus" if len(qualifying)>=3 else None))
    return {"consensus_score":consensus,"qualifying_profiles":len(qualifying),"strong_profiles":len(strong),"tier":tier,"top_profiles":scores[:4],"avg_score":round(avg,1)}

def build_entry(symbol, raw, avgs=None):
    if avgs is None: avgs={}
    raw["sector"]=sector_for(symbol,raw.get("sector","Unknown"))
    scoring=score_stock(raw,avgs); sc=get_sector_comp(raw,avgs); mp=get_matching_profiles(raw,avgs)
    return {
        "symbol":symbol,
        **{k:raw.get(k) for k in ["company_name","sector","industry","description","website","employees",
           "current_price","price_change_pct","market_cap","52w_high","52w_low","avg_volume",
           "pe_ratio","pb_ratio","ev_ebitda","peg_ratio","book_value","roe","roa","roce",
           "debt_to_equity","operating_margins","net_margins","revenue_growth","earnings_growth",
           "current_ratio","quick_ratio","interest_coverage","dividend_yield","eps","beta","fcf",
           "revenue","ebitda","promoter_holding","promoter_pledge","institutional_holding",
           "analyst_recommendation","target_price","num_analysts",
           "quarterly_revenue","quarterly_profit","annual_revenue","annual_profit",
           "pros","cons","data_source"]},
        "scoring":scoring,"conviction":conviction(scoring["composite"]),
        "matching_profiles":mp,"sector_comparison":sc,"cached_at":datetime.now().isoformat(),
    }


EDUCATION = {
"metrics":[
{"id":"pe-ratio","title":"Price to Earnings (P/E) Ratio","category":"metrics","difficulty":"beginner","read_time":3,"summary":"How much you pay for every rupee of profit a company earns.","content":"P/E = Price / EPS. A P/E of 20x means you pay Rs20 for every Rs1 of annual profit. Lower is generally cheaper but context matters - always compare within the same sector.\n\nBenjamin Graham required P/E below 15x. Warren Buffett pays up to 30-35x for exceptional businesses. Raamdeo Agrawal uses PEG (P/E divided by growth rate) - targets below 1.5x.\n\nNifty 50 historical average: 20-22x. Below 15x = historically cheap. Above 28x = historically expensive.","example_stock":"NESTLEIND","watch_out":"Very low P/E can be a value trap. Always ask why it is cheap.","related":["pb-ratio","peg-ratio","ev-ebitda"]},
{"id":"roe","title":"Return on Equity (ROE)","category":"metrics","difficulty":"beginner","read_time":3,"summary":"How efficiently a company uses shareholder money to generate profit.","content":"ROE = Net Profit / Shareholders Equity x 100. A 20% ROE means the company generates Rs20 of profit for every Rs100 of shareholder capital annually.\n\nROE above 20% is excellent. Sustained high ROE over 10+ years is the hallmark of a genuine competitive moat.\n\nWarren Buffett requires ROE consistently above 20% WITHOUT using excessive debt. Marcellus requires 20%+ for 10 consecutive years. Rakesh Jhunjhunwala required 15%+.\n\nKey warning: High ROE through high debt is dangerous. Always check D/E ratio alongside ROE.","example_stock":"ASIANPAINT","watch_out":"ROE inflated by debt is misleading. ROCE is a better quality indicator as it accounts for all capital.","related":["roce","debt-equity"]},
{"id":"roce","title":"Return on Capital Employed (ROCE)","category":"metrics","difficulty":"intermediate","read_time":3,"summary":"The purest measure of how well a business uses ALL its capital.","content":"ROCE = EBIT / Capital Employed. Accounts for ALL capital - both equity and debt. The cleanest measure of business quality.\n\nROCE above 20% consistently = hallmark of truly great businesses. Marcellus entire strategy built around companies with ROCE above 15% (CCP targets 25-40%+) for 10 consecutive years.\n\nCharlie Munger: Show me a business with 25% ROCE sustained over 20 years and I will show you a real durable moat.\n\nFor financial companies (banks, NBFCs) use ROE instead.","example_stock":"PIDILITIND","watch_out":"Capital-intensive businesses will naturally have lower ROCE. Always compare ROCE within the same sector.","related":["roe","operating-margins"]},
{"id":"debt-equity","title":"Debt to Equity Ratio","category":"metrics","difficulty":"beginner","read_time":3,"summary":"How much debt a company has compared to shareholder funds.","content":"D/E of 0.5 = Rs50 debt for every Rs100 equity. D/E of 2.0 = Rs200 debt for every Rs100 equity.\n\nIndia biggest failures - IL&FS, DHFL, Reliance Communications, Jet Airways - all had extreme leverage.\n\nChandrakant Sampat made zero debt his single non-negotiable criterion. Marcellus requires near-zero debt. Buffett strongly prefers D/E below 0.5. Rakesh Jhunjhunwala required D/E below 0.5.","example_stock":"HINDUNILVR","watch_out":"Zero debt is not always optimal. The question is whether ROCE exceeds cost of borrowing.","related":["roe","interest-coverage","current-ratio"]},
{"id":"operating-margins","title":"Operating Profit Margin (OPM)","category":"metrics","difficulty":"beginner","read_time":3,"summary":"What percentage of revenue becomes operating profit - the pricing power signal.","content":"OPM = Operating Profit / Revenue x 100. A 20% OPM means Rs20 of every Rs100 revenue is operating profit after all operating costs but before interest and taxes.\n\nHigh and stable OPM = pricing power. Nestle, Asian Paints, Pidilite consistently maintain 20%+ OPM because of brand strength.\n\nWarren Buffett requires OPM above 15%. Rakesh Jhunjhunwala required OPM above 15%. Charlie Munger requires OPM above 25%.","example_stock":"BRITANNIA","watch_out":"Compare margins within sectors only. Never compare margins across industries.","related":["roe","roce","revenue-growth"]},
{"id":"pb-ratio","title":"Price to Book (P/B) Ratio","category":"metrics","difficulty":"intermediate","read_time":3,"summary":"What premium the market charges over the company net assets.","content":"Book value = what shareholders receive if company sold all assets and paid all debts today.\n\nP/B below 1 = market values company less than its net assets. Benjamin Graham looked for stocks below 1.5x book as his primary entry criterion.\n\nFor asset-heavy businesses (banks, manufacturing) P/B is very meaningful. For software companies, P/B is less relevant - their value is intellectual property, not balance sheet assets.","example_stock":"SBIN","watch_out":"Low P/B can mean assets are impaired. Always check asset quality before buying low P/B stocks.","related":["pe-ratio"]},
{"id":"peg-ratio","title":"PEG Ratio - Growth at Reasonable Price","category":"metrics","difficulty":"intermediate","read_time":3,"summary":"P/E ratio adjusted for growth - the tool Peter Lynch used to beat the market.","content":"PEG = P/E Ratio divided by Earnings Growth Rate.\n\nPEG below 1.0 = you are paying less than the growth rate justifies. PEG above 2.0 = paying a significant premium for expected growth.\n\nExample: P/E of 30x with earnings growing 35% = PEG of 0.86 - excellent value. P/E of 50x with 15% growth = PEG of 3.3 - very expensive.\n\nRaamdeo Agrawal QGLP framework targets PEG below 1.5x. Motilal Oswal screens specifically for low PEG stocks.","example_stock":"BAJFINANCE","watch_out":"PEG relies on future growth estimates which can be wrong. Use trailing earnings growth, not analyst projections.","related":["pe-ratio","earnings-growth"]},
{"id":"ev-ebitda","title":"EV/EBITDA - The Professional Valuation Metric","category":"metrics","difficulty":"advanced","read_time":4,"summary":"Enterprise value relative to operating earnings - capital-structure neutral valuation used by PE firms.","content":"EV = Market Cap + Total Debt - Cash. EBITDA = operating earnings before accounting adjustments.\n\nEV/EBITDA is capital-structure neutral - does not matter whether company is funded by debt or equity, making it ideal for comparing across companies.\n\nBelow 8x generally cheap, above 15x expensive. This is why M&A professionals and PE firms use it almost exclusively.","example_stock":"TATAMOTORS","watch_out":"EBITDA ignores capex requirements. For capital-intensive businesses use EV/FCF instead. Never use EV/EBITDA for banks.","related":["pe-ratio","free-cash-flow"]},
{"id":"dividend-yield","title":"Dividend Yield","category":"metrics","difficulty":"beginner","read_time":2,"summary":"Annual cash returned to shareholders as a percentage of stock price.","content":"Dividend Yield = Annual Dividend per Share / Stock Price x 100.\n\nA Rs200 stock paying Rs10 annual dividend = 5% yield.\n\nBest dividend stocks grow their dividend over time. A company growing dividends 10% annually doubles your income stream every 7 years.","example_stock":"COALINDIA","watch_out":"Very high yield (above 6-7%) often signals investors expect a dividend cut. Always check if payout is covered by free cash flow.","related":["free-cash-flow"]},
{"id":"promoter-holding","title":"Promoter Holding","category":"metrics","difficulty":"beginner","read_time":2,"summary":"How much of the company is owned by its founders - the skin-in-the-game indicator.","content":"High promoter holding (>50%) means founders personally lose money if the company fails.\n\nRakesh Jhunjhunwala required promoter holding above 50%. Vijay Kedia uses it as a key management quality indicator.\n\nPromoter pledge is equally important - if promoters pledged shares as collateral for loans, a stock price fall can trigger forced selling and create a death spiral.","example_stock":"TITAN","watch_out":"High promoter holding in a poorly governed company can mean minority shareholders have no protection.","related":["corporate-governance"]},
{"id":"current-ratio","title":"Current Ratio","category":"metrics","difficulty":"intermediate","read_time":2,"summary":"Can the company pay its bills over the next 12 months?","content":"Current Ratio = Current Assets / Current Liabilities.\n\nAbove 2.0 = company has Rs2 for every Rs1 of near-term obligations. Benjamin Graham required current ratio above 2.0.\n\nBelow 1.0 = cannot pay current bills from current assets - serious warning sign.","example_stock":"HDFCBANK","watch_out":"High current ratio is not always good - could mean excess inventory not selling or receivables not being collected.","related":["debt-equity","interest-coverage"]},
{"id":"interest-coverage","title":"Interest Coverage Ratio","category":"metrics","difficulty":"intermediate","read_time":2,"summary":"How easily can the company pay its interest obligations?","content":"Interest Coverage = EBIT / Interest Expense.\n\nBelow 1.5x = dangerous. Above 5x = excellent.\n\nDebt-free companies have infinite interest coverage - no risk of financial distress regardless of business cycles. This is why Chandrakant Sampat and Marcellus love zero-debt businesses.","example_stock":"HINDUNILVR","watch_out":"Interest coverage can deteriorate rapidly in cyclical downturns.","related":["debt-equity","current-ratio"]},
{"id":"free-cash-flow","title":"Free Cash Flow (FCF)","category":"metrics","difficulty":"intermediate","read_time":3,"summary":"The actual cash a business generates after maintaining and growing its asset base.","content":"FCF = Operating Cash Flow - Capital Expenditure.\n\nA company can show accounting profits while burning cash. FCF cuts through accounting and shows real cash generation.\n\nMarcellus CCP strategy specifically focuses on companies with consistent FCF generation. FCF yield (FCF / Market Cap) is an excellent valuation metric - 5%+ FCF yield is generally attractive.","example_stock":"PIDILITIND","watch_out":"Negative FCF is not always bad - fast-growing companies invest heavily in future growth. Context matters.","related":["roce","ev-ebitda"]},
{"id":"revenue-growth","title":"Revenue Growth","category":"metrics","difficulty":"beginner","read_time":2,"summary":"How fast the company is growing its sales year over year.","content":"Revenue growth above 15% = high growth. 10-15% = good. Below 5% = maturing or struggling.\n\nRevenue growth MUST be accompanied by profitable margins. A company growing revenue at 30% but losing money on every sale is destroying value.\n\nMarcellus requires 10% CAGR for 10 consecutive years. Raamdeo Agrawal requires 15-20% earnings growth.","example_stock":"TCS","watch_out":"Discounts and price cuts can temporarily inflate revenue growth while destroying profitability.","related":["earnings-growth","operating-margins"]},
{"id":"earnings-growth","title":"Earnings Growth","category":"metrics","difficulty":"beginner","read_time":2,"summary":"How fast profits are growing - the primary engine of stock price appreciation.","content":"Earnings growth is the primary driver of stock price appreciation. A company growing profits at 20% annually will roughly double its stock price every 4 years.\n\nPeter Lynch key insight: in the long run, stock price follows earnings. Find a company that grows earnings at 20% for 10 years - the stock will follow.\n\nEarnings above 20% = high growth. 12-20% = good. Below 8% = slow growth.","example_stock":"BAJFINANCE","watch_out":"One-time items can inflate or deflate earnings. Always check if growth is sustainable.","related":["revenue-growth","pe-ratio","peg-ratio"]}
],
"strategies":[
{"id":"value-investing","title":"Value Investing - Buy What Others Ignore","category":"strategies","difficulty":"beginner","read_time":5,"summary":"The art of buying good businesses at prices below what they are actually worth.","content":"Invented by Benjamin Graham and perfected by Warren Buffett. Core idea: stocks represent ownership in real businesses, and like any asset, businesses can be bought cheaply or expensively.\n\nThe market is not always rational. Fear causes prices to drop below intrinsic value. Greed causes prices to rise above it. Value investors profit from this irrationality.\n\nIn India, best value opportunities come during: market crashes (2008, 2020), sector downturns (IT in 2001, pharma in 2016-17), company-specific bad news that is temporary, PSU reforms.\n\nKey principles: Always buy with margin of safety. Think like a business owner not a trader. Be patient. Distinguish temporary problems from permanent decline.","related":["pe-ratio","pb-ratio"]},
{"id":"quality-investing","title":"Quality Investing - Great Businesses at Fair Prices","category":"strategies","difficulty":"intermediate","read_time":5,"summary":"Finding businesses with durable competitive advantages and holding them for decades.","content":"Quality investing evolved from value investing. While Graham looked for cheap businesses, Buffett (influenced by Charlie Munger) evolved to paying fair prices for genuinely great businesses.\n\nThe insight: a great business at a fair price is better than a mediocre business at a cheap price. Over 10+ years, business quality dominates everything else.\n\nWhat makes a quality business in India: Consistent high ROCE (above 20%) for 10+ years. Pricing power. Low debt. Strong management with integrity. Large addressable market.\n\nMarcellus Consistent Compounders Portfolio is built entirely on quality principles - their universe of stocks passing all filters is fewer than 25 companies in all of India.","related":["roce","moat"]},
{"id":"growth-investing","title":"Growth Investing - Riding the Earnings Tide","category":"strategies","difficulty":"intermediate","read_time":4,"summary":"Investing in companies growing faster than the market and holding through the growth phase.","content":"Growth investors focus on businesses growing revenue and earnings significantly faster than the market.\n\nPeter Lynch key insight: find a company that grows earnings at 20% for 10 years and it will be a 6x return regardless of price - as long as you do not massively overpay.\n\nIndia biggest growth stories: Bajaj Finance (200x in 10 years), HDFC Bank (100x in 20 years), Asian Paints (50x in 15 years).\n\nThe risk: growth can disappoint. A company priced for 30% growth at 60x PE that delivers only 15% growth will see the stock fall 40-60%.","related":["peg-ratio","earnings-growth"]},
{"id":"moat","title":"Competitive Moats - What Protects a Business","category":"strategies","difficulty":"intermediate","read_time":5,"summary":"Why some businesses earn high returns indefinitely while others cannot.","content":"Warren Buffett popularized the economic moat concept.\n\n5 types of moats:\n1. Brand moat: Fevicol (Pidilite) - no contractor risks using cheaper alternative.\n2. Switching costs: Tally accounting software - years of data make migration prohibitively expensive.\n3. Network effects: NSE - more traders attract more liquidity.\n4. Cost advantage: DMart - EDLP model, owned stores, no frills.\n5. Regulatory moat: CAMS - processes 70% of mutual fund transactions.\n\nBusinesses with strong moats sustain high ROCEs for decades.","related":["quality-investing","roce"]},
{"id":"contrarian-investing","title":"Contrarian Investing - Opportunity in Hatred","category":"strategies","difficulty":"intermediate","read_time":4,"summary":"Finding great opportunities in sectors and stocks that everyone else is avoiding.","content":"Buy what is universally hated, sell what is universally loved.\n\nPrashant Jain (HDFC MF) built his career on contrarian calls: bought PSU banks in 2012-13 when everyone hated them, bought infrastructure in 2014 when out of favour.\n\nDolly Khanna specialises in buying cyclical businesses at the absolute bottom of their cycle.\n\nChallenge: being too early is the same as being wrong. Requires deep conviction and ability to hold for 3-5 years while being publicly wrong.","related":["value-investing"]},
{"id":"smallcap-investing","title":"Smallcap Investing - Where the Real Multibaggers Are","category":"strategies","difficulty":"advanced","read_time":5,"summary":"Why small cap stocks deliver the highest returns - and the risks that come with it.","content":"Small caps (market cap below Rs5,000 Cr) deliver the highest long-term returns because institutional investors cannot buy them in meaningful size. This institutional exclusion creates systematic mispricing.\n\nVijay Kedia bought Atul Auto at Rs5 when it was a Rs50 crore company. Porinju Veliyath built his fortune finding beaten-down quality small caps.\n\nThe risks: Low liquidity. Less information. Higher volatility (50-60% drawdowns normal). Higher failure rate.\n\nRule: only invest in small caps with strong promoters, clean accounting, and a clear business model you can understand yourself.","related":["vijay-kedia-smile"]},
{"id":"dividend-investing","title":"Dividend Investing - Getting Paid to Wait","category":"strategies","difficulty":"beginner","read_time":3,"summary":"Building wealth through companies that share profits consistently with shareholders.","content":"Focus on companies that regularly pay a portion of profits to shareholders as cash.\n\nIn India, consistent dividend payers include Coal India, ITC, Infosys, Power Grid, NTPC.\n\nThe magic of dividend growth: if a company yields 3% today and grows dividends at 10% annually, after 10 years your yield on original cost is 7.8%. After 20 years, 20%.","related":["dividend-yield","free-cash-flow"]}
],
"beginners":[
{"id":"what-is-a-stock","title":"What is a Stock?","category":"beginners","difficulty":"beginner","read_time":3,"summary":"Owning a stock means owning a small piece of a real business.","content":"When you buy one share of Reliance Industries, you become a part-owner of one of India largest businesses. A stock is not just a price on a screen - it represents real ownership in a real business with real assets, employees, customers, and profits.\n\nCompanies issue shares to raise money from the public. Shareholders own a proportional part of the business and share in profits through dividends and benefit from business growth through rising share prices.\n\nNSE and BSE are marketplaces where shares are bought and sold every trading day, 9:15 AM to 3:30 PM IST.","related":["market-cap","nifty-sensex-explained"]},
{"id":"market-cap","title":"What is Market Capitalisation?","category":"beginners","difficulty":"beginner","read_time":2,"summary":"The total value the market places on a company at any given time.","content":"Market capitalisation = Share Price x Total Number of Shares.\n\nIn India, companies are classified by market cap:\nLarge Cap: Top 100 companies (above Rs20,000 Cr) - stable, well-followed\nMid Cap: Companies ranked 101-250 (Rs5,000-20,000 Cr) - good growth with moderate risk\nSmall Cap: Companies ranked below 250 (below Rs5,000 Cr) - highest growth potential, highest risk","related":["what-is-a-stock","smallcap-investing"]},
{"id":"how-to-read-annual-report","title":"How to Read an Annual Report in 10 Minutes","category":"beginners","difficulty":"intermediate","read_time":5,"summary":"The 5 things you must check in every annual report before investing.","content":"1. MD Letter to Shareholders (3 min): Is management honest? Are they acknowledging problems or only celebrating wins?\n\n2. P and L Statement (2 min): Is revenue growing? Are margins expanding or contracting?\n\n3. Balance Sheet (2 min): Is debt increasing? Is cash building? Are receivables growing faster than revenue?\n\n4. Cash Flow Statement (2 min): Most honest statement - cannot be easily manipulated. Is the company actually collecting cash?\n\n5. Related Party Transactions (1 min): Large transactions with promoter-owned companies? This is how money gets siphoned out quietly.\n\nBonus: Read auditor notes - any qualifications are serious warning signs.","related":["debt-equity","free-cash-flow","promoter-holding"]},
{"id":"nifty-sensex-explained","title":"What are Nifty and Sensex?","category":"beginners","difficulty":"beginner","read_time":3,"summary":"India two main stock market indices - and what they actually measure.","content":"The Sensex is the BSE index of 30 large companies. The Nifty 50 is the NSE index of 50 large companies. Think of them as the average temperature of the Indian stock market.\n\nThe Nifty P/E ratio shows whether the entire market is cheap or expensive. Historical average: 20-22x. Below 15x = historically very cheap. Above 28x = historically expensive.\n\nIf your portfolio significantly underperforms the Nifty over 5+ years, you would have been better off in a simple Nifty index fund.","related":["pe-ratio","value-investing"]},
{"id":"understanding-ipo","title":"IPOs - Should You Apply?","category":"beginners","difficulty":"intermediate","read_time":4,"summary":"What an IPO is and how to think rationally about whether to invest in one.","content":"An IPO is when a private company sells shares to the public for the first time. The company and its investment bankers price the IPO to maximise proceeds - they are NOT leaving money on the table for retail investors.\n\nReality of IPOs: Most underperform the market over 3-5 years. The exceptions get enormous media coverage. The failures are quickly forgotten.\n\nWhen to consider: You have deeply researched the business and believe in its 5-10 year story. The valuation is reasonable compared to listed peers. You are buying to hold for years, not for listing day gains.","related":["valuation","market-cap"]},
{"id":"sip-vs-lumpsum","title":"SIP vs Lumpsum - What the Data Says","category":"beginners","difficulty":"beginner","read_time":3,"summary":"The evidence-based answer to India biggest investing debate.","content":"SIP means investing a fixed amount every month. Lumpsum means investing a large amount at once.\n\nData shows: In bull markets, lumpsum outperforms SIP. In volatile markets, SIP outperforms lumpsum. Over 10+ years, returns are usually similar.\n\nReal answer: SIP wins for most people not because of mathematical superiority but because of behavioural superiority. Most people cannot time the market. SIP forces discipline.\n\nIf you receive a large sum: invest 50% immediately and the rest via SIP over 12 months.","related":["compounding"]}
],
"investors":[
{"id":"rj-deep-dive","title":"Rakesh Jhunjhunwala - The Exact Criteria","category":"investors","difficulty":"intermediate","read_time":6,"summary":"The precise quantitative and qualitative criteria India greatest investor used to select stocks.","content":"QUANTITATIVE FILTERS (all must be met):\nMarket Cap: Above Rs5,000 Cr\nRevenue Growth: Above 10% CAGR for 5 years\nROCE: Above 15%\nROE: Above 15%\nDebt/Equity: Below 0.5\nOPM: Above 15%\nPromoter Holding: Above 50%\nP/E: Below industry/sector average at time of purchase\n\nQUALITATIVE FILTERS:\nBusiness with entry barriers - a durable competitive advantage\nLarge addressable market with a 10+ year runway\nStrong cash reserves on balance sheet\nManagement he respected and trusted personally\nIndia-specific growth story riding secular megatrends\n\nHIS PROCESS:\n1. Start with a macro thesis about India growth\n2. Identify sectors that benefit most from that growth\n3. Find the best-run company in that sector\n4. Verify financials meet minimum criteria\n5. Buy and hold for 5-20 years\n\nKEY PRINCIPLE: He held Titan for 20+ years, Crisil for 15 years. He did not sell during market crashes - he bought more.\n\nON SELLING: He only sold when (1) he needed capital for a better opportunity or (2) when the stock market PE became so irrational that valuation was unsustainable.","related":["roe","roce","promoter-holding","value-investing"]},
{"id":"marcellus-deep-dive","title":"Marcellus - The Forensic Accounting Approach","category":"investors","difficulty":"advanced","read_time":7,"summary":"Saurabh Mukherjea precise 12-ratio forensic screen and exact CCP criteria.","content":"STAGE 1 - QUANTITATIVE SCREEN:\nMarket Cap: Above Rs100 Cr\nROCE: Above 15% for 10 consecutive years (CCP typically finds 25-40%+ ROCE stocks)\nRevenue Growth: Above 10% CAGR for 10 consecutive years\nDebt: Near-zero (D/E typically below 0.2)\nPromoter Pledge: Zero or near-zero\n\nSTAGE 2 - FORENSIC ACCOUNTING (12 ratios from Schilit Financial Shenanigans):\nCash flow from operations vs net profit ratio\nRevenue recognition quality\nDays of inventory change\nDays of receivables change\nRelated party transaction analysis\nContingent liabilities assessment\nAudit quality and auditor tenure\nManagement compensation relative to profit\n\nPHILOSOPHY:\nGreat businesses destroy competition slowly and surely, without making noise. They are boring - paint, adhesives, biscuits, software - but they do it better than anyone else, consistently, for decades.\n\nPORTFOLIO CONSTRUCTION:\n12-15 stocks maximum. Equal weight. Annual April rebalance. Very low turnover.\n\nWHAT THEY AVOID: Any leverage, aggressive revenue recognition, large related-party transactions, promoter pledge, acquisitive companies.","related":["roce","free-cash-flow","promoter-holding"]},
{"id":"buffett-deep-dive","title":"Warren Buffett - The Complete Criteria","category":"investors","difficulty":"intermediate","read_time":6,"summary":"Every criterion Buffett uses to evaluate an investment, in his own words.","content":"BUSINESS QUALITY CRITERIA:\nROE consistently above 20% (not through leverage)\nOperating margins above 15% (pricing power signal)\nDebt/Equity below 0.5 (preferably near zero)\nBusiness he can understand in 5 minutes\nConsistent earnings - not cyclical, not lumpy\nPricing power - can raise prices without losing customers\n\nMANAGEMENT CRITERIA:\nHonest and candid management\nManagement treats shareholder capital like their own\nLong tenure - management stability\nCEO incentives aligned with shareholders\n\nVALUATION CRITERIA:\nIntrinsic value = Present value of all future cash flows\nPrefers fair price not cheap price for great business\nWould not pay more than 25-35x earnings for even the best business\nMargin of safety - always buy below intrinsic value\n\nHIS CHECKLIST:\n1. Is this a business I understand?\n2. Does it have durable competitive advantages?\n3. Is management honest and capable?\n4. Is the price reasonable relative to intrinsic value?\n5. Would I be comfortable owning this for 10+ years?","related":["roe","debt-equity","operating-margins","quality-investing"]},
{"id":"vijay-kedia-smile","title":"Vijay Kedia SMILE Framework - Complete Guide","category":"investors","difficulty":"intermediate","read_time":5,"summary":"How to use Kedia legendary SMILE framework to find small cap multibaggers.","content":"S - SMALL IN SIZE\nMarket cap typically under Rs1,000-5,000 Cr. Small enough to be ignored by institutional investors. Kedia says: Small companies have more room to grow.\n\nM - MEDIUM IN EXPERIENCE\nManagement with 10-15 years running this specific business. Survived at least one major economic downturn. Knows the industry deeply.\n\nL - LARGE IN ASPIRATION\nManagement must think big - fire in the belly. Actively expanding. Not satisfied with current size.\n\nE - EXTRA-LARGE MARKET POTENTIAL\nThe industry TAM must be enormous. Company currently has small market share - lots of room to grow.\n\nHOW KEDIA FINDS THESE:\nReads extensively. Talks to industry participants. Visits company facilities. Meets management personally. Holds for 10-20 years once convinced.\n\nBIGGEST WINS:\nAtul Auto: Bought at Rs5, sold at Rs800 (160x in 15 years)\nCera Sanitaryware: Rs30 to Rs4,800 (160x in 16 years)","related":["smallcap-investing","promoter-holding"]}
]
}

def get_all_content(category=None):
    all_items = []
    for cat, items in EDUCATION.items():
        for item in items:
            if not category or item["category"] == category:
                all_items.append({k:v for k,v in item.items() if k != "content"})
    return all_items

# ═══════════════════════════════════════════════════════════════════════════════
# CACHE
# ═══════════════════════════════════════════════════════════════════════════════
def save_cache():
    try:
        with _cache_lock: data = {"cache_time": _cache_time.isoformat() if _cache_time else None, "stocks": _cache}
        with open(CACHE_FILE, "w") as f: json.dump(data, f)
        with open(SECTOR_CACHE_FILE, "w") as f: json.dump(_sector_averages, f)
        print(f"Saved {len(_cache)} stocks, {len(_sector_averages)} sectors")
    except Exception as e: print(f"Save error: {e}")

def load_cache():
    global _cache, _cache_time, _sector_averages
    try:
        if not os.path.exists(CACHE_FILE): return False
        with open(CACHE_FILE) as f: data = json.load(f)
        stocks = data.get("stocks", {}); ct = data.get("cache_time")
        if not stocks: return False
        with _cache_lock:
            _cache = stocks
            _cache_time = datetime.fromisoformat(ct) if ct else datetime.now()
        if os.path.exists(SECTOR_CACHE_FILE):
            with open(SECTOR_CACHE_FILE) as f: _sector_averages = json.load(f)
        print(f"Loaded {len(stocks)} stocks, {len(_sector_averages)} sector avgs")
        return True
    except Exception as e: print(f"Load error: {e}"); return False

def refresh_cache():
    global _cache, _cache_time, _is_refreshing, _refresh_progress, _sector_averages
    if _is_refreshing: return
    _is_refreshing = True
    universe = NIFTY_500
    _refresh_progress = {"done": 0, "total": len(universe)}
    print(f"Starting cache refresh: {len(universe)} stocks")
    new_cache = {}
    with _cache_lock: avgs = dict(_sector_averages)
    for i, symbol in enumerate(universe):
        try:
            print(f"  [{i+1}/{len(universe)}] {symbol}...", end=" ", flush=True)
            raw = fetch_screener(symbol)
            if raw and raw.get("current_price"):
                entry = build_entry(symbol, raw, avgs)
                new_cache[symbol] = entry
                print(f"ok {entry['scoring']['composite']:.0f}")
            else: print("no data")
            _refresh_progress["done"] = i + 1
            if (i + 1) % 25 == 0:
                with _cache_lock: _cache.update(new_cache)
                avgs = compute_sector_averages({**_cache, **new_cache})
                with _cache_lock: _sector_averages = avgs; _cache_time = datetime.now()
                save_cache()
            time.sleep(0.8)
        except Exception as e:
            print(f"err {e}"); _refresh_progress["done"] = i + 1; time.sleep(1)
    final_avgs = compute_sector_averages(new_cache)
    for sym in list(new_cache.keys()):
        try:
            new_cache[sym]["sector_comparison"] = get_sector_comp(new_cache[sym], final_avgs)
            new_cache[sym]["matching_profiles"] = get_matching_profiles(new_cache[sym], final_avgs)
            new_cache[sym]["scoring"] = score_stock(new_cache[sym], final_avgs)
            new_cache[sym]["conviction"] = conviction(new_cache[sym]["scoring"]["composite"])
        except: pass
    with _cache_lock:
        _cache = new_cache; _cache_time = datetime.now(); _sector_averages = final_avgs
    save_cache()
    print(f"Refresh complete: {len(new_cache)} stocks, {len(final_avgs)} sectors")
    _is_refreshing = False

@app.on_event("startup")
async def startup():
    global _sector_averages
    loaded = load_cache()
    if loaded:
        with _cache_lock:
            for sym, stock in _cache.items():
                if stock.get("sector", "Unknown") in ("Unknown", "", None):
                    stock["sector"] = sector_for(sym, "Unknown")
        avgs = compute_sector_averages(_cache)
        with _cache_lock: _sector_averages = avgs
        print(f"Startup: {len(_cache)} stocks, {len(_sector_averages)} sector avgs")
        age_h = (datetime.now() - _cache_time).total_seconds() / 3600
        sample = list(_cache.values())[:10]
        missing = sum(1 for s in sample if s.get("operating_margins") is None and s.get("net_margins") is None)
        if age_h > 6 or missing >= 5:
            print(f"Triggering rebuild (age={age_h:.1f}h, {missing}/10 missing margins)")
            threading.Thread(target=refresh_cache, daemon=True).start()
    else:
        threading.Thread(target=refresh_cache, daemon=True).start()

@app.get("/")
def root():
    return {"app": "stocks.ai", "version": "13.0.0", "cached_stocks": len(_cache),
            "refreshing": _is_refreshing, "progress": f"{_refresh_progress['done']}/{_refresh_progress['total']}",
            "sectors_indexed": len(_sector_averages), "profiles": len(INVESTOR_PROFILES),
            "cache_age": str(datetime.now() - _cache_time).split(".")[0] if _cache_time else "warming"}

@app.get("/api/cache/status")
def cache_status():
    return {"ready": len(_cache) > 0, "count": len(_cache), "refreshing": _is_refreshing,
            "progress": _refresh_progress, "sectors": len(_sector_averages)}

@app.get("/api/cache/refresh")
def trigger_refresh(bg: BackgroundTasks):
    if _is_refreshing: return {"message": "Already refreshing"}
    bg.add_task(refresh_cache); return {"message": "Refresh started"}

@app.get("/api/profiles")
def get_profiles():
    return {"profiles": INVESTOR_PROFILES, "count": len(INVESTOR_PROFILES)}

@app.get("/api/symbols")
def get_symbols():
    with _cache_lock:
        cached = [{"symbol": v["symbol"], "name": v["company_name"], "sector": v.get("sector", "Unknown")} for v in _cache.values() if v.get("symbol")]
    cached_syms = {s["symbol"] for s in cached}
    extra = [{"symbol": s, "name": s, "sector": NSE_SECTOR_MAP.get(s, "")} for s in NIFTY_500 if s not in cached_syms]
    return {"symbols": cached + extra, "count": len(cached) + len(extra)}

@app.get("/api/sector-averages")
def get_sector_avgs():
    global _sector_averages
    if not _sector_averages and _cache:
        avgs = compute_sector_averages(_cache)
        with _cache_lock: _sector_averages = avgs
    return {"sectors": _sector_averages, "count": len(_sector_averages)}

@app.get("/api/stock/{symbol}")
def get_stock(symbol: str):
    symbol = symbol.upper().strip()
    with _cache_lock: cached = _cache.get(symbol)
    with _cache_lock: avgs = dict(_sector_averages)
    if cached:
        if cached.get("sector", "Unknown") in ("Unknown", "", None):
            cached = dict(cached); cached["sector"] = sector_for(symbol, "Unknown")
        sc = get_sector_comp(cached, avgs)
        if sc or not cached.get("sector_comparison"):
            cached = dict(cached); cached["sector_comparison"] = sc
        return cached
    raw = fetch_screener(symbol)
    if not raw or not raw.get("current_price"):
        raise HTTPException(404, f"Could not find {symbol}")
    entry = build_entry(symbol, raw, avgs)
    with _cache_lock: _cache[symbol] = entry
    return entry

@app.get("/api/screen")
def screen(min_score: float = Query(40), sector: str = Query(None),
           conviction_f: str = Query(None, alias="conviction"),
           profile: str = Query(None), limit: int = Query(30, le=100),
           min_market_cap: float = Query(None), max_pe: float = Query(None),
           min_roe: float = Query(None)):
    with _cache_lock: stocks = list(_cache.values())
    if not stocks:
        done = _refresh_progress.get("done", 0); total = _refresh_progress.get("total", 0)
        return {"count": 0, "stocks": [], "warming": True,
                "message": f"Loading data... {done}/{total} stocks processed. Try again in a moment."}
    with _cache_lock: avgs = dict(_sector_averages)
    results = []
    for s in stocks:
        if s["scoring"]["composite"] < min_score: continue
        if conviction_f and conviction_f.lower() not in s["conviction"].lower(): continue
        if sector and sector.lower() not in (s.get("sector", "")).lower(): continue
        if min_market_cap and (s.get("market_cap") or 0) < min_market_cap * 1e7: continue
        if max_pe and s.get("pe_ratio") and s["pe_ratio"] > max_pe: continue
        if min_roe and s.get("roe") and s["roe"] * 100 < min_roe: continue
        if profile:
            ps = score_profile(s, profile, avgs)
            if ps["score"] < 30: continue
            s = dict(s); s["profile_score"] = ps["score"]; s["profile_reasons"] = ps["reasons"]
        results.append(s)
    results.sort(key=lambda x: x.get("profile_score", x["scoring"]["composite"]), reverse=True)
    return {"count": len(results), "stocks": results[:limit], "total_cached": len(stocks)}

@app.get("/api/watchlist")
def watchlist(symbols: str = Query(...)):
    syms = [s.strip().upper() for s in symbols.split(",") if s.strip()][:25]
    results = []; missing = []
    with _cache_lock: cached = dict(_cache)
    with _cache_lock: avgs = dict(_sector_averages)
    for sym in syms:
        if sym in cached:
            s = dict(cached[sym]); s["sector_comparison"] = get_sector_comp(s, avgs); results.append(s)
        else: missing.append(sym)
    for sym in missing:
        try:
            raw = fetch_screener(sym)
            if raw and raw.get("current_price"):
                entry = build_entry(sym, raw, avgs)
                with _cache_lock: _cache[sym] = entry
                results.append(entry)
            time.sleep(0.5)
        except: pass
    results.sort(key=lambda x: x["scoring"]["composite"], reverse=True)
    return {"count": len(results), "stocks": results}

@app.get("/api/market/pulse")
def market_pulse():
    npe = fetch_nifty_pe(); mv = get_market_valuation(npe)
    with _cache_lock: stocks = list(_cache.values())
    if not stocks:
        return {"nifty_pe": npe, "market": mv, "strong_buys": [], "near_lows": [], "top_sectors": [], "total_indexed": 0}
    top_stocks = sorted([s for s in stocks if s["scoring"]["composite"] >= 55],
                        key=lambda x: x["scoring"]["composite"], reverse=True)[:8]
    near_lows = []
    for s in stocks:
        p = s.get("current_price"); lo = s.get("52w_low"); hi = s.get("52w_high")
        if p and lo and hi and hi > lo:
            pfl = ((p - lo) / (hi - lo)) * 100
            if pfl < 25: near_lows.append({**s, "pct_from_low": round(pfl, 1)})
    near_lows = sorted(near_lows, key=lambda x: x["scoring"]["composite"], reverse=True)[:6]
    sc = {}
    for s in stocks:
        sec = s.get("sector", "Unknown")
        if sec != "Unknown": sc[sec] = sc.get(sec, 0) + 1
    top_secs = sorted(sc.items(), key=lambda x: x[1], reverse=True)[:6]
    return {
        "nifty_pe": npe, "market": mv,
        "strong_buys": [{"symbol": s["symbol"], "company_name": s["company_name"],
                          "score": s["scoring"]["composite"], "sector": s.get("sector"),
                          "conviction": s["conviction"]} for s in top_stocks],
        "near_lows": [{"symbol": s["symbol"], "company_name": s["company_name"],
                       "pct_from_low": s["pct_from_low"], "score": s["scoring"]["composite"],
                       "sector": s.get("sector")} for s in near_lows],
        "top_sectors": [{"sector": s[0], "count": s[1]} for s in top_secs],
        "total_indexed": len(stocks),
    }

@app.get("/api/education")
def get_education(category: str = Query(None)):
    return {"content": get_all_content(category), "categories": list(EDUCATION.keys())}

@app.get("/api/education/{content_id}")
def get_education_item(content_id: str):
    for items in EDUCATION.values():
        for item in items:
            if item["id"] == content_id: return item
    raise HTTPException(404, f"Article not found: {content_id}")

@app.post("/api/portfolio/build")
def build_portfolio_endpoint(profile_id: str = Query(...), capital: float = Query(...),
                              limit: int = Query(None), mode: str = Query("single")):
    npe = fetch_nifty_pe()
    if mode == "consensus":
        return build_consensus(capital, npe, limit)
    if profile_id not in INVESTOR_PROFILES:
        raise HTTPException(400, f"Unknown profile: {profile_id}")
    alloc = compute_allocation(profile_id, capital, npe)
    equity_cap = alloc["equity_capital"]
    profile = INVESTOR_PROFILES[profile_id]
    target_n = limit or profile.get("portfolio_size", 15)
    with _cache_lock: stocks = list(_cache.values())
    if not stocks: raise HTTPException(503, "Cache not ready. Try again in 2 minutes.")
    with _cache_lock: avgs = dict(_sector_averages)
    scored = []
    for s in stocks:
        try:
            ps = score_profile(s, profile_id, avgs)
            if ps["score"] >= 35:
                s = dict(s); s["profile_score"] = ps["score"]; s["profile_reasons"] = ps["reasons"]
                scored.append(s)
        except: pass
    scored.sort(key=lambda x: x["profile_score"], reverse=True)
    top = scored[:target_n]; near_misses = scored[target_n:target_n + 6]
    if not top:
        raise HTTPException(404, f"No stocks meet {profile['name']} criteria with current data.")
    portfolio = get_portfolio_allocation(profile_id, top, equity_cap)
    for pos in portfolio["positions"]:
        try:
            stock_data = next((s for s in top if s["symbol"] == pos["symbol"]), {})
            exp = explain_stock(stock_data, profile_id, avgs)
            pos["full_analysis"] = exp["full_analysis"]
            pos["qualifying_metrics"] = exp["qualifying_metrics"]
            pos["one_liner"] = exp.get("one_liner", "")
            pos["why_included"] = pos["one_liner"] or (pos.get("profile_reasons", ["Meets profile criteria"])[0])
        except:
            pos["full_analysis"] = f"Selected based on {profile['name']} investment criteria."
            pos["qualifying_metrics"] = []; pos["one_liner"] = ""; pos["why_included"] = "Meets profile criteria"
    try: why_not = why_not_list(profile_id, near_misses, avgs)
    except: why_not = []
    portfolio.update({
        "profile_id": profile_id, "profile_name": profile["name"],
        "profile_philosophy": profile["philosophy"], "profile_bio": profile["bio"],
        "profile_exact_criteria": profile.get("exact_criteria", {}),
        "capital_input": capital, "equity_capital": equity_cap,
        "asset_allocation": alloc, "why_not": why_not,
        "generated_at": datetime.now().isoformat(), "mode": "single"
    })
    return portfolio

def build_consensus(capital: float, npe: float, limit: int = None):
    alloc = compute_allocation("parag_parikh", capital, npe)
    equity_cap = alloc["equity_capital"]
    with _cache_lock: stocks = list(_cache.values())
    with _cache_lock: avgs = dict(_sector_averages)
    cs = []
    for s in stocks:
        try:
            c = score_consensus(s, avgs)
            if c["tier"]:
                s = dict(s); s["consensus_score"] = c["consensus_score"]
                s["consensus_data"] = c; s["profile_score"] = c["consensus_score"]; cs.append(s)
        except: pass
    cs.sort(key=lambda x: x["consensus_score"], reverse=True)
    top = cs[:limit or 20]
    if not top: raise HTTPException(404, "Not enough consensus stocks found")
    total_q = sum(s["consensus_data"]["qualifying_profiles"] for s in top)
    weights = [s["consensus_data"]["qualifying_profiles"] / (total_q or 1) for s in top]
    tw = sum(weights); weights = [w / tw for w in weights]
    positions = []
    for i, (stock, w) in enumerate(zip(top, weights)):
        price = stock.get("current_price") or 0; amt = equity_cap * w
        shares = int(amt / price) if price > 0 else 0; actual = shares * price if price > 0 else amt
        cd = stock["consensus_data"]
        try: exp = explain_stock(stock, "buffett", avgs)
        except: exp = {"full_analysis": "Multi-profile consensus pick.", "qualifying_metrics": []}
        positions.append({
            "rank": i + 1, "symbol": stock["symbol"], "company_name": stock["company_name"],
            "sector": stock.get("sector", "Unknown"), "current_price": price,
            "weight_pct": round(w * 100, 1), "amount": round(actual), "shares": shares,
            "profile_score": stock["consensus_score"], "consensus_tier": cd["tier"],
            "qualifying_profiles": cd["qualifying_profiles"],
            "top_agreeing_profiles": [{"name": p["profile_name"], "score": p["score"]} for p in cd["top_profiles"][:3]],
            "conviction": stock["conviction"],
            "why_included": f"{cd['qualifying_profiles']} of {len(INVESTOR_PROFILES)} legendary investors agree on this stock",
            "full_analysis": exp["full_analysis"], "qualifying_metrics": exp["qualifying_metrics"][:4],
            "one_liner": "", "profile_reasons": []
        })
    se = {}
    for pos in positions:
        sec = pos["sector"]
        if sec != "Unknown": se[sec] = round(se.get(sec, 0) + pos["weight_pct"], 1)
    return {
        "positions": positions, "total_stocks": len(positions), "total_capital": capital,
        "equity_capital": equity_cap, "total_deployed": round(sum(p["amount"] for p in positions)),
        "sector_exposure": se, "asset_allocation": alloc, "why_not": [],
        "portfolio_rationale": "Legend Consensus selects stocks where multiple legendary investors with different philosophies independently agree.",
        "entry_strategy": "Enter systematically over 3-6 months. Consensus approach reduces single-style risk.",
        "rebalance_note": "Quarterly review. Replace stocks dropping below 3-profile consensus.",
        "profile_id": "consensus", "profile_name": "Legend Consensus",
        "profile_philosophy": "Intersection of all legendary investor philosophies.",
        "profile_bio": "A meta-strategy finding common ground between multiple legendary investors.",
        "profile_exact_criteria": {}, "capital_input": capital,
        "generated_at": datetime.now().isoformat(), "mode": "consensus"
    }
