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

export async function screenStocks({ minScore = 40, sector = null, conviction = null, limit = 30 } = {}) {
  const params = new URLSearchParams({ min_score: minScore, limit });
  if (sector) params.set("sector", sector);
  if (conviction) params.set("conviction", conviction);
  const res = await fetch(`${BASE_URL}/api/screen?${params}`);
  if (!res.ok) throw new Error("Screener failed");
  return res.json();
}

export async function buildPortfolio(profileId, capital, limit = null) {
  const params = new URLSearchParams({ profile_id: profileId, capital });
  if (limit) params.set("limit", limit);
  const res = await fetch(`${BASE_URL}/api/portfolio/build?${params}`, { method: "POST" });
  if (!res.ok) throw new Error("Portfolio build failed");
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
  const pct = Math.abs(val) < 2 ? val * 100 : val;
  return `${pct.toFixed(1)}%`;
}

export function formatNum(val, decimals = 1) {
  if (val === null || val === undefined) return "N/A";
  return val.toFixed(decimals);
}

export function formatRupees(val) {
  if (!val) return "₹0";
  if (val >= 1e7) return `₹${(val/1e7).toFixed(2)} Cr`;
  if (val >= 1e5) return `₹${(val/1e5).toFixed(1)} L`;
  if (val >= 1e3) return `₹${(val/1e3).toFixed(1)}K`;
  return `₹${val.toFixed(0)}`;
}

export const SCORE_COLOR = (score) => {
  if (score >= 70) return "#16a34a";
  if (score >= 55) return "#059669";
  if (score >= 40) return "#d97706";
  if (score >= 25) return "#ea580c";
  return "#dc2626";
};

export const SCORE_BG = (score) => {
  if (score >= 70) return "#dcfce7";
  if (score >= 55) return "#d1fae5";
  if (score >= 40) return "#fef9c3";
  if (score >= 25) return "#ffedd5";
  return "#fee2e2";
};

export const BASE = BASE_URL;
