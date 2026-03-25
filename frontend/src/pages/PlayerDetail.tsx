import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { formatCurrency, formatRatio } from "@/lib/format";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { PositionBadge } from "@/components/scouting/PositionBadge";
import { ValueBadge } from "@/components/scouting/ValueBadge";
import { DataSourcePill } from "@/components/scouting/DataSourcePill";
import { PercentileBar } from "@/components/scouting/PercentileBar";
import { RadarChartComponent } from "@/components/scouting/RadarChart";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

const METRIC_CATEGORIES: Record<string, string[]> = {
  Shooting: ["goals_per90", "npxg_per90", "shots_per90", "shot_on_target_pct"],
  Passing: ["assists_per90", "xa_per90", "key_passes_per90", "pass_completion_pct", "progressive_passes_per90"],
  Defense: ["tackles_per90", "interceptions_per90", "blocks_per90", "clearances_per90"],
  Possession: ["touches_per90", "carries_per90", "progressive_carries_per90", "take_ons_per90"],
  Misc: ["aerial_won_pct", "fouls_per90", "pressures_per90"],
};

export default function PlayerDetail() {
  const { playerId } = useParams<{ playerId: string }>();
  const navigate = useNavigate();

  const { data: player, isLoading, error } = useQuery({
    queryKey: ["player", playerId],
    queryFn: () => api.getPlayer(playerId!),
    enabled: !!playerId,
    retry: false,
  });

  const { data: similarData } = useQuery({
    queryKey: ["similar", playerId],
    queryFn: () => api.getSimilarPlayers(playerId!),
    enabled: !!playerId,
    retry: false,
  });

  const { data: report } = useQuery({
    queryKey: ["report", playerId],
    queryFn: () => api.getReport(playerId!),
    enabled: !!playerId,
    retry: false,
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
        </div>
      </div>
    );
  }

  if (error || !player) {
    return (
      <div className="text-center py-20 text-muted-foreground">
        <p>Player not found.</p>
        <Button variant="ghost" onClick={() => navigate("/")} className="mt-4">
          <ArrowLeft className="mr-2 h-4 w-4" /> Back to search
        </Button>
      </div>
    );
  }

  const uniqueSources = [...new Set(Object.values(player.data_sources || {}))];

  return (
    <div className="space-y-4">
      <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
        <ArrowLeft className="mr-2 h-4 w-4" /> Back
      </Button>

      {/* Bio Card */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold">{player.player_name}</h1>
              <div className="flex flex-wrap items-center gap-2 mt-2">
                <span className="text-muted-foreground">{player.age} yrs</span>
                <span className="text-muted-foreground">•</span>
                <span className="text-muted-foreground">{player.nationality}</span>
                <span className="text-muted-foreground">•</span>
                <span>{player.team}</span>
                <Badge variant="outline">{player.league}</Badge>
                <PositionBadge position={player.position_group} />
              </div>
              {player.contract_expiry && (
                <p className="text-xs text-muted-foreground mt-1">
                  Contract: {player.contract_expiry}
                </p>
              )}
              <div className="flex flex-wrap gap-1 mt-2">
                {uniqueSources.map((s) => <DataSourcePill key={s} source={s} />)}
              </div>
            </div>
            <div className="text-right space-y-1">
              <p className="text-lg font-bold">{formatCurrency(player.market_value_eur)}</p>
              <ValueBadge valueRatio={player.value_ratio} />
              <p className="text-xs text-muted-foreground mt-1">
                Data: {player.data_completeness_pct}% complete
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Radar + Percentiles */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Composite Profile</CardTitle>
          </CardHeader>
          <CardContent>
            <RadarChartComponent
              composites={player.composites || {}}
              base64Image={report?.radar_chart_base64}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Percentile Rankings</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {Object.entries(METRIC_CATEGORIES).map(([category, metrics]) => {
              const available = metrics.filter(
                (m) => m in (player.percentiles || {}) || m in (player.metrics || {})
              );
              if (!available.length) return null;
              return (
                <div key={category}>
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">
                    {category}
                  </p>
                  <div className="space-y-1">
                    {available.map((m) => (
                      <PercentileBar
                        key={m}
                        metric={m.replace(/_per90|_pct/g, "").replace(/_/g, " ")}
                        value={player.metrics?.[m] ?? null}
                        percentile={player.percentiles?.[m] ?? null}
                        compact
                      />
                    ))}
                  </div>
                </div>
              );
            })}
            {/* Show any metrics not in categories */}
            {report?.percentile_table?.length && (
              <div>
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">
                  All Metrics
                </p>
                <div className="space-y-1">
                  {report.percentile_table.map((row) => (
                    <PercentileBar
                      key={row.metric}
                      metric={row.metric.replace(/_/g, " ")}
                      value={row.value}
                      percentile={row.percentile}
                      compact
                    />
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Similar Players */}
      {similarData?.similar?.length ? (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Similar Players</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-3 overflow-x-auto pb-2">
              {similarData.similar.map((sp) => (
                <div
                  key={sp.player.player_id}
                  className="min-w-[180px] p-3 rounded-md border bg-muted/30 cursor-pointer hover:bg-muted/60 transition-colors"
                  onClick={() => navigate(`/players/${sp.player.player_id}`)}
                >
                  <p className="font-medium text-sm truncate">{sp.player.player_name}</p>
                  <p className="text-xs text-muted-foreground">{sp.player.team} • {sp.player.league}</p>
                  <div className="flex items-center gap-2 mt-2">
                    <PositionBadge position={sp.player.position_group} />
                    <span className="text-xs">{sp.player.age} yrs</span>
                  </div>
                  <p className="text-primary font-bold text-sm mt-2">
                    {(sp.similarity_score * 100).toFixed(0)}% match
                  </p>
                  <p className="text-[10px] text-muted-foreground">
                    Based on {(sp.shared_features_pct * 100).toFixed(0)}% shared metrics
                  </p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : null}

      {/* Value Assessment */}
      {player.predicted_value_eur != null && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Value Assessment</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <p className="text-xs text-muted-foreground">Market Value</p>
                <p className="text-lg font-bold">{formatCurrency(player.market_value_eur)}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Predicted Value</p>
                <p className="text-lg font-bold">{formatCurrency(player.predicted_value_eur)}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Value Ratio</p>
                <p className="text-lg font-bold">{formatRatio(player.value_ratio)}</p>
                <ValueBadge valueRatio={player.value_ratio} />
              </div>
            </div>
            {report?.shap_chart_base64 && (
              <div className="mt-4">
                <p className="text-xs text-muted-foreground mb-2">SHAP Feature Importance</p>
                <img
                  src={`data:image/png;base64,${report.shap_chart_base64}`}
                  alt="SHAP waterfall chart"
                  className="max-w-lg"
                />
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
