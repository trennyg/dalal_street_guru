import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer, Tooltip } from "recharts";

export default function ScoreRadar({ scores }) {
  const data = [
    { subject: "Buffett", value: scores.buffett },
    { subject: "RJ Style", value: scores.rj_style },
    { subject: "Quality", value: scores.quality },
    { subject: "Value", value: scores.value },
  ];

  return (
    <ResponsiveContainer width="100%" height={220}>
      <RadarChart data={data} margin={{ top: 10, right: 30, bottom: 10, left: 30 }}>
        <PolarGrid stroke="#2a2a2a" />
        <PolarAngleAxis
          dataKey="subject"
          tick={{ fill: "#9ca3af", fontSize: 11, fontFamily: "var(--font-mono)" }}
        />
        <Tooltip
          contentStyle={{
            background: "#111",
            border: "1px solid #333",
            borderRadius: 8,
            color: "#fff",
            fontSize: 12,
          }}
          formatter={(v) => [`${v}/100`, "Score"]}
        />
        <Radar
          name="Score"
          dataKey="value"
          stroke="#f59e0b"
          fill="#f59e0b"
          fillOpacity={0.15}
          strokeWidth={2}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}
