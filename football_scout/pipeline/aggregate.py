"""Event-level to season aggregate computation (primarily for StatsBomb)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_per90(df: pd.DataFrame, raw_col: str, minutes_col: str = "minutes_played") -> pd.Series:
    """Compute per-90 minute rate for a given column."""
    nineties = df[minutes_col] / 90.0
    return np.where(nineties > 0, df[raw_col] / nineties, np.nan)


def add_per90_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add all per-90 rate columns to a DataFrame with raw counting stats."""
    df = df.copy()

    if "minutes_played" not in df.columns:
        return df

    per90_map = {
        "goals_p90": "goals",
        "assists_p90": "assists",
        "xg_p90": "xg",
        "npxg_p90": "npxg",
        "xag_p90": "xag",
        "sca_p90": "sca",
        "gca_p90": "gca",
        "progressive_passes_p90": "progressive_passes",
        "progressive_carries_p90": "progressive_carries",
        "key_passes_p90": "key_passes",
        "tackles_won_p90": "tackles_won",
        "interceptions_p90": "interceptions",
        "blocks_p90": "blocks",
        "pressures_p90": "pressures",
        "pressures_att_third_p90": "pressures_att_third",
        "successful_dribbles_p90": "successful_dribbles",
        "touches_p90": "touches",
    }

    for p90_col, raw_col in per90_map.items():
        if raw_col in df.columns:
            df[p90_col] = compute_per90(df, raw_col)

    # Pass completion percentage
    if "passes_attempted" in df.columns and "passes_completed" in df.columns:
        df["pass_completion_pct"] = np.where(
            df["passes_attempted"] > 0,
            df["passes_completed"] / df["passes_attempted"] * 100,
            np.nan,
        )

    # Pressure success percentage
    if "pressures" in df.columns and "pressure_successes" in df.columns:
        df["pressure_success_pct"] = np.where(
            df["pressures"] > 0,
            df["pressure_successes"] / df["pressures"] * 100,
            np.nan,
        )

    return df
