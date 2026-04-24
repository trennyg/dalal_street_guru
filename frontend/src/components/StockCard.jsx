import { SCORE_COLOR, SCORE_BG, fmtNum, fmtPct, fmtMarketCap } from "../lib/api";

const CONVICTION_CLASS = {
  "Strong Buy": "conviction-strong-buy",
  "Buy": "conviction-buy",
  "Watch": "conviction-watch",
  "Neutral": "conviction-neutral",
  "Avoid": "conviction-avoid",
};

const SCORE_DIMS = [
  { key: "quality", label: "Quality" },
  { key: "growth", label: "Growth" },
  { key: "safety", label: "Safety" },
  { key: "value", label: "Value" },
];

function SectorBadge({ comparison, field }) {
  if (!comparison || !comparison[field]) return null;
  const { status } = comparison[field];
  if (status === "better") return <span className="sector-arrow-up" title="Better than sector avg">↑</span>;
  if (status === "worse") return <span className="sector-arrow-down" title="Worse than sector avg">↓</span>;
  return <span className="sector-arrow-neutral" title="In line with sector avg">→</span>;
}

export default function StockCard({ stock, onClick, activeProfile }) {
  const {
    symbol, company_name, sector, current_price, pe_ratio, pb_ratio,
    roe, operating_margins, scoring, conviction, matching_profiles,
    sector_comparison, price_change_pct, market_cap,
  } = stock;

  const displayScore = activeProfile && stock.profile_score !== undefined
    ? stock.profile_score
    : scoring.composite;

  const sc = sector_comparison || {};
  const priceUp = price_change_pct !== null && price_change_pct !== undefined && price_change_pct > 0;
  const priceDown = price_change_pct !== null && price_change_pct !== undefined && price_change_pct < 0;

  return (
    <div
      className="stock-card"
      onClick={() => onClick(stock)}
      style={{ "--score-color": SCORE_COLOR(displayScore) }}
    >
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 4, flexWrap: "wrap" }}>
            <span style={{
              fontFamily: "var(--font-mono)",
              fontSize: 15, fontWeight: 600,
              color: "var(--blue)", letterSpacing: 0.3,
            }}>
              {symbol}
            </span>
            <span className={`conviction-badge ${CONVICTION_CLASS[conviction] || "conviction-neutral"}`}>
              {conviction}
            </span>
          </div>
          <div style={{ fontSize: 12.5, color: "var(--text2)", fontWeight: 500, marginBottom: 2 }}>
            {company_name?.split(" ").slice(0, 4).join(" ")}
          </div>
          <div style={{
            fontSize: 10, color: "var(--text3)",
            textTransform: "uppercase", letterSpacing: 0.8,
            fontFamily: "var(--font-mono)",
          }}>
            {sector !== "Unknown" ? sector : "—"}
          </div>
        </div>

        {/* Score circle */}
        <div className="score-circle" style={{
          background: SCORE_BG(displayScore),
          border: `2px solid ${SCORE_COLOR(displayScore)}`,
        }}>
          <div className="score-value" style={{ color: SCORE_COLOR(displayScore) }}>
            {displayScore}
          </div>
          <div className="score-label" style={{ color: SCORE_COLOR(displayScore) }}>
            {activeProfile ? "fit" : "score"}
          </div>
        </div>
      </div>

      {/* Profile match reasons */}
      {activeProfile && stock.profile_reasons?.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          {stock.profile_reasons.slice(0, 2).map((r, i) => (
            <div key={i} style={{ display: "flex", gap: 5, marginBottom: 3, alignItems: "flex-start" }}>
              <span style={{ color: "var(--green)", fontSize: 10, flexShrink: 0, marginTop: 1 }}>✓</span>
              <span style={{ fontSize: 11.5, color: "var(--text2)", lineHeight: 1.4 }}>{r}</span>
            </div>
          ))}
        </div>
      )}

      {/* Matching profile badges */}
      {!activeProfile && matching_profiles?.length > 0 && (
        <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 11 }}>
          <span style={{ fontSize: 10, color: "var(--text3)", fontFamily: "var(--font-mono)" }}>Matches:</span>
          {matching_profiles.slice(0, 3).map(p => (
            <span key={p.id}
              title={`${p.name} — ${p.score}/100`}
              style={{
                fontSize: 9.5, fontWeight: 700,
                background: "var(--blue-light)",
                color: p.color || "var(--blue)",
                border: `1px solid ${p.color || "var(--blue-mid)"}`,
                borderRadius: 5, padding: "2px 6px",
                fontFamily: "var(--font-mono)",
                cursor: "help",
              }}>
              {p.avatar}
            </span>
          ))}
        </div>
      )}

      {/* Score dimension bars */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px 14px", marginBottom: 13 }}>
        {SCORE_DIMS.map(({ key, label }) => {
          const val = scoring.scores?.[key] ?? 0;
          return (
            <div key={key}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                <span style={{ fontSize: 9.5, color: "var(--text3)", fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.4 }}>
                  {label}
                </span>
                <span style={{ fontSize: 9.5, fontFamily: "var(--font-mono)", fontWeight: 600, color: SCORE_COLOR(val) }}>
                  {val}
                </span>
              </div>
              <div className="score-bar-track">
                <div className="score-bar-fill" style={{
                  width: `${val}%`,
                  background: SCORE_COLOR(val),
                  animationDelay: "0.1s",
                }} />
              </div>
            </div>
          );
        })}
      </div>

      {/* Key metrics row */}
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(4, 1fr)",
        gap: 6, borderTop: "1px solid var(--border)", paddingTop: 11,
      }}>
        {[
          { label: "P/E", value: pe_ratio ? fmtNum(pe_ratio) : "—", field: "pe_ratio" },
          { label: "ROE", value: roe ? fmtPct(roe) : "—", field: "roe" },
          { label: "OPM", value: operating_margins ? fmtPct(operating_margins) : "—", field: "operating_margins" },
          {
            label: "Price",
            value: current_price ? `₹${Math.round(current_price).toLocaleString("en-IN")}` : "—",
            field: null,
            extra: price_change_pct !== null && price_change_pct !== undefined ? (
              <span style={{
                fontSize: 9, fontFamily: "var(--font-mono)", fontWeight: 600,
                color: priceUp ? "var(--green)" : priceDown ? "var(--red)" : "var(--text3)",
              }}>
                {priceUp ? "+" : ""}{price_change_pct?.toFixed(1)}%
              </span>
            ) : null,
          },
        ].map(m => (
          <div key={m.label} style={{ textAlign: "center" }}>
            <div style={{ fontSize: 9, color: "var(--text3)", fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 2 }}>
              {m.label}
            </div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 2 }}>
              <span style={{ fontSize: 12, color: "var(--text)", fontFamily: "var(--font-mono)", fontWeight: 600 }}>
                {m.value}
              </span>
              {m.field && <SectorBadge comparison={sc} field={m.field} />}
              {m.extra}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
