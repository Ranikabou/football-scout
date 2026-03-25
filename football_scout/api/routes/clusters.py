"""Cluster data endpoint."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException

from football_scout.api.routes.players import _load_features
from football_scout.api.schemas import ClusterPoint
from football_scout.models.clustering import ArchetypeClusterer

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/clusters/{position_group}")
async def get_clusters(position_group: str):
    df = _load_features()
    if df.empty:
        raise HTTPException(status_code=404, detail="No data available")

    clusterer = ArchetypeClusterer()
    try:
        clustered = clusterer.cluster(df, position_group)
    except Exception as e:
        logger.error("Clustering failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Clustering failed: {e}")

    results = []
    for _, row in clustered.iterrows():
        # Get top 3 metrics for this player
        metric_cols = [c for c in row.index if c.endswith("_p90") or c in [
            "pressing_intensity", "chance_creation", "defensive_contrib",
            "progressive_action", "goal_threat", "aerial_dominance",
        ]]
        top_metrics = {}
        for col in metric_cols:
            if pd.notna(row.get(col)):
                top_metrics[col] = float(row[col])

        # Keep only top 3
        if len(top_metrics) > 3:
            sorted_metrics = sorted(top_metrics.items(), key=lambda x: abs(x[1]), reverse=True)
            top_metrics = dict(sorted_metrics[:3])

        results.append(ClusterPoint(
            player_id=str(row.get("player_id", "")),
            player_name=str(row.get("player_name", "")),
            team=str(row.get("team", "")),
            cluster_label=str(row.get("cluster_label", "Unknown")),
            umap_x=float(row["umap_x"]) if pd.notna(row.get("umap_x")) else 0.0,
            umap_y=float(row["umap_y"]) if pd.notna(row.get("umap_y")) else 0.0,
            top_metrics=top_metrics,
        ).model_dump())

    labels = list({r["cluster_label"] for r in results})
    return {"clusters": results, "labels": labels, "position_group": position_group}
