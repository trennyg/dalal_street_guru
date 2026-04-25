import { useState, useEffect } from "react";
import { X, ExternalLink, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { fetchStock, SCORE_COLOR, SCORE_BG, fmtNum, fmtPct, fmtMarketCap, fmtPrice, METRIC_TOOLTIPS } from "../lib/api";

const CONVICTION_CLASS = {
  "Strong Buy": "conviction-strong-buy", "Buy": "conviction-buy",
  "Watch": "conviction-watch", "Neutral": "conviction-neutral", "Avoid": "conviction-avoid",
};

function Tooltip({ text }) {
  if (!text) return null;
  return (
    <span className="tooltip-wrap" style={{ marginLeft: 4 }}>
      <span className="tooltip-icon">?</span>
      <span className="tooltip-box">{text}</span>
    </span>
  );
}

function MetricRow({ label, value, sectorAvg, lowerBetter = false, format = "num", tooltipKey }) {
  const display = format === "pct" ? (value !== null && value !== undefined ? fmtPct(value) : "N/A")
    : format === "num" ? (value !== null && value !== undefined ? fmtNum(value) : "N/A")
    : (value ?? "N/A");

  // Try to get sector avg from sector_comparison prop
  const avgDisplay = sectorAvg !== null && sectorAvg !== undefined
    ? (format === "pct" ? fmtPct(sectorAvg) : fmtNum(sectorAvg))
    : "—";

  let StatusIcon = Minus;
  let statusColor = "var(--text3)";

  if (value !== null && value !== undefined && sectorAvg !== null && sectorAvg !== undefined) {
    const isGood = lowerBetter ? value < sectorAvg * 0.9 : value > sectorAvg * 1.05;
    const isBad = lowerBetter ? value > sectorAvg * 1.1 : value < sectorAvg * 0.9;
    if (isGood) { statusColor = "var(--green)"; StatusIcon = TrendingUp; }
    else if (isBad) { statusColor = "var(--red)"; StatusIcon = TrendingDown; }
    else { statusColor = "var(--amber)"; }
  }

  return (
    <div className="metric-row">
      <div className="metric-name" style={{ display: "flex", alignItems: "center" }}>
        {label}
        <Tooltip text={METRIC_TOOLTIPS[tooltipKey]} />
      </div>
      <div className="metric-value">{display}</div>
      <div className="metric-sector">
        <span className="metric-sector-val">{avgDisplay}</span>
        {sectorAvg !== null && sectorAvg !== undefined && (
          <StatusIcon size={11} color={statusColor} style={{ marginLeft: 4 }} />
        )}
      </div>
    </div>
  );
}

function MiniBarChart({ data, label, color = "var(--blue)" }) {
  if (!data || data.length === 0) return null;
  const max = Math.max(...data.map(Math.abs));
  if (max === 0) return null;
  return (
    <div>
      <div style={{ fontSize: 10, color: "var(--text3)", fontFamily: "var(--font-mono)", textTransform: "uppercase", letterSpacing: 0.6, marginBottom: 8 }}>{label}</div>
      <div style={{ display: "flex", alignItems: "flex-end", gap: 3, height: 52 }}>
        {data.slice(0, 6).reverse().map((val, i) => {
          const h = val !== null ? Math.abs(val) / max * 100 : 0;
          const isNeg = val < 0;
          return (
            <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "flex-end", height: "100%" }}>
              <div style={{
                width: "100%", borderRadius: "3px 3px 0 0",
                background: isNeg ? "var(--red)" : color,
                height: `${h}%`,
                minHeight: 2,
                opacity: 0.8 + (i / data.length) * 0.2,
                transition: "height 0.4s ease",
              }} />
            </div>
          );
        })}
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

  const priceChangeUp = d.price_change_pct > 0;

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="detail-modal">
        {/* Header */}
        <div style={{
          padding: "22px 28px 18px",
          borderBottom: "1px solid var(--border)",
          position: "sticky", top: 0,
          background: "var(--surface)", zIndex: 10,
        }}>
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 5, flexWrap: "wrap" }}>
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 22, fontWeight: 600, color: "var(--blue)", letterSpacing: 0.5 }}>
                  {stock.symbol}
                </span>
                <span className={`conviction-badge ${CONVICTION_CLASS[stock.conviction] || "conviction-neutral"}`}>
                  {stock.conviction}
                </span>
                <a href={`https://www.screener.in/company/${stock.symbol}/`}
                  target="_blank" rel="noreferrer"
                  style={{ color: "var(--text3)", display: "flex", alignItems: "center" }}>
                  <ExternalLink size={13} />
                </a>
              </div>
              <div style={{ fontSize: 15, color: "var(--text)", fontWeight: 600, marginBottom: 3, fontFamily: "var(--font-display)" }}>
                {d.company_name}
              </div>
              <div style={{ fontSize: 12, color: "var(--text3)", fontFamily: "var(--font-mono)" }}>
                {d.sector !== "Unknown" ? d.sector : "—"} · {d.industry !== d.sector && d.industry !== "Unknown" ? d.industry : ""} · {fmtMarketCap(d.market_cap)}
                {d.data_source && (
                  <span style={{ marginLeft: 8, opacity: 0.5 }}>· {d.data_source}</span>
                )}
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div className="score-circle" style={{
                background: SCORE_BG(stock.scoring.composite),
                border: `2.5px solid ${SCORE_COLOR(stock.scoring.composite)}`,
                width: 58, height: 58,
              }}>
                <div style={{ fontFamily: "var(--font-display)", fontSize: 21, fontWeight: 700, color: SCORE_COLOR(stock.scoring.composite), lineHeight: 1 }}>
                  {stock.scoring.composite}
                </div>
                <div style={{ fontSize: 8, color: SCORE_COLOR(stock.scoring.composite), opacity: 0.7, textTransform: "uppercase" }}>score</div>
              </div>
              <button onClick={onClose} style={{
                background: "var(--surface2)", border: "1px solid var(--border)",
                borderRadius: "var(--radius-sm)", padding: 8, cursor: "pointer",
                display: "flex", color: "var(--text2)",
              }}><X size={16} /></button>
            </div>
          </div>
        </div>

        {loading ? (
          <div style={{ padding: 48, textAlign: "center", color: "var(--text3)", fontSize: 13 }}>Loading full data...</div>
        ) : (
          <div style={{ padding: "22px 28px" }}>
            {/* Price strip */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px,1fr))", gap: 10, marginBottom: 22 }}>
              {[
                {
                  label: "Price",
                  value: (
                    <div>
                      <span style={{ fontFamily: "var(--font-mono)", fontSize: 18, fontWeight: 700, color: "var(--text)" }}>
                        {fmtPrice(d.current_price)}
                      </span>
                      {d.price_change_pct !== null && d.price_change_pct !== undefined && (
                        <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", fontWeight: 600, marginLeft: 6, color: priceChangeUp ? "var(--green)" : "var(--red)" }}>
                          {priceChangeUp ? "+" : ""}{d.price_change_pct?.toFixed(2)}%
                        </span>
                      )}
                    </div>
                  )
                },
                { label: "52W High", value: <span style={{ fontFamily: "var(--font-mono)", fontSize: 15, fontWeight: 600 }}>{fmtPrice(d["52w_high"])}</span> },
                { label: "52W Low", value: <span style={{ fontFamily: "var(--font-mono)", fontSize: 15, fontWeight: 600 }}>{fmtPrice(d["52w_low"])}</span> },
                { label: "Market Cap", value: <span style={{ fontFamily: "var(--font-mono)", fontSize: 15, fontWeight: 600 }}>{fmtMarketCap(d.market_cap)}</span> },
              ].map(m => (
                <div key={m.label} style={{ background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "12px 14px" }}>
                  <div style={{ fontSize: 10, color: "var(--text3)", textTransform: "uppercase", letterSpacing: 0.6, fontWeight: 600, marginBottom: 5, fontFamily: "var(--font-mono)" }}>{m.label}</div>
                  {m.value}
                </div>
              ))}
            </div>

            {/* Description */}
            {d.description && (
              <div style={{ fontSize: 13, color: "var(--text2)", lineHeight: 1.65, marginBottom: 20, padding: "12px 16px", background: "var(--surface2)", borderRadius: "var(--radius)", border: "1px solid var(--border)" }}>
                {d.description}
              </div>
            )}

            {/* Two columns */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px,1fr))", gap: 18, marginBottom: 20 }}>
              {/* Fundamentals vs sector */}
              <div style={{ background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: 18 }}>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", marginBottom: 10, paddingBottom: 6, borderBottom: "1px solid var(--border)" }}>
                  {["Metric","Value","Sector Avg"].map(h => (
                    <div key={h} style={{ fontSize: 9.5, color: "var(--text3)", fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.4, fontFamily: "var(--font-mono)" }}>{h}</div>
                  ))}
                </div>
                <div className="metric-table">
                  <MetricRow label="P/E Ratio" value={d.pe_ratio} sectorAvg={sc.pe_ratio?.sector_avg} lowerBetter tooltipKey="pe_ratio" />
                  <MetricRow label="P/B Ratio" value={d.pb_ratio} sectorAvg={sc.pb_ratio?.sector_avg} lowerBetter tooltipKey="pb_ratio" />
                  <MetricRow label="EV/EBITDA" value={d.ev_ebitda} sectorAvg={sc.ev_ebitda?.sector_avg} lowerBetter tooltipKey="ev_ebitda" />
                  <MetricRow label="PEG Ratio" value={d.peg_ratio} lowerBetter format="num" tooltipKey="peg_ratio" />
                  <MetricRow label="ROE" value={d.roe} sectorAvg={sc.roe?.sector_avg} format="pct" tooltipKey="roe" />
                  <MetricRow label="ROCE" value={d.roce} sectorAvg={sc.roce?.sector_avg} format="pct" tooltipKey="roce" />
                  <MetricRow label="OPM" value={d.operating_margins} sectorAvg={sc.operating_margins?.sector_avg} format="pct" tooltipKey="operating_margins" />
                  <MetricRow label="Net Margin" value={d.net_margins} sectorAvg={sc.net_margins?.sector_avg} format="pct" tooltipKey="net_margins" />
                  <MetricRow label="Debt/Equity" value={d.debt_to_equity} sectorAvg={sc.debt_to_equity?.sector_avg} lowerBetter tooltipKey="debt_to_equity" />
                  <MetricRow label="Current Ratio" value={d.current_ratio} format="num" tooltipKey="current_ratio" />
                  <MetricRow label="Dividend Yield" value={d.dividend_yield} format="pct" tooltipKey="dividend_yield" />
                  <MetricRow label="Revenue Growth" value={d.revenue_growth} sectorAvg={sc.revenue_growth?.sector_avg} format="pct" tooltipKey="revenue_growth" />
                  <MetricRow label="Earnings Growth" value={d.earnings_growth} format="pct" tooltipKey="earnings_growth" />
                  {d.promoter_holding !== null && d.promoter_holding !== undefined && (
                    <MetricRow label="Promoter Holding" value={d.promoter_holding} format="pct" />
                  )}
                  {d.beta !== null && d.beta !== undefined && (
                    <MetricRow label="Beta" value={d.beta} format="num" tooltipKey="beta" />
                  )}
                </div>
              </div>

              {/* Scores + analyst */}
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                {/* Dimension scores */}
                <div style={{ background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: 18 }}>
                  <div style={{ fontSize: 10, color: "var(--blue)", fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.8, fontFamily: "var(--font-mono)", marginBottom: 14 }}>
                    Score Breakdown
                  </div>
                  {(() => {
                    const sub = stock.scoring.sub_scores;
                    const scores = stock.scoring.scores || {};
                    // Use sub_scores if available, else build from scores dict
                    const items = sub && sub.length > 0 ? sub
                      : Object.entries(scores).map(([k,v]) => ({label: k.charAt(0).toUpperCase()+k.slice(1).replace(/_/g," "), score: v}));
                    return items.map(s => {
                      const label = s.label || s.key || ""; 
                      const val = s.score ?? s.value ?? 0;
                      return (
                        <div key={label} style={{ marginBottom: 10 }}>
                          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                            <span style={{ fontSize: 12.5, color: "var(--text2)", fontWeight: 500 }}>{label}</span>
                            <span style={{ fontSize: 12, fontFamily: "var(--font-mono)", fontWeight: 700, color: SCORE_COLOR(val) }}>{val}/100</span>
                          </div>
                          <div style={{ height: 5, background: "var(--surface3)", borderRadius: 3 }}>
                            <div style={{ height: "100%", width: `${val}%`, background: SCORE_COLOR(val), borderRadius: 3, transition: "width 0.5s ease" }} />
                          </div>
                        </div>
                      );
                    });
                  })()}
                </div>

                {/* Analyst */}
                {(d.analyst_recommendation || d.target_price) && (
                  <div style={{ background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: 18 }}>
                    <div style={{ fontSize: 10, color: "var(--blue)", fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.8, fontFamily: "var(--font-mono)", marginBottom: 10 }}>
                      Analyst Consensus
                    </div>
                    {d.analyst_recommendation && (
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                        <span style={{ fontSize: 12.5, color: "var(--text2)" }}>Recommendation</span>
                        <span style={{ fontSize: 13, fontWeight: 700, color: "var(--text)", textTransform: "capitalize" }}>{d.analyst_recommendation.replace(/_/g, " ")}</span>
                      </div>
                    )}
                    {d.target_price && (
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                        <span style={{ fontSize: 12.5, color: "var(--text2)" }}>Target Price</span>
                        <span style={{ fontSize: 13, fontFamily: "var(--font-mono)", fontWeight: 700, color: d.target_price > d.current_price ? "var(--green)" : "var(--red)" }}>
                          ₹{Math.round(d.target_price).toLocaleString("en-IN")}
                          {d.current_price && (
                            <span style={{ fontSize: 10, marginLeft: 4 }}>
                              ({((d.target_price - d.current_price) / d.current_price * 100).toFixed(1)}%)
                            </span>
                          )}
                        </span>
                      </div>
                    )}
                    {d.num_analysts && (
                      <div style={{ fontSize: 11, color: "var(--text3)", fontFamily: "var(--font-mono)" }}>
                        Based on {d.num_analysts} analysts
                      </div>
                    )}
                  </div>
                )}

                {/* Why this score */}
                {stock.scoring.top_reasons?.length > 0 && (
                  <div style={{ background: "var(--green-light)", border: "1px solid var(--green-mid)", borderRadius: "var(--radius)", padding: 16 }}>
                    <div style={{ fontSize: 10, color: "var(--green)", fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.8, fontFamily: "var(--font-mono)", marginBottom: 10 }}>
                      Scoring Signals
                    </div>
                    {stock.scoring.top_reasons.map((r, i) => (
                      <div key={i} style={{ display: "flex", gap: 7, marginBottom: 6 }}>
                        <span style={{ color: "var(--green)", flexShrink: 0, fontSize: 11 }}>✓</span>
                        <span style={{ fontSize: 12.5, color: "var(--text)", lineHeight: 1.5 }}>{r}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Revenue / Profit charts */}
            {(d.quarterly_revenue?.length > 0 || d.annual_revenue?.length > 0) && (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px,1fr))", gap: 14, marginBottom: 20 }}>
                {d.quarterly_revenue?.length > 0 && (
                  <div style={{ background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: 16 }}>
                    <MiniBarChart data={d.quarterly_revenue} label="Quarterly Revenue (Cr)" color="var(--blue)" />
                  </div>
                )}
                {d.quarterly_profit?.length > 0 && (
                  <div style={{ background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: 16 }}>
                    <MiniBarChart data={d.quarterly_profit} label="Quarterly Profit (Cr)" color="#0a7c4f" />
                  </div>
                )}
                {d.annual_revenue?.length > 0 && (
                  <div style={{ background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: 16 }}>
                    <MiniBarChart data={d.annual_revenue} label="Annual Revenue (Cr)" color="#4a7cee" />
                  </div>
                )}
                {d.annual_profit?.length > 0 && (
                  <div style={{ background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: 16 }}>
                    <MiniBarChart data={d.annual_profit} label="Annual Profit (Cr)" color="#059669" />
                  </div>
                )}
              </div>
            )}

            {/* Matching profiles */}
            {stock.matching_profiles?.length > 0 && (
              <div style={{ marginBottom: 20 }}>
                <div style={{ fontSize: 10, color: "var(--blue)", fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.8, fontFamily: "var(--font-mono)", marginBottom: 10 }}>
                  Best Matching Investor Profiles
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px,1fr))", gap: 10 }}>
                  {stock.matching_profiles.map(p => (
                    <div key={p.id} style={{ background: "var(--blue-light)", border: "1.5px solid var(--blue-mid)", borderRadius: "var(--radius)", padding: "12px 14px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                        <div style={{
                          width: 30, height: 30, borderRadius: 8,
                          background: p.color || "var(--blue)",
                          display: "flex", alignItems: "center", justifyContent: "center",
                          fontSize: 9, fontWeight: 800, color: "white",
                          fontFamily: "var(--font-mono)",
                        }}>{p.avatar}</div>
                        <div>
                          <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text)" }}>{p.name}</div>
                          <div style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--blue)" }}>Match: {p.score}/100</div>
                        </div>
                      </div>
                      {p.reasons?.slice(0, 2).map((r, i) => (
                        <div key={i} style={{ fontSize: 10.5, color: "var(--text2)", display: "flex", gap: 4, marginTop: 3 }}>
                          <span style={{ color: "var(--green)" }}>✓</span><span>{r}</span>
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Pros/Cons */}
            {(d.pros?.length > 0 || d.cons?.length > 0) && (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px,1fr))", gap: 12, marginBottom: 16 }}>
                {d.pros?.length > 0 && (
                  <div style={{ background: "var(--green-light)", border: "1px solid #a7f3d0", borderRadius: "var(--radius)", padding: 16 }}>
                    <div style={{ fontSize: 10, color: "var(--green)", fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.8, fontFamily: "var(--font-mono)", marginBottom: 8 }}>Strengths</div>
                    {d.pros.map((p, i) => (
                      <div key={i} style={{ fontSize: 12.5, color: "var(--text)", padding: "3px 0", display: "flex", gap: 6, lineHeight: 1.5 }}>
                        <span style={{ color: "var(--green)", flexShrink: 0 }}>+</span>{p}
                      </div>
                    ))}
                  </div>
                )}
                {d.cons?.length > 0 && (
                  <div style={{ background: "var(--red-light)", border: "1px solid #fecaca", borderRadius: "var(--radius)", padding: 16 }}>
                    <div style={{ fontSize: 10, color: "var(--red)", fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.8, fontFamily: "var(--font-mono)", marginBottom: 8 }}>Risks</div>
                    {d.cons.map((c, i) => (
                      <div key={i} style={{ fontSize: 12.5, color: "var(--text)", padding: "3px 0", display: "flex", gap: 6, lineHeight: 1.5 }}>
                        <span style={{ color: "var(--red)", flexShrink: 0 }}>−</span>{c}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Company info */}
            {(d.employees || d.website) && (
              <div style={{ display: "flex", gap: 16, flexWrap: "wrap", fontSize: 12, color: "var(--text3)", fontFamily: "var(--font-mono)" }}>
                {d.employees && <span>Employees: {Number(d.employees).toLocaleString("en-IN")}</span>}
                {d.website && (
                  <a href={d.website} target="_blank" rel="noreferrer" style={{ color: "var(--blue)", textDecoration: "none" }}>
                    {d.website.replace(/^https?:\/\//, "").replace(/\/$/, "")} ↗
                  </a>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
