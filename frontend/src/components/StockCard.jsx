import { SCORE_COLOR, SCORE_BG, formatNum, formatPct, formatMarketCap } from "../lib/api";

const CONVICTION_CLASS = {
  "Strong Buy": "conviction-strong-buy",
  "Buy": "conviction-buy",
  "Watch": "conviction-watch",
  "Neutral": "conviction-neutral",
  "Avoid": "conviction-avoid",
};

const PROFILE_AVATARS = {
  buffett:"🧠", rj:"🐂", ramesh_damani:"🎯", vijay_kedia:"💡",
  parag_parikh:"🌍", marcellus:"🔬", motilal_qglp:"📊",
  porinju:"🔍", ashish_kacholia:"🚀", dolly_khanna:"💎",
  chandrakant_sampat:"📜", radhakishan_damani:"🛒", raamdeo_agrawal:"📋",
  sanjay_bakshi:"🎓", kenneth_andrade:"🌉", manish_kejriwal:"🌐",
  peter_lynch:"📈", ben_graham:"⚖️", charlie_munger:"🦁", phil_fisher:"🔭",
  nippon_smallcap:"🌱", mirae_asset:"🏆", hdfc_mf:"🏦",
  anand_rathi:"⚡", white_oak:"🌳", enam:"🛡️", nemish_shah:"🎯",
  ask_investment:"💰", carnelian:"💫", murugappa:"🏭",
};

function SectorTag({ value, sectorAvg, label, lowerBetter = false }) {
  if (value === null || value === undefined || !sectorAvg) return null;
  const isGood = lowerBetter ? value < sectorAvg : value > sectorAvg * 1.05;
  const isBad = lowerBetter ? value > sectorAvg * 1.1 : value < sectorAvg * 0.9;
  const color = isGood ? "#16a34a" : isBad ? "#dc2626" : "#d97706";
  const arrow = isGood ? "↑" : isBad ? "↓" : "→";
  return (
    <span style={{ fontSize: 10, color, fontFamily: "JetBrains Mono, monospace", marginLeft: 4 }}>
      {arrow}
    </span>
  );
}

