import { useState, useCallback } from "react";
import { Search, Filter, TrendingUp, List, RefreshCw, AlertCircle, BookOpen } from "lucide-react";
import StockCard from "./components/StockCard";
import StockDetail from "./components/StockDetail";
import { fetchStock, fetchWatchlist, screenStocks } from "./lib/api";
import "./App.css";

const DEFAULT_WATCHLIST = ["RELIANCE", "TCS", "HDFCBANK", "BAJFINANCE", "TITAN", "NESTLEIND", "PIDILITIND", "ASIANPAINT"];

const TABS = [
  { id: "watchlist", label: "Watchlist", icon: List },
  { id: "screener", label: "Screener", icon: Filter },
  { id: "search", label: "Search", icon: Search },
];

export default function App() {
  const [tab, setTab] = useState("watchlist");
  const [stocks, setStocks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedStock, setSelectedStock] = useState(null);

  // Watchlist state
  const [watchlistInput, setWatchlistInput] = useState(DEFAULT_WATCHLIST.join(", "));

  // Screener state
  const [minScore, setMinScore] = useState(45);
  const [sectorFilter, setSectorFilter] = useState("");
  const [convictionFilter, setConvictionFilter] = useState("");

  // Search state
  const [searchInput, setSearchInput] = useState("");

  const runWatchlist = useCallback(async () => {
    const symbols = watchlistInput.split(/[\s,]+/).map(s => s.trim().toUpperCase()).filter(Boolean);
    if (!symbols.length) return;
    setLoading(true);
    setError(null);
    setStocks([]);
    try {
      const data = await fetchWatchlist(symbols);
      setStocks(data.stocks || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [watchlistInput]);

  const runScreener = useCallback(async () => {
    setLoading(true);
    setError(null);
    setStocks([]);
    try {
      const data = await screenStocks({
        minScore,
        sector: sectorFilter || null,
        conviction: convictionFilter || null,
        limit: 20,
      });
      setStocks(data.stocks || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [minScore, sectorFilter, convictionFilter]);

  const runSearch = useCallback(async () => {
    const symbol = searchInput.trim().toUpperCase();
    if (!symbol) return;
    setLoading(true);
    setError(null);
    setStocks([]);
    try {
      const stock = await fetchStock(symbol);
      setSelectedStock({ ...stock, scoring: stock.scoring });
    } catch (e) {
      setError(`Could not find "${symbol}" — check the NSE symbol`);
    } finally {
      setLoading(false);
    }
  }, [searchInput]);

  return (
    <div className="app">
      {/* Nav */}
      <nav className="nav">
        <div className="nav-inner">
          <div className="logo">
            <span className="logo-mark">◈</span>
            <span className="logo-text">Dalal Street <span className="logo-accent">Guru</span></span>
          </div>
          <div className="nav-tabs">
            {TABS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                className={`nav-tab ${tab === id ? "active" : ""}`}
                onClick={() => setTab(id)}
              >
                <Icon size={14} />
                {label}
              </button>
            ))}
          </div>
          <div className="nav-meta">NSE · India</div>
        </div>
      </nav>

      <main className="main">
        {/* Methodology banner */}
        <div className="method-banner">
          <BookOpen size={12} />
          <span>Scoring: Buffett (30%) · RJ Style (30%) · Quality/MF (25%) · Graham Value (15%)</span>
        </div>

        {/* Controls */}
        <div className="controls">
          {tab === "watchlist" && (
            <div className="control-row">
              <input
                className="control-input wide"
                value={watchlistInput}
                onChange={e => setWatchlistInput(e.target.value)}
                placeholder="Enter NSE symbols, comma-separated (e.g. RELIANCE, TCS, HDFC)"
                onKeyDown={e => e.key === "Enter" && runWatchlist()}
              />
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
                <input
                  type="range" min={20} max={80} value={minScore}
                  onChange={e => setMinScore(+e.target.value)}
                  className="control-range"
                />
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
                Screen NSE Top 40
              </button>
              <div className="screener-note">⚡ Takes ~45s — fetching live data for each stock</div>
            </div>
          )}

          {tab === "search" && (
            <div className="control-row">
              <input
                className="control-input"
                value={searchInput}
                onChange={e => setSearchInput(e.target.value.toUpperCase())}
                placeholder="NSE symbol (e.g. BAJFINANCE)"
                onKeyDown={e => e.key === "Enter" && runSearch()}
              />
              <button className="btn-primary" onClick={runSearch} disabled={loading}>
                {loading ? <RefreshCw size={14} className="spin" /> : <Search size={14} />}
                Analyse
              </button>
            </div>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="error-banner">
            <AlertCircle size={14} />
            {error}
          </div>
        )}

        {/* Loading shimmer */}
        {loading && (
          <div className="shimmer-grid">
            {[1,2,3,4,5,6].map(i => (
              <div key={i} className="shimmer-card" style={{ animationDelay: `${i * 0.08}s` }} />
            ))}
          </div>
        )}

        {/* Results */}
        {!loading && stocks.length > 0 && (
          <>
            <div className="results-header">
              <span className="results-count">{stocks.length} stock{stocks.length !== 1 ? "s" : ""}</span>
              <span className="results-sort">sorted by guru score ↓</span>
            </div>
            <div className="stock-grid">
              {stocks.map(s => (
                <StockCard key={s.symbol} stock={s} onClick={setSelectedStock} />
              ))}
            </div>
          </>
        )}

        {/* Empty state */}
        {!loading && stocks.length === 0 && !error && (
          <div className="empty-state">
            <div className="empty-icon">◈</div>
            <div className="empty-title">
              {tab === "watchlist" ? "Enter symbols above and click Analyse" :
               tab === "screener" ? "Set filters and click Screen" :
               "Search an NSE stock symbol"}
            </div>
            <div className="empty-sub">
              {tab === "watchlist" ? "Default list loaded — just hit Analyse" : ""}
            </div>
          </div>
        )}
      </main>

      {/* Detail modal */}
      {selectedStock && (
        <StockDetail
          stock={selectedStock}
          onClose={() => setSelectedStock(null)}
        />
      )}
    </div>
  );
}
