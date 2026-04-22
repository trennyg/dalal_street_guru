import { useState, useCallback, useEffect } from "react";
import { Search, Filter, TrendingUp, List, RefreshCw, AlertCircle, Users } from "lucide-react";
import StockCard from "./components/StockCard";
import StockDetail from "./components/StockDetail";
import { fetchStock, fetchWatchlist, screenStocks } from "./lib/api";
import "./App.css";

const DEFAULT_WATCHLIST = ["RELIANCE", "TCS", "HDFCBANK", "BAJFINANCE", "TITAN", "NESTLEIND", "PIDILITIND", "ASIANPAINT"];

const TABS = [
  { id: "watchlist", label: "Watchlist", icon: List },
  { id: "screener", label: "Screener", icon: Filter },
  { id: "profiles", label: "Investor Profiles", icon: Users },
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
    { id: "marcellus", name: "Marcellus (Saurabh Mukherjea)", avatar: "🔬", focus: "Forensic Quality Only", color: "#06b6d4" },
    { id: "motilal_qglp", name: "Motilal Oswal QGLP", avatar: "📊", focus: "Quality + Growth + Longevity + Price", color: "#f97316" },
    { id: "nippon_smallcap", name: "Nippon India Small Cap", avatar: "🌱", focus: "High Growth Small Caps", color: "#22d3ee" },
    { id: "mirae_asset", name: "Mirae Asset India", avatar: "🏆", focus: "Quality Growth Large Cap", color: "#a3e635" },
    { id: "hdfc_mf", name: "HDFC Mutual Fund", avatar: "🏦", focus: "Value + Quality Blend", color: "#fb923c" },
    { id: "anand_rathi", name: "Anand Rathi Wealth", avatar: "⚡", focus: "Wealth Preservation + Growth", color: "#fbbf24" },
    { id: "white_oak", name: "White Oak Capital", avatar: "🌳", focus: "Earnings Quality Growth", color: "#86efac" },
    { id: "enam", name: "Enam / Vallabh Bhansali", avatar: "🛡️", focus: "Forensic + Long Term", color: "#c4b5fd" },
    { id: "ask_investment", name: "ASK Investment Managers", avatar: "💰", focus: "Quality Large Cap PMS", color: "#fdba74" },
    { id: "carnelian", name: "Carnelian Asset (Vikas Khemani)", avatar: "💫", focus: "Emerging Sector Leaders", color: "#67e8f9" },
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
  const [watchlistInput, setWatchlistInput] = useState(DEFAULT_WATCHLIST.join(", "));
  const [minScore, setMinScore] = useState(40);
  const [convictionFilter, setConvictionFilter] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [selectedProfile, setSelectedProfile] = useState(null);

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

  return (
    <div className="app">
      <nav className="nav">
        <div className="nav-inner">
          <div className="logo">
            <span className="logo-mark">◈</span>
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
            <div className="nav-meta">NSE · BSE · India</div>
          </div>
        </div>
      </nav>

      <main className="main">
        <div className="method-banner">
          <span>◈</span>
          <span>Scoring: Buffett (30%) · RJ Style (30%) · Quality/MF (25%) · Graham Value (15%) · {ALL_PROFILES_FLAT.length} investor profiles · NSE + BSE universe</span>
        </div>

        <div className="controls">
          {tab === "watchlist" && (
            <div className="control-row">
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
            <div className="control-row wrap">
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
            <div className="profiles-container">
              {Object.entries(INVESTOR_PROFILES).map(([category, profiles]) => (
                <div key={category} className="profile-category">
                  <div className="profile-category-label">{category}</div>
                  <div className="profiles-grid">
                    {profiles.map(p => (
                      <div key={p.id} className="profile-card"
                        style={{ "--profile-color": p.color }}
                        onClick={() => { setSelectedProfile(p); runProfileScreen(p.id); }}>
                        <div className="profile-avatar">{p.avatar}</div>
                        <div className="profile-info">
                          <div className="profile-name">{p.name}</div>
                          <div className="profile-focus">{p.focus}</div>
                        </div>
                        <div className="profile-arrow">→</div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          {tab === "profiles" && selectedProfile && (
            <div className="control-row">
              <button className="btn-back" onClick={() => { setSelectedProfile(null); setStocks([]); }}>
                ← All profiles
              </button>
              <div className="selected-profile-badge" style={{ "--profile-color": selectedProfile.color }}>
                <span>{selectedProfile.avatar}</span>
                <span>{selectedProfile.name}</span>
                <span className="profile-focus-small">{selectedProfile.focus}</span>
              </div>
              <button className="btn-primary" onClick={() => runProfileScreen(selectedProfile.id)} disabled={loading}>
                {loading ? <RefreshCw size={14} className="spin" /> : <RefreshCw size={14} />}
                Refresh
              </button>
            </div>
          )}

          {tab === "search" && (
            <div className="control-row">
              <input className="control-input" value={searchInput}
                onChange={e => setSearchInput(e.target.value.toUpperCase())}
                placeholder="NSE/BSE symbol (e.g. BAJFINANCE, WIPRO)"
                onKeyDown={e => e.key === "Enter" && runSearch()} />
              <button className="btn-primary" onClick={runSearch} disabled={loading}>
                {loading ? <RefreshCw size={14} className="spin" /> : <Search size={14} />}
                Analyse
              </button>
            </div>
          )}
        </div>

        {error && <div className="error-banner"><AlertCircle size={14} />{error}</div>}

        {loading && (
          <div className="shimmer-grid">
            {[1,2,3,4,5,6].map(i => <div key={i} className="shimmer-card" style={{ animationDelay: `${i*0.08}s` }} />)}
          </div>
        )}

        {!loading && stocks.length > 0 && (
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

        {!loading && stocks.length === 0 && !error && tab !== "profiles" && (
          <div className="empty-state">
            <div className="empty-icon">◈</div>
            <div className="empty-title">
              {tab === "watchlist" ? "Enter symbols above and click Analyse" :
               tab === "screener" ? "Set filters and click Screen All Stocks" :
               "Search an NSE/BSE stock symbol"}
            </div>
            {tab === "watchlist" && <div className="empty-sub">Default list loaded — just hit Analyse</div>}
          </div>
        )}
      </main>

      {selectedStock && <StockDetail stock={selectedStock} onClose={() => setSelectedStock(null)} />}
    </div>
  );
}
