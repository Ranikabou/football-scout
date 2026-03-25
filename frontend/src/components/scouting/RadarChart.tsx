import {
  Radar,
  RadarChart as RechartsRadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Legend,
} from "recharts";

interface RadarChartProps {
  composites: Record<string, number | null>;
  base64Image?: string;
}

const COMPOSITE_KEYS = [
  "pressing_intensity",
  "chance_creation",
  "defensive_contrib",
  "progressive_action",
  "goal_threat",
  "aerial_dominance",
];

const labels: Record<string, string> = {
  pressing_intensity: "Pressing",
  chance_creation: "Creation",
  defensive_contrib: "Defense",
  progressive_action: "Progression",
  goal_threat: "Goal Threat",
  aerial_dominance: "Aerial",
};

export function RadarChartComponent({ composites, base64Image }: RadarChartProps) {
  if (base64Image) {
    return (
      <img
        src={`data:image/png;base64,${base64Image}`}
        alt="Radar chart"
        className="w-full max-w-sm mx-auto"
      />
    );
  }

  const data = COMPOSITE_KEYS.map((key) => ({
    metric: labels[key] || key,
    value: composites[key] ?? 0,
    median: 50,
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <RechartsRadarChart data={data}>
        <PolarGrid stroke="hsl(var(--border))" />
        <PolarAngleAxis
          dataKey="metric"
          tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
        />
        <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
        <Radar
          name="Median"
          dataKey="median"
          stroke="hsl(var(--muted-foreground))"
          fill="hsl(var(--muted))"
          fillOpacity={0.3}
          strokeDasharray="4 4"
        />
        <Radar
          name="Player"
          dataKey="value"
          stroke="hsl(var(--primary))"
          fill="hsl(var(--primary))"
          fillOpacity={0.3}
        />
        <Legend />
      </RechartsRadarChart>
    </ResponsiveContainer>
  );
}
