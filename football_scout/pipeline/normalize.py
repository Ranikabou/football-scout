"""Percentile rank normalization within position groups."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

# Metrics to percentile-rank
METRICS_TO_RANK = [
    "goals_p90", "assists_p90", "xg_p90", "npxg_p90", "xag_p90",
    "sca_p90", "gca_p90",
    "progressive_passes_p90", "progressive_carries_p90",
    "key_passes_p90", "pass_completion_pct",
    "tackles_won_p90", "interceptions_p90", "blocks_p90",
    "pressures_p90", "pressures_att_third_p90", "pressure_success_pct",
    "successful_dribbles_p90", "touches_p90",
    "pressing_intensity", "chance_creation", "defensive_contrib",
    "progressive_action", "goal_threat", "aerial_dominance",
]


def compute_percentile_ranks(
    df: pd.DataFrame,
    position_col: str = "position_group",
    metrics: list[str] | None = None,
) -> pd.DataFrame:
    """Add percentile rank columns ({metric}_pctl, 0–100) within each position group."""
    df = df.copy()
    metrics = metrics or METRICS_TO_RANK
    available_metrics = [m for m in metrics if m in df.columns]

    if not available_metrics:
        logger.warning("No metrics available for percentile ranking")
        return df

    if position_col not in df.columns:
        logger.warning(
            "Position column '%s' not found; computing percentiles across all players",
            position_col,
        )
        for metric in available_metrics:
            pctl_col = f"{metric}_pctl"
            values = df[metric].dropna().values
            if len(values) == 0:
                df[pctl_col] = np.nan
                continue
            df[pctl_col] = df[metric].apply(
                lambda x, v=values: (
                    stats.percentileofscore(v, x, kind="rank")
                    if pd.notna(x) else np.nan
                )
            )
        return df

    for metric in available_metrics:
        pctl_col = f"{metric}_pctl"
        df[pctl_col] = np.nan

        for group_name, group_df in df.groupby(position_col):
            group_values = group_df[metric].dropna().values
            if len(group_values) == 0:
                continue

            mask = df[position_col] == group_name
            df.loc[mask, pctl_col] = df.loc[mask, metric].apply(
                lambda x, v=group_values: (
                    stats.percentileofscore(v, x, kind="rank")
                    if pd.notna(x) else np.nan
                )
            )

    return df


def normalize_and_save(df: pd.DataFrame) -> pd.DataFrame:
    """Compute percentile ranks and save to parquet."""
    df = compute_percentile_ranks(df)

    output_path = Path("data/processed/player_features.parquet")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)
    logger.info("Saved normalized features to %s (%d players)", output_path, len(df))

    return df
