import { useState, useEffect } from "react";
import { X, ExternalLink, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { fetchStock, SCORE_COLOR, SCORE_BG, formatNum, formatPct, formatMarketCap } from "../lib/api";

const CONVICTION_CLASS = {
  "Strong Buy": "conviction-strong-buy",
  "Buy": "conviction-buy",
  "Watch": "conviction-watch",
  "Neutral": "conviction-neutral",
  "Avoid": "conviction-avoid",
};

function MetricRow({ label, value, sectorAvg, lowerBetter = false, format = "num" }) {
  const display = format === "pct" ? formatPct(value) : format === "num" ? (value ? formatNum(value) : "N/A") : value;
  const avgDisplay = format === "pct" ? formatPct(sectorAvg) : format === "num" ? (sectorAvg ? formatNum(sectorAvg) : "—") : sectorAvg;

  let status = null;
  let statusColor = "#94a3b8";
  let StatusIcon = Minus;

  if (value !== null && value !== undefined && sectorAvg) {
    const isGood = lowerBetter ? value < sectorAvg : value > sectorAvg * 1.05;
    const isBad = lowerBetter ? value > sectorAvg * 1.1 : value < sectorAvg * 0.9;
    if (isGood) { statusColor = "#16a34a"; StatusIcon = TrendingUp; status = "better"; }
    else if (isBad) { statusColor = "#dc2626"; StatusIcon = TrendingDown; status = "worse"; }
    else { statusColor = "#d97706"; StatusIcon = Minus; status = "inline"; }
  }

  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "1fr 1fr 1fr",
      gap: 8,
      padding: "10px 0",
      borderBottom: "1px solid #f1f5f9",
      alignItems: "center",
    }}>
      <div style={{ fontSize: 12, color: "#64748b", fontWeight: 500 }}>{label}</div>
      <div style={{ fontSize: 13, fontFamily: "JetBrains Mono, monospace", fontWeight: 700, color: "#0f172a" }}>
        {display || "N/A"}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
        {sectorAvg && (
          <>
            <span style={{ fontSize: 11, color: "#94a3b8", fontFamily: "JetBrains Mono, monospace" }}>
              {avgDisplay}
            </span>
            <StatusIcon size={12} color={statusColor} />
          </>
        )}
      </div>
    </div>
  );
}

