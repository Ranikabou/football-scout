"""Pydantic response models for the API."""

from __future__ import annotations

from pydantic import BaseModel

from football_scout.schema.enums import PositionGroup


class PlayerSummary(BaseModel):
    player_id: str
    player_name: str
    team: str
    league: str
    season: str
    age: int | None = None
    nationality: str | None = None
    position_group: str | None = None
    minutes_played: int | None = None
    data_completeness_pct: float = 0.0


class PlayerDetail(PlayerSummary):
    metrics: dict[str, float | None] = {}
    percentiles: dict[str, float | None] = {}
    composites: dict[str, float | None] = {}
    cluster_label: str | None = None
    market_value_eur: float | None = None
    predicted_value_eur: float | None = None
    value_ratio: float | None = None
    contract_expiry: str | None = None
    data_sources: dict[str, str] = {}


class SimilarPlayer(BaseModel):
    player: PlayerSummary
    similarity_score: float
    shared_features_pct: float = 0.0


class MetricThreshold(BaseModel):
    metric: str
    operator: str
    value: float


class ShortlistQuery(BaseModel):
    position_group: str
    max_age: int = 26
    min_minutes: int = 900
    leagues: list[str] | None = None
    max_market_value_eur: float | None = None
    metric_thresholds: list[MetricThreshold] | None = None
    similarity_to: str | None = None
    undervalued_only: bool = False
    sort_by: str = "similarity_score"
    top_n: int = 20


class ShortlistResult(BaseModel):
    players: list[PlayerDetail]
    total_matches: int
    data_coverage: dict[str, float] = {}


class ClusterPoint(BaseModel):
    player_id: str
    player_name: str
    team: str
    cluster_label: str
    umap_x: float
    umap_y: float
    top_metrics: dict[str, float] = {}


class ScoutingReport(BaseModel):
    bio: dict
    radar_chart_base64: str = ""
    percentile_table: list[dict] = []
    similar_players: list[SimilarPlayer] = []
    value_assessment: dict = {}
    shap_chart_base64: str | None = None
    provenance: dict[str, str] = {}


class MetaInfo(BaseModel):
    leagues: list[str] = []
    seasons: list[str] = []
    positions: dict[str, list[str]] = {}
    sources: dict[str, dict] = {}
