const BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";

export const BASE = BASE_URL;

export async function fetchStock(symbol) {
  const r = await fetch(`${BASE_URL}/api/stock/${symbol}`);
  if (!r.ok) throw new Error(`Could not find ${symbol}`);
  return r.json();
}

export async function fetchWatchlist(symbols) {
  const r = await fetch(`${BASE_URL}/api/watchlist?symbols=${symbols.join(",")}`);
  if (!r.ok) throw new Error("Watchlist fetch failed");
  return r.json();
}

export async function screenStocks({ minScore = 40, sector, conviction, profile, limit = 30, minMarketCap, maxPE, minROE } = {}) {
  const p = new URLSearchParams({ min_score: minScore, limit });
  if (sector) p.set("sector", sector);
  if (conviction) p.set("conviction", conviction);
  if (profile) p.set("profile", profile);
  if (minMarketCap) p.set("min_market_cap", minMarketCap);
  if (maxPE) p.set("max_pe", maxPE);
  if (minROE) p.set("min_roe", minROE);
  const r = await fetch(`${BASE_URL}/api/screen?${p}`);
  if (!r.ok) throw new Error("Screener failed");
  return r.json();
}

export async function buildPortfolio(profileId, capital, limit = null) {
  const p = new URLSearchParams({ profile_id: profileId, capital });
  if (limit) p.set("limit", limit);
  const r = await fetch(`${BASE_URL}/api/portfolio/build?${p}`, { method: "POST" });
  if (!r.ok) throw new Error("Portfolio build failed");
  return r.json();
}

export async function fetchEducation(category = null) {
  const p = category ? `?category=${category}` : "";
  const r = await fetch(`${BASE_URL}/api/education${p}`);
  if (!r.ok) throw new Error("Education fetch failed");
  return r.json();
}

export async function fetchEducationItem(id) {
  const r = await fetch(`${BASE_URL}/api/education/${id}`);
  if (!r.ok) throw new Error("Article not found");
  return r.json();
}

export function fmtMarketCap(val) {
  if (!val) return "N/A";
  const cr = val / 1e7;
  if (cr >= 1e5) return `₹${(cr/1e5).toFixed(2)}L Cr`;
  if (cr >= 1e3) return `₹${(cr/1e3).toFixed(1)}K Cr`;
  return `₹${cr.toFixed(0)} Cr`;
}

export function fmtPct(val, alreadyPct = false) {
  if (val === null || val === undefined) return "N/A";
  const v = alreadyPct ? val : val * 100;
  return `${v.toFixed(1)}%`;
}

export function fmtNum(val, dec = 1) {
  if (val === null || val === undefined) return "N/A";
  return Number(val).toFixed(dec);
}

export function fmtPrice(val) {
  if (!val) return "N/A";
  return `₹${Number(val).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

export function fmtRupees(val) {
  if (!val) return "₹0";
  if (val >= 1e7) return `₹${(val/1e7).toFixed(2)} Cr`;
  if (val >= 1e5) return `₹${(val/1e5).toFixed(1)} L`;
  if (val >= 1e3) return `₹${(val/1e3).toFixed(1)}K`;
  return `₹${Math.round(val)}`;
}

export const SCORE_COLOR = (s) => {
  if (s >= 70) return "#0a7c4f";
  if (s >= 55) return "#047857";
  if (s >= 40) return "#b45309";
  if (s >= 25) return "#c2410c";
  return "#b91c1c";
};

export const SCORE_BG = (s) => {
  if (s >= 70) return "#d1fae5";
  if (s >= 55) return "#ecfdf5";
  if (s >= 40) return "#fef9c3";
  if (s >= 25) return "#ffedd5";
  return "#fee2e2";
};

export const METRIC_TOOLTIPS = {
  pe_ratio: "Price-to-Earnings: how much you pay per rupee of profit. Lower = cheaper.",
  pb_ratio: "Price-to-Book: market price vs net assets. Below 1 = below book value.",
  roe: "Return on Equity: profit generated per rupee of shareholder capital. Higher = better.",
  roce: "Return on Capital Employed: profit per rupee of all capital used. Best quality indicator.",
  operating_margins: "Operating Profit Margin: % of revenue that becomes operating profit.",
  net_margins: "Net Profit Margin: % of revenue that becomes final profit after all costs.",
  debt_to_equity: "Debt-to-Equity: debt relative to equity. Lower = safer balance sheet.",
  ev_ebitda: "Enterprise Value / EBITDA: professional valuation metric, capital-structure neutral.",
  peg_ratio: "PEG Ratio: P/E adjusted for growth. Below 1 = growth at reasonable price.",
  current_ratio: "Current Assets / Current Liabilities. Above 1.5 = good short-term health.",
  dividend_yield: "Annual dividend as % of stock price. Regular income to shareholders.",
  revenue_growth: "Year-over-year revenue growth rate.",
  earnings_growth: "Year-over-year earnings (profit) growth rate.",
  beta: "Volatility vs market. Beta > 1 = more volatile than Nifty.",
};
