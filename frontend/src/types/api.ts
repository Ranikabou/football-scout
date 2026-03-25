export interface PlayerSummary {
  player_id: string;
  player_name: string;
  team: string;
  league: string;
  season: string;
  age: number;
  nationality: string;
  position_group: "GK" | "CB" | "FB" | "CM" | "WG" | "ST";
  minutes_played: number;
  data_completeness_pct: number;
}

export interface PlayerDetail extends PlayerSummary {
  metrics: Record<string, number | null>;
  percentiles: Record<string, number | null>;
  composites: Record<string, number | null>;
  cluster_label: string | null;
  market_value_eur: number | null;
  predicted_value_eur: number | null;
  value_ratio: number | null;
  contract_expiry: string | null;
  data_sources: Record<string, string>;
}

export interface SimilarPlayer {
  player: PlayerSummary;
  similarity_score: number;
  shared_features_pct: number;
}

export interface ClusterPoint {
  player_id: string;
  player_name: string;
  team: string;
  cluster_label: string;
  umap_x: number;
  umap_y: number;
  top_metrics: Record<string, number>;
}

export interface ScoutingReport {
  bio: Record<string, any>;
  radar_chart_base64: string;
  percentile_table: Array<{
    metric: string;
    value: number | null;
    percentile: number | null;
    tier: "red" | "amber" | "green" | "gray";
  }>;
  similar_players: SimilarPlayer[];
  value_assessment: {
    predicted_value_eur: number | null;
    actual_value_eur: number | null;
    value_ratio: number | null;
    undervalued: boolean;
  };
  shap_chart_base64: string | null;
  provenance: Record<string, string>;
}

export interface ShortlistQuery {
  position_group: string;
  max_age?: number;
  leagues?: string[];
  max_market_value_eur?: number;
  metric_thresholds?: Array<{ metric: string; operator: string; value: number }>;
  similarity_to?: string;
  undervalued_only?: boolean;
  sort_by?: string;
  top_n?: number;
}

export interface PositionGroupInfo {
  group: string;
  positions: string[];
}

export interface DataSource {
  name: string;
  status: string;
  last_refresh: string;
}
