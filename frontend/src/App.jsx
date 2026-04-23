import { useState, useCallback, useEffect } from "react";
import { Search, Filter, TrendingUp, List, RefreshCw, AlertCircle, Users, BarChart2, X, Download } from "lucide-react";
import StockCard from "./components/StockCard";
import StockDetail from "./components/StockDetail";
import { fetchStock, fetchWatchlist, screenStocks, buildPortfolio, formatRupees, SCORE_COLOR } from "./lib/api";
import "./App.css";

const DEFAULT_WATCHLIST = ["RELIANCE", "TCS", "HDFCBANK", "BAJFINANCE", "TITAN", "NESTLEIND", "PIDILITIND", "ASIANPAINT"];

const TABS = [
  { id: "watchlist", label: "Watchlist", icon: List },
  { id: "screener", label: "Screener", icon: Filter },
  { id: "profiles", label: "Investor Profiles", icon: Users },
  { id: "portfolio", label: "Portfolio Builder", icon: BarChart2 },
  { id: "search", label: "Search", icon: Search },
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

export default function App() {
  const [tab, setTab] = useState("watchlist");
  const [stocks, setStocks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedStock, setSelectedStock] = useState(null);
  const [cacheStatus, setCacheStatus] = useState(null);

  // Watchlist
  const [watchlistInput, setWatchlistInput] = useState(DEFAULT_WATCHLIST.join(", "));

  // Screener
  const [minScore, setMinScore] = useState(40);
  const [convictionFilter, setConvictionFilter] = useState("");

  // Profiles
  const [selectedProfile, setSelectedProfile] = useState(null);
  const [profileDetail, setProfileDetail] = useState(null); // profile bio modal

  // Portfolio
  const [portfolioProfile, setPortfolioProfile] = useState(null);
  const [capitalInput, setCapitalInput] = useState("");
  const [portfolio, setPortfolio] = useState(null);
  const [portfolioLoading, setPortfolioLoading] = useState(false);

  // Search
  const [searchInput, setSearchInput] = useState("");

  const BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";

  useEffect(() => {
    const check = async () => {
      try {
        const r = await fetch(`${BASE_URL}/api/cache/status`);
        const d = await r.json();
        setCacheStatus(d);
      } catch {}
    };
    check();
    const interval = setInterval(check, 10000);
    return () => clearInterval(interval);
  }, [BASE_URL]);

  const runWatchlist = useCallback(async () => {
    const symbols = watchlistInput.split(/[\s,]+/).map(s => s.trim().toUpperCase()).filter(Boolean);
    if (!symbols.length) return;
    setLoading(true); setError(null); setStocks([]);
    try {
      const data = await fetchWatchlist(symbols);
      setStocks(data.stocks || []);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, [watchlistInput]);

  const runScreener = useCallback(async () => {
    setLoading(true); setError(null); setStocks([]);
    try {
      const data = await screenStocks({ minScore, conviction: convictionFilter || null, limit: 30 });
      if (data.warming) setError(`⏳ ${data.message}`);
      else setStocks(data.stocks || []);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, [minScore, convictionFilter]);

  const runProfileScreen = useCallback(async (profileId) => {
    setLoading(true); setError(null); setStocks([]);
    try {
      const params = new URLSearchParams({ min_score: 25, limit: 30, profile: profileId });
      const r = await fetch(`${BASE_URL}/api/screen?${params}`);
      const data = await r.json();
      if (data.warming) setError(`⏳ ${data.message}`);
      else setStocks(data.stocks || []);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, [BASE_URL]);

  const runBuildPortfolio = useCallback(async () => {
    if (!portfolioProfile || !capitalInput) return;
    const capital = parseFloat(capitalInput.replace(/[^0-9.]/g, ""));
    if (!capital || capital <= 0) { setError("Please enter a valid capital amount"); return; }
    setPortfolioLoading(true); setError(null); setPortfolio(null);
    try {
      const data = await buildPortfolio(portfolioProfile.id, capital);
      setPortfolio(data);
    } catch (e) { setError(e.message); }
    finally { setPortfolioLoading(false); }
  }, [portfolioProfile, capitalInput]);

  const runSearch = useCallback(async () => {
    const symbol = searchInput.trim().toUpperCase();
    if (!symbol) return;
    setLoading(true); setError(null); setStocks([]);
    try {
      const stock = await fetchStock(symbol);
      setSelectedStock(stock);
    } catch (e) { setError(`Could not find "${symbol}" — check the NSE/BSE symbol`); }
    finally { setLoading(false); }
  }, [searchInput]);

  const exportPortfolioCSV = () => {
    if (!portfolio) return;
    const headers = ["Rank","Symbol","Company","Sector","Weight %","Amount (₹)","Shares","Price","Score","Why Included"];
    const rows = portfolio.positions.map(p => [
      p.rank, p.symbol, p.company_name, p.sector,
      p.weight_pct, p.amount, p.shares, p.current_price,
      p.profile_score, `"${p.why_included}"`,
    ]);
    const csv = [headers, ...rows].map(r => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `${portfolioProfile?.name}_portfolio.csv`; a.click();
  };

  return (
    <div className="app">
      {/* Nav */}
      <nav className="nav">
        <div className="nav-inner">
          <div className="logo">
            <div className="logo-icon">S</div>
            <div className="logo-text-wrap">
              <span className="logo-main">stocks<span className="logo-dot">.</span>ai</span>
              <span className="logo-sub">by relentless ais</span>
            </div>
          </div>
          <div className="nav-tabs">
            {TABS.map(({ id, label, icon: Icon }) => (
              <button key={id} className={`nav-tab ${tab === id ? "active" : ""}`} onClick={() => setTab(id)}>
                <Icon size={14} />{label}
              </button>
            ))}
          </div>
          <div className="nav-right">
            {cacheStatus && (
              <div className="cache-pill">
                <span className={`cache-dot ${cacheStatus.ready ? "ready" : "loading"}`} />
                {cacheStatus.ready
                  ? `${cacheStatus.count} stocks indexed`
                  : `Loading ${cacheStatus.progress?.done || 0}/${cacheStatus.progress?.total || 0}...`}
              </div>
            )}
            <div className="nav-meta">NSE · BSE</div>
          </div>
        </div>
      </nav>

      <main className="main">
        <div className="method-banner">
          <div className="method-dot" />
          <span>
            Scoring: Buffett (30%) · RJ Style (30%) · Quality/MF (25%) · Graham Value (15%) ·
            {" "}{ALL_PROFILES_FLAT.length} investor profiles · Sector averages included
          </span>
        </div>

        {/* Controls */}
        {tab === "watchlist" && (
          <div className="control-row" style={{ marginBottom: 24 }}>
            <input className="control-input wide" value={watchlistInput}
              onChange={e => setWatchlistInput(e.target.value)}
              placeholder="NSE/BSE symbols comma-separated (e.g. RELIANCE, TCS, HDFC)"
              onKeyDown={e => e.key === "Enter" && runWatchlist()} />
            <button className="btn-primary" onClick={runWatchlist} disabled={loading}>
              {loading ? <RefreshCw size={14} className="spin" /> : <TrendingUp size={14} />}
              Analyse
            </button>
          </div>
        )}

        {tab === "screener" && (
          <div className="control-row wrap" style={{ marginBottom: 24 }}>
            <div className="control-group">
              <label className="control-label">Min Score: {minScore}</label>
              <input type="range" min={20} max={80} value={minScore}
                onChange={e => setMinScore(+e.target.value)} className="control-range" />
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
              {loading ? <RefreshCw size={14} className="spin" /> : <Filter size={14} />}
              Screen All Stocks
            </button>
          </div>
        )}

        {tab === "profiles" && !selectedProfile && (
          <div className="profiles-container" style={{ marginBottom: 24 }}>
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
                      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
                        <div className="profile-arrow">→</div>
                        <button
                          style={{
                            fontSize: 10, color: p.color,
                            background: "transparent", border: "none",
                            cursor: "pointer", fontWeight: 600,
                          }}
                          onClick={e => { e.stopPropagation(); setProfileDetail(p); }}
                        >
                          About
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {tab === "profiles" && selectedProfile && (
          <div className="selected-profile-bar" style={{ marginBottom: 24 }}>
            <button className="btn-back" onClick={() => { setSelectedProfile(null); setStocks([]); }}>
              ← All profiles
            </button>
            <div className="selected-profile-info">
              <span style={{ fontSize: 24 }}>{selectedProfile.avatar}</span>
              <div>
                <div className="selected-profile-name">{selectedProfile.name}</div>
                <div className="selected-profile-focus">{selectedProfile.focus}</div>
              </div>
            </div>
            <button className="btn-secondary" onClick={() => setProfileDetail(selectedProfile)}>
              About this investor
            </button>
            <button className="btn-secondary" onClick={() => { setTab("portfolio"); setPortfolioProfile(selectedProfile); }}>
              Build portfolio →
            </button>
            <button className="btn-primary" onClick={() => runProfileScreen(selectedProfile.id)} disabled={loading}>
              {loading ? <RefreshCw size={14} className="spin" /> : <RefreshCw size={14} />}
              Refresh
            </button>
          </div>
        )}

        {tab === "portfolio" && (
          <div style={{ marginBottom: 24 }}>
            {!portfolio ? (
              <div className="control-row wrap">
                <div className="control-group">
                  <label className="control-label">Investor Style</label>
                  <select className="control-select" style={{ width: 260 }}
                    value={portfolioProfile?.id || ""}
                    onChange={e => {
                      const p = ALL_PROFILES_FLAT.find(x => x.id === e.target.value);
                      setPortfolioProfile(p || null);
                    }}>
                    <option value="">Select an investor profile...</option>
                    {Object.entries(INVESTOR_PROFILES).map(([cat, profiles]) => (
                      <optgroup key={cat} label={cat}>
                        {profiles.map(p => (
                          <option key={p.id} value={p.id}>{p.avatar} {p.name}</option>
                        ))}
                      </optgroup>
                    ))}
                  </select>
                </div>
                <div className="control-group">
                  <label className="control-label">Capital (₹)</label>
                  <input
                    className="control-input"
                    value={capitalInput}
                    onChange={e => setCapitalInput(e.target.value)}
                    placeholder="e.g. 1000000"
                    style={{ width: 180 }}
                    onKeyDown={e => e.key === "Enter" && runBuildPortfolio()}
                  />
                </div>
                {portfolioProfile && (
                  <div style={{
                    display: "flex", alignItems: "center", gap: 8,
                    background: "#eff6ff", border: "1px solid #bfdbfe",
                    borderRadius: 8, padding: "8px 14px", fontSize: 12, color: "#1e40af",
                  }}>
                    <span>{portfolioProfile.avatar}</span>
                    <span>{portfolioProfile.focus}</span>
                  </div>
                )}
                <button className="btn-primary" onClick={runBuildPortfolio}
                  disabled={portfolioLoading || !portfolioProfile || !capitalInput}>
                  {portfolioLoading ? <RefreshCw size={14} className="spin" /> : <BarChart2 size={14} />}
                  Build Portfolio
                </button>
              </div>
            ) : (
              <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                <button className="btn-back" onClick={() => setPortfolio(null)}>← Rebuild</button>
                <span style={{ fontSize: 14, fontWeight: 700, color: "#0f172a" }}>
                  {portfolioProfile?.avatar} {portfolio.profile_name} Portfolio
                </span>
                <span style={{ fontSize: 12, color: "#64748b" }}>
                  ₹{Number(capitalInput).toLocaleString("en-IN")} invested across {portfolio.total_stocks} stocks
                </span>
                <button className="btn-secondary" style={{ marginLeft: "auto" }} onClick={exportPortfolioCSV}>
                  <Download size={13} /> Export CSV
                </button>
              </div>
            )}
          </div>
        )}

        {tab === "search" && (
          <div className="control-row" style={{ marginBottom: 24 }}>
            <input className="control-input" value={searchInput}
              onChange={e => setSearchInput(e.target.value.toUpperCase())}
              placeholder="NSE/BSE symbol (e.g. BAJFINANCE)"
              onKeyDown={e => e.key === "Enter" && runSearch()} />
            <button className="btn-primary" onClick={runSearch} disabled={loading}>
              {loading ? <RefreshCw size={14} className="spin" /> : <Search size={14} />}
              Analyse
            </button>
          </div>
        )}

        {/* Error */}
        {error && <div className="error-banner"><AlertCircle size={14} />{error}</div>}

        {/* Portfolio output */}
        {tab === "portfolio" && portfolio && (
          <div className="portfolio-container">
            <div className="portfolio-header">
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
                <span style={{ fontSize: 32 }}>{portfolioProfile?.avatar}</span>
                <div>
                  <div className="portfolio-title">{portfolio.profile_name} Portfolio</div>
                  <div className="portfolio-subtitle">{portfolio.profile_philosophy?.slice(0, 120)}...</div>
                </div>
              </div>
            </div>

            {/* Stats */}
            <div className="portfolio-stats">
              {[
                { label: "Total Stocks", value: portfolio.total_stocks },
                { label: "Capital Deployed", value: `₹${Number(portfolio.total_deployed).toLocaleString("en-IN")}` },
                { label: "Sectors", value: Object.keys(portfolio.sector_exposure || {}).length },
                { label: "Top Position", value: `${portfolio.positions[0]?.weight_pct}%` },
              ].map(s => (
                <div key={s.label} className="portfolio-stat">
                  <div className="portfolio-stat-value">{s.value}</div>
                  <div className="portfolio-stat-label">{s.label}</div>
                </div>
              ))}
            </div>

            {/* Rationale */}
            <div className="portfolio-rationale">
              <strong>Why this portfolio:</strong> {portfolio.portfolio_rationale}
            </div>

            {/* Sector breakdown */}
            {portfolio.sector_exposure && Object.keys(portfolio.sector_exposure).length > 0 && (
              <div className="sector-breakdown">
                <div style={{ fontSize: 11, fontWeight: 700, color: "#2563eb", textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 12 }}>
                  Sector Allocation
                </div>
                {Object.entries(portfolio.sector_exposure)
                  .sort((a,b) => b[1]-a[1])
                  .map(([sector, pct]) => (
                    <div key={sector} className="sector-row">
                      <div className="sector-name">{sector}</div>
                      <div className="sector-bar-track">
                        <div className="sector-bar-fill" style={{ width: `${Math.min(pct, 100)}%` }} />
                      </div>
                      <div className="sector-pct">{pct.toFixed(1)}%</div>
                    </div>
                  ))}
              </div>
            )}

            {/* Positions table */}
            <div className="portfolio-positions">
              <div style={{ fontSize: 11, fontWeight: 700, color: "#2563eb", textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 14 }}>
                Positions
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "36px 1fr 80px 120px 80px 70px", gap: 12, padding: "0 0 10px", borderBottom: "2px solid #e2e8f0", marginBottom: 4 }}>
                {["#", "Stock", "Weight", "Amount", "Shares", "Score"].map(h => (
                  <div key={h} style={{ fontSize: 10, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: 0.5 }}>{h}</div>
                ))}
              </div>
              {portfolio.positions.map(p => (
                <div key={p.symbol} className="position-row">
                  <div className="position-rank">{p.rank}</div>
                  <div>
                    <div className="position-symbol">{p.symbol}</div>
                    <div className="position-company">{p.company_name?.split(" ").slice(0,4).join(" ")}</div>
                    <div className="position-reason">{p.why_included}</div>
                  </div>
                  <div className="position-weight">{p.weight_pct}%</div>
                  <div className="position-amount">₹{Number(p.amount).toLocaleString("en-IN")}</div>
                  <div className="position-shares">{p.shares} shares<br />
                    <span style={{ fontSize: 10, color: "#94a3b8" }}>@ ₹{p.current_price ? p.current_price.toFixed(0) : "N/A"}</span>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <span style={{
                      fontSize: 13, fontWeight: 700,
                      color: SCORE_COLOR(p.profile_score),
                      fontFamily: "JetBrains Mono, monospace",
                    }}>
                      {p.profile_score}
                    </span>
                  </div>
                </div>
              ))}
            </div>

            {/* Entry strategy */}
            <div className="entry-strategy-box">
              <div className="entry-strategy-label">Entry Strategy</div>
              {portfolio.entry_strategy}
            </div>

            {/* Rebalance note */}
            <div style={{ margin: "0 28px 28px", padding: "14px 18px", background: "#f8faff", border: "1px solid #e2e8f0", borderRadius: 8, fontSize: 12, color: "#475569" }}>
              <strong>Rebalancing:</strong> {portfolio.rebalance_note}
            </div>
          </div>
        )}

        {/* Loading shimmer */}
        {loading && tab !== "portfolio" && (
          <div className="shimmer-grid">
            {[1,2,3,4,5,6].map(i => <div key={i} className="shimmer-card" style={{ animationDelay: `${i*0.08}s` }} />)}
          </div>
        )}

        {/* Stock results */}
        {!loading && stocks.length > 0 && tab !== "portfolio" && (
          <>
            <div className="results-header">
              <span className="results-count">{stocks.length} stock{stocks.length !== 1 ? "s" : ""}</span>
              <span className="results-sort">
                {selectedProfile ? `sorted by ${selectedProfile.name} fit ↓` : "sorted by guru score ↓"}
              </span>
            </div>
            <div className="stock-grid">
              {stocks.map(s => (
                <StockCard key={s.symbol} stock={s} onClick={setSelectedStock} activeProfile={selectedProfile?.id} />
              ))}
            </div>
          </>
        )}

        {/* Empty state */}
        {!loading && stocks.length === 0 && !error && !["profiles","portfolio"].includes(tab) && (
          <div className="empty-state">
            <div className="empty-icon">📊</div>
            <div className="empty-title">
              {tab === "watchlist" ? "Enter symbols above and click Analyse" :
               tab === "screener" ? "Set filters and click Screen All Stocks" :
               "Search an NSE/BSE symbol"}
            </div>
            {tab === "watchlist" && <div className="empty-sub">Default list loaded — just hit Analyse</div>}
          </div>
        )}

        {tab === "portfolio" && !portfolio && !portfolioLoading && !error && (
          <div className="empty-state">
            <div className="empty-icon">📋</div>
            <div className="empty-title">Select an investor profile and enter your capital</div>
            <div className="empty-sub">The app will build a portfolio using that investor's philosophy and position sizing style</div>
          </div>
        )}
      </main>

      {/* Profile detail modal */}
      {profileDetail && (
        <ProfileDetailModal profile={profileDetail} onClose={() => setProfileDetail(null)}
          onBuildPortfolio={() => { setProfileDetail(null); setTab("portfolio"); setPortfolioProfile(profileDetail); }} />
      )}

      {/* Stock detail modal */}
      {selectedStock && <StockDetail stock={selectedStock} onClose={() => setSelectedStock(null)} />}
    </div>
  );
}

function ProfileDetailModal({ profile, onClose, onBuildPortfolio }) {
  const BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";
  const [fullProfile, setFullProfile] = useState(null);

  useEffect(() => {
    fetch(`${BASE_URL}/api/profiles`)
      .then(r => r.json())
      .then(d => {
        if (d.profiles && d.profiles[profile.id]) {
          setFullProfile(d.profiles[profile.id]);
        }
      })
      .catch(() => {});
  }, [profile.id, BASE_URL]);

  const fp = fullProfile || {};

  return (
    <div className="profile-modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="profile-modal">
        <div className="profile-modal-header">
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
              <span style={{ fontSize: 40 }}>{profile.avatar}</span>
              <div>
                <div style={{ fontSize: 20, fontWeight: 800, color: "#0f172a", marginBottom: 4 }}>{profile.name}</div>
                <div style={{
                  display: "inline-block", padding: "3px 12px",
                  background: "#eff6ff", border: "1px solid #bfdbfe",
                  borderRadius: 20, fontSize: 12, fontWeight: 600,
                  color: profile.color || "#2563eb",
                }}>
                  {profile.focus}
                </div>
              </div>
            </div>
            <button onClick={onClose} style={{
              background: "#f8faff", border: "1px solid #e2e8f0",
              borderRadius: 8, padding: 8, cursor: "pointer", display: "flex", color: "#64748b",
            }}>
              <X size={16} />
            </button>
          </div>
        </div>

        <div className="profile-modal-body">
          {fp.bio && (
            <div className="profile-section">
              <div className="profile-section-title">Background</div>
              <div className="profile-section-text">{fp.bio}</div>
            </div>
          )}

          {fp.philosophy && (
            <div className="profile-section">
              <div className="profile-section-title">Investment Philosophy</div>
              <div className="profile-section-text">{fp.philosophy}</div>
            </div>
          )}

          {fp.what_he_looked_for && (
            <div className="profile-section">
              <div className="profile-section-title">What They Look For</div>
              <div className="profile-section-text">{fp.what_he_looked_for}</div>
            </div>
          )}

          {fp.what_he_avoided && (
            <div className="profile-section">
              <div className="profile-section-title">What They Avoided</div>
              <div className="profile-section-text">{fp.what_he_avoided}</div>
            </div>
          )}

          {fp.famous_investments && fp.famous_investments.length > 0 && (
            <div className="profile-section">
              <div className="profile-section-title">Famous Investments</div>
              <div className="profile-investments-list">
                {fp.famous_investments.map((inv, i) => (
                  <span key={i} className="profile-investment-tag">{inv}</span>
                ))}
              </div>
            </div>
          )}

          {fp.signature_quote && (
            <div className="profile-section">
              <div className="profile-section-title">Signature Quote</div>
              <div className="profile-quote">"{fp.signature_quote}"</div>
            </div>
          )}

          {fp.rebalance_style && (
            <div className="profile-section">
              <div className="profile-section-title">Rebalancing Style</div>
              <div className="profile-section-text">{fp.rebalance_style}</div>
            </div>
          )}

          <div style={{ display: "flex", gap: 10, marginTop: 24 }}>
            <button className="btn-primary" style={{ flex: 1 }} onClick={onBuildPortfolio}>
              <BarChart2 size={14} /> Build Portfolio in This Style
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
