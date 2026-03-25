"""Composite metric computation and feature engineering."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Composite formulas: if ANY input is NaN, the result is NaN (no zero-filling)
COMPOSITE_FORMULAS: dict[str, tuple[list[str], callable]] = {
    "pressing_intensity": (
        ["pressures_att_third_p90", "pressure_success_pct"],
        lambda df: df["pressures_att_third_p90"] * df["pressure_success_pct"],
    ),
    "chance_creation": (
        ["xag_p90", "sca_p90"],
        lambda df: df["xag_p90"] + df["sca_p90"] / 5,
    ),
    "defensive_contrib": (
        ["tackles_won_p90", "interceptions_p90", "blocks_p90"],
        lambda df: df["tackles_won_p90"] + df["interceptions_p90"] + df["blocks_p90"],
    ),
    "progressive_action": (
        ["progressive_carries_p90", "progressive_passes_p90"],
        lambda df: df["progressive_carries_p90"] + df["progressive_passes_p90"],
    ),
    "goal_threat": (
        ["npxg_p90", "xag_p90"],
        lambda df: df["npxg_p90"] + 0.5 * df["xag_p90"],
    ),
    "aerial_dominance": (
        ["aerials_won", "aerials_lost"],
        lambda df: df["aerials_won"] / (df["aerials_won"] + df["aerials_lost"]),
    ),
}


def compute_composites(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all composite metrics. NaN propagates naturally."""
    df = df.copy()

    for metric_name, (required_cols, formula) in COMPOSITE_FORMULAS.items():
        # Check if all required columns exist
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            logger.debug(
                "Skipping composite '%s': missing columns %s",
                metric_name, missing,
            )
            df[metric_name] = np.nan
            continue

        try:
            df[metric_name] = formula(df)
        except Exception as e:
            logger.warning("Failed to compute '%s': %s", metric_name, e)
            df[metric_name] = np.nan

    return df


def compute_all_features(df: pd.DataFrame) -> pd.DataFrame:
    """Run the full feature engineering pipeline."""
    from football_scout.pipeline.aggregate import add_per90_columns

    df = add_per90_columns(df)
    df = compute_composites(df)
    return df
