"""Player search and detail endpoints."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Request

from football_scout.api.schemas import PlayerDetail, PlayerSummary

logger = logging.getLogger(__name__)
router = APIRouter()

FEATURES_PATH = Path("data/processed/player_features.parquet")


def _load_features() -> pd.DataFrame:
    if FEATURES_PATH.exists():
        return pd.read_parquet(FEATURES_PATH)
    unified = Path("data/processed/unified_players.parquet")
    if unified.exists():
        return pd.read_parquet(unified)
    return pd.DataFrame()


def _row_to_summary(row: pd.Series) -> dict:
    return PlayerSummary(
        player_id=str(row.get("player_id", "")),
        player_name=str(row.get("player_name", "")),
        team=str(row.get("team", "")),
        league=str(row.get("league", "")),
        season=str(row.get("season", "")),
        age=int(row["age"]) if pd.notna(row.get("age")) else None,
        nationality=str(row["nationality"]) if pd.notna(row.get("nationality")) else None,
        position_group=str(row.get("position_group", "")) if pd.notna(row.get("position_group")) else None,
        minutes_played=int(row["minutes_played"]) if pd.notna(row.get("minutes_played")) else None,
        data_completeness_pct=float(row.get("data_completeness_pct", 0)),
    ).model_dump()


def _row_to_detail(row: pd.Series) -> dict:
    # Separate metrics, percentiles, and composites
    metrics = {}
    percentiles = {}
    composites = {}
    metric_cols = [c for c in row.index if c.endswith("_p90")]
    pctl_cols = [c for c in row.index if c.endswith("_pctl")]
    composite_cols = [
        "pressing_intensity", "chance_creation", "defensive_contrib",
        "progressive_action", "goal_threat", "aerial_dominance",
    ]

    for col in metric_cols:
        val = row[col]
        metrics[col] = float(val) if pd.notna(val) else None

    for col in pctl_cols:
        val = row[col]
        percentiles[col.replace("_pctl", "")] = float(val) if pd.notna(val) else None

    for col in composite_cols:
        if col in row.index:
            val = row[col]
            composites[col] = float(val) if pd.notna(val) else None

    data_sources = {}
    if "data_sources" in row.index and isinstance(row["data_sources"], dict):
        data_sources = {k: str(v) for k, v in row["data_sources"].items()}
    elif "data_source" in row.index:
        data_sources = {"primary": str(row["data_source"])}

    return PlayerDetail(
        player_id=str(row.get("player_id", "")),
        player_name=str(row.get("player_name", "")),
        team=str(row.get("team", "")),
        league=str(row.get("league", "")),
        season=str(row.get("season", "")),
        age=int(row["age"]) if pd.notna(row.get("age")) else None,
        nationality=str(row["nationality"]) if pd.notna(row.get("nationality")) else None,
        position_group=str(row.get("position_group", "")) if pd.notna(row.get("position_group")) else None,
        minutes_played=int(row["minutes_played"]) if pd.notna(row.get("minutes_played")) else None,
        data_completeness_pct=float(row.get("data_completeness_pct", 0)),
        metrics=metrics,
        percentiles=percentiles,
        composites=composites,
        cluster_label=str(row["cluster_label"]) if pd.notna(row.get("cluster_label")) else None,
        market_value_eur=float(row["market_value_eur"]) if pd.notna(row.get("market_value_eur")) else None,
        predicted_value_eur=float(row["predicted_value_eur"]) if pd.notna(row.get("predicted_value_eur")) else None,
        value_ratio=float(row["value_ratio"]) if pd.notna(row.get("value_ratio")) else None,
        contract_expiry=str(row["contract_expiry"]) if pd.notna(row.get("contract_expiry")) else None,
        data_sources=data_sources,
    ).model_dump()


@router.get("/players")
async def list_players(
    league: str | None = Query(None),
    season: str | None = Query(None),
    position: str | None = Query(None),
    min_minutes: int = Query(900),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
):
    df = _load_features()
    if df.empty:
        return {"players": [], "total": 0}

    if league and "league" in df.columns:
        df = df[df["league"].str.contains(league, case=False, na=False)]
    if season and "season" in df.columns:
        df = df[df["season"] == season]
    if position and "position_group" in df.columns:
        df = df[df["position_group"] == position]
    if "minutes_played" in df.columns:
        df = df[df["minutes_played"] >= min_minutes]

    total = len(df)
    page = df.iloc[offset : offset + limit]

    players = [_row_to_summary(row) for _, row in page.iterrows()]
    return {"players": players, "total": total}


@router.get("/players/{player_id}")
async def get_player(player_id: str):
    df = _load_features()
    if df.empty:
        raise HTTPException(status_code=404, detail="No data available")

    match = df[df["player_id"] == player_id]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"Player {player_id} not found")

    return _row_to_detail(match.iloc[0])
