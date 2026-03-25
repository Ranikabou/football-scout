import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import Plot from "react-plotly.js";

const POS_GROUPS = ["GK", "CB", "FB", "CM", "WG", "ST"];

const CLUSTER_COLORS = [
  "#2dd4bf", "#60a5fa", "#a78bfa", "#fb923c", "#f87171",
  "#34d399", "#facc15", "#f472b6", "#818cf8", "#22d3ee",
];

export default function ClusterExplorer() {
  const [posGroup, setPosGroup] = useState("CM");
  const navigate = useNavigate();

  const { data, isLoading, error } = useQuery({
    queryKey: ["clusters", posGroup],
    queryFn: () => api.getClusters(posGroup),
    retry: false,
  });

  const clusterGroups = data?.clusters?.reduce((acc, pt) => {
    (acc[pt.cluster_label] = acc[pt.cluster_label] || []).push(pt);
    return acc;
  }, {} as Record<string, typeof data.clusters>);

  const traces = clusterGroups
    ? Object.entries(clusterGroups).map(([label, points], i) => ({
        x: points.map((p) => p.umap_x),
        y: points.map((p) => p.umap_y),
        text: points.map(
          (p) =>
            `${p.player_name}<br>${p.team}<br>${label}<br>${Object.entries(p.top_metrics)
              .slice(0, 3)
              .map(([k, v]) => `${k}: ${v.toFixed(1)}`)
              .join("<br>")}`
        ),
        customdata: points.map((p) => p.player_id),
        type: "scatter" as const,
        mode: "markers" as const,
        name: label,
        marker: {
          color: CLUSTER_COLORS[i % CLUSTER_COLORS.length],
          size: 6,
          opacity: 0.7,
        },
        hoverinfo: "text" as const,
      }))
    : [];

  return (
    <div className="space-y-4">
      <Tabs value={posGroup} onValueChange={setPosGroup}>
        <TabsList>
          {POS_GROUPS.map((g) => (
            <TabsTrigger key={g} value={g}>{g}</TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {error && (
        <div className="text-destructive text-sm p-3 bg-destructive/10 rounded-md">
          Failed to load clusters.
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_280px] gap-4">
        <Card>
          <CardContent className="pt-4">
            {isLoading ? (
              <Skeleton className="h-[500px] w-full" />
            ) : (
              <Plot
                data={traces}
                layout={{
                  autosize: true,
                  height: 500,
                  paper_bgcolor: "transparent",
                  plot_bgcolor: "transparent",
                  font: { color: "hsl(210,20%,70%)", size: 11 },
                  xaxis: { title: { text: "UMAP 1" }, gridcolor: "hsl(222,15%,20%)", zerolinecolor: "hsl(222,15%,25%)" },
                  yaxis: { title: { text: "UMAP 2" }, gridcolor: "hsl(222,15%,20%)", zerolinecolor: "hsl(222,15%,25%)" },
                  legend: { orientation: "h", y: -0.15 },
                  margin: { t: 20, r: 20, b: 60, l: 50 },
                }}
                config={{ responsive: true, displayModeBar: false }}
                style={{ width: "100%" }}
                onClick={(e) => {
                  const point = e.points[0];
                  if (point?.customdata) {
                    navigate(`/players/${point.customdata}`);
                  }
                }}
              />
            )}
          </CardContent>
        </Card>

        {/* Cluster summaries */}
        <div className="space-y-2">
          {data?.labels?.map((label, i) => {
            const pts = clusterGroups?.[label] || [];
            const avgAge = pts.length
              ? 0 // We don't have age in ClusterPoint, show count only
              : 0;
            return (
              <Card key={label} className="cursor-pointer hover:bg-muted/30 transition-colors">
                <CardContent className="py-3 px-4">
                  <div className="flex items-center gap-2">
                    <div
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: CLUSTER_COLORS[i % CLUSTER_COLORS.length] }}
                    />
                    <span className="font-medium text-sm">{label}</span>
                    <Badge variant="secondary" className="text-xs ml-auto">
                      {pts.length}
                    </Badge>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
}
