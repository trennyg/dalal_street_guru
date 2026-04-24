import { useState, useCallback, useEffect, useRef } from "react";
import { Search, Filter, TrendingUp, List, RefreshCw, AlertCircle, Users, BarChart2, X, Download, Menu, BookOpen } from "lucide-react";
import StockCard from "./components/StockCard";
import StockDetail from "./components/StockDetail";
import { fetchStock, fetchWatchlist, screenStocks, buildPortfolio, fetchEducation, fetchEducationItem, SCORE_COLOR } from "./lib/api";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";
import "./App.css";

const DEFAULT_WATCHLIST = ["RELIANCE","TCS","HDFCBANK","BAJFINANCE","TITAN","NESTLEIND","PIDILITIND","ASIANPAINT"];

const TABS = [
  { id: "watchlist", label: "Watchlist", icon: List },
  { id: "screener", label: "Screener", icon: Filter },
  { id: "profiles", label: "Investor Profiles", icon: Users },
  { id: "portfolio", label: "Portfolio Builder", icon: BarChart2 },
  { id: "learn", label: "Learn", icon: BookOpen },
  { id: "search", label: "Search", icon: Search },
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
const PIE_COLORS = ["#1a56db","#0ea5e9","#06b6d4","#10b981","#84cc16","#f59e0b","#f97316","#ec4899","#8b5cf6","#64748b","#e11d48","#7c3aed"];

// ─── Autocomplete search ──────────────────────────────────────────────────────
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

  const handleInput = val => {
    setQuery(val);
    if (!val.trim()) { setSuggestions([]); return; }
    const q = val.toUpperCase().trim();
    setSuggestions(
      allSymbols.filter(s =>
        (s.symbol.startsWith(q) || s.symbol.includes(q) || s.name?.toUpperCase().includes(q))
        && !existingSymbols.includes(s.symbol)
      ).slice(0, 8)
    );
  };

  const handleSelect = sym => {
    onAdd(sym);
    setQuery("");
    setSuggestions([]);
    inputRef.current?.focus();
  };

  return (
    <div className="autocomplete-wrap">
      <input
        ref={inputRef}
        value={query}
        onChange={e => handleInput(e.target.value)}
        onKeyDown={e => {
          if (e.key === "Enter" && query.trim()) handleSelect(suggestions[0]?.symbol || query.trim().toUpperCase());
          if (e.key === "Escape") setSuggestions([]);
        }}
        placeholder={placeholder}
        className="control-input"
        style={{ width: "100%" }}
        autoComplete="off"
        autoCapitalize="characters"
      />
      {suggestions.length > 0 && (
        <div className="autocomplete-dropdown">
          {suggestions.map(s => (
            <div key={s.symbol} className="autocomplete-item" onClick={() => handleSelect(s.symbol)}>
              <div>
                <span className="autocomplete-symbol">{s.symbol}</span>
                <span className="autocomplete-name">{s.name?.split(" ").slice(0, 4).join(" ")}</span>
              </div>
              <span className="autocomplete-sector">{s.sector !== "Unknown" ? s.sector : ""}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Main App ─────────────────────────────────────────────────────────────────
export default function App() {
  const [tab, setTab] = useState("watchlist");
  const [menuOpen, setMenuOpen] = useState(false);
  const [stocks, setStocks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedStock, setSelectedStock] = useState(null);

  const [watchlist, setWatchlist] = useState(() => {
    try { const s = localStorage.getItem("watchlist_v3"); return s ? JSON.parse(s) : DEFAULT_WATCHLIST; }
    catch { return DEFAULT_WATCHLIST; }
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

  const [learnContent, setLearnContent] = useState([]);
  const [learnCategory, setLearnCategory] = useState("all");
  const [learnArticle, setLearnArticle] = useState(null);
  const [learnLoading, setLearnLoading] = useState(false);

  const BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";

  useEffect(() => { localStorage.setItem("watchlist_v3", JSON.stringify(watchlist)); }, [watchlist]);

  const addToWatchlist = sym => { const s = sym.trim().toUpperCase(); if (s && !watchlist.includes(s)) setWatchlist(p => [...p, s]); };
  const removeFromWatchlist = sym => setWatchlist(p => p.filter(s => s !== sym));

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
    try {
      const params = new URLSearchParams({ min_score: minScore, limit: 30 });
      if (convictionFilter) params.set("conviction", convictionFilter);
      if (maxPE) params.set("max_pe", maxPE);
      if (minROE) params.set("min_roe", minROE);
      const r = await fetch(`${BASE_URL}/api/screen?${params}`);
      const d = await r.json();
      if (d.warming) setError(d.message);
      else setStocks(d.stocks || []);
    } catch (e) { setError(e.message); } finally { setLoading(false); }
  }, [minScore, convictionFilter, maxPE, minROE, BASE_URL]);

  const runProfileScreen = useCallback(async (profileId) => {
    setLoading(true); setError(null); setStocks([]);
    try {
      const r = await fetch(`${BASE_URL}/api/screen?min_score=25&limit=30&profile=${profileId}`);
      const d = await r.json();
      if (d.warming) setError(d.message);
      else setStocks(d.stocks || []);
    } catch (e) { setError(e.message); } finally { setLoading(false); }
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
    const symbol = (sym || "").trim().toUpperCase();
    if (!symbol) return;
    setLoading(true); setError(null);
    try { const s = await fetchStock(symbol); setSelectedStock(s); }
    catch (e) { setError(`Could not find "${symbol}"`); } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    if (tab !== "learn") return;
    setLearnLoading(true);
    fetchEducation(learnCategory === "all" ? null : learnCategory)
      .then(d => setLearnContent(d.content || []))
      .catch(() => {})
      .finally(() => setLearnLoading(false));
  }, [tab, learnCategory]);

  const openLearnArticle = async (id) => {
    try { const d = await fetchEducationItem(id); setLearnArticle(d); }
    catch {}
  };

  const exportCSV = () => {
    if (!portfolio) return;
    const rows = [
      ["Rank","Symbol","Company","Sector","Weight%","Amount","Shares","Price","Score"],
      ...portfolio.positions.map(p => [p.rank,p.symbol,p.company_name,p.sector,p.weight_pct,p.amount,p.shares,p.current_price,p.profile_score])
    ];
    const blob = new Blob([rows.map(r => r.join(",")).join("\n")], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${portfolioProfile?.name}_portfolio.csv`;
    a.click();
  };

  const switchTab = id => { setTab(id); setMenuOpen(false); setError(null); };

  return (
    <div className="app">
      {/* ── Nav ── */}
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
          <div className="nav-right" />
        </div>

        {/* Mobile row — separate line below logo */}
        <div className="nav-mobile-row">
          <button className="hamburger-btn" onClick={() => setMenuOpen(o => !o)}>
            {menuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
          <span className="mobile-tab-label">{TABS.find(t => t.id === tab)?.label}</span>
        </div>

        {menuOpen && (
          <div className="mobile-menu">
            {TABS.map(({ id, label, icon: Icon }) => (
              <button key={id} className={`mobile-menu-item ${tab === id ? "active" : ""}`} onClick={() => switchTab(id)}>
                <Icon size={16} /><span>{label}</span>
                {tab === id && <span style={{ marginLeft: "auto", color: "var(--blue)" }}>●</span>}
              </button>
            ))}
          </div>
        )}
      </nav>

      <main className="main" onClick={() => menuOpen && setMenuOpen(false)}>

        {/* ── WATCHLIST ── */}
        {tab === "watchlist" && (
          <>
            <div className="page-header">
              <div className="page-title">My Watchlist</div>
              <div className="page-subtitle">Track and analyse your selected stocks</div>
            </div>
            <div className="control-card">
              <div style={{ fontSize: 10, fontWeight: 700, color: "var(--blue)", textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 12, fontFamily: "var(--font-mono)" }}>
                {watchlist.length} stocks tracked
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 14 }}>
                {watchlist.map(sym => (
                  <div key={sym} className="watchlist-chip">
                    <span className="watchlist-chip-label">{sym}</span>
                    <button className="watchlist-chip-remove" onClick={() => removeFromWatchlist(sym)}><X size={11} /></button>
                  </div>
                ))}
              </div>
              <StockSearch onAdd={addToWatchlist} existingSymbols={watchlist} placeholder="Add stock — type symbol or company name..." />
            </div>
            <button className="btn-primary" style={{ width: "100%", justifyContent: "center", marginBottom: 22 }}
              onClick={() => runWatchlist(watchlist)} disabled={loading || watchlist.length === 0}>
              {loading ? <RefreshCw size={14} className="spin" /> : <TrendingUp size={14} />}
              Analyse Watchlist
            </button>
          </>
        )}

        {/* ── SCREENER ── */}
        {tab === "screener" && (
          <>
            <div className="page-header">
              <div className="page-title">Stock Screener</div>
              <div className="page-subtitle">Filter all indexed stocks using quality, value and growth criteria</div>
            </div>
            <div className="control-card" style={{ marginBottom: 22 }}>
              <div className="control-row">
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
                <div className="control-group">
                  <label className="control-label">Max P/E</label>
                  <input className="control-input" style={{ width: 90 }} value={maxPE} onChange={e => setMaxPE(e.target.value)} placeholder="e.g. 30" />
                </div>
                <div className="control-group">
                  <label className="control-label">Min ROE %</label>
                  <input className="control-input" style={{ width: 90 }} value={minROE} onChange={e => setMinROE(e.target.value)} placeholder="e.g. 15" />
                </div>
                <button className="btn-primary" onClick={runScreener} disabled={loading}>
                  {loading ? <RefreshCw size={14} className="spin" /> : <Filter size={14} />} Screen
                </button>
              </div>
            </div>
          </>
        )}

        {/* ── PROFILES ── */}
        {tab === "profiles" && !selectedProfile && (
          <>
            <div className="page-header">
              <div className="page-title">Investor Profiles</div>
              <div className="page-subtitle">Screen stocks through the lens of legendary investors</div>
            </div>
            <div className="profiles-container">
              {Object.entries(INVESTOR_PROFILES).map(([category, profiles], ci) => (
                <div key={category}>
                  <div className="profile-category-header">
                    <span className="profile-category-label">{category}</span>
                    <div className="profile-category-line" />
                  </div>
                  <div className="profiles-grid">
                    {profiles.map((p, pi) => (
                      <div key={p.id} className="profile-card"
                        style={{ "--profile-color": p.color, animationDelay: `${(ci * 5 + pi) * 0.04}s` }}
                        onClick={() => { setSelectedProfile(p); runProfileScreen(p.id); }}>
                        <div className="profile-avatar-badge"
                          style={{ width: 40, height: 40, background: p.color, color: "white", fontSize: 10, fontWeight: 700, fontFamily: "var(--font-mono)", borderRadius: 9 }}>
                          {p.avatar}
                        </div>
                        <div className="profile-info">
                          <div className="profile-name">{p.name}</div>
                          <div className="profile-focus">{p.focus}</div>
                        </div>
                        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 5 }}>
                          <div className="profile-arrow">→</div>
                          <button style={{ fontSize: 10, color: p.color, background: "transparent", border: "none", cursor: "pointer", fontWeight: 600 }}
                            onClick={e => { e.stopPropagation(); setProfileDetail(p); }}>About</button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}

        {tab === "profiles" && selectedProfile && (
          <div className="selected-profile-bar">
            <button className="btn-back" onClick={() => { setSelectedProfile(null); setStocks([]); }}>← All</button>
            <div className="selected-profile-info">
              <div className="profile-avatar-badge"
                style={{ width: 36, height: 36, background: selectedProfile.color, color: "white", fontSize: 10, fontWeight: 700, fontFamily: "var(--font-mono)", borderRadius: 9, display: "flex", alignItems: "center", justifyContent: "center" }}>
                {selectedProfile.avatar}
              </div>
              <div>
                <div className="selected-profile-name">{selectedProfile.name}</div>
                <div className="selected-profile-focus">{selectedProfile.focus}</div>
              </div>
            </div>
            <button className="btn-secondary" onClick={() => setProfileDetail(selectedProfile)}>About</button>
            <button className="btn-secondary" onClick={() => { setTab("portfolio"); setPortfolioProfile(selectedProfile); }}>Build Portfolio →</button>
            <button className="btn-primary" onClick={() => runProfileScreen(selectedProfile.id)} disabled={loading}>
              {loading ? <RefreshCw size={14} className="spin" /> : <RefreshCw size={14} />}
            </button>
          </div>
        )}

        {/* ── PORTFOLIO ── */}
        {tab === "portfolio" && !portfolio && (
          <>
            <div className="page-header">
              <div className="page-title">Portfolio Builder</div>
              <div className="page-subtitle">Build a position-sized portfolio in the style of a legendary investor</div>
            </div>
            <div className="control-card" style={{ marginBottom: 22 }}>
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <div className="control-group">
                  <label className="control-label">Investor Style</label>
                  <select className="control-select" style={{ width: "100%" }} value={portfolioProfile?.id || ""}
                    onChange={e => setPortfolioProfile(ALL_PROFILES_FLAT.find(x => x.id === e.target.value) || null)}>
                    <option value="">Select an investor profile...</option>
                    {Object.entries(INVESTOR_PROFILES).map(([cat, profiles]) => (
                      <optgroup key={cat} label={cat}>
                        {profiles.map(p => <option key={p.id} value={p.id}>{p.avatar} — {p.name}</option>)}
                      </optgroup>
                    ))}
                  </select>
                </div>
                <div className="control-group">
                  <label className="control-label">Capital (INR)</label>
                  <input className="control-input" style={{ width: "100%" }} value={capitalInput}
                    onChange={e => setCapitalInput(e.target.value)} placeholder="e.g. 500000"
                    onKeyDown={e => e.key === "Enter" && runBuildPortfolio()} />
                </div>
                {portfolioProfile && (
                  <div style={{ display: "flex", alignItems: "center", gap: 10, background: "var(--blue-light)", border: "1px solid var(--blue-mid)", borderRadius: "var(--radius)", padding: "12px 16px" }}>
                    <div style={{ width: 38, height: 38, borderRadius: 9, background: portfolioProfile.color, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 800, color: "white", fontFamily: "var(--font-mono)", flexShrink: 0 }}>
                      {portfolioProfile.avatar}
                    </div>
                    <div>
                      <div style={{ fontSize: 14, fontWeight: 700, color: "var(--text)" }}>{portfolioProfile.name}</div>
                      <div style={{ fontSize: 11, color: "var(--blue)", fontFamily: "var(--font-mono)" }}>{portfolioProfile.focus}</div>
                    </div>
                    <button className="btn-ghost" style={{ marginLeft: "auto" }} onClick={() => setProfileDetail(portfolioProfile)}>
                      About this investor →
                    </button>
                  </div>
                )}
                <button className="btn-primary" style={{ justifyContent: "center" }}
                  onClick={runBuildPortfolio} disabled={portfolioLoading || !portfolioProfile || !capitalInput}>
                  {portfolioLoading ? <RefreshCw size={14} className="spin" /> : <BarChart2 size={14} />}
                  Build Portfolio
                </button>
              </div>
            </div>
          </>
        )}

        {tab === "portfolio" && portfolio && (
          <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap", marginBottom: 20 }}>
            <button className="btn-back" onClick={() => setPortfolio(null)}>← Rebuild</button>
            <span style={{ fontSize: 15, fontWeight: 700, color: "var(--text)", fontFamily: "var(--font-display)" }}>
              {portfolio.profile_name} Portfolio
            </span>
            <button className="btn-secondary" style={{ marginLeft: "auto" }} onClick={exportCSV}>
              <Download size={13} /> Export CSV
            </button>
          </div>
        )}

        {/* ── LEARN ── */}
        {tab === "learn" && !learnArticle && (
          <>
            <div className="page-header">
              <div className="page-title">Learn Investing</div>
              <div className="page-subtitle">Every metric explained. Every strategy decoded. Built for Indian investors.</div>
            </div>
            <div style={{ display: "flex", gap: 8, marginBottom: 20, flexWrap: "wrap" }}>
              {["all","metrics","strategies","beginners"].map(cat => (
                <button key={cat} onClick={() => setLearnCategory(cat)} style={{
                  padding: "6px 16px", borderRadius: 20, border: "1.5px solid",
                  borderColor: learnCategory === cat ? "var(--blue)" : "var(--border)",
                  background: learnCategory === cat ? "var(--blue-light)" : "var(--surface)",
                  color: learnCategory === cat ? "var(--blue)" : "var(--text2)",
                  fontSize: 13, fontWeight: 600, cursor: "pointer", textTransform: "capitalize",
                  transition: "var(--transition)",
                }}>
                  {cat === "all" ? "All Topics" : cat}
                </button>
              ))}
            </div>
            {learnLoading ? (
              <div className="shimmer-grid">{[1,2,3,4,5,6].map(i => <div key={i} className="shimmer-card" style={{ height: 160, animationDelay: `${i*0.07}s` }} />)}</div>
            ) : (
              <div className="learn-grid">
                {learnContent.map((item, i) => (
                  <div key={item.id} className="learn-card" style={{ animationDelay: `${i*0.05}s` }} onClick={() => openLearnArticle(item.id)}>
                    <div className={`learn-category-pill learn-category-${item.category}`}>{item.category}</div>
                    <div className="learn-card-title">{item.title}</div>
                    <div className="learn-card-summary">{item.summary}</div>
                    <div className="learn-card-meta">
                      <span className={`difficulty-badge difficulty-${item.difficulty}`}>{item.difficulty}</span>
                      <span>{item.read_time} min read</span>
                      {item.example_stock && <span>· {item.example_stock}</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {tab === "learn" && learnArticle && (
          <div>
            <button className="btn-back" style={{ marginBottom: 20 }} onClick={() => setLearnArticle(null)}>← Back to Learn</button>
            <div style={{ maxWidth: 680 }}>
              <div className={`learn-category-pill learn-category-${learnArticle.category}`} style={{ marginBottom: 12 }}>{learnArticle.category}</div>
              <h1 style={{ fontFamily: "var(--font-display)", fontSize: 26, fontWeight: 700, color: "var(--text)", letterSpacing: "-0.5px", marginBottom: 8, lineHeight: 1.3 }}>
                {learnArticle.title}
              </h1>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 24 }}>
                <span className={`difficulty-badge difficulty-${learnArticle.difficulty}`}>{learnArticle.difficulty}</span>
                <span style={{ fontSize: 12, color: "var(--text3)", fontFamily: "var(--font-mono)" }}>{learnArticle.read_time} min read</span>
              </div>
              <div style={{ fontSize: 16, color: "var(--blue)", fontStyle: "italic", lineHeight: 1.6, marginBottom: 24, paddingLeft: 16, borderLeft: "3px solid var(--blue)" }}>
                {learnArticle.summary}
              </div>
              <div style={{ fontSize: 14.5, color: "var(--text2)", lineHeight: 1.8, marginBottom: 24, whiteSpace: "pre-line" }}>
                {learnArticle.content}
              </div>
              {learnArticle.example_stock && learnArticle.example_text && (
                <div style={{ background: "var(--blue-light)", border: "1px solid var(--blue-mid)", borderRadius: "var(--radius)", padding: "16px 20px", marginBottom: 20 }}>
                  <div style={{ fontSize: 10, fontWeight: 700, color: "var(--blue)", textTransform: "uppercase", letterSpacing: 0.8, fontFamily: "var(--font-mono)", marginBottom: 8 }}>
                    Real Example: {learnArticle.example_stock}
                  </div>
                  <div style={{ fontSize: 13.5, color: "var(--text)", lineHeight: 1.65 }}>{learnArticle.example_text}</div>
                </div>
              )}
              {learnArticle.watch_out && (
                <div style={{ background: "var(--amber-light)", border: "1px solid #fcd34d", borderRadius: "var(--radius)", padding: "16px 20px", marginBottom: 20 }}>
                  <div style={{ fontSize: 10, fontWeight: 700, color: "var(--amber)", textTransform: "uppercase", letterSpacing: 0.8, fontFamily: "var(--font-mono)", marginBottom: 8 }}>Watch Out For</div>
                  <div style={{ fontSize: 13.5, color: "var(--text)", lineHeight: 1.65 }}>{learnArticle.watch_out}</div>
                </div>
              )}
              {learnArticle.related?.length > 0 && (
                <div>
                  <div style={{ fontSize: 10, fontWeight: 700, color: "var(--text3)", textTransform: "uppercase", letterSpacing: 0.8, fontFamily: "var(--font-mono)", marginBottom: 10 }}>Related Topics</div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                    {learnArticle.related.map(r => (
                      <button key={r} onClick={() => openLearnArticle(r)} style={{ padding: "5px 14px", borderRadius: 20, border: "1.5px solid var(--border2)", background: "var(--surface)", fontSize: 12.5, fontWeight: 500, color: "var(--text2)", cursor: "pointer", transition: "var(--transition)" }}>
                        {r.replace(/-/g, " ")} →
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── SEARCH ── */}
        {tab === "search" && (
          <>
            <div className="page-header">
              <div className="page-title">Search Any Stock</div>
              <div className="page-subtitle">NSE and BSE listed companies — full analysis</div>
            </div>
            <div className="control-card" style={{ marginBottom: 22 }}>
              <StockSearch onAdd={sym => runSearch(sym)} existingSymbols={[]} placeholder="Type NSE/BSE symbol or company name..." />
            </div>
          </>
        )}

        {/* Error */}
        {error && <div className="error-banner"><AlertCircle size={14} />{error}</div>}

        {/* Portfolio output */}
        {tab === "portfolio" && portfolio && <PortfolioOutput portfolio={portfolio} portfolioProfile={portfolioProfile} />}

        {/* Loading shimmer */}
        {loading && tab !== "portfolio" && (
          <div className="shimmer-grid">
            {[1,2,3,4,5,6].map(i => <div key={i} className="shimmer-card" style={{ animationDelay: `${i*0.07}s` }} />)}
          </div>
        )}

        {/* Stock results grid */}
        {!loading && stocks.length > 0 && tab !== "portfolio" && (
          <>
            <div className="results-header">
              <span className="results-count">{stocks.length} stocks</span>
              <span className="results-sort">{selectedProfile ? `${selectedProfile.name} fit ↓` : "sector-relative score ↓"}</span>
              {tab === "watchlist" && (
                <button className="btn-ghost" style={{ marginLeft: "auto" }} onClick={() => runWatchlist(watchlist)}>
                  <RefreshCw size={12} /> Refresh
                </button>
              )}
            </div>
            <div className="stock-grid">
              {stocks.map((s, i) => (
                <div key={s.symbol} className="fade-up" style={{ animationDelay: `${i * 0.04}s` }}>
                  <StockCard stock={s} onClick={setSelectedStock} activeProfile={selectedProfile?.id} />
                </div>
              ))}
            </div>
          </>
        )}

        {/* Empty states */}
        {!loading && stocks.length === 0 && !error && tab === "screener" && (
          <div className="empty-state">
            <div className="empty-icon"><Filter size={26} /></div>
            <div className="empty-title">Set filters and click Screen</div>
            <div className="empty-sub">Filter across all indexed stocks with quality, value and growth criteria</div>
          </div>
        )}
        {tab === "portfolio" && !portfolio && !portfolioLoading && !error && (
          <div className="empty-state">
            <div className="empty-icon"><BarChart2 size={26} /></div>
            <div className="empty-title">Select a profile and enter your capital</div>
            <div className="empty-sub">Builds a portfolio using that investor's exact philosophy and position sizing</div>
          </div>
        )}
      </main>

      {profileDetail && (
        <ProfileModal profile={profileDetail} onClose={() => setProfileDetail(null)}
          onBuildPortfolio={() => { setProfileDetail(null); setTab("portfolio"); setPortfolioProfile(profileDetail); }} />
      )}
      {selectedStock && <StockDetail stock={selectedStock} onClose={() => setSelectedStock(null)} />}
    </div>
  );
}

// ─── Portfolio Output ─────────────────────────────────────────────────────────
function PortfolioOutput({ portfolio, portfolioProfile }) {
  const stockData = portfolio.positions.map((p, i) => ({
    name: p.symbol, value: p.weight_pct, color: PIE_COLORS[i % PIE_COLORS.length],
  }));
  const sectorData = Object.entries(portfolio.sector_exposure || {})
    .filter(([s]) => s !== "Unknown")
    .sort((a, b) => b[1] - a[1])
    .map(([name, value], i) => ({ name, value, color: PIE_COLORS[i % PIE_COLORS.length] }));

  return (
    <div className="portfolio-container">
      <div className="portfolio-header">
        <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 10 }}>
          <div style={{ width: 46, height: 46, borderRadius: 11, background: portfolioProfile?.color || "var(--blue)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 800, color: "white", fontFamily: "var(--font-mono)", flexShrink: 0 }}>
            {portfolioProfile?.avatar}
          </div>
          <div>
            <div className="portfolio-title">{portfolio.profile_name} Portfolio</div>
            <div className="portfolio-subtitle">{portfolio.profile_philosophy?.slice(0, 130)}...</div>
          </div>
        </div>
      </div>

      <div className="portfolio-stats">
        {[
          { label: "Stocks", value: portfolio.total_stocks },
          { label: "Deployed", value: `₹${Number(portfolio.total_deployed).toLocaleString("en-IN")}` },
          { label: "Sectors", value: Object.keys(portfolio.sector_exposure || {}).filter(s => s !== "Unknown").length },
          { label: "Top Hold", value: `${portfolio.positions[0]?.weight_pct}%` },
        ].map(s => (
          <div key={s.label} className="portfolio-stat">
            <div className="portfolio-stat-value">{s.value}</div>
            <div className="portfolio-stat-label">{s.label}</div>
          </div>
        ))}
      </div>

      <div className="portfolio-rationale">
        <strong>Why this portfolio: </strong>{portfolio.portfolio_rationale}
      </div>

      {/* Pie charts */}
      <div className="portfolio-charts">
        <div className="chart-card">
          <div className="chart-title">Stock Allocation</div>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={stockData} cx="50%" cy="50%" innerRadius={48} outerRadius={78} dataKey="value" paddingAngle={2}>
                {stockData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
              </Pie>
              <Tooltip formatter={v => [`${v}%`, "Weight"]} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
              <Legend iconType="circle" iconSize={7} formatter={v => <span style={{ fontSize: 10, color: "var(--text2)" }}>{v}</span>} />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="chart-card">
          <div className="chart-title">Sector Allocation</div>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={sectorData} cx="50%" cy="50%" innerRadius={48} outerRadius={78} dataKey="value" paddingAngle={2}>
                {sectorData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
              </Pie>
              <Tooltip formatter={v => [`${v}%`, "Sector"]} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
              <Legend iconType="circle" iconSize={7} formatter={v => <span style={{ fontSize: 10, color: "var(--text2)" }}>{v.length > 16 ? v.slice(0, 16) + "…" : v}</span>} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Sector bars */}
      {sectorData.length > 0 && (
        <div className="sector-breakdown">
          <div style={{ fontSize: 10, fontWeight: 700, color: "var(--blue)", textTransform: "uppercase", letterSpacing: 0.8, fontFamily: "var(--font-mono)", marginBottom: 12 }}>Sector Exposure</div>
          {sectorData.map(({ name, value }) => (
            <div key={name} className="sector-row">
              <div className="sector-name">{name}</div>
              <div className="sector-bar-track"><div className="sector-bar-fill" style={{ width: `${Math.min(value, 100)}%` }} /></div>
              <div className="sector-pct">{value.toFixed(1)}%</div>
            </div>
          ))}
        </div>
      )}

      {/* Positions table */}
      <div className="portfolio-positions">
        <div style={{ fontSize: 10, fontWeight: 700, color: "var(--blue)", textTransform: "uppercase", letterSpacing: 0.8, fontFamily: "var(--font-mono)", marginBottom: 14 }}>Positions</div>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 480 }}>
            <thead>
              <tr style={{ background: "var(--surface2)" }}>
                {["#","Stock","Weight","Amount","Shares","Score"].map(h => (
                  <th key={h} style={{ padding: "8px 10px", textAlign: "left", fontSize: 9.5, fontWeight: 700, color: "var(--text3)", textTransform: "uppercase", letterSpacing: 0.5, borderBottom: "2px solid var(--border)" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {portfolio.positions.map(p => (
                <tr key={p.symbol} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td style={{ padding: "11px 10px" }}>
                    <div style={{ width: 24, height: 24, borderRadius: "50%", background: "var(--blue-light)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700, color: "var(--blue)" }}>{p.rank}</div>
                  </td>
                  <td style={{ padding: "11px 10px" }}>
                    <div style={{ fontFamily: "var(--font-mono)", fontWeight: 600, color: "var(--blue)", fontSize: 13 }}>{p.symbol}</div>
                    <div style={{ fontSize: 11, color: "var(--text2)", marginTop: 1 }}>{p.company_name?.split(" ").slice(0, 3).join(" ")}</div>
                    <div style={{ fontSize: 10, color: "var(--green)", fontStyle: "italic", marginTop: 2 }}>{p.why_included}</div>
                  </td>
                  <td style={{ padding: "11px 10px", fontFamily: "var(--font-mono)", fontWeight: 700, color: "var(--blue)", fontSize: 13 }}>{p.weight_pct}%</td>
                  <td style={{ padding: "11px 10px", fontFamily: "var(--font-mono)", fontSize: 12 }}>₹{Number(p.amount).toLocaleString("en-IN")}</td>
                  <td style={{ padding: "11px 10px", fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text2)" }}>
                    {p.shares}<br /><span style={{ fontSize: 10 }}>@₹{p.current_price?.toFixed(0)}</span>
                  </td>
                  <td style={{ padding: "11px 10px", fontFamily: "var(--font-mono)", fontWeight: 700, color: SCORE_COLOR(p.profile_score), fontSize: 13 }}>{p.profile_score}</td>
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
      <div style={{ margin: "0 28px 28px", padding: "14px 18px", background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", fontSize: 13, color: "var(--text2)" }}>
        <strong>Rebalancing:</strong> {portfolio.rebalance_note}
      </div>
    </div>
  );
}

// ─── Profile Modal ────────────────────────────────────────────────────────────
function ProfileModal({ profile, onClose, onBuildPortfolio }) {
  const BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";
  const [fp, setFp] = useState({});

  useEffect(() => {
    fetch(`${BASE_URL}/api/profiles`)
      .then(r => r.json())
      .then(d => { if (d.profiles?.[profile.id]) setFp(d.profiles[profile.id]); })
      .catch(() => {});
  }, [profile.id, BASE_URL]);

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <div className="modal-header">
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
              <div style={{ width: 52, height: 52, borderRadius: 12, background: profile.color || "var(--blue)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, fontWeight: 800, color: "white", fontFamily: "var(--font-mono)", flexShrink: 0 }}>
                {profile.avatar}
              </div>
              <div>
                <div style={{ fontFamily: "var(--font-display)", fontSize: 18, fontWeight: 700, color: "var(--text)", marginBottom: 5 }}>{profile.name}</div>
                <div style={{ display: "inline-block", padding: "3px 12px", background: "var(--blue-light)", border: "1px solid var(--blue-mid)", borderRadius: 20, fontSize: 12, fontWeight: 600, color: profile.color || "var(--blue)" }}>
                  {profile.focus}
                </div>
              </div>
            </div>
            <button onClick={onClose} style={{ background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: 8, cursor: "pointer", display: "flex", color: "var(--text2)" }}><X size={16} /></button>
          </div>
        </div>
        <div className="modal-body">
          {[
            { key: "bio", title: "Background" },
            { key: "philosophy", title: "Investment Philosophy" },
            { key: "what_he_looked_for", title: "What They Look For" },
            { key: "what_he_avoided", title: "What They Avoid" },
          ].map(({ key, title }) => fp[key] && (
            <div key={key} className="modal-section">
              <div className="modal-section-title">{title}</div>
              <div className="modal-section-text">{fp[key]}</div>
            </div>
          ))}
          {fp.famous_investments?.length > 0 && (
            <div className="modal-section">
              <div className="modal-section-title">Famous Investments</div>
              <div className="investment-tags">
                {fp.famous_investments.map((inv, i) => <span key={i} className="investment-tag">{inv}</span>)}
              </div>
            </div>
          )}
          {fp.signature_quote && (
            <div className="modal-section">
              <div className="modal-section-title">Signature Quote</div>
              <div className="quote-block">"{fp.signature_quote}"</div>
            </div>
          )}
          {fp.rebalance_style && (
            <div className="modal-section">
              <div className="modal-section-title">Rebalancing Style</div>
              <div className="modal-section-text">{fp.rebalance_style}</div>
            </div>
          )}
          <div style={{ marginTop: 24 }}>
            <button className="btn-primary" style={{ width: "100%", justifyContent: "center" }} onClick={onBuildPortfolio}>
              <BarChart2 size={14} /> Build Portfolio in This Style
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