export default function StockCard({ stock, onClick, activeProfile }) {
  const {
    symbol, company_name, sector, current_price, pe_ratio, pb_ratio,
    roe, scoring, conviction, matching_profiles, sector_comparison,
  } = stock;

  const displayScore = activeProfile && stock.profile_score !== undefined
    ? stock.profile_score
    : scoring.composite;

  const sc = sector_comparison || {};

  return (
    <div
      onClick={() => onClick(stock)}
      style={{
        background: "white",
        border: "1.5px solid #e2e8f0",
        borderRadius: 14,
        padding: "18px 20px",
        cursor: "pointer",
        transition: "all 0.15s",
        boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
        position: "relative",
        overflow: "hidden",
      }}
      onMouseEnter={e => {
        e.currentTarget.style.borderColor = "#2563eb";
        e.currentTarget.style.transform = "translateY(-2px)";
        e.currentTarget.style.boxShadow = "0 8px 16px rgba(37,99,235,0.12)";
      }}
      onMouseLeave={e => {
        e.currentTarget.style.borderColor = "#e2e8f0";
        e.currentTarget.style.transform = "translateY(0)";
        e.currentTarget.style.boxShadow = "0 1px 3px rgba(0,0,0,0.06)";
      }}
    >
      {/* Top accent bar */}
      <div style={{
        position: "absolute", top: 0, left: 0, right: 0, height: 3,
        background: `linear-gradient(90deg, ${SCORE_COLOR(displayScore)}, transparent)`,
        opacity: 0.8,
      }} />

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <span style={{
              fontFamily: "JetBrains Mono, monospace",
              fontSize: 15, fontWeight: 700,
              color: "#1e40af", letterSpacing: 0.5,
            }}>
              {symbol}
            </span>
            <span className={`conviction-badge ${CONVICTION_CLASS[conviction] || "conviction-neutral"}`}>
              {conviction}
            </span>
          </div>
          <div style={{ fontSize: 12, color: "#64748b", fontWeight: 500 }}>
            {company_name?.split(" ").slice(0, 5).join(" ")}
          </div>
          <div style={{
            fontSize: 10, color: "#94a3b8",
            textTransform: "uppercase", letterSpacing: 0.8,
            marginTop: 2, fontFamily: "JetBrains Mono, monospace",
          }}>
            {sector}
          </div>
        </div>

        {/* Score circle */}
        <div style={{
          width: 52, height: 52,
          borderRadius: "50%",
          background: SCORE_BG(displayScore),
          border: `2px solid ${SCORE_COLOR(displayScore)}`,
          display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center",
          flexShrink: 0,
        }}>
          <div style={{
            fontSize: 18, fontWeight: 800,
            color: SCORE_COLOR(displayScore),
            fontFamily: "JetBrains Mono, monospace",
            lineHeight: 1,
          }}>
            {displayScore}
          </div>
          <div style={{ fontSize: 8, color: SCORE_COLOR(displayScore), opacity: 0.7 }}>
            {activeProfile ? "fit" : "score"}
          </div>
        </div>
      </div>

      {/* Profile reasons in profile mode */}
      {activeProfile && stock.profile_reasons?.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          {stock.profile_reasons.map((r, i) => (
            <div key={i} style={{ fontSize: 11, color: "#16a34a", display: "flex", gap: 5, marginBottom: 3 }}>
              <span>✓</span><span>{r}</span>
            </div>
          ))}
        </div>
      )}

      {/* Matching profiles */}
      {!activeProfile && matching_profiles?.length > 0 && (
        <div style={{ display: "flex", gap: 4, marginBottom: 12, alignItems: "center" }}>
          <span style={{ fontSize: 10, color: "#94a3b8", marginRight: 2 }}>Matches:</span>
          {matching_profiles.slice(0, 3).map(p => (
            <span key={p.id} title={`${p.name} (${p.score}/100)`}
              style={{ fontSize: 16, cursor: "help" }}>
              {PROFILE_AVATARS[p.id] || "•"}
            </span>
          ))}
        </div>
      )}

      {/* Score bars */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px 14px", marginBottom: 14 }}>
        {Object.entries(scoring.scores).map(([key, val]) => (
          <div key={key}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
              <span style={{ fontSize: 9, color: "#94a3b8", textTransform: "uppercase", letterSpacing: 0.5, fontWeight: 600 }}>
                {key.replace("_", " ")}
              </span>
              <span style={{ fontSize: 9, color: SCORE_COLOR(val), fontFamily: "JetBrains Mono, monospace", fontWeight: 700 }}>
                {val}
              </span>
            </div>
            <div style={{ height: 4, background: "#f1f5f9", borderRadius: 2 }}>
              <div style={{
                height: "100%", width: `${val}%`,
                background: SCORE_COLOR(val), borderRadius: 2,
                transition: "width 0.5s ease",
              }} />
            </div>
          </div>
        ))}
      </div>

      {/* Key metrics with sector comparison */}
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(4,1fr)",
        gap: 8, borderTop: "1px solid #f1f5f9", paddingTop: 12,
      }}>
        {[
          { label: "P/E", value: pe_ratio ? formatNum(pe_ratio) : "—", scKey: "pe_ratio", lb: true },
          { label: "P/B", value: pb_ratio ? formatNum(pb_ratio) : "—", scKey: "pb_ratio", lb: true },
          { label: "ROE", value: roe ? formatPct(roe) : "—", scKey: "roe", lb: false },
          { label: "Price", value: current_price ? `₹${formatNum(current_price, 0)}` : "—", scKey: null },
        ].map(m => (
          <div key={m.label} style={{ textAlign: "center" }}>
            <div style={{ fontSize: 9, color: "#94a3b8", fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 2 }}>
              {m.label}
            </div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
              <span style={{ fontSize: 12, color: "#0f172a", fontFamily: "JetBrains Mono, monospace", fontWeight: 600 }}>
                {m.value}
              </span>
              {m.scKey && sc[m.scKey] && (
                <SectorTag
                  value={sc[m.scKey].value}
                  sectorAvg={sc[m.scKey].sector_avg}
                  lowerBetter={m.lb}
                />
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
