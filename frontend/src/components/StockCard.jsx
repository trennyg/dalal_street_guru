import { CONVICTION_COLORS, SCORE_COLOR, formatNum, formatPct, formatMarketCap } from "../lib/api";

export default function StockCard({ stock, onClick }) {
  const { symbol, company_name, sector, current_price, pe_ratio, pb_ratio, roe, scoring, conviction } = stock;
  const cc = CONVICTION_COLORS[conviction] || CONVICTION_COLORS["Neutral"];

  return (
    <div
      onClick={() => onClick(stock)}
      style={{
        background: "#111",
        border: "1px solid #222",
        borderRadius: 12,
        padding: "16px 20px",
        cursor: "pointer",
        transition: "border-color 0.15s, transform 0.1s",
        position: "relative",
        overflow: "hidden",
      }}
      onMouseEnter={e => {
        e.currentTarget.style.borderColor = "#f59e0b44";
        e.currentTarget.style.transform = "translateY(-1px)";
      }}
      onMouseLeave={e => {
        e.currentTarget.style.borderColor = "#222";
        e.currentTarget.style.transform = "translateY(0)";
      }}
    >
      {/* Score bar accent */}
      <div style={{
        position: "absolute", top: 0, left: 0, right: 0, height: 3,
        background: `linear-gradient(90deg, ${SCORE_COLOR(scoring.composite)} 0%, transparent ${scoring.composite}%, transparent 100%)`,
      }} />

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 15, fontWeight: 700, color: "#f59e0b", letterSpacing: 1 }}>
              {symbol}
            </span>
            <span style={{
              fontSize: 10, fontWeight: 600, padding: "2px 8px", borderRadius: 20,
              background: cc.bg, color: cc.text, border: `1px solid ${cc.border}`,
              textTransform: "uppercase", letterSpacing: 0.8,
            }}>
              {conviction}
            </span>
          </div>
          <div style={{ fontSize: 12, color: "#6b7280", marginTop: 2 }}>
            {company_name?.split(" ").slice(0, 4).join(" ")}
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{
            fontSize: 26, fontWeight: 800,
            color: SCORE_COLOR(scoring.composite),
            fontFamily: "var(--font-mono)",
            lineHeight: 1,
          }}>
            {scoring.composite}
          </div>
          <div style={{ fontSize: 10, color: "#4b5563", marginTop: 2 }}>/ 100</div>
        </div>
      </div>

      <div style={{ fontSize: 10, color: "#4b5563", marginBottom: 10, textTransform: "uppercase", letterSpacing: 0.6 }}>
        {sector}
      </div>

      {/* Mini score bars */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px 12px", marginBottom: 10 }}>
        {Object.entries(scoring.scores).map(([key, val]) => (
          <div key={key}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
              <span style={{ fontSize: 9, color: "#6b7280", textTransform: "uppercase", letterSpacing: 0.5 }}>
                {key.replace("_", " ")}
              </span>
              <span style={{ fontSize: 9, color: SCORE_COLOR(val), fontFamily: "var(--font-mono)" }}>{val}</span>
            </div>
            <div style={{ height: 3, background: "#222", borderRadius: 2 }}>
              <div style={{
                height: "100%", width: `${val}%`,
                background: SCORE_COLOR(val), borderRadius: 2,
                transition: "width 0.4s ease",
              }} />
            </div>
          </div>
        ))}
      </div>

      {/* Key metrics row */}
      <div style={{ display: "flex", gap: 12, borderTop: "1px solid #1a1a1a", paddingTop: 10 }}>
        {[
          { label: "P/E", value: pe_ratio ? formatNum(pe_ratio) : "—" },
          { label: "P/B", value: pb_ratio ? formatNum(pb_ratio) : "—" },
          { label: "ROE", value: roe ? formatPct(roe) : "—" },
          { label: "Price", value: current_price ? `₹${formatNum(current_price, 0)}` : "—" },
        ].map(m => (
          <div key={m.label} style={{ flex: 1, textAlign: "center" }}>
            <div style={{ fontSize: 10, color: "#4b5563" }}>{m.label}</div>
            <div style={{ fontSize: 12, color: "#e5e7eb", fontFamily: "var(--font-mono)", marginTop: 2 }}>
              {m.value}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