export default function StockDetail({ stock, onClose }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!stock) return;
    setLoading(true);
    fetchStock(stock.symbol)
      .then(setDetail)
      .catch(() => setDetail(stock))
      .finally(() => setLoading(false));
  }, [stock?.symbol]);

  if (!stock) return null;
  const d = detail || stock;
  const sc = d.sector_comparison || {};

  return (
    <div
      style={{
        position: "fixed", inset: 0, zIndex: 100,
        background: "rgba(15,23,42,0.5)", backdropFilter: "blur(4px)",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: "20px",
      }}
      onClick={e => e.target === e.currentTarget && onClose()}
    >
      <div style={{
        background: "white",
        borderRadius: 16,
        width: "100%",
        maxWidth: 800,
        maxHeight: "90vh",
        overflow: "auto",
        boxShadow: "0 25px 50px rgba(0,0,0,0.15)",
        margin: "0 auto",
      }}>
        {/* Header */}
        <div style={{
          padding: "20px max(16px, min(28px, 4vw)) 16px",
          borderBottom: "1px solid #e2e8f0",
          position: "sticky", top: 0,
          background: "white", zIndex: 10,
        }}>
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
                <span style={{
                  fontFamily: "JetBrains Mono, monospace",
                  fontSize: 22, fontWeight: 800,
                  color: "#1e40af", letterSpacing: 1,
                }}>
                  {stock.symbol}
                </span>
                <span className={`conviction-badge ${CONVICTION_CLASS[stock.conviction] || "conviction-neutral"}`}>
                  {stock.conviction}
                </span>
                <a href={`https://www.screener.in/company/${stock.symbol}/`}
                  target="_blank" rel="noreferrer"
                  style={{ color: "#94a3b8", display: "flex" }}>
                  <ExternalLink size={14} />
                </a>
              </div>
              <div style={{ fontSize: 15, color: "#0f172a", fontWeight: 600, marginBottom: 2 }}>
                {d.company_name}
              </div>
              <div style={{ fontSize: 12, color: "#94a3b8", fontFamily: "JetBrains Mono, monospace" }}>
                {d.sector} · {formatMarketCap(d.market_cap)}
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
              <div style={{
                width: 60, height: 60, borderRadius: "50%",
                background: SCORE_BG(stock.scoring.composite),
                border: `2.5px solid ${SCORE_COLOR(stock.scoring.composite)}`,
                display: "flex", flexDirection: "column",
                alignItems: "center", justifyContent: "center",
              }}>
                <div style={{
                  fontSize: 20, fontWeight: 900,
                  color: SCORE_COLOR(stock.scoring.composite),
                  fontFamily: "JetBrains Mono, monospace", lineHeight: 1,
                }}>
                  {stock.scoring.composite}
                </div>
                <div style={{ fontSize: 9, color: SCORE_COLOR(stock.scoring.composite), opacity: 0.7 }}>score</div>
              </div>
              <button onClick={onClose} style={{
                background: "#f8faff", border: "1px solid #e2e8f0",
                borderRadius: 8, padding: 8, cursor: "pointer",
                display: "flex", color: "#64748b",
              }}>
                <X size={16} />
              </button>
            </div>
          </div>
        </div>

        {loading && (
          <div style={{ padding: 48, textAlign: "center", color: "#94a3b8", fontSize: 13 }}>
            Loading full data...
          </div>
        )}

        {!loading && (
          <div style={{ padding: "16px max(16px, min(28px, 4vw))" }}>
            {/* Price strip */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: 12, marginBottom: 24 }}>
              {[
                { label: "Current Price", value: d.current_price ? `₹${formatNum(d.current_price, 0)}` : "N/A" },
                { label: "52W High", value: d["52w_high"] ? `₹${formatNum(d["52w_high"], 0)}` : "N/A" },
                { label: "52W Low", value: d["52w_low"] ? `₹${formatNum(d["52w_low"], 0)}` : "N/A" },
                { label: "Market Cap", value: formatMarketCap(d.market_cap) },
              ].map(m => (
                <div key={m.label} style={{
                  background: "#f8faff", border: "1px solid #e2e8f0",
                  borderRadius: 10, padding: "12px 16px",
                }}>
                  <div style={{ fontSize: 10, color: "#94a3b8", textTransform: "uppercase", letterSpacing: 0.6, fontWeight: 600, marginBottom: 4 }}>
                    {m.label}
                  </div>
                  <div style={{ fontSize: 16, fontFamily: "JetBrains Mono, monospace", color: "#0f172a", fontWeight: 700 }}>
                    {m.value}
                  </div>
                </div>
              ))}
            </div>

            {/* Two column layout */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 20, marginBottom: 24 }}>
              {/* Fundamentals with sector comparison */}
              <div style={{ background: "#f8faff", border: "1px solid #e2e8f0", borderRadius: 12, padding: 18 }}>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", marginBottom: 8 }}>
                  <div style={{ fontSize: 11, color: "#94a3b8", fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.5 }}>Metric</div>
                  <div style={{ fontSize: 11, color: "#94a3b8", fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.5 }}>Value</div>
                  <div style={{ fontSize: 11, color: "#94a3b8", fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.5 }}>Sector Avg</div>
                </div>
                <MetricRow label="P/E Ratio" value={d.pe_ratio} sectorAvg={sc.pe_ratio?.sector_avg} lowerBetter format="num" />
                <MetricRow label="P/B Ratio" value={d.pb_ratio} sectorAvg={sc.pb_ratio?.sector_avg} lowerBetter format="num" />
                <MetricRow label="ROE" value={d.roe} sectorAvg={sc.roe?.sector_avg} format="pct" />
                <MetricRow label="ROCE" value={d.roce} sectorAvg={sc.roce?.sector_avg} format="pct" />
                <MetricRow label="OPM" value={d.operating_margins} sectorAvg={sc.operating_margins?.sector_avg} format="pct" />
                <MetricRow label="Debt/Equity" value={d.debt_to_equity} sectorAvg={sc.debt_to_equity?.sector_avg} lowerBetter format="num" />
                <MetricRow label="Dividend Yield" value={d.dividend_yield} format="pct" />
                <MetricRow label="Promoter Holding" value={d.promoter_holding} format="pct" />
                {d.promoter_pledge !== null && d.promoter_pledge !== undefined && (
                  <MetricRow label="Promoter Pledge" value={d.promoter_pledge} format="pct" lowerBetter />
                )}
              </div>

              {/* Scores and reasons */}
              <div>
                <div style={{ background: "#f8faff", border: "1px solid #e2e8f0", borderRadius: 12, padding: 18, marginBottom: 12 }}>
                  <div style={{ fontSize: 11, color: "#2563eb", fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 12 }}>
                    Principle Scores
                  </div>
                  {stock.scoring.sub_scores?.map(s => (
                    <div key={s.label} style={{ marginBottom: 10 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                        <span style={{ fontSize: 12, color: "#475569", fontWeight: 600 }}>{s.label}</span>
                        <span style={{ fontSize: 12, fontFamily: "JetBrains Mono, monospace", fontWeight: 700, color: SCORE_COLOR(s.score) }}>
                          {s.score}/100
                        </span>
                      </div>
                      <div style={{ height: 6, background: "#e2e8f0", borderRadius: 3 }}>
                        <div style={{
                          height: "100%", width: `${s.score}%`,
                          background: SCORE_COLOR(s.score), borderRadius: 3,
                        }} />
                      </div>
                    </div>
                  ))}
                </div>

                {/* Why this score */}
                <div style={{ background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 12, padding: 18 }}>
                  <div style={{ fontSize: 11, color: "#16a34a", fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 10 }}>
                    Why This Score
                  </div>
                  {stock.scoring.top_reasons?.length > 0 ? (
                    stock.scoring.top_reasons.map((r, i) => (
                      <div key={i} style={{ display: "flex", gap: 8, marginBottom: 6 }}>
                        <span style={{ color: "#16a34a", flexShrink: 0, marginTop: 1 }}>✓</span>
                        <span style={{ fontSize: 12, color: "#374151", lineHeight: 1.5 }}>{r}</span>
                      </div>
                    ))
                  ) : (
                    <div style={{ fontSize: 12, color: "#94a3b8" }}>No standout signals detected</div>
                  )}
                </div>
              </div>
            </div>

            {/* Matching investor profiles */}
            {stock.matching_profiles?.length > 0 && (
              <div style={{ marginBottom: 24 }}>
                <div style={{ fontSize: 11, color: "#2563eb", fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 12 }}>
                  Best Matching Investor Profiles
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 10 }}>
                  {stock.matching_profiles.map(p => (
                    <div key={p.id} style={{
                      background: "#f8faff", border: "1.5px solid #bfdbfe",
                      borderRadius: 10, padding: "12px 14px",
                    }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                        <span style={{ fontSize: 20 }}>{p.avatar}</span>
                        <div>
                          <div style={{ fontSize: 11, fontWeight: 700, color: "#1e40af" }}>{p.name}</div>
                          <div style={{ fontSize: 10, color: "#2563eb", fontFamily: "JetBrains Mono, monospace" }}>
                            Match: {p.score}/100
                          </div>
                        </div>
                      </div>
                      {p.reasons?.slice(0, 2).map((r, i) => (
                        <div key={i} style={{ fontSize: 10, color: "#475569", display: "flex", gap: 4, marginTop: 3 }}>
                          <span style={{ color: "#16a34a" }}>✓</span><span>{r}</span>
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Pros and Cons */}
            {(d.pros?.length > 0 || d.cons?.length > 0) && (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 12, marginBottom: 24 }}>
                {d.pros?.length > 0 && (
                  <div style={{ background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 10, padding: 16 }}>
                    <div style={{ fontSize: 11, color: "#16a34a", fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 8 }}>
                      Strengths
                    </div>
                    {d.pros.map((p, i) => (
                      <div key={i} style={{ fontSize: 12, color: "#374151", padding: "4px 0", lineHeight: 1.5, display: "flex", gap: 6 }}>
                        <span style={{ color: "#16a34a" }}>+</span>{p}
                      </div>
                    ))}
                  </div>
                )}
                {d.cons?.length > 0 && (
                  <div style={{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 10, padding: 16 }}>
                    <div style={{ fontSize: 11, color: "#dc2626", fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 8 }}>
                      Risks
                    </div>
                    {d.cons.map((c, i) => (
                      <div key={i} style={{ fontSize: 12, color: "#374151", padding: "4px 0", lineHeight: 1.5, display: "flex", gap: 6 }}>
                        <span style={{ color: "#dc2626" }}>−</span>{c}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* EPS */}
            {d.eps && (
              <div style={{
                padding: "10px 16px",
                background: "#f8faff",
                border: "1px solid #e2e8f0",
                borderRadius: 8,
                fontSize: 13, color: "#475569",
              }}>
                EPS: <span style={{ fontFamily: "JetBrains Mono, monospace", fontWeight: 700, color: "#0f172a" }}>
                  ₹{formatNum(d.eps)}
                </span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
