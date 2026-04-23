import { useState, useCallback, useEffect, useRef } from "react";
import { Search, Filter, TrendingUp, List, RefreshCw, AlertCircle, Users, BarChart2, X, Download, Menu } from "lucide-react";
import StockCard from "./components/StockCard";
import StockDetail from "./components/StockDetail";
import { fetchStock, fetchWatchlist, screenStocks, buildPortfolio, SCORE_COLOR } from "./lib/api";
import "./App.css";

const DEFAULT_WATCHLIST = ["RELIANCE", "TCS", "HDFCBANK", "BAJFINANCE", "TITAN", "NESTLEIND", "PIDILITIND", "ASIANPAINT"];

const TABS = [
  { id: "watchlist", label: "Watchlist", icon: List },
  { id: "screener", label: "Screener", icon: Filter },
  { id: "profiles", label: "Investor Profiles", icon: Users },
  { id: "portfolio", label: "Portfolio Builder", icon: BarChart2 },
  { id: "search", label: "Search Stock", icon: Search },
];

const INVESTOR_PROFILES = {
  "Indian Legend": [
    { id: "rj", name: "Rakesh Jhunjhunwala", avatar: "🐂", focus: "India Growth Compounder", color: "#f59e0b" },
    { id: "ramesh_damani", name: "Ramesh Damani", avatar: "🎯", focus: "Contrarian Deep Value", color: "#ef4444" },
    { id: "vijay_kedia", name: "Vijay Kedia", avatar: "💡", focus: "SMILE — Niche Leaders", color: "#8b5cf6" },
    { id: "porinju", name: "Porinju Veliyath", avatar: "🔍", focus: "Smallcap Contrarian", color: "#ec4899" },
    { id: "ashish_kacholia", name: "Ashish Kacholia", avatar: "🚀", focus: "Emerging Compounders", color: "#84cc16" },
    { id: "dolly_khanna", name: "Dolly Khanna", avatar: "💎", focus: "Cyclical Turnarounds", color: "#f472b6" },
    { id: "chandrakant_sampat", name: "Chandrakant Sampat", avatar: "📜", focus: "Original Indian Value", color: "#a78bfa" },
    { id: "radhakishan_damani", name: "Radhakishan Damani", avatar: "🛒", focus: "Retail & Consumer Value", color: "#fb923c" },
    { id: "raamdeo_agrawal", name: "Raamdeo Agrawal", avatar: "📋", focus: "QGLP — Quality Growth", color: "#60a5fa" },
    { id: "sanjay_bakshi", name: "Sanjay Bakshi", avatar: "🎓", focus: "Behavioral Value Investing", color: "#818cf8" },
    { id: "kenneth_andrade", name: "Kenneth Andrade", avatar: "🌉", focus: "Asset-Light Capital Efficiency", color: "#34d399" },
    { id: "manish_kejriwal", name: "Manish Kejriwal", avatar: "🌐", focus: "Quality Growth PE Style", color: "#f0abfc" },
  ],
  "Global Legend": [
    { id: "buffett", name: "Warren Buffett", avatar: "🧠", focus: "Quality at Fair Price", color: "#3b82f6" },
    { id: "peter_lynch", name: "Peter Lynch", avatar: "📈", focus: "GARP — Growth at Reasonable Price", color: "#06b6d4" },
    { id: "ben_graham", name: "Benjamin Graham", avatar: "⚖️", focus: "Deep Value / Margin of Safety", color: "#64748b" },
    { id: "charlie_munger", name: "Charlie Munger", avatar: "🦁", focus: "Wonderful Company at Fair Price", color: "#0ea5e9" },
    { id: "phil_fisher", name: "Philip Fisher", avatar: "🔭", focus: "Scuttlebutt Growth Investor", color: "#14b8a6" },
  ],
  "Indian Fund": [
    { id: "parag_parikh", name: "Parag Parikh Flexi Cap", avatar: "🌍", focus: "Owner-Operator Quality", color: "#10b981" },
    { id: "marcellus", name: "Marcellus Investment", avatar: "🔬", focus: "Forensic Quality Only", color: "#06b6d4" },
    { id: "motilal_qglp", name: "Motilal Oswal QGLP", avatar: "📊", focus: "Quality + Growth + Longevity + Price", color: "#f97316" },
    { id: "nippon_smallcap", name: "Nippon India Small Cap", avatar: "🌱", focus: "High Growth Small Caps", color: "#22d3ee" },
    { id: "mirae_asset", name: "Mirae Asset India", avatar: "🏆", focus: "Quality Growth Large Cap", color: "#a3e635" },
    { id: "hdfc_mf", name: "HDFC Mutual Fund", avatar: "🏦", focus: "Value + Quality Blend", color: "#fb923c" },
    { id: "anand_rathi", name: "Anand Rathi Wealth", avatar: "⚡", focus: "Wealth Preservation + Growth", color: "#fbbf24" },
    { id: "white_oak", name: "White Oak Capital", avatar: "🌳", focus: "Earnings Quality Growth", color: "#86efac" },
    { id: "enam", name: "Enam / Vallabh Bhansali", avatar: "🛡️", focus: "Forensic + Long Term", color: "#c4b5fd" },
    { id: "nemish_shah", name: "Nemish Shah", avatar: "🎯", focus: "Consumer & Pharma Quality", color: "#e879f9" },
    { id: "ask_investment", name: "ASK Investment Managers", avatar: "💰", focus: "Quality Large Cap PMS", color: "#fdba74" },
    { id: "carnelian", name: "Carnelian Asset", avatar: "💫", focus: "Emerging Sector Leaders", color: "#67e8f9" },
    { id: "murugappa", name: "Murugappa Group Style", avatar: "🏭", focus: "South India Industrial Quality", color: "#fcd34d" },
  ],
};

