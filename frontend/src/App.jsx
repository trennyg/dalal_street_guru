import { useState, useCallback, useEffect, useRef } from "react";
import { Search, Filter, TrendingUp, List, RefreshCw, AlertCircle, Users, BarChart2, X, Download, Menu, BookOpen, ChevronDown, ChevronUp, ArrowRight, Zap } from "lucide-react";
import StockCard from "./components/StockCard";
import StockDetail from "./components/StockDetail";
import { fetchStock, fetchWatchlist, screenStocks, buildPortfolio, fetchEducation, fetchEducationItem, SCORE_COLOR } from "./lib/api";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";
import "./App.css";

const BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";
const DEFAULT_WATCHLIST = ["RELIANCE","TCS","HDFCBANK","BAJFINANCE","TITAN","NESTLEIND","PIDILITIND","ASIANPAINT"];
const PIE_COLORS = ["#1a56db","#0ea5e9","#10b981","#f59e0b","#ec4899","#8b5cf6","#06b6d4","#84cc16","#f97316","#64748b","#e11d48","#7c3aed"];

const TABS = [
  { id:"home", label:"Home", icon:Zap },
  { id:"watchlist", label:"Watchlist", icon:List },
  { id:"screener", label:"Screener", icon:Filter },
  { id:"profiles", label:"Investor Profiles", icon:Users },
  { id:"portfolio", label:"Portfolio Builder", icon:BarChart2 },
  { id:"learn", label:"Learn", icon:BookOpen },
  { id:"search", label:"Search", icon:Search },
];

const INVESTOR_PROFILES = {
  "Indian Legend": [
    { id:"rj", name:"Rakesh Jhunjhunwala", avatar:"RJ", focus:"India Growth Compounder", color:"#f59e0b" },
    { id:"vijay_kedia", name:"Vijay Kedia", avatar:"VK", focus:"SMILE — Niche Leaders", color:"#8b5cf6" },
    { id:"porinju", name:"Porinju Veliyath", avatar:"PV", focus:"Smallcap Contrarian", color:"#ec4899" },
    { id:"ashish_kacholia", name:"Ashish Kacholia", avatar:"AK", focus:"Emerging Compounders", color:"#84cc16" },
    { id:"dolly_khanna", name:"Dolly Khanna", avatar:"DK", focus:"Cyclical Turnarounds", color:"#f472b6" },
  ],
  "Global Legend": [
    { id:"buffett", name:"Warren Buffett", avatar:"WB", focus:"Quality at Fair Price", color:"#3b82f6" },
    { id:"ben_graham", name:"Benjamin Graham", avatar:"BG", focus:"Deep Value / Margin of Safety", color:"#64748b" },
    { id:"peter_lynch", name:"Peter Lynch", avatar:"PL", focus:"GARP — Growth at Reasonable Price", color:"#06b6d4" },
    { id:"charlie_munger", name:"Charlie Munger", avatar:"CM", focus:"Wonderful Company at Fair Price", color:"#0ea5e9" },
  ],
  "Indian Fund": [
    { id:"parag_parikh", name:"Parag Parikh Flexi Cap", avatar:"PP", focus:"Owner-Operator Quality", color:"#10b981" },
    { id:"marcellus", name:"Marcellus Investment", avatar:"MC", focus:"Forensic Quality Only", color:"#06b6d4" },
    { id:"motilal_qglp", name:"Motilal Oswal QGLP", avatar:"MO", focus:"Quality + Growth + Longevity", color:"#f97316" },
    { id:"enam", name:"Enam / Vallabh Bhansali", avatar:"EN", focus:"Forensic Long-Term Quality", color:"#c4b5fd" },
    { id:"white_oak", name:"White Oak Capital", avatar:"WO", focus:"Earnings Quality Growth", color:"#34d399" },
    { id:"carnelian", name:"Carnelian Asset", avatar:"CA", focus:"Emerging Sector Leaders", color:"#67e8f9" },
  ],
};
const ALL_PROFILES_FLAT = Object.values(INVESTOR_PROFILES).flat();

const QUIZ_QUESTIONS = [
  { q:"How long are you willing to hold an investment?", sub:"Patience is the foundation of all great investing", options:[
    { key:"A", label:"1-2 years", desc:"I want to see results soon", value:"short" },
    { key:"B", label:"3-5 years", desc:"Medium term, willing to wait", value:"medium" },
    { key:"C", label:"10+ years", desc:"I think in decades, not years", value:"long" },
  ]},
  { q:"What matters more to you in a business?", sub:"This reveals your investing temperament", options:[
    { key:"A", label:"Safety first", desc:"Strong balance sheet, low debt, predictable earnings", value:"safety" },
    { key:"B", label:"Growth above all", desc:"Fast growing revenue and earnings, even if risky", value:"growth" },
    { key:"C", label:"Value — buy cheap", desc:"Pay less than what the business is worth", value:"value" },
  ]},
  { q:"How do you feel about debt in a company?", sub:"Balance sheet philosophy varies widely among legends", options:[
    { key:"A", label:"Zero tolerance", desc:"I only invest in debt-free businesses", value:"no_debt" },
    { key:"B", label:"Acceptable if manageable", desc:"Some debt is fine if earnings cover it well", value:"some_debt" },
    { key:"C", label:"Debt is fine", desc:"Leverage can amplify returns if used wisely", value:"debt_ok" },
  ]},
  { q:"Which type of company excites you most?", sub:"Your answer reveals your market cap preference", options:[
    { key:"A", label:"Small, ignored, huge potential", desc:"Under Rs 5,000 Cr — nobody watching, maximum upside", value:"small" },
    { key:"B", label:"Mid-size quality grower", desc:"Rs 5,000-50,000 Cr — proven but still growing", value:"mid" },
    { key:"C", label:"Large, dominant, dependable", desc:"Market leaders with decades of track record", value:"large" },
  ]},
  { q:"How do you handle a 30% portfolio drop?", sub:"Volatility tolerance separates investing styles", options:[
    { key:"A", label:"Buy more aggressively", desc:"This is exactly what I was waiting for", value:"buy_dip" },
    { key:"B", label:"Hold and review thesis", desc:"I stay calm and re-examine my investment case", value:"hold" },
    { key:"C", label:"Reduce exposure", desc:"Capital preservation is paramount", value:"reduce" },
  ]},
  { q:"What is your primary investing goal?", sub:"Goals determine the right strategy", options:[
    { key:"A", label:"Build generational wealth", desc:"Multi-decade compounding, not short-term gains", value:"generational" },
    { key:"B", label:"Beat Nifty consistently", desc:"Outperform the index over 5-7 years", value:"beat_index" },
    { key:"C", label:"Regular income", desc:"Dividends and steady returns matter as much as growth", value:"income" },
  ]},
];

function getQuizResult(answers) {
  const score = { rj:0, buffett:0, ben_graham:0, marcellus:0, vijay_kedia:0, porinju:0, parag_parikh:0, peter_lynch:0 };
  const [horizon, style, debt, size, volatility, goal] = answers;
  if (horizon==="long") { score.buffett+=3; score.rj+=2; score.marcellus+=3; }
  else if (horizon==="medium") { score.peter_lynch+=3; score.parag_parikh+=2; }
  else { score.porinju+=2; score.vijay_kedia+=1; }
  if (style==="safety") { score.marcellus+=3; score.buffett+=2; score.parag_parikh+=2; }
  else if (style==="growth") { score.rj+=3; score.peter_lynch+=2; score.vijay_kedia+=2; }
  else { score.ben_graham+=3; }
  if (debt==="no_debt") { score.marcellus+=3; score.buffett+=2; }
  else if (debt==="some_debt") { score.parag_parikh+=2; score.rj+=1; }
  else { score.porinju+=1; }
  if (size==="small") { score.porinju+=3; score.vijay_kedia+=3; score.ashish_kacholia+=3; }
  else if (size==="mid") { score.rj+=2; score.peter_lynch+=2; }
  else { score.buffett+=2; score.marcellus+=2; }
  if (volatility==="buy_dip") { score.rj+=3; score.buffett+=2; }
  else if (volatility==="hold") { score.marcellus+=2; score.parag_parikh+=2; }
  else { score.ben_graham+=2; }
  if (goal==="generational") { score.buffett+=3; score.marcellus+=2; }
  else if (goal==="beat_index") { score.rj+=2; score.peter_lynch+=2; }
  else { score.parag_parikh+=2; score.ben_graham+=1; }
  const winner = Object.entries(score).sort((a,b)=>b[1]-a[1])[0][0];
  return ALL_PROFILES_FLAT.find(p=>p.id===winner) || ALL_PROFILES_FLAT[0];
}

