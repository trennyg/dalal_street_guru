import { useState, useEffect } from "react";
import { X, TrendingUp, TrendingDown, Minus, ExternalLink } from "lucide-react";
import { fetchStock, CONVICTION_COLORS, SCORE_COLOR, formatNum, formatPct, formatMarketCap } from "../lib/api";
import ScoreRadar from "./ScoreRadar";

export default function StockDetail({ stock, onClose }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!stock) return;
    setLoading(true);
    setError(null);
    fetchStock(stock.symbol)
      .then(setDetail)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [stock?.symbol]);

  if (!stock) return null;

  const cc = CONVICTION_COLORS[stock.conviction] || CONVICTION_COLORS["Neutral"];
  const d = detail || stock;

  return (
    <div
      style={{
        position: "fixed", inset: 0, zIndex: 100,
        background: "rgba(0,0,0,0.85)", backdropFilter: "blur(4px)",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: "20px",
      }}
      onClick={e => e.target === e.currentTarget && onClose()}
    >
      <div style={{
        background: "#0d0d0d",
        border: "1px solid #222",
        borderRadius: 16,
        width: "100%",
        maxWidth: 760,
        maxHeight: "90vh",
        overflow: "auto",
        position: "relative",
      }}>
        {/* Header */}
        <div style={{
          padding: "24px 28px 20px",
          borderBottom: "1px solid #1a1a1a",
          position: "sticky", top: 0, background: "#0d0d0d", zIndex: 10,
        }}>
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{
                  fontFamily: "var(--font-mono)", fontSize: 22, fontWeight: 800,
                  color: "#f59e0b", letterSpacing: 1.5,
                }}>
                  {stock.symbol}
                </span>
                <span style={{
                  fontSize: 11, padding: "3px 10px", borderRadius: 20, fontWeight: 700,
                  background: cc.bg, color: cc.text, border: `1px solid ${cc.border}`,
                  textTransform: "uppercase", letterSpacing: 1,
                }}>
                  {stock.conviction}
                </span>
                <a
                  href={`https://www.screener.in/company/${stock.symbol}/`}
                  target="_blank"
                  rel="noreferrer"
                  style={{ color: "#4b5563", display: "flex" }}
                >
                  <ExternalLink size={14} />
                </a>
              </div>
              <div style={{ color: "#9ca3af", fontSize: 13, marginTop: 4 }}>
                {d.company_name} · {d.sector}
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: 32, fontWeight: 900, color: SCORE_COLOR(stock.scoring.composite), fontFamily: "var(--font-mono)", lineHeight: 1 }}>
                  {stock.scoring.composite}
                </div>
                <div style={{ fontSize: 10, color: "#4b5563" }}>guru score</div>
              </div>
              <button
                onClick={onClose}
                style={{ background: "#1a1a1a", border: "none", color: "#6b7280", borderRadius: 8, padding: 8, cursor: "pointer", display: "flex" }}
              >
                <X size={16} />
              </button>
            </div>
          </div>
        </div>

        {loading && (
          <div style={{ padding: 40, textAlign: "center", color: "#4b5563" }}>
            <div style={{ fontSize: 13, fontFamily: "var(--font-mono)" }}>Fetching deep data...</div>
          </div>
        )}

        {!loading && (
          <div style={{ padding: "24px 28px" }}>
            {/* Price strip */}
            <div style={{
              display: "grid", gridTemplateColumns: "repeat(4, 1fr)",
              gap: 12, marginBottom: 24,
            }}>
              {[
                { label: "Current Price", value: d.current_price ? `₹${formatNum(d.current_price, 0)}` : "N/A" },
                { label: "52W High", value: d["52w_high"] ? `₹${formatNum(d["52w_high"], 0)}` : "N/A" },
                { label: "52W Low", value: d["52w_low"] ? `₹${formatNum(d["52w_low"], 0)}` : "N/A" },
                { label: "Market Cap", value: formatMarketCap(d.market_cap) },
              ].map(m => (
                <div key={m.label} style={{
                  background: "#111", border: "1px solid #1e1e1e",
                  borderRadius: 8, padding: "12px 14px",
                }}>
                  <div style={{ fontSize: 10, color: "#4b5563", textTransform: "uppercase", letterSpacing: 0.6, marginBottom: 4 }}>{m.label}</div>
                  <div style={{ fontSize: 15, fontFamily: "var(--font-mono)", color: "#e5e7eb", fontWeight: 600 }}>{m.value}</div>
                </div>
              ))}
            </div>

            {/* Two-col: radar + scores */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 24 }}>
              <div style={{ background: "#111", border: "1px solid #1e1e1e", borderRadius: 12, padding: 16 }}>
                <div style={{ fontSize: 11, color: "#6b7280", textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 8 }}>
                  Principle scores
                </div>
                <ScoreRadar scores={stock.scoring.scores} />
              </div>

              <div style={{ background: "#111", border: "1px solid #1e1e1e", borderRadius: 12, padding: 16 }}>
                <div style={{ fontSize: 11, color: "#6b7280", textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 12 }}>
                  Why this score
                </div>
                {stock.scoring.top_reasons?.length > 0 ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {stock.scoring.top_reasons.map((r, i) => (
                      <div key={i} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                        <span style={{ color: "#22c55e", marginTop: 1, flexShrink: 0 }}>✓</span>
                        <span style={{ fontSize: 12, color: "#9ca3af", lineHeight: 1.5 }}>{r}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ fontSize: 12, color: "#4b5563" }}>No standout signals detected</div>
                )}

                {/* Sub scores */}
                <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 8 }}>
                  {stock.scoring.sub_scores?.map(s => (
                    <div key={s.label}>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                        <span style={{ fontSize: 11, color: "#6b7280" }}>{s.label}</span>
                        <span style={{ fontSize: 11, color: SCORE_COLOR(s.score), fontFamily: "var(--font-mono)" }}>
                          {s.score}/100
                        </span>
                      </div>
                      <div style={{ height: 4, background: "#1a1a1a", borderRadius: 2 }}>
                        <div style={{
                          height: "100%", width: `${s.score}%`,
                          background: SCORE_COLOR(s.score),
                          borderRadius: 2,
                        }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Fundamentals grid */}
            <div style={{ background: "#111", border: "1px solid #1e1e1e", borderRadius: 12, padding: 16, marginBottom: 16 }}>
              <div style={{ fontSize: 11, color: "#6b7280", textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 14 }}>
                Fundamentals
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
                {[
                  { label: "P/E Ratio", value: d.pe_ratio ? formatNum(d.pe_ratio) : "N/A", note: d.pe_ratio < 25 ? "✓ Reasonable" : d.pe_ratio < 40 ? "~ Elevated" : "✗ Expensive" },
                  { label: "P/B Ratio", value: d.pb_ratio ? formatNum(d.pb_ratio) : "N/A", note: d.pb_ratio < 2 ? "✓ Value zone" : "" },
                  { label: "ROE", value: d.roe ? formatPct(d.roe) : "N/A", note: (d.roe > 0.15 || d.roe > 15) ? "✓ Strong" : "" },
                  { label: "Debt/Equity", value: d.debt_to_equity ? formatNum(d.debt_to_equity) : "N/A", note: d.debt_to_equity < 0.5 ? "✓ Low debt" : d.debt_to_equity < 1 ? "~ Moderate" : "✗ High" },
                  { label: "Revenue Growth", value: d.revenue_growth ? formatPct(d.revenue_growth) : "N/A", note: "" },
                  { label: "Earnings Growth", value: d.earnings_growth ? formatPct(d.earnings_growth) : "N/A", note: "" },
                  { label: "Operating Margin", value: d.operating_margins ? formatPct(d.operating_margins) : "N/A", note: "" },
                  { label: "Gross Margin", value: d.gross_margins ? formatPct(d.gross_margins) : "N/A", note: "" },
                  { label: "Dividend Yield", value: d.dividend_yield ? formatPct(d.dividend_yield) : "N/A", note: "" },
                ].map(m => (
                  <div key={m.label}>
                    <div style={{ fontSize: 10, color: "#4b5563", marginBottom: 2 }}>{m.label}</div>
                    <div style={{ fontSize: 14, fontFamily: "var(--font-mono)", color: "#e5e7eb" }}>{m.value}</div>
                    {m.note && (
                      <div style={{
                        fontSize: 10, marginTop: 2,
                        color: m.note.startsWith("✓") ? "#22c55e" : m.note.startsWith("✗") ? "#f87171" : "#facc15",
                      }}>
                        {m.note}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Screener extras */}
            {d.screener_extras?.pros?.length > 0 && (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div style={{ background: "#0a1a0a", border: "1px solid #1a2e1a", borderRadius: 10, padding: 14 }}>
                  <div style={{ fontSize: 10, color: "#22c55e", textTransform: "uppercase", letterSpacing: 0.6, marginBottom: 8 }}>
                    Screener Pros
                  </div>
                  {d.screener_extras.pros.map((p, i) => (
                    <div key={i} style={{ fontSize: 11, color: "#6b7280", padding: "3px 0", lineHeight: 1.5 }}>
                      + {p}
                    </div>
                  ))}
                </div>
                {d.screener_extras?.cons?.length > 0 && (
                  <div style={{ background: "#1a0a0a", border: "1px solid #2e1a1a", borderRadius: 10, padding: 14 }}>
                    <div style={{ fontSize: 10, color: "#f87171", textTransform: "uppercase", letterSpacing: 0.6, marginBottom: 8 }}>
                      Screener Cons
                    </div>
                    {d.screener_extras.cons.map((c, i) => (
                      <div key={i} style={{ fontSize: 11, color: "#6b7280", padding: "3px 0", lineHeight: 1.5 }}>
                        − {c}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
