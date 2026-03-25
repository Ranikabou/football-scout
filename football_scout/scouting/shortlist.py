"""Scouting query interface with filters and ranking."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from football_scout.models.similarity import SimilarityEngine

logger = logging.getLogger(__name__)


@dataclass
class ScoutingQuery:
    """Query parameters for building a scouting shortlist."""

    position_group: str
    max_age: int = 26
    min_minutes: int = 900
    leagues: list[str] | None = None
    max_market_value_eur: float | None = None
    metric_thresholds: dict[str, tuple[str, float]] | None = None
    similarity_to: str | None = None
    undervalued_only: bool = False
    sort_by: str = "similarity_score"
    top_n: int = 20


def run_shortlist(
    query: ScoutingQuery,
    feature_df: pd.DataFrame,
    config: dict | None = None,
) -> pd.DataFrame:
    """Execute a scouting query against the feature dataset.

    Returns a ranked DataFrame of matching players.
    """
    config = config or {}
    df = feature_df.copy()

    # Filter by position group
    if "position_group" in df.columns:
        df = df[df["position_group"] == query.position_group]

    # Filter by age
    if "age" in df.columns:
        df = df[df["age"].notna() & (df["age"] <= query.max_age)]

    # Filter by minimum minutes
    if "minutes_played" in df.columns:
        df = df[df["minutes_played"] >= query.min_minutes]

    # Filter by leagues
    if query.leagues and "league" in df.columns:
        df = df[df["league"].isin(query.leagues)]

    # Filter by max market value
    if query.max_market_value_eur is not None and "market_value_eur" in df.columns:
        df = df[
            df["market_value_eur"].isna()
            | (df["market_value_eur"] <= query.max_market_value_eur)
        ]

    # Apply metric thresholds
    if query.metric_thresholds:
        for metric, (op, threshold) in query.metric_thresholds.items():
            if metric not in df.columns:
                continue
            if op == ">":
                df = df[df[metric] > threshold]
            elif op == ">=":
                df = df[df[metric] >= threshold]
            elif op == "<":
                df = df[df[metric] < threshold]
            elif op == "<=":
                df = df[df[metric] <= threshold]
            elif op == "==":
                df = df[df[metric] == threshold]

    if df.empty:
        logger.warning("No players match the query filters")
        return pd.DataFrame()

    # Similarity scoring
    if query.similarity_to:
        engine = SimilarityEngine(feature_df, config)
        similar = engine.find_similar(
            target=query.similarity_to,
            position_group=query.position_group,
            n=len(df),
            leagues=query.leagues,
        )
        if not similar.empty:
            # Merge similarity scores
            sim_scores = similar.set_index("player_name")["similarity_score"]
            df["similarity_score"] = df["player_name"].map(sim_scores)
        else:
            df["similarity_score"] = np.nan
    else:
        if "similarity_score" not in df.columns:
            df["similarity_score"] = np.nan

    # Filter undervalued only
    if query.undervalued_only and "value_ratio" in df.columns:
        df = df[df["value_ratio"] > 1.4]

    # Sort
    if query.sort_by in df.columns:
        df = df.sort_values(query.sort_by, ascending=False, na_position="last")
    else:
        logger.warning("Sort column '%s' not found, using default order", query.sort_by)

    # Select top N
    result = df.head(query.top_n)

    # Select output columns
    output_cols = [
        "player_name", "team", "age", "league", "nationality", "position_group",
        "minutes_played", "similarity_score",
        "market_value_eur", "predicted_value_eur", "value_ratio",
        "data_completeness_pct",
    ]

    # Add top metric percentiles (dynamic based on position)
    pctl_cols = [c for c in result.columns if c.endswith("_pctl")]
    if pctl_cols:
        # Pick top 5 by average percentile
        avg_pctls = result[pctl_cols].mean()
        top_pctl_cols = avg_pctls.nlargest(5).index.tolist()
        output_cols.extend(top_pctl_cols)

    # Add cluster label if available
    if "cluster_label" in result.columns:
        output_cols.append("cluster_label")

    available_cols = [c for c in output_cols if c in result.columns]
    return result[available_cols].reset_index(drop=True)