// ─── Autocomplete ─────────────────────────────────────────────────────────────
function StockSearch({ onAdd, existingSymbols=[], placeholder="Search symbol or company name..." }) {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [allSymbols, setAllSymbols] = useState([]);
  const inputRef = useRef(null);

  useEffect(() => {
    fetch(`${BASE_URL}/api/symbols`)
      .then(r=>r.json())
      .then(d=>{ if(d.symbols) setAllSymbols(d.symbols); })
      .catch(()=>{
        fetch(`${BASE_URL}/api/screen?min_score=0&limit=300`)
          .then(r=>r.json())
          .then(d=>{ if(d.stocks) setAllSymbols(d.stocks.map(s=>({symbol:s.symbol,name:s.company_name,sector:s.sector}))); })
          .catch(()=>{});
      });
  }, []);

  const handleInput = val => {
    setQuery(val);
    if (!val.trim()) { setSuggestions([]); return; }
    const q = val.toUpperCase().trim();
    const exact = allSymbols.filter(s=>s.symbol.startsWith(q)&&!existingSymbols.includes(s.symbol));
    const nameMatch = allSymbols.filter(s=>!s.symbol.startsWith(q)&&s.name?.toUpperCase().includes(q)&&!existingSymbols.includes(s.symbol));
    const contains = allSymbols.filter(s=>!s.symbol.startsWith(q)&&s.symbol.includes(q)&&!s.name?.toUpperCase().includes(q)&&!existingSymbols.includes(s.symbol));
    setSuggestions([...exact,...nameMatch,...contains].slice(0,8));
  };

  const handleSelect = sym => { onAdd(sym); setQuery(""); setSuggestions([]); inputRef.current?.focus(); };

  return (
    <div className="autocomplete-wrap">
      <input ref={inputRef} value={query} onChange={e=>handleInput(e.target.value)}
        onKeyDown={e=>{
          if(e.key==="Enter"&&query.trim()) handleSelect(suggestions[0]?.symbol||query.trim().toUpperCase());
          if(e.key==="Escape") setSuggestions([]);
        }}
        placeholder={placeholder} className="control-input" style={{width:"100%"}}
        autoComplete="off" autoCapitalize="characters" />
      {suggestions.length>0&&(
        <div className="autocomplete-dropdown">
          {suggestions.map(s=>(
            <div key={s.symbol} className="autocomplete-item" onClick={()=>handleSelect(s.symbol)}>
              <div><span className="autocomplete-symbol">{s.symbol}</span><span className="autocomplete-name">{s.name?.split(" ").slice(0,4).join(" ")}</span></div>
              <span className="autocomplete-sector">{s.sector&&s.sector!=="Unknown"?s.sector:""}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Learn Drawer ─────────────────────────────────────────────────────────────
function LearnDrawer({ learnId, onClose, onOpenFullLearn }) {
  const [article, setArticle] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!learnId) return;
    setLoading(true);
    fetchEducationItem(learnId)
      .then(setArticle)
      .catch(()=>setArticle(null))
      .finally(()=>setLoading(false));
  }, [learnId]);

  return (
    <div className="learn-drawer-overlay" onClick={e=>e.target===e.currentTarget&&onClose()}>
      <div className="learn-drawer">
        <div className="learn-drawer-header">
          <div>
            {article && <div className={`learn-category-pill learn-category-${article.category}`} style={{marginBottom:6}}>{article.category}</div>}
            <div className="learn-drawer-title">{loading?"Loading...":article?.title||"Not found"}</div>
          </div>
          <button onClick={onClose} style={{background:"var(--surface2)",border:"1px solid var(--border)",borderRadius:"var(--radius-sm)",padding:7,cursor:"pointer",display:"flex",color:"var(--text2)",flexShrink:0}}><X size={15}/></button>
        </div>
        <div className="learn-drawer-body">
          {loading&&<div style={{color:"var(--text3)",fontSize:13}}>Loading article...</div>}
          {!loading&&article&&(
            <>
              <div className="learn-drawer-summary">{article.summary}</div>
              <div className="learn-drawer-content">{article.content}</div>
              {article.example_text&&(
                <div className="learn-drawer-example">
                  <div style={{fontSize:10,fontWeight:700,color:"var(--blue)",textTransform:"uppercase",letterSpacing:0.8,fontFamily:"var(--font-mono)",marginBottom:6}}>Real Example: {article.example_stock}</div>
                  {article.example_text}
                </div>
              )}
              {article.watch_out&&(
                <div className="learn-drawer-watchout">
                  <div style={{fontSize:10,fontWeight:700,color:"var(--amber)",textTransform:"uppercase",letterSpacing:0.8,fontFamily:"var(--font-mono)",marginBottom:6}}>Watch Out For</div>
                  {article.watch_out}
                </div>
              )}
              <button className="btn-primary" style={{width:"100%",justifyContent:"center",marginTop:20}} onClick={()=>onOpenFullLearn(learnId)}>
                <BookOpen size={14}/> Read Full Article in Learn Tab
              </button>
            </>
          )}
          {!loading&&!article&&<div style={{color:"var(--text3)",fontSize:13}}>Article not found. Browse the Learn tab for all topics.</div>}
        </div>
      </div>
    </div>
  );
}

// ─── Metric Pill ─────────────────────────────────────────────────────────────
function MetricPill({ label, value, status="inline", learnId, onLearnClick }) {
  return (
    <span className={`metric-pill ${status}`} onClick={()=>learnId&&onLearnClick&&onLearnClick(learnId)} title={learnId?"Click to learn about "+label:""}>
      <span>{label}: {value}</span>
      {learnId&&<span className="metric-pill-learn">Learn →</span>}
    </span>
  );
}

// ─── Main App ─────────────────────────────────────────────────────────────────
export default function App() {
  const [tab, setTab] = useState("home");
  const [menuOpen, setMenuOpen] = useState(false);
  const [stocks, setStocks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedStock, setSelectedStock] = useState(null);
  const [learnDrawer, setLearnDrawer] = useState(null); // learnId string

  const [watchlist, setWatchlist] = useState(()=>{
    try{const s=localStorage.getItem("watchlist_v3");return s?JSON.parse(s):DEFAULT_WATCHLIST;}catch{return DEFAULT_WATCHLIST;}
  });
  const [watchlistLoaded, setWatchlistLoaded] = useState(false);

  const [minScore, setMinScore] = useState(40);
  const [convictionFilter, setConvictionFilter] = useState("");
  const [maxPE, setMaxPE] = useState("");
  const [minROE, setMinROE] = useState("");

  const [selectedProfile, setSelectedProfile] = useState(null);
  const [profileDetail, setProfileDetail] = useState(null);

  const [portfolioProfile, setPortfolioProfile] = useState(null);
  const [capitalInput, setCapitalInput] = useState("");
  const [portfolio, setPortfolio] = useState(null);
  const [portfolioLoading, setPortfolioLoading] = useState(false);
  const [portfolioMode, setPortfolioMode] = useState("single"); // "single" | "consensus"

  const [learnContent, setLearnContent] = useState([]);
  const [learnCategory, setLearnCategory] = useState("all");
  const [learnArticle, setLearnArticle] = useState(null);
  const [learnLoading, setLearnLoading] = useState(false);

  const [pulse, setPulse] = useState(null);
  const [quizStep, setQuizStep] = useState(-1); // -1=not started, 0-5=questions, 6=result
  const [quizAnswers, setQuizAnswers] = useState([]);
  const [quizResult, setQuizResult] = useState(null);

  useEffect(()=>{localStorage.setItem("watchlist_v3",JSON.stringify(watchlist));},[watchlist]);

  // Load market pulse on home tab
  useEffect(()=>{
    if(tab!=="home"||pulse) return;
    fetch(`${BASE_URL}/api/market/pulse`).then(r=>r.json()).then(setPulse).catch(()=>{});
  },[tab,pulse]);

  useEffect(()=>{
    if(tab!=="learn") return;
    setLearnLoading(true);
    fetchEducation(learnCategory==="all"?null:learnCategory)
      .then(d=>setLearnContent(d.content||[]))
      .catch(()=>{}).finally(()=>setLearnLoading(false));
  },[tab,learnCategory]);

  const addToWatchlist = sym=>{const s=sym.trim().toUpperCase();if(s&&!watchlist.includes(s))setWatchlist(p=>[...p,s]);};
  const removeFromWatchlist = sym=>setWatchlist(p=>p.filter(s=>s!==sym));

  const runWatchlist = useCallback(async(symbols)=>{
    if(!symbols?.length) return;
    setLoading(true);setError(null);setStocks([]);
    try{const d=await fetchWatchlist(symbols);setStocks(d.stocks||[]);setWatchlistLoaded(true);}
    catch(e){setError(e.message);}finally{setLoading(false);}
  },[]);

  useEffect(()=>{
    if(tab==="watchlist"&&!watchlistLoaded&&watchlist.length>0) runWatchlist(watchlist);
  },[tab,watchlistLoaded,watchlist,runWatchlist]);

  const runScreener = useCallback(async()=>{
    setLoading(true);setError(null);setStocks([]);
    try{
      const p=new URLSearchParams({min_score:minScore,limit:30});
      if(convictionFilter) p.set("conviction",convictionFilter);
      if(maxPE) p.set("max_pe",maxPE);
      if(minROE) p.set("min_roe",minROE);
      const r=await fetch(`${BASE_URL}/api/screen?${p}`);
      const d=await r.json();
      if(d.warming) setError(d.message); else setStocks(d.stocks||[]);
    }catch(e){setError(e.message);}finally{setLoading(false);}
  },[minScore,convictionFilter,maxPE,minROE]);

  const runProfileScreen = useCallback(async(profileId)=>{
    setLoading(true);setError(null);setStocks([]);
    try{
      const r=await fetch(`${BASE_URL}/api/screen?min_score=25&limit=30&profile=${profileId}`);
      const d=await r.json();
      if(d.warming) setError(d.message); else setStocks(d.stocks||[]);
    }catch(e){setError(e.message);}finally{setLoading(false);}
  },[]);

  const runBuildPortfolio = useCallback(async()=>{
    if(portfolioMode==="single"&&!portfolioProfile) return;
    if(!capitalInput) return;
    const capital=parseFloat(capitalInput.replace(/[^0-9.]/g,""));
    if(!capital){setError("Enter a valid capital amount");return;}
    setPortfolioLoading(true);setError(null);setPortfolio(null);
    try{
      const profileId=portfolioMode==="consensus"?"rj":(portfolioProfile?.id||"rj");
      const p=new URLSearchParams({profile_id:profileId,capital,mode:portfolioMode});
      const r=await fetch(`${BASE_URL}/api/portfolio/build?${p}`,{method:"POST"});
      if(!r.ok) throw new Error("Portfolio build failed");
      const d=await r.json();
      setPortfolio(d);
    }catch(e){setError(e.message);}finally{setPortfolioLoading(false);}
  },[portfolioProfile,capitalInput,portfolioMode]);

  const runSearch = useCallback(async(sym)=>{
    const symbol=(sym||"").trim().toUpperCase();
    if(!symbol) return;
    setLoading(true);setError(null);
    try{const s=await fetchStock(symbol);setSelectedStock(s);}
    catch(e){setError(`Could not find "${symbol}"`);}finally{setLoading(false);}
  },[]);

  const openLearnArticle = async(id)=>{
    try{const d=await fetchEducationItem(id);setLearnArticle(d);}catch{}
  };

  const handleQuizAnswer = (answer) => {
    const newAnswers=[...quizAnswers,answer];
    setQuizAnswers(newAnswers);
    if(quizStep>=QUIZ_QUESTIONS.length-1){
      const result=getQuizResult(newAnswers.map(a=>a.value));
      setQuizResult(result);setQuizStep(QUIZ_QUESTIONS.length);
    } else {
      setQuizStep(quizStep+1);
    }
  };

  const exportCSV=()=>{
    if(!portfolio) return;
    const rows=[["Rank","Symbol","Company","Sector","Weight%","Amount","Shares","Price","Score"],
      ...portfolio.positions.map(p=>[p.rank,p.symbol,p.company_name,p.sector,p.weight_pct,p.amount,p.shares,p.current_price,p.profile_score])];
    const blob=new Blob([rows.map(r=>r.join(",")).join("\n")],{type:"text/csv"});
    const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download=`${portfolio.profile_name}_portfolio.csv`;a.click();
  };

  const switchTab=id=>{setTab(id);setMenuOpen(false);setError(null);};

  const openLearnFromMetric=(learnId)=>setLearnDrawer(learnId);

  return (
    <div className="app">
      <nav className="nav">
        <div className="nav-inner">
          <div className="logo">
            <div className="logo-icon">S</div>
            <div className="logo-text-wrap">
              <span className="logo-main">stocks<span className="logo-dot">.</span>ai</span>
              <span className="logo-sub">by relentless ais</span>
            </div>
          </div>
          <div className="nav-tabs desktop-only">
            {TABS.map(({id,label,icon:Icon})=>(
              <button key={id} className={`nav-tab ${tab===id?"active":""}`} onClick={()=>switchTab(id)}>
                <Icon size={14}/>{label}
              </button>
            ))}
          </div>
          <div className="nav-right"/>
        </div>
        <div className="nav-mobile-row">
          <button className="hamburger-btn" onClick={()=>setMenuOpen(o=>!o)}>
            {menuOpen?<X size={20}/>:<Menu size={20}/>}
          </button>
          <span className="mobile-tab-label">{TABS.find(t=>t.id===tab)?.label}</span>
        </div>
        {menuOpen&&(
          <div className="mobile-menu">
            {TABS.map(({id,label,icon:Icon})=>(
              <button key={id} className={`mobile-menu-item ${tab===id?"active":""}`} onClick={()=>switchTab(id)}>
                <Icon size={16}/><span>{label}</span>
                {tab===id&&<span style={{marginLeft:"auto",color:"var(--blue)"}}>●</span>}
              </button>
            ))}
          </div>
        )}
      </nav>

      <main className="main" onClick={()=>menuOpen&&setMenuOpen(false)}>

        {/* ── HOME ── */}
        {tab==="home"&&(
          <HomeTab pulse={pulse} onViewStock={s=>{setSelectedStock(s);}} onSwitchTab={switchTab}
            quizStep={quizStep} setQuizStep={setQuizStep} quizAnswers={quizAnswers}
            handleQuizAnswer={handleQuizAnswer} quizResult={quizResult} setQuizResult={setQuizResult}
            setQuizAnswers={setQuizAnswers} setPortfolioProfile={setPortfolioProfile} />
        )}

        {/* ── WATCHLIST ── */}
        {tab==="watchlist"&&(
          <>
            <div className="page-header">
              <div className="page-title">My Watchlist</div>
              <div className="page-subtitle">Track and analyse your selected stocks</div>
            </div>
            <div className="control-card">
              <div style={{fontSize:10,fontWeight:700,color:"var(--blue)",textTransform:"uppercase",letterSpacing:0.8,marginBottom:12,fontFamily:"var(--font-mono)"}}>{watchlist.length} stocks tracked</div>
              <div style={{display:"flex",flexWrap:"wrap",gap:8,marginBottom:14}}>
                {watchlist.map(sym=>(
                  <div key={sym} className="watchlist-chip">
                    <span className="watchlist-chip-label">{sym}</span>
                    <button className="watchlist-chip-remove" onClick={()=>removeFromWatchlist(sym)}><X size={11}/></button>
                  </div>
                ))}
              </div>
              <StockSearch onAdd={addToWatchlist} existingSymbols={watchlist} placeholder="Add stock — type symbol or company name..."/>
            </div>
            <button className="btn-primary" style={{width:"100%",justifyContent:"center",marginBottom:22}}
              onClick={()=>runWatchlist(watchlist)} disabled={loading||watchlist.length===0}>
              {loading?<RefreshCw size={14} className="spin"/>:<TrendingUp size={14}/>} Analyse Watchlist
            </button>
          </>
        )}

        {/* ── SCREENER ── */}
        {tab==="screener"&&(
          <>
            <div className="page-header">
              <div className="page-title">Stock Screener</div>
              <div className="page-subtitle">Filter all indexed stocks with sector-relative quality, value and growth criteria</div>
            </div>
            <div className="control-card" style={{marginBottom:22}}>
              <div className="control-row">
                <div className="control-group">
                  <label className="control-label">Min Score: {minScore}</label>
                  <input type="range" min={20} max={80} value={minScore} onChange={e=>setMinScore(+e.target.value)} className="control-range"/>
                </div>
                <div className="control-group">
                  <label className="control-label">Conviction</label>
                  <select className="control-select" value={convictionFilter} onChange={e=>setConvictionFilter(e.target.value)}>
                    <option value="">All</option>
                    <option value="Strong Buy">Strong Buy</option>
                    <option value="Buy">Buy</option>
                    <option value="Watch">Watch</option>
                  </select>
                </div>
                <div className="control-group">
                  <label className="control-label">Max P/E</label>
                  <input className="control-input" style={{width:90}} value={maxPE} onChange={e=>setMaxPE(e.target.value)} placeholder="e.g. 30"/>
                </div>
                <div className="control-group">
                  <label className="control-label">Min ROE %</label>
                  <input className="control-input" style={{width:90}} value={minROE} onChange={e=>setMinROE(e.target.value)} placeholder="e.g. 15"/>
                </div>
                <button className="btn-primary" onClick={runScreener} disabled={loading}>
                  {loading?<RefreshCw size={14} className="spin"/>:<Filter size={14}/>} Screen
                </button>
              </div>
            </div>
          </>
        )}

        {/* ── PROFILES ── */}
        {tab==="profiles"&&!selectedProfile&&(
          <>
            <div className="page-header">
              <div className="page-title">Investor Profiles</div>
              <div className="page-subtitle">Screen stocks through the lens of legendary investors — each with their own philosophy and criteria</div>
            </div>
            <div className="profiles-container">
              {Object.entries(INVESTOR_PROFILES).map(([category,profiles],ci)=>(
                <div key={category}>
                  <div className="profile-category-header">
                    <span className="profile-category-label">{category}</span>
                    <div className="profile-category-line"/>
                  </div>
                  <div className="profiles-grid">
                    {profiles.map((p,pi)=>(
                      <div key={p.id} className="profile-card" style={{"--profile-color":p.color,animationDelay:`${(ci*5+pi)*0.04}s`}}
                        onClick={()=>{setSelectedProfile(p);runProfileScreen(p.id);}}>
                        <div className="profile-avatar-badge" style={{width:40,height:40,background:p.color,color:"white",fontSize:10,fontWeight:700,fontFamily:"var(--font-mono)",borderRadius:9,display:"flex",alignItems:"center",justifyContent:"center"}}>
                          {p.avatar}
                        </div>
                        <div className="profile-info">
                          <div className="profile-name">{p.name}</div>
                          <div className="profile-focus">{p.focus}</div>
                        </div>
                        <div style={{display:"flex",flexDirection:"column",alignItems:"flex-end",gap:5}}>
                          <div className="profile-arrow">→</div>
                          <button style={{fontSize:10,color:p.color,background:"transparent",border:"none",cursor:"pointer",fontWeight:600}}
                            onClick={e=>{e.stopPropagation();setProfileDetail(p);}}>About</button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}

        {tab==="profiles"&&selectedProfile&&(
          <div className="selected-profile-bar">
            <button className="btn-back" onClick={()=>{setSelectedProfile(null);setStocks([]);}}>← All</button>
            <div className="selected-profile-info">
              <div className="profile-avatar-badge" style={{width:36,height:36,background:selectedProfile.color,color:"white",fontSize:10,fontWeight:700,fontFamily:"var(--font-mono)",borderRadius:9,display:"flex",alignItems:"center",justifyContent:"center"}}>
                {selectedProfile.avatar}
              </div>
              <div>
                <div className="selected-profile-name">{selectedProfile.name}</div>
                <div className="selected-profile-focus">{selectedProfile.focus}</div>
              </div>
            </div>
            <button className="btn-secondary" onClick={()=>setProfileDetail(selectedProfile)}>About</button>
            <button className="btn-secondary" onClick={()=>{setTab("portfolio");setPortfolioProfile(selectedProfile);setPortfolioMode("single");}}>Build Portfolio →</button>
            <button className="btn-primary" onClick={()=>runProfileScreen(selectedProfile.id)} disabled={loading}>
              {loading?<RefreshCw size={14} className="spin"/>:<RefreshCw size={14}/>}
            </button>
          </div>
        )}

        {/* ── PORTFOLIO ── */}
        {tab==="portfolio"&&!portfolio&&(
          <>
            <div className="page-header">
              <div className="page-title">Portfolio Builder</div>
              <div className="page-subtitle">Build a professionally allocated portfolio with asset allocation, position sizing, and full stock-level analysis</div>
            </div>
            {/* Mode selector */}
            <div style={{display:"flex",gap:10,marginBottom:18}}>
              <button onClick={()=>setPortfolioMode("single")} style={{flex:1,padding:"12px 16px",borderRadius:"var(--radius)",border:"1.5px solid",borderColor:portfolioMode==="single"?"var(--blue)":"var(--border)",background:portfolioMode==="single"?"var(--blue-light)":"var(--surface)",color:portfolioMode==="single"?"var(--blue)":"var(--text2)",fontWeight:600,fontSize:14,cursor:"pointer",transition:"var(--transition)"}}>
                Single Investor Style
              </button>
              <button onClick={()=>setPortfolioMode("consensus")} style={{flex:1,padding:"12px 16px",borderRadius:"var(--radius)",border:"1.5px solid",borderColor:portfolioMode==="consensus"?"var(--blue)":"var(--border)",background:portfolioMode==="consensus"?"var(--blue-light)":"var(--surface)",color:portfolioMode==="consensus"?"var(--blue)":"var(--text2)",fontWeight:600,fontSize:14,cursor:"pointer",transition:"var(--transition)"}}>
                Legend Consensus
              </button>
            </div>
            {portfolioMode==="consensus"&&(
              <div style={{background:"linear-gradient(135deg,var(--blue-light),var(--surface))",border:"1px solid var(--blue-mid)",borderRadius:"var(--radius)",padding:"14px 18px",marginBottom:16,fontSize:13,color:"var(--text2)",lineHeight:1.6}}>
                <strong style={{color:"var(--blue)"}}>Legend Consensus</strong> — finds stocks where multiple legendary investors independently agree. A stock that satisfies Buffett, RJ, Marcellus, and Graham simultaneously is extraordinarily rare and high conviction. Position sizing is weighted by consensus breadth.
              </div>
            )}
            <div className="control-card" style={{marginBottom:22}}>
              <div style={{display:"flex",flexDirection:"column",gap:14}}>
                {portfolioMode==="single"&&(
                  <div className="control-group">
                    <label className="control-label">Investor Style</label>
                    <select className="control-select" style={{width:"100%"}} value={portfolioProfile?.id||""}
                      onChange={e=>setPortfolioProfile(ALL_PROFILES_FLAT.find(x=>x.id===e.target.value)||null)}>
                      <option value="">Select an investor profile...</option>
                      {Object.entries(INVESTOR_PROFILES).map(([cat,profiles])=>(
                        <optgroup key={cat} label={cat}>
                          {profiles.map(p=><option key={p.id} value={p.id}>{p.avatar} — {p.name}</option>)}
                        </optgroup>
                      ))}
                    </select>
                  </div>
                )}
                <div className="control-group">
                  <label className="control-label">Total Capital (INR)</label>
                  <input className="control-input" style={{width:"100%"}} value={capitalInput}
                    onChange={e=>setCapitalInput(e.target.value)} placeholder="e.g. 1000000 — this includes equity + gold + debt allocation"
                    onKeyDown={e=>e.key==="Enter"&&runBuildPortfolio()}/>
                </div>
                {portfolioMode==="single"&&portfolioProfile&&(
                  <div style={{display:"flex",alignItems:"center",gap:10,background:"var(--blue-light)",border:"1px solid var(--blue-mid)",borderRadius:"var(--radius)",padding:"12px 16px"}}>
                    <div style={{width:38,height:38,borderRadius:9,background:portfolioProfile.color,display:"flex",alignItems:"center",justifyContent:"center",fontSize:11,fontWeight:800,color:"white",fontFamily:"var(--font-mono)",flexShrink:0}}>
                      {portfolioProfile.avatar}
                    </div>
                    <div>
                      <div style={{fontSize:14,fontWeight:700,color:"var(--text)"}}>{portfolioProfile.name}</div>
                      <div style={{fontSize:11,color:"var(--blue)",fontFamily:"var(--font-mono)"}}>{portfolioProfile.focus}</div>
                    </div>
                    <button className="btn-ghost" style={{marginLeft:"auto"}} onClick={()=>setProfileDetail(portfolioProfile)}>About →</button>
                  </div>
                )}
                <button className="btn-primary" style={{justifyContent:"center"}}
                  onClick={runBuildPortfolio} disabled={portfolioLoading||(portfolioMode==="single"&&!portfolioProfile)||!capitalInput}>
                  {portfolioLoading?<RefreshCw size={14} className="spin"/>:<BarChart2 size={14}/>}
                  {portfolioMode==="consensus"?"Build Legend Consensus Portfolio":"Build Portfolio"}
                </button>
              </div>
            </div>
          </>
        )}

        {tab==="portfolio"&&portfolio&&(
          <div style={{display:"flex",gap:10,alignItems:"center",flexWrap:"wrap",marginBottom:20}}>
            <button className="btn-back" onClick={()=>setPortfolio(null)}>← Rebuild</button>
            <span style={{fontSize:15,fontWeight:700,color:"var(--text)",fontFamily:"var(--font-display)"}}>{portfolio.profile_name} Portfolio</span>
            <button className="btn-secondary" style={{marginLeft:"auto"}} onClick={exportCSV}><Download size={13}/> Export CSV</button>
          </div>
        )}

        {/* ── LEARN ── */}
        {tab==="learn"&&!learnArticle&&(
          <>
            <div className="page-header">
              <div className="page-title">Learn Investing</div>
              <div className="page-subtitle">Every metric explained. Every strategy decoded. Tap any metric in the app to open its explanation here.</div>
            </div>
            <div style={{display:"flex",gap:8,marginBottom:20,flexWrap:"wrap"}}>
              {["all","metrics","strategies","beginners"].map(cat=>(
                <button key={cat} onClick={()=>setLearnCategory(cat)} style={{padding:"6px 16px",borderRadius:20,border:"1.5px solid",borderColor:learnCategory===cat?"var(--blue)":"var(--border)",background:learnCategory===cat?"var(--blue-light)":"var(--surface)",color:learnCategory===cat?"var(--blue)":"var(--text2)",fontSize:13,fontWeight:600,cursor:"pointer",textTransform:"capitalize",transition:"var(--transition)"}}>
                  {cat==="all"?"All Topics":cat}
                </button>
              ))}
            </div>
            {learnLoading?(
              <div className="shimmer-grid">{[1,2,3,4,5,6].map(i=><div key={i} className="shimmer-card" style={{height:160,animationDelay:`${i*0.07}s`}}/>)}</div>
            ):(
              <div className="learn-grid">
                {learnContent.map((item,i)=>(
                  <div key={item.id} className="learn-card" style={{animationDelay:`${i*0.05}s`}} onClick={()=>openLearnArticle(item.id)}>
                    <div className={`learn-category-pill learn-category-${item.category}`}>{item.category}</div>
                    <div className="learn-card-title">{item.title}</div>
                    <div className="learn-card-summary">{item.summary}</div>
                    <div className="learn-card-meta">
                      <span className={`difficulty-badge difficulty-${item.difficulty}`}>{item.difficulty}</span>
                      <span>{item.read_time} min read</span>
                      {item.example_stock&&<span>· {item.example_stock}</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {tab==="learn"&&learnArticle&&(
          <div>
            <button className="btn-back" style={{marginBottom:20}} onClick={()=>setLearnArticle(null)}>← Back to Learn</button>
            <div style={{maxWidth:680}}>
              <div className={`learn-category-pill learn-category-${learnArticle.category}`} style={{marginBottom:12}}>{learnArticle.category}</div>
              <h1 style={{fontFamily:"var(--font-display)",fontSize:26,fontWeight:700,color:"var(--text)",letterSpacing:"-0.5px",marginBottom:8,lineHeight:1.3}}>{learnArticle.title}</h1>
              <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:24}}>
                <span className={`difficulty-badge difficulty-${learnArticle.difficulty}`}>{learnArticle.difficulty}</span>
                <span style={{fontSize:12,color:"var(--text3)",fontFamily:"var(--font-mono)"}}>{learnArticle.read_time} min read</span>
              </div>
              <div style={{fontSize:16,color:"var(--blue)",fontStyle:"italic",lineHeight:1.6,marginBottom:24,paddingLeft:16,borderLeft:"3px solid var(--blue)"}}>{learnArticle.summary}</div>
              <div style={{fontSize:14.5,color:"var(--text2)",lineHeight:1.8,marginBottom:24,whiteSpace:"pre-line"}}>{learnArticle.content}</div>
              {learnArticle.example_text&&(
                <div style={{background:"var(--blue-light)",border:"1px solid var(--blue-mid)",borderRadius:"var(--radius)",padding:"16px 20px",marginBottom:20}}>
                  <div style={{fontSize:10,fontWeight:700,color:"var(--blue)",textTransform:"uppercase",letterSpacing:0.8,fontFamily:"var(--font-mono)",marginBottom:8}}>Real Example: {learnArticle.example_stock}</div>
                  <div style={{fontSize:13.5,color:"var(--text)",lineHeight:1.65}}>{learnArticle.example_text}</div>
                </div>
              )}
              {learnArticle.watch_out&&(
                <div style={{background:"var(--amber-light)",border:"1px solid #fcd34d",borderRadius:"var(--radius)",padding:"16px 20px",marginBottom:20}}>
                  <div style={{fontSize:10,fontWeight:700,color:"var(--amber)",textTransform:"uppercase",letterSpacing:0.8,fontFamily:"var(--font-mono)",marginBottom:8}}>Watch Out For</div>
                  <div style={{fontSize:13.5,color:"var(--text)",lineHeight:1.65}}>{learnArticle.watch_out}</div>
                </div>
              )}
              {learnArticle.related?.length>0&&(
                <div>
                  <div style={{fontSize:10,fontWeight:700,color:"var(--text3)",textTransform:"uppercase",letterSpacing:0.8,fontFamily:"var(--font-mono)",marginBottom:10}}>Related Topics</div>
                  <div style={{display:"flex",flexWrap:"wrap",gap:8}}>
                    {learnArticle.related.map(r=>(
                      <button key={r} onClick={()=>openLearnArticle(r)} style={{padding:"5px 14px",borderRadius:20,border:"1.5px solid var(--border2)",background:"var(--surface)",fontSize:12.5,fontWeight:500,color:"var(--text2)",cursor:"pointer",transition:"var(--transition)"}}>
                        {r.replace(/-/g," ")} →
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── SEARCH ── */}
        {tab==="search"&&(
          <>
            <div className="page-header">
              <div className="page-title">Search Any Stock</div>
              <div className="page-subtitle">NSE and BSE listed companies — full sector-relative analysis</div>
            </div>
            <div className="control-card" style={{marginBottom:22}}>
              <StockSearch onAdd={sym=>runSearch(sym)} existingSymbols={[]} placeholder="Type NSE/BSE symbol or company name..."/>
            </div>
          </>
        )}

        {/* Error */}
        {error&&<div className="error-banner"><AlertCircle size={14}/>{error}</div>}

        {/* Portfolio output */}
        {tab==="portfolio"&&portfolio&&<PortfolioOutput portfolio={portfolio} portfolioProfile={portfolioProfile} portfolioMode={portfolioMode} onLearnClick={openLearnFromMetric}/>}

        {/* Loading */}
        {loading&&tab!=="portfolio"&&(
          <div className="shimmer-grid">{[1,2,3,4,5,6].map(i=><div key={i} className="shimmer-card" style={{animationDelay:`${i*0.07}s`}}/>)}</div>
        )}

        {/* Stock grid */}
        {!loading&&stocks.length>0&&tab!=="portfolio"&&(
          <>
            <div className="results-header">
              <span className="results-count">{stocks.length} stocks</span>
              <span className="results-sort">{selectedProfile?`${selectedProfile.name} fit ↓`:"sector-relative score ↓"}</span>
              {tab==="watchlist"&&<button className="btn-ghost" style={{marginLeft:"auto"}} onClick={()=>runWatchlist(watchlist)}><RefreshCw size={12}/> Refresh</button>}
            </div>
            <div className="stock-grid">
              {stocks.map((s,i)=>(
                <div key={s.symbol} className="fade-up" style={{animationDelay:`${i*0.04}s`}}>
                  <StockCard stock={s} onClick={setSelectedStock} activeProfile={selectedProfile?.id} onLearnClick={openLearnFromMetric}/>
                </div>
              ))}
            </div>
          </>
        )}

        {/* Empty states */}
        {!loading&&stocks.length===0&&!error&&tab==="screener"&&(
          <div className="empty-state"><div className="empty-icon"><Filter size={26}/></div><div className="empty-title">Set filters and click Screen</div></div>
        )}
        {tab==="portfolio"&&!portfolio&&!portfolioLoading&&!error&&(
          <div className="empty-state"><div className="empty-icon"><BarChart2 size={26}/></div><div className="empty-title">Configure and build your portfolio above</div></div>
        )}
      </main>

      {profileDetail&&<ProfileModal profile={profileDetail} onClose={()=>setProfileDetail(null)}
        onBuildPortfolio={()=>{setProfileDetail(null);setTab("portfolio");setPortfolioProfile(profileDetail);setPortfolioMode("single");}}/>}
      {selectedStock&&<StockDetail stock={selectedStock} onClose={()=>setSelectedStock(null)} onLearnClick={openLearnFromMetric}/>}
      {learnDrawer&&<LearnDrawer learnId={learnDrawer} onClose={()=>setLearnDrawer(null)}
        onOpenFullLearn={(id)=>{setLearnDrawer(null);setTab("learn");openLearnArticle(id);}}/>}
    </div>
  );
}

// ─── Home Tab ─────────────────────────────────────────────────────────────────
function HomeTab({ pulse, onSwitchTab, quizStep, setQuizStep, quizAnswers, handleQuizAnswer, quizResult, setQuizResult, setQuizAnswers, setPortfolioProfile }) {
  if (quizStep >= 0 && !quizResult) {
    const q = QUIZ_QUESTIONS[quizStep];
    return (
      <div className="quiz-container">
        <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:20}}>
          <div style={{fontSize:12,color:"var(--text3)",fontFamily:"var(--font-mono)"}}>Question {quizStep+1} of {QUIZ_QUESTIONS.length}</div>
          <button className="btn-ghost" onClick={()=>{setQuizStep(-1);setQuizAnswers([]);}}>Cancel</button>
        </div>
        <div className="quiz-progress"><div className="quiz-progress-fill" style={{width:`${((quizStep)/QUIZ_QUESTIONS.length)*100}%`}}/></div>
        <div className="quiz-question">{q.q}</div>
        <div className="quiz-subtitle">{q.sub}</div>
        <div className="quiz-options">
          {q.options.map(opt=>(
            <button key={opt.key} className="quiz-option" onClick={()=>handleQuizAnswer(opt)}>
              <div className="quiz-option-key">{opt.key}</div>
              <div>
                <div className="quiz-option-label">{opt.label}</div>
                <div className="quiz-option-desc">{opt.desc}</div>
              </div>
            </button>
          ))}
        </div>
      </div>
    );
  }

  if (quizResult) {
    return (
      <div className="quiz-container">
        <div className="quiz-result">
          <div className="quiz-result-avatar" style={{background:quizResult.color||"var(--blue)"}}>{quizResult.avatar}</div>
          <div className="quiz-result-title">You invest like {quizResult.name}</div>
          <div className="quiz-result-desc">{quizResult.focus} — Your answers reveal a preference for {quizResult.focus.toLowerCase()} investing. This profile's philosophy aligns strongly with your risk tolerance and investment horizon.</div>
          <div style={{display:"flex",flexDirection:"column",gap:10,maxWidth:360,margin:"0 auto"}}>
            <button className="btn-primary" style={{justifyContent:"center"}} onClick={()=>{setPortfolioProfile(quizResult);onSwitchTab("portfolio");}}>
              <BarChart2 size={14}/> Build {quizResult.name} Portfolio
            </button>
            <button className="btn-secondary" style={{justifyContent:"center"}} onClick={()=>onSwitchTab("profiles")}>
              Explore all investor profiles
            </button>
            <button className="btn-ghost" style={{justifyContent:"center"}} onClick={()=>{setQuizResult(null);setQuizStep(-1);setQuizAnswers([]);}}>
              Retake quiz
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="page-header">
        <div className="page-title">Market Pulse</div>
        <div className="page-subtitle">Live market intelligence — updated every session</div>
      </div>

      {/* Quiz CTA */}
      <div style={{background:"linear-gradient(135deg,#1a56db,#0ea5e9)",borderRadius:"var(--radius-lg)",padding:"20px 24px",marginBottom:20,color:"white",display:"flex",alignItems:"center",justifyContent:"space-between",gap:16,flexWrap:"wrap",boxShadow:"var(--shadow-blue)"}}>
        <div>
          <div style={{fontFamily:"var(--font-display)",fontSize:17,fontWeight:700,marginBottom:4}}>Which legendary investor do you think like?</div>
          <div style={{fontSize:13,opacity:0.85,lineHeight:1.5}}>Answer 6 questions — discover your investor style and build your first portfolio in 2 minutes</div>
        </div>
        <button onClick={()=>setQuizStep(0)} style={{background:"white",color:"var(--blue)",border:"none",borderRadius:8,padding:"10px 22px",fontWeight:700,fontSize:14,cursor:"pointer",flexShrink:0,borderRadius:8}}>
          Take the Quiz →
        </button>
      </div>

      {/* Nifty PE + Market Intelligence */}
      {pulse ? (
        <div className="pulse-grid">
          {/* PE Gauge */}
          <div className="pulse-card">
            <div className="pulse-section-title">Nifty 50 Valuation</div>
            <div className="nifty-pe-gauge">
              <div className="pe-value" style={{color:pulse.market?.color||"var(--blue)"}}>{pulse.nifty_pe}x</div>
              <div className="pe-zone" style={{background:pulse.market?.color+"22",color:pulse.market?.color}}>{pulse.market?.zone}</div>
              <div className="pe-bar-track">
                <div className="pe-indicator" style={{left:`${Math.min(Math.max((pulse.nifty_pe-12)/20*100,2),98)}%`}}/>
              </div>
              <div className="pe-scale"><span>12x</span><span>18x</span><span>22x</span><span>26x</span><span>32x</span></div>
              <div style={{fontSize:12,color:"var(--text2)",lineHeight:1.6,marginTop:12,textAlign:"left"}}>{pulse.market?.description}</div>
            </div>
          </div>

          {/* Strong Buys */}
          <div className="pulse-card">
            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:16}}>
              <div>
                <div className="pulse-section-title">Strong Buy Zone</div>
                {pulse.strong_buys?.map(s=>(
                  <div key={s.symbol} className="pulse-stock-row">
                    <div><div className="pulse-symbol">{s.symbol}</div><div className="pulse-name">{s.company_name?.split(" ").slice(0,3).join(" ")}</div></div>
                    <div className="pulse-score" style={{color:SCORE_COLOR(s.score)}}>{s.score}</div>
                  </div>
                ))}
              </div>
              <div>
                <div className="pulse-section-title">Near 52W Lows</div>
                {pulse.near_lows?.map(s=>(
                  <div key={s.symbol} className="pulse-stock-row">
                    <div><div className="pulse-symbol">{s.symbol}</div><div className="pulse-name" style={{color:"var(--amber)"}}>↓ {s.pct_from_low?.toFixed(0)}% from low</div></div>
                    <div className="pulse-score" style={{color:SCORE_COLOR(s.score)}}>{s.score}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="shimmer-grid" style={{gridTemplateColumns:"300px 1fr",marginBottom:28}}>
          <div className="shimmer-card" style={{height:280}}/><div className="shimmer-card" style={{height:280}}/>
        </div>
      )}

      {/* Quick Actions */}
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(200px,1fr))",gap:12,marginBottom:28}}>
        {[
          {label:"Screen All Stocks",desc:"Find strong buys across 500+ stocks",tab:"screener",color:"var(--blue)"},
          {label:"Investor Profiles",desc:"Invest like Buffett, RJ, or Marcellus",tab:"profiles",color:"#8b5cf6"},
          {label:"Build Portfolio",desc:"Full allocation with asset split",tab:"portfolio",color:"#10b981"},
          {label:"Learn Investing",desc:"Every metric explained simply",tab:"learn",color:"#f59e0b"},
        ].map(a=>(
          <button key={a.tab} onClick={()=>onSwitchTab(a.tab)} style={{background:"var(--surface)",border:"1.5px solid var(--border)",borderRadius:"var(--radius)",padding:"16px",textAlign:"left",cursor:"pointer",transition:"var(--transition)",boxShadow:"var(--shadow-xs)"}}>
            <div style={{fontSize:14,fontWeight:700,color:a.color,marginBottom:4}}>{a.label}</div>
            <div style={{fontSize:12,color:"var(--text2)"}}>{a.desc}</div>
            <div style={{fontSize:11,color:a.color,marginTop:8,fontWeight:600}}>Go →</div>
          </button>
        ))}
      </div>
    </>
  );
}

// ─── Portfolio Output ─────────────────────────────────────────────────────────
function PortfolioOutput({ portfolio, portfolioProfile, portfolioMode, onLearnClick }) {
  const [expandedPosition, setExpandedPosition] = useState(null);
  const alloc = portfolio.asset_allocation;
  const stockData = portfolio.positions.map((p,i)=>({name:p.symbol,value:p.weight_pct,color:PIE_COLORS[i%PIE_COLORS.length]}));
  const sectorData = Object.entries(portfolio.sector_exposure||{}).filter(([s])=>s!=="Unknown").sort((a,b)=>b[1]-a[1]).map(([name,value],i)=>({name,value,color:PIE_COLORS[i%PIE_COLORS.length]}));

  return (
    <div className="portfolio-container">
      <div className="portfolio-header">
        <div style={{display:"flex",alignItems:"center",gap:14,marginBottom:10}}>
          <div style={{width:46,height:46,borderRadius:11,background:portfolioProfile?.color||"var(--blue)",display:"flex",alignItems:"center",justifyContent:"center",fontSize:12,fontWeight:800,color:"white",fontFamily:"var(--font-mono)",flexShrink:0}}>
            {portfolio.mode==="consensus"?"LC":portfolioProfile?.avatar}
          </div>
          <div>
            <div className="portfolio-title">{portfolio.profile_name} Portfolio</div>
            <div className="portfolio-subtitle">{portfolio.profile_philosophy?.slice(0,130)}...</div>
          </div>
        </div>
      </div>

      {/* Asset Allocation */}
      {alloc&&(
        <div style={{padding:"20px 28px",borderBottom:"1px solid var(--border)"}}>
          <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:12,flexWrap:"wrap",gap:8}}>
            <div style={{fontSize:11,fontWeight:700,color:"var(--blue)",textTransform:"uppercase",letterSpacing:0.8,fontFamily:"var(--font-mono)"}}>Asset Allocation</div>
            <div style={{display:"flex",alignItems:"center",gap:8}}>
              <div style={{fontSize:12,color:"var(--text2)"}}>Nifty PE: <strong style={{color:alloc.market_valuation?.color}}>{alloc.nifty_pe}x — {alloc.market_valuation?.zone}</strong></div>
            </div>
          </div>
          <div className="allocation-grid">
            {[
              {key:"equity",label:"Equity",color:"var(--blue)",instrument:`→ ${portfolio.total_stocks} stocks below`},
              {key:"gold",label:"Gold",color:"#f59e0b",instrument:alloc.instruments?.gold||"Gold ETF"},
              {key:"debt",label:"Debt",color:"#10b981",instrument:alloc.instruments?.debt||"Liquid Fund"},
              {key:"cash",label:"Cash",color:"#8b5cf6",instrument:alloc.instruments?.cash||"Savings Account"},
            ].map(a=>(
              <div key={a.key} className={`allocation-card ${a.key}`}>
                <div className="allocation-label">{a.label}</div>
                <div className="allocation-pct" style={{color:a.color}}>{alloc.allocation_pct?.[a.key]||0}%</div>
                <div className="allocation-amount">₹{Number(alloc.allocation_amt?.[a.key]||0).toLocaleString("en-IN")}</div>
                <div className="allocation-instrument">{a.instrument}</div>
              </div>
            ))}
          </div>
          <div style={{fontSize:12,color:"var(--text2)",lineHeight:1.65,marginTop:12,padding:"10px 14px",background:"var(--surface2)",borderRadius:"var(--radius-sm)",border:"1px solid var(--border)"}}>{alloc.logic}</div>
        </div>
      )}

      <div className="portfolio-stats">
        {[
          {label:"Stocks",value:portfolio.total_stocks},
          {label:"Equity Deployed",value:`₹${Number(portfolio.total_deployed).toLocaleString("en-IN")}`},
          {label:"Sectors",value:Object.keys(portfolio.sector_exposure||{}).filter(s=>s!=="Unknown").length},
          {label:"Top Hold",value:`${portfolio.positions[0]?.weight_pct}%`},
        ].map(s=>(
          <div key={s.label} className="portfolio-stat">
            <div className="portfolio-stat-value">{s.value}</div>
            <div className="portfolio-stat-label">{s.label}</div>
          </div>
        ))}
      </div>

      <div className="portfolio-rationale"><strong>Portfolio Rationale: </strong>{portfolio.portfolio_rationale}</div>

      {/* Pie charts */}
      <div className="portfolio-charts">
        <div className="chart-card">
          <div className="chart-title">Stock Allocation</div>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={stockData.slice(0,10)} cx="50%" cy="50%" innerRadius={48} outerRadius={78} dataKey="value" paddingAngle={2}>
                {stockData.slice(0,10).map((e,i)=><Cell key={i} fill={e.color}/>)}
              </Pie>
              <Tooltip formatter={v=>[`${v}%`,"Weight"]} contentStyle={{fontSize:12,borderRadius:8}}/>
              <Legend iconType="circle" iconSize={7} formatter={v=><span style={{fontSize:9,color:"var(--text2)"}}>{v}</span>}/>
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="chart-card">
          <div className="chart-title">Sector Allocation</div>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={sectorData.slice(0,8)} cx="50%" cy="50%" innerRadius={48} outerRadius={78} dataKey="value" paddingAngle={2}>
                {sectorData.slice(0,8).map((e,i)=><Cell key={i} fill={e.color}/>)}
              </Pie>
              <Tooltip formatter={v=>[`${v}%`,"Sector"]} contentStyle={{fontSize:12,borderRadius:8}}/>
              <Legend iconType="circle" iconSize={7} formatter={v=><span style={{fontSize:9,color:"var(--text2)"}}>{v.length>14?v.slice(0,14)+"…":v}</span>}/>
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Positions with full analysis */}
      <div className="portfolio-positions">
        <div style={{fontSize:11,fontWeight:700,color:"var(--blue)",textTransform:"uppercase",letterSpacing:0.8,fontFamily:"var(--font-mono)",marginBottom:16}}>
          Positions — tap any stock for full analysis
        </div>
        {portfolio.positions.map(p=>(
          <div key={p.symbol} className="position-card">
            <div className="position-header" onClick={()=>setExpandedPosition(expandedPosition===p.symbol?null:p.symbol)}>
              <div style={{width:28,height:28,borderRadius:"50%",background:"var(--blue-light)",display:"flex",alignItems:"center",justifyContent:"center",fontSize:11,fontWeight:700,color:"var(--blue)"}}>{p.rank}</div>
              <div>
                <div style={{fontFamily:"var(--font-mono)",fontWeight:600,color:"var(--blue)",fontSize:14}}>{p.symbol}</div>
                <div style={{fontSize:11,color:"var(--text2)"}}>{p.company_name?.split(" ").slice(0,4).join(" ")}</div>
                {p.consensus_tier&&<div style={{fontSize:10,color:"#f59e0b",fontFamily:"var(--font-mono)",fontWeight:600}}>{p.consensus_tier} · {p.qualifying_profiles} profiles agree</div>}
              </div>
              <div style={{fontFamily:"var(--font-mono)",fontWeight:700,color:"var(--blue)",fontSize:13}}>{p.weight_pct}%</div>
              <div style={{fontFamily:"var(--font-mono)",fontSize:12,color:"var(--text2)"}}>₹{Number(p.amount).toLocaleString("en-IN")}</div>
              <div style={{color:expandedPosition===p.symbol?"var(--blue)":"var(--text3)",display:"flex"}}>
                {expandedPosition===p.symbol?<ChevronUp size={16}/>:<ChevronDown size={16}/>}
              </div>
            </div>

            {expandedPosition===p.symbol&&(
              <div className="position-analysis">
                <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",padding:"12px 0 8px",flexWrap:"wrap",gap:8}}>
                  <div style={{fontFamily:"var(--font-mono)",fontSize:11,color:"var(--text3)"}}>
                    {p.shares} shares @ ₹{p.current_price?.toFixed(0)} · Score: <span style={{color:SCORE_COLOR(p.profile_score),fontWeight:700}}>{p.profile_score}/100</span>
                  </div>
                </div>

                <div className="position-analysis-text">{p.full_analysis}</div>

                {p.qualifying_metrics?.length>0&&(
                  <div style={{marginBottom:16}}>
                    <div style={{fontSize:10,fontWeight:700,color:"var(--text3)",textTransform:"uppercase",letterSpacing:0.8,fontFamily:"var(--font-mono)",marginBottom:8}}>Qualifying Metrics</div>
                    <div>
                      {p.qualifying_metrics.map((m,i)=>(
                        <div key={i} style={{marginBottom:8}}>
                          <MetricPill label={m.metric} value={m.value+(m.vs_sector?" "+m.vs_sector:"")} status={m.status||"inline"} learnId={m.learn_id} onLearnClick={onLearnClick}/>
                          <div style={{fontSize:12,color:"var(--text2)",lineHeight:1.5,marginTop:3,marginLeft:4}}>{m.explanation}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {p.top_agreeing_profiles?.length>0&&(
                  <div style={{marginBottom:14}}>
                    <div style={{fontSize:10,fontWeight:700,color:"var(--text3)",textTransform:"uppercase",letterSpacing:0.8,fontFamily:"var(--font-mono)",marginBottom:8}}>Profiles in Agreement</div>
                    <div style={{display:"flex",gap:8,flexWrap:"wrap"}}>
                      {p.top_agreeing_profiles.map((prof,i)=>(
                        <div key={i} style={{background:"var(--blue-light)",border:"1px solid var(--blue-mid)",borderRadius:"var(--radius-sm)",padding:"4px 10px",fontSize:11,fontWeight:600,color:"var(--blue)"}}>
                          {prof.name} · {prof.score}/100
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Why Not */}
      {portfolio.why_not?.length>0&&(
        <div style={{padding:"0 28px 24px"}}>
          <div style={{fontSize:11,fontWeight:700,color:"var(--red)",textTransform:"uppercase",letterSpacing:0.8,fontFamily:"var(--font-mono)",marginBottom:12}}>
            Why These Stocks Did Not Qualify
          </div>
          <div style={{fontSize:12,color:"var(--text2)",marginBottom:12,lineHeight:1.5}}>Understanding why stocks were excluded is as valuable as knowing why they were included.</div>
          {portfolio.why_not.map((w,i)=>(
            <div key={i} className="why-not-card">
              <div className="why-not-symbol">{w.symbol}<br/><span style={{fontSize:10,color:"var(--text3)",fontWeight:400}}>{w.score}/100</span></div>
              <div className="why-not-reason">
                {w.reason}
                {w.learn_id&&<span style={{marginLeft:6,cursor:"pointer",color:"var(--blue)",fontWeight:600}} onClick={()=>onLearnClick(w.learn_id)}>Learn why →</span>}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="entry-strategy-box">
        <div className="entry-strategy-label">Entry Strategy</div>
        {portfolio.entry_strategy}
      </div>
      <div style={{margin:"0 28px 28px",padding:"14px 18px",background:"var(--surface2)",border:"1px solid var(--border)",borderRadius:"var(--radius-sm)",fontSize:13,color:"var(--text2)"}}>
        <strong>Rebalancing:</strong> {portfolio.rebalance_note}
      </div>
    </div>
  );
}

// ─── Profile Modal ────────────────────────────────────────────────────────────
function ProfileModal({ profile, onClose, onBuildPortfolio }) {
  const [fp, setFp] = useState({});
  useEffect(()=>{
    fetch(`${BASE_URL}/api/profiles`).then(r=>r.json())
      .then(d=>{if(d.profiles?.[profile.id])setFp(d.profiles[profile.id]);}).catch(()=>{});
  },[profile.id]);

  return (
    <div className="modal-overlay" onClick={e=>e.target===e.currentTarget&&onClose()}>
      <div className="modal">
        <div className="modal-header">
          <div style={{display:"flex",alignItems:"flex-start",justifyContent:"space-between"}}>
            <div style={{display:"flex",alignItems:"center",gap:14}}>
              <div style={{width:52,height:52,borderRadius:12,background:profile.color||"var(--blue)",display:"flex",alignItems:"center",justifyContent:"center",fontSize:13,fontWeight:800,color:"white",fontFamily:"var(--font-mono)",flexShrink:0}}>{profile.avatar}</div>
              <div>
                <div style={{fontFamily:"var(--font-display)",fontSize:18,fontWeight:700,color:"var(--text)",marginBottom:5}}>{profile.name}</div>
                <div style={{display:"inline-block",padding:"3px 12px",background:"var(--blue-light)",border:"1px solid var(--blue-mid)",borderRadius:20,fontSize:12,fontWeight:600,color:profile.color||"var(--blue)"}}>{profile.focus}</div>
              </div>
            </div>
            <button onClick={onClose} style={{background:"var(--surface2)",border:"1px solid var(--border)",borderRadius:"var(--radius-sm)",padding:8,cursor:"pointer",display:"flex",color:"var(--text2)"}}><X size={16}/></button>
          </div>
        </div>
        <div className="modal-body">
          {[{key:"bio",title:"Background"},{key:"philosophy",title:"Investment Philosophy"},{key:"what_he_looked_for",title:"What They Look For"},{key:"what_he_avoided",title:"What They Avoid"}]
            .map(({key,title})=>fp[key]&&(
              <div key={key} className="modal-section">
                <div className="modal-section-title">{title}</div>
                <div className="modal-section-text">{fp[key]}</div>
              </div>
            ))}
          {fp.famous_investments?.length>0&&(
            <div className="modal-section">
              <div className="modal-section-title">Famous Investments</div>
              <div className="investment-tags">{fp.famous_investments.map((inv,i)=><span key={i} className="investment-tag">{inv}</span>)}</div>
            </div>
          )}
          {fp.signature_quote&&(
            <div className="modal-section">
              <div className="modal-section-title">Signature Quote</div>
              <div className="quote-block">"{fp.signature_quote}"</div>
            </div>
          )}
          <div style={{marginTop:24}}>
            <button className="btn-primary" style={{width:"100%",justifyContent:"center"}} onClick={onBuildPortfolio}>
              <BarChart2 size={14}/> Build Portfolio in This Style
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
