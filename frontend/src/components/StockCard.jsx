import { CONVICTION_COLORS, SCORE_COLOR, formatNum, formatPct } from "../lib/api";

const PROFILE_AVATARS = {
  buffett: "🧠", rj: "🐂", ramesh_damani: "🎯", vijay_kedia: "💡",
  parag_parikh: "🌍", marcellus: "🔬", motilal_qglp: "📊",
  porinju: "🔍", ashish_kacholia: "🚀",
};

export default function StockCard({ stock, onClick, activeProfile }) {
  const { symbol, company_name, sector, current_price, pe_ratio, pb_ratio, roe, scoring, conviction, matching_profiles } = stock;
  const cc = CONVICTION_COLORS[conviction] || CONVICTION_COLORS["Neutral"];

  const displayScore = activeProfile && stock.profile_score !== undefined
    ? stock.profile_score
    : scoring.composite;

  return (
    <div
      onClick={() => onClick(stock)}
      style={{
        background: "#111", border: "1px solid #222", borderRadius: 12,
        padding: "16px 20px", cursor: "pointer", transition: "border-color 0.15s, transform 0.1s",
        position: "relative", overflow: "hidden",
      }}
      onMouseEnter={e => { e.currentTarget.style.borderColor = "#f59e0b44"; e.currentTarget.style.transform = "translateY(-1px)"; }}
      onMouseLeave={e => { e.currentTarget.style.borderColor = "#222"; e.currentTarget.style.transform = "translateY(0)"; }}
    >
      {/* Score bar accent */}
      <div style={{
        position: "absolute", top: 0, left: 0, right: 0, height: 3,
        background: `linear-gradient(90deg, ${SCORE_COLOR(displayScore)} 0%, transparent ${displayScore}%, transparent 100%)`,
      }} />

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontFamily: "IBM Plex Mono, monospace", fontSize: 15, fontWeight: 700, color: "#f59e0b", letterSpacing: 1 }}>
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
          <div style={{ fontSize: 26, fontWeight: 800, color: SCORE_COLOR(displayScore), fontFamily: "IBM Plex Mono, monospace", lineHeight: 1 }}>
            {displayScore}
          </div>
          <div style={{ fontSize: 10, color: "#4b5563", marginTop: 2 }}>
            {activeProfile ? "profile fit" : "/ 100"}
          </div>
        </div>
      </div>

      <div style={{ fontSize: 10, color: "#4b5563", marginBottom: 10, textTransform: "uppercase", letterSpacing: 0.6 }}>
        {sector}
      </div>

      {/* Profile reasons when in profile mode */}
      {activeProfile && stock.profile_reasons?.length > 0 && (
        <div style={{ marginBottom: 10, display: "flex", flexDirection: "column", gap: 3 }}>
          {stock.profile_reasons.map((r, i) => (
            <div key={i} style={{ fontSize: 10, color: "#22c55e", display: "flex", gap: 5 }}>
              <span>✓</span><span>{r}</span>
            </div>
          ))}
        </div>
      )}

      {/* Matching investor profile avatars */}
      {!activeProfile && matching_profiles?.length > 0 && (
        <div style={{ display: "flex", gap: 4, marginBottom: 10, alignItems: "center" }}>
          <span style={{ fontSize: 9, color: "#4b5563", marginRight: 2 }}>Matches:</span>
          {matching_profiles.slice(0, 3).map(p => (
            <span key={p.id} title={`${p.name} (${p.score}/100)`}
              style={{ fontSize: 14, cursor: "help" }}>
              {PROFILE_AVATARS[p.id] || "•"}
            </span>
          ))}
        </div>
      )}

      {/* Mini score bars */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px 12px", marginBottom: 10 }}>
        {Object.entries(scoring.scores).map(([key, val]) => (
          <div key={key}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
              <span style={{ fontSize: 9, color: "#6b7280", textTransform: "uppercase", letterSpacing: 0.5 }}>
                {key.replace("_", " ")}
              </span>
              <span style={{ fontSize: 9, color: SCORE_COLOR(val), fontFamily: "IBM Plex Mono, monospace" }}>{val}</span>
            </div>
            <div style={{ height: 3, background: "#222", borderRadius: 2 }}>
              <div style={{ height: "100%", width: `${val}%`, background: SCORE_COLOR(val), borderRadius: 2 }} />
            </div>
          </div>
        ))}
      </div>

      {/* Key metrics */}
      <div style={{ display: "flex", gap: 12, borderTop: "1px solid #1a1a1a", paddingTop: 10 }}>
        {[
          { label: "P/E", value: pe_ratio ? formatNum(pe_ratio) : "—" },
          { label: "P/B", value: pb_ratio ? formatNum(pb_ratio) : "—" },
          { label: "ROE", value: roe ? formatPct(roe) : "—" },
          { label: "Price", value: current_price ? `₹${formatNum(current_price, 0)}` : "—" },
        ].map(m => (
          <div key={m.label} style={{ flex: 1, textAlign: "center" }}>
            <div style={{ fontSize: 10, color: "#4b5563" }}>{m.label}</div>
            <div style={{ fontSize: 12, color: "#e5e7eb", fontFamily: "IBM Plex Mono, monospace", marginTop: 2 }}>{m.value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
