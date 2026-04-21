const BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";

export async function fetchStock(symbol) {
  const res = await fetch(`${BASE_URL}/api/stock/${symbol}`);
  if (!res.ok) throw new Error(`Failed to fetch ${symbol}`);
  return res.json();
}

export async function fetchWatchlist(symbols) {
  const joined = symbols.join(",");
  const res = await fetch(`${BASE_URL}/api/watchlist?symbols=${joined}`);
  if (!res.ok) throw new Error("Watchlist fetch failed");
  return res.json();
}

export async function screenStocks({ minScore = 50, sector = null, conviction = null, limit = 20 } = {}) {
  const params = new URLSearchParams({ min_score: minScore, limit });
  if (sector) params.set("sector", sector);
  if (conviction) params.set("conviction", conviction);
  const res = await fetch(`${BASE_URL}/api/screen?${params}`);
  if (!res.ok) throw new Error("Screener failed");
  return res.json();
}

export function formatMarketCap(val) {
  if (!val) return "N/A";
  const cr = val / 1e7;
  if (cr >= 1e5) return `₹${(cr / 1e5).toFixed(2)}L Cr`;
  if (cr >= 1e3) return `₹${(cr / 1e3).toFixed(1)}K Cr`;
  return `₹${cr.toFixed(0)} Cr`;
}

export function formatPct(val) {
  if (val === null || val === undefined) return "N/A";
  const pct = val < 1 && val > -1 ? val * 100 : val;
  return `${pct.toFixed(1)}%`;
}

export function formatNum(val, decimals = 1) {
  if (val === null || val === undefined) return "N/A";
  return val.toFixed(decimals);
}

export const CONVICTION_COLORS = {
  "Strong Buy": { bg: "#0a2e1a", text: "#22c55e", border: "#16a34a" },
  "Buy":        { bg: "#0f2a1a", text: "#4ade80", border: "#15803d" },
  "Watch":      { bg: "#1c1a08", text: "#facc15", border: "#ca8a04" },
  "Neutral":    { bg: "#1a1a1a", text: "#9ca3af", border: "#4b5563" },
  "Avoid":      { bg: "#2a0a0a", text: "#f87171", border: "#dc2626" },
};

export const SCORE_COLOR = (score) => {
  if (score >= 75) return "#22c55e";
  if (score >= 60) return "#4ade80";
  if (score >= 45) return "#facc15";
  if (score >= 30) return "#fb923c";
  return "#f87171";
};