const ALL_PROFILES_FLAT = Object.values(INVESTOR_PROFILES).flat();

function StockSearch({ onAdd, existingSymbols = [], placeholder = "Search symbol or company name..." }) {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [allSymbols, setAllSymbols] = useState([]);
  const inputRef = useRef(null);
  const BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";

  useEffect(() => {
    fetch(`${BASE_URL}/api/screen?min_score=0&limit=100`)
      .then(r => r.json())
      .then(d => { if (d.stocks) setAllSymbols(d.stocks.map(s => ({ symbol: s.symbol, name: s.company_name, sector: s.sector }))); })
      .catch(() => {});
  }, [BASE_URL]);

  const handleInput = (val) => {
    setQuery(val);
    if (!val.trim()) { setSuggestions([]); return; }
    const q = val.toUpperCase().trim();
    const matches = allSymbols
      .filter(s => (s.symbol.startsWith(q) || s.symbol.includes(q) || s.name?.toUpperCase().includes(q)) && !existingSymbols.includes(s.symbol))
      .slice(0, 8);
    setSuggestions(matches);
  };

  const handleSelect = (sym) => {
    onAdd(sym);
    setQuery("");
    setSuggestions([]);
    inputRef.current?.focus();
  };

  return (
    <div style={{ position: "relative" }}>
      <input ref={inputRef} value={query} onChange={e => handleInput(e.target.value)}
        onKeyDown={e => {
          if (e.key === "Enter" && query.trim()) { if (suggestions.length > 0) handleSelect(suggestions[0].symbol); else handleSelect(query.trim().toUpperCase()); }
          if (e.key === "Escape") setSuggestions([]);
        }}
        placeholder={placeholder} className="control-input" style={{ width: "100%" }}
        autoComplete="off" autoCapitalize="characters" />
      {suggestions.length > 0 && (
        <div style={{ position: "absolute", top: "100%", left: 0, right: 0, background: "white", border: "1.5px solid #bfdbfe", borderRadius: 10, boxShadow: "0 8px 20px rgba(37,99,235,0.12)", zIndex: 50, overflow: "hidden", marginTop: 4 }}>
          {suggestions.map(s => (
            <div key={s.symbol} onClick={() => handleSelect(s.symbol)}
              style={{ padding: "10px 14px", cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid #f1f5f9" }}
              onMouseEnter={e => e.currentTarget.style.background = "#eff6ff"}
              onMouseLeave={e => e.currentTarget.style.background = "white"}>
              <div>
                <span style={{ fontFamily: "JetBrains Mono, monospace", fontWeight: 700, color: "#1e40af", fontSize: 13 }}>{s.symbol}</span>
                <span style={{ fontSize: 12, color: "#64748b", marginLeft: 8 }}>{s.name?.split(" ").slice(0, 4).join(" ")}</span>
              </div>
              <span style={{ fontSize: 10, color: "#94a3b8" }}>{s.sector !== "Unknown" ? s.sector : ""}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState("watchlist");
  const [menuOpen, setMenuOpen] = useState(false);
  const [stocks, setStocks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedStock, setSelectedStock] = useState(null);

  const [watchlist, setWatchlist] = useState(() => {
    try { const s = localStorage.getItem("watchlist_v2"); return s ? JSON.parse(s) : DEFAULT_WATCHLIST; }
    catch { return DEFAULT_WATCHLIST; }
  });
  const [watchlistLoaded, setWatchlistLoaded] = useState(false);

  const [minScore, setMinScore] = useState(40);
  const [convictionFilter, setConvictionFilter] = useState("");
  const [selectedProfile, setSelectedProfile] = useState(null);
  const [profileDetail, setProfileDetail] = useState(null);
  const [portfolioProfile, setPortfolioProfile] = useState(null);
  const [capitalInput, setCapitalInput] = useState("");
  const [portfolio, setPortfolio] = useState(null);
  const [portfolioLoading, setPortfolioLoading] = useState(false);
  const [searchInput, setSearchInput] = useState("");

  const BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";

  useEffect(() => { localStorage.setItem("watchlist_v2", JSON.stringify(watchlist)); }, [watchlist]);

  const addToWatchlist = (sym) => { const s = sym.trim().toUpperCase(); if (s && !watchlist.includes(s)) setWatchlist(p => [...p, s]); };
  const removeFromWatchlist = (sym) => setWatchlist(p => p.filter(s => s !== sym));

  const runWatchlist = useCallback(async (symbols) => {
    if (!symbols?.length) return;
    setLoading(true); setError(null); setStocks([]);
    try { const d = await fetchWatchlist(symbols); setStocks(d.stocks || []); setWatchlistLoaded(true); }
    catch (e) { setError(e.message); } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    if (tab === "watchlist" && !watchlistLoaded && watchlist.length > 0) runWatchlist(watchlist);
  }, [tab, watchlistLoaded, watchlist, runWatchlist]);

  const runScreener = useCallback(async () => {
    setLoading(true); setError(null); setStocks([]);
    try { const d = await screenStocks({ minScore, conviction: convictionFilter || null, limit: 30 }); if (d.warming) setError(`⏳ ${d.message}`); else setStocks(d.stocks || []); }
    catch (e) { setError(e.message); } finally { setLoading(false); }
  }, [minScore, convictionFilter]);

  const runProfileScreen = useCallback(async (profileId) => {
    setLoading(true); setError(null); setStocks([]);
    try { const r = await fetch(`${BASE_URL}/api/screen?min_score=25&limit=30&profile=${profileId}`); const d = await r.json(); if (d.warming) setError(`⏳ ${d.message}`); else setStocks(d.stocks || []); }
    catch (e) { setError(e.message); } finally { setLoading(false); }
  }, [BASE_URL]);

  const runBuildPortfolio = useCallback(async () => {
    if (!portfolioProfile || !capitalInput) return;
    const capital = parseFloat(capitalInput.replace(/[^0-9.]/g, ""));
    if (!capital) { setError("Enter a valid capital amount"); return; }
    setPortfolioLoading(true); setError(null); setPortfolio(null);
    try { const d = await buildPortfolio(portfolioProfile.id, capital); setPortfolio(d); }
    catch (e) { setError(e.message); } finally { setPortfolioLoading(false); }
  }, [portfolioProfile, capitalInput]);

  const runSearch = useCallback(async (sym) => {
    const symbol = (sym || searchInput).trim().toUpperCase();
    if (!symbol) return;
    setLoading(true); setError(null);
    try { const s = await fetchStock(symbol); setSelectedStock(s); }
    catch (e) { setError(`Could not find "${symbol}"`); } finally { setLoading(false); }
  }, [searchInput]);

  const exportCSV = () => {
    if (!portfolio) return;
    const rows = [["Rank","Symbol","Company","Sector","Weight %","Amount","Shares","Price","Score"],
      ...portfolio.positions.map(p => [p.rank,p.symbol,p.company_name,p.sector,p.weight_pct,p.amount,p.shares,p.current_price,p.profile_score])];
    const blob = new Blob([rows.map(r=>r.join(",")).join("\n")], { type:"text/csv" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = `${portfolioProfile?.name}_portfolio.csv`; a.click();
  };

  const switchTab = (id) => { setTab(id); setMenuOpen(false); setError(null); };

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
            {TABS.map(({ id, label, icon: Icon }) => (
              <button key={id} className={`nav-tab ${tab === id ? "active" : ""}`} onClick={() => switchTab(id)}>
                <Icon size={14} />{label}
              </button>
            ))}
          </div>
          <div className="nav-right">
            <div className="mobile-tab-label">{TABS.find(t => t.id === tab)?.label}</div>
            <button className="hamburger-btn" onClick={() => setMenuOpen(o => !o)}>
              {menuOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
        </div>
        {menuOpen && (
          <div className="mobile-menu">
            {TABS.map(({ id, label, icon: Icon }) => (
              <button key={id} className={`mobile-menu-item ${tab === id ? "active" : ""}`} onClick={() => switchTab(id)}>
                <Icon size={16} /><span>{label}</span>
                {tab === id && <span style={{ marginLeft: "auto", color: "#2563eb" }}>●</span>}
              </button>
            ))}
          </div>
        )}
      </nav>

      <main className="main" onClick={() => menuOpen && setMenuOpen(false)}>
        <div className="method-banner">
          <div className="method-dot" />
          <span>Buffett (30%) · RJ Style (30%) · Quality/MF (25%) · Graham Value (15%) · {ALL_PROFILES_FLAT.length} investor profiles · Sector comparisons</span>
        </div>

        {tab === "watchlist" && (
          <>
            <div style={{ background:"white", border:"1.5px solid #e2e8f0", borderRadius:14, padding:"18px 20px", marginBottom:16, boxShadow:"0 1px 3px rgba(0,0,0,0.06)" }}>
              <div style={{ fontSize:12, fontWeight:700, color:"#2563eb", textTransform:"uppercase", letterSpacing:0.8, marginBottom:12, fontFamily:"JetBrains Mono, monospace" }}>
                My Watchlist · {watchlist.length} stocks
              </div>
              <div style={{ display:"flex", flexWrap:"wrap", gap:8, marginBottom:14 }}>
                {watchlist.map(sym => (
                  <div key={sym} style={{ display:"flex", alignItems:"center", gap:6, background:"#eff6ff", border:"1px solid #bfdbfe", borderRadius:20, padding:"4px 10px 4px 12px" }}>
                    <span style={{ fontFamily:"JetBrains Mono, monospace", fontSize:12, fontWeight:700, color:"#1e40af" }}>{sym}</span>
                    <button onClick={() => removeFromWatchlist(sym)} style={{ background:"none", border:"none", cursor:"pointer", color:"#94a3b8", padding:0, display:"flex" }}><X size={12} /></button>
                  </div>
                ))}
              </div>
              <StockSearch onAdd={addToWatchlist} existingSymbols={watchlist} placeholder="Add stock — type symbol or company name..." />
            </div>
            <button className="btn-primary" style={{ width:"100%", marginBottom:20, justifyContent:"center" }}
              onClick={() => runWatchlist(watchlist)} disabled={loading || watchlist.length === 0}>
              {loading ? <RefreshCw size={14} className="spin" /> : <TrendingUp size={14} />}
              Analyse Watchlist
            </button>
          </>
        )}

        {tab === "screener" && (
          <div className="control-row wrap" style={{ marginBottom:24 }}>
            <div className="control-group">
              <label className="control-label">Min Score: {minScore}</label>
              <input type="range" min={20} max={80} value={minScore} onChange={e => setMinScore(+e.target.value)} className="control-range" />
            </div>
            <div className="control-group">
              <label className="control-label">Conviction</label>
              <select className="control-select" value={convictionFilter} onChange={e => setConvictionFilter(e.target.value)}>
                <option value="">All</option>
                <option value="Strong Buy">Strong Buy</option>
                <option value="Buy">Buy</option>
                <option value="Watch">Watch</option>
              </select>
            </div>
            <button className="btn-primary" onClick={runScreener} disabled={loading}>
              {loading ? <RefreshCw size={14} className="spin" /> : <Filter size={14} />} Screen All Stocks
            </button>
          </div>
        )}

        {tab === "profiles" && !selectedProfile && (
          <div className="profiles-container" style={{ marginBottom:24 }}>
            {Object.entries(INVESTOR_PROFILES).map(([category, profiles]) => (
              <div key={category}>
                <div className="profile-category-header">
                  <span className="profile-category-label">{category}</span>
                  <div className="profile-category-line" />
                </div>
                <div className="profiles-grid">
                  {profiles.map(p => (
                    <div key={p.id} className="profile-card" style={{ "--profile-color": p.color }}
                      onClick={() => { setSelectedProfile(p); runProfileScreen(p.id); }}>
                      <div className="profile-avatar">{p.avatar}</div>
                      <div className="profile-info">
                        <div className="profile-name">{p.name}</div>
                        <div className="profile-focus">{p.focus}</div>
                      </div>
                      <div style={{ display:"flex", flexDirection:"column", alignItems:"flex-end", gap:6 }}>
                        <div className="profile-arrow">→</div>
                        <button style={{ fontSize:10, color:p.color, background:"transparent", border:"none", cursor:"pointer", fontWeight:600 }}
                          onClick={e => { e.stopPropagation(); setProfileDetail(p); }}>About</button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {tab === "profiles" && selectedProfile && (
          <div className="selected-profile-bar" style={{ marginBottom:24 }}>
            <button className="btn-back" onClick={() => { setSelectedProfile(null); setStocks([]); }}>← All</button>
            <div className="selected-profile-info">
              <span style={{ fontSize:24 }}>{selectedProfile.avatar}</span>
              <div>
                <div className="selected-profile-name">{selectedProfile.name}</div>
                <div className="selected-profile-focus">{selectedProfile.focus}</div>
              </div>
            </div>
            <button className="btn-secondary" onClick={() => setProfileDetail(selectedProfile)}>About</button>
            <button className="btn-secondary" onClick={() => { setTab("portfolio"); setPortfolioProfile(selectedProfile); }}>Build →</button>
            <button className="btn-primary" onClick={() => runProfileScreen(selectedProfile.id)} disabled={loading}>
              {loading ? <RefreshCw size={14} className="spin" /> : <RefreshCw size={14} />}
            </button>
          </div>
        )}

        {tab === "portfolio" && !portfolio && (
          <div className="control-row wrap" style={{ marginBottom:24 }}>
            <div className="control-group" style={{ width:"100%" }}>
              <label className="control-label">Investor Style</label>
              <select className="control-select" style={{ width:"100%" }} value={portfolioProfile?.id || ""}
                onChange={e => setPortfolioProfile(ALL_PROFILES_FLAT.find(x => x.id === e.target.value) || null)}>
                <option value="">Select an investor profile...</option>
                {Object.entries(INVESTOR_PROFILES).map(([cat, profiles]) => (
                  <optgroup key={cat} label={cat}>
                    {profiles.map(p => <option key={p.id} value={p.id}>{p.avatar} {p.name}</option>)}
                  </optgroup>
                ))}
              </select>
            </div>
            <div className="control-group" style={{ width:"100%" }}>
              <label className="control-label">Capital (₹)</label>
              <input className="control-input" style={{ width:"100%" }} value={capitalInput}
                onChange={e => setCapitalInput(e.target.value)} placeholder="e.g. 500000"
                onKeyDown={e => e.key === "Enter" && runBuildPortfolio()} />
            </div>
            {portfolioProfile && (
              <div style={{ width:"100%", display:"flex", alignItems:"center", gap:8, background:"#eff6ff", border:"1px solid #bfdbfe", borderRadius:8, padding:"10px 14px" }}>
                <span style={{ fontSize:22 }}>{portfolioProfile.avatar}</span>
                <div>
                  <div style={{ fontSize:13, fontWeight:700, color:"#1e40af" }}>{portfolioProfile.name}</div>
                  <div style={{ fontSize:11, color:"#3b82f6" }}>{portfolioProfile.focus}</div>
                </div>
              </div>
            )}
            <button className="btn-primary" style={{ width:"100%", justifyContent:"center" }}
              onClick={runBuildPortfolio} disabled={portfolioLoading || !portfolioProfile || !capitalInput}>
              {portfolioLoading ? <RefreshCw size={14} className="spin" /> : <BarChart2 size={14} />} Build Portfolio
            </button>
          </div>
        )}

        {tab === "portfolio" && portfolio && (
          <div style={{ display:"flex", gap:10, alignItems:"center", flexWrap:"wrap", marginBottom:20 }}>
            <button className="btn-back" onClick={() => setPortfolio(null)}>← Rebuild</button>
            <span style={{ fontSize:14, fontWeight:700, color:"#0f172a" }}>{portfolioProfile?.avatar} {portfolio.profile_name}</span>
            <button className="btn-secondary" style={{ marginLeft:"auto" }} onClick={exportCSV}><Download size={13} /> CSV</button>
          </div>
        )}

        {tab === "search" && (
          <div style={{ background:"white", border:"1.5px solid #e2e8f0", borderRadius:14, padding:"18px 20px", marginBottom:24, boxShadow:"0 1px 3px rgba(0,0,0,0.06)" }}>
            <div style={{ fontSize:12, fontWeight:700, color:"#2563eb", textTransform:"uppercase", letterSpacing:0.8, marginBottom:12, fontFamily:"JetBrains Mono, monospace" }}>
              Search Any NSE / BSE Stock
            </div>
            <StockSearch onAdd={sym => runSearch(sym)} existingSymbols={[]} placeholder="Type symbol or company name..." />
          </div>
        )}

        {error && <div className="error-banner"><AlertCircle size={14} />{error}</div>}

        {tab === "portfolio" && portfolio && <PortfolioOutput portfolio={portfolio} portfolioProfile={portfolioProfile} />}

        {loading && tab !== "portfolio" && (
          <div className="shimmer-grid">{[1,2,3,4,5,6].map(i => <div key={i} className="shimmer-card" style={{ animationDelay:`${i*0.08}s` }} />)}</div>
        )}

        {!loading && stocks.length > 0 && tab !== "portfolio" && (
          <>
            <div className="results-header">
              <span className="results-count">{stocks.length} stocks</span>
              <span className="results-sort">{selectedProfile ? `${selectedProfile.name} fit ↓` : "guru score ↓"}</span>
              {tab === "watchlist" && (
                <button style={{ marginLeft:"auto", fontSize:11, color:"#2563eb", background:"none", border:"none", cursor:"pointer", fontWeight:600 }}
                  onClick={() => runWatchlist(watchlist)}>↻ Refresh</button>
              )}
            </div>
            <div className="stock-grid">
              {stocks.map(s => <StockCard key={s.symbol} stock={s} onClick={setSelectedStock} activeProfile={selectedProfile?.id} />)}
            </div>
          </>
        )}

        {!loading && stocks.length === 0 && !error && tab === "screener" && (
          <div className="empty-state"><div className="empty-icon">📊</div><div className="empty-title">Set filters and click Screen All Stocks</div></div>
        )}
        {tab === "portfolio" && !portfolio && !portfolioLoading && !error && (
          <div className="empty-state"><div className="empty-icon">📋</div><div className="empty-title">Select a profile and enter your capital</div><div className="empty-sub">Builds a portfolio using that investor's exact philosophy</div></div>
        )}
      </main>

      {profileDetail && <ProfileDetailModal profile={profileDetail} onClose={() => setProfileDetail(null)}
        onBuildPortfolio={() => { setProfileDetail(null); setTab("portfolio"); setPortfolioProfile(profileDetail); }} />}
      {selectedStock && <StockDetail stock={selectedStock} onClose={() => setSelectedStock(null)} />}
    </div>
  );
}

function PortfolioOutput({ portfolio, portfolioProfile }) {
  return (
    <div className="portfolio-container">
      <div className="portfolio-header">
        <div style={{ display:"flex", alignItems:"center", gap:12, marginBottom:8 }}>
          <span style={{ fontSize:32 }}>{portfolioProfile?.avatar}</span>
          <div>
            <div className="portfolio-title">{portfolio.profile_name} Portfolio</div>
            <div className="portfolio-subtitle">{portfolio.profile_philosophy?.slice(0,120)}...</div>
          </div>
        </div>
      </div>
      <div className="portfolio-stats">
        {[
          { label:"Stocks", value:portfolio.total_stocks },
          { label:"Deployed", value:`₹${Number(portfolio.total_deployed).toLocaleString("en-IN")}` },
          { label:"Sectors", value:Object.keys(portfolio.sector_exposure||{}).length },
          { label:"Top Position", value:`${portfolio.positions[0]?.weight_pct}%` },
        ].map(s => (
          <div key={s.label} className="portfolio-stat">
            <div className="portfolio-stat-value">{s.value}</div>
            <div className="portfolio-stat-label">{s.label}</div>
          </div>
        ))}
      </div>
      <div className="portfolio-rationale"><strong>Why this portfolio:</strong> {portfolio.portfolio_rationale}</div>
      {portfolio.sector_exposure && (
        <div className="sector-breakdown">
          <div style={{ fontSize:11, fontWeight:700, color:"#2563eb", textTransform:"uppercase", letterSpacing:0.8, marginBottom:12 }}>Sector Allocation</div>
          {Object.entries(portfolio.sector_exposure).filter(([s]) => s !== "Unknown").sort((a,b) => b[1]-a[1]).map(([sector, pct]) => (
            <div key={sector} className="sector-row">
              <div className="sector-name">{sector}</div>
              <div className="sector-bar-track"><div className="sector-bar-fill" style={{ width:`${Math.min(pct,100)}%` }} /></div>
              <div className="sector-pct">{pct.toFixed(1)}%</div>
            </div>
          ))}
        </div>
      )}
      <div className="portfolio-positions">
        <div style={{ fontSize:11, fontWeight:700, color:"#2563eb", textTransform:"uppercase", letterSpacing:0.8, marginBottom:14 }}>Positions</div>
        <div style={{ overflowX:"auto" }}>
          <table style={{ width:"100%", borderCollapse:"collapse", fontSize:13, minWidth:460 }}>
            <thead>
              <tr style={{ background:"#f8faff" }}>
                {["#","Stock","Weight","Amount","Shares","Score"].map(h => (
                  <th key={h} style={{ padding:"8px 10px", textAlign:"left", fontSize:10, fontWeight:700, color:"#94a3b8", textTransform:"uppercase", borderBottom:"2px solid #e2e8f0" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {portfolio.positions.map(p => (
                <tr key={p.symbol} style={{ borderBottom:"1px solid #f1f5f9" }}>
                  <td style={{ padding:"10px 10px" }}>
                    <div style={{ width:24, height:24, borderRadius:"50%", background:"#eff6ff", display:"flex", alignItems:"center", justifyContent:"center", fontSize:11, fontWeight:700, color:"#2563eb" }}>{p.rank}</div>
                  </td>
                  <td style={{ padding:"10px 10px" }}>
                    <div style={{ fontFamily:"JetBrains Mono, monospace", fontWeight:700, color:"#1e40af", fontSize:13 }}>{p.symbol}</div>
                    <div style={{ fontSize:11, color:"#64748b" }}>{p.company_name?.split(" ").slice(0,3).join(" ")}</div>
                    <div style={{ fontSize:10, color:"#16a34a", fontStyle:"italic", marginTop:2 }}>{p.why_included}</div>
                  </td>
                  <td style={{ padding:"10px 10px", fontFamily:"JetBrains Mono, monospace", fontWeight:700, color:"#2563eb" }}>{p.weight_pct}%</td>
                  <td style={{ padding:"10px 10px", fontFamily:"JetBrains Mono, monospace", fontSize:12 }}>₹{Number(p.amount).toLocaleString("en-IN")}</td>
                  <td style={{ padding:"10px 10px", fontFamily:"JetBrains Mono, monospace", fontSize:11, color:"#64748b" }}>{p.shares}<br/><span style={{ fontSize:10 }}>@₹{p.current_price?.toFixed(0)}</span></td>
                  <td style={{ padding:"10px 10px", fontFamily:"JetBrains Mono, monospace", fontWeight:700, color:SCORE_COLOR(p.profile_score) }}>{p.profile_score}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div className="entry-strategy-box">
        <div className="entry-strategy-label">Entry Strategy</div>
        {portfolio.entry_strategy}
      </div>
      <div style={{ margin:"0 28px 28px", padding:"14px 18px", background:"#f8faff", border:"1px solid #e2e8f0", borderRadius:8, fontSize:12, color:"#475569" }}>
        <strong>Rebalancing:</strong> {portfolio.rebalance_note}
      </div>
    </div>
  );
}

function ProfileDetailModal({ profile, onClose, onBuildPortfolio }) {
  const BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";
  const [fp, setFp] = useState({});
  useEffect(() => {
    fetch(`${BASE_URL}/api/profiles`).then(r => r.json())
      .then(d => { if (d.profiles?.[profile.id]) setFp(d.profiles[profile.id]); }).catch(() => {});
  }, [profile.id, BASE_URL]);

  return (
    <div className="profile-modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="profile-modal">
        <div className="profile-modal-header">
          <div style={{ display:"flex", alignItems:"flex-start", justifyContent:"space-between" }}>
            <div style={{ display:"flex", alignItems:"center", gap:14 }}>
              <span style={{ fontSize:40 }}>{profile.avatar}</span>
              <div>
                <div style={{ fontSize:18, fontWeight:800, color:"#0f172a", marginBottom:4 }}>{profile.name}</div>
                <div style={{ display:"inline-block", padding:"3px 12px", background:"#eff6ff", border:"1px solid #bfdbfe", borderRadius:20, fontSize:12, fontWeight:600, color:profile.color||"#2563eb" }}>{profile.focus}</div>
              </div>
            </div>
            <button onClick={onClose} style={{ background:"#f8faff", border:"1px solid #e2e8f0", borderRadius:8, padding:8, cursor:"pointer", display:"flex", color:"#64748b" }}><X size={16} /></button>
          </div>
        </div>
        <div className="profile-modal-body">
          {[{key:"bio",title:"Background"},{key:"philosophy",title:"Philosophy"},{key:"what_he_looked_for",title:"What They Look For"},{key:"what_he_avoided",title:"What They Avoided"}]
            .map(({key,title}) => fp[key] && (
              <div key={key} className="profile-section">
                <div className="profile-section-title">{title}</div>
                <div className="profile-section-text">{fp[key]}</div>
              </div>
            ))}
          {fp.famous_investments?.length > 0 && (
            <div className="profile-section">
              <div className="profile-section-title">Famous Investments</div>
              <div className="profile-investments-list">{fp.famous_investments.map((inv,i) => <span key={i} className="profile-investment-tag">{inv}</span>)}</div>
            </div>
          )}
          {fp.signature_quote && (
            <div className="profile-section">
              <div className="profile-section-title">Signature Quote</div>
              <div className="profile-quote">"{fp.signature_quote}"</div>
            </div>
          )}
          <div style={{ marginTop:24 }}>
            <button className="btn-primary" style={{ width:"100%", justifyContent:"center" }} onClick={onBuildPortfolio}>
              <BarChart2 size={14} /> Build Portfolio in This Style
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
