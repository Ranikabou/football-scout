"""Tests for composite features and percentile normalization."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from football_scout.pipeline.features import compute_all_features, compute_composites
from football_scout.pipeline.normalize import compute_percentile_ranks


class TestComposites:
    def test_goal_threat_formula(self):
        df = pd.DataFrame({
            "npxg_p90": [0.5],
            "xag_p90": [0.3],
            "minutes_played": [2700],
        })
        result = compute_composites(df)
        expected = 0.5 + 0.5 * 0.3
        assert abs(result.iloc[0]["goal_threat"] - expected) < 1e-6

    def test_defensive_contrib_formula(self):
        df = pd.DataFrame({
            "tackles_won_p90": [2.0],
            "interceptions_p90": [1.5],
            "blocks_p90": [0.5],
            "minutes_played": [2700],
        })
        result = compute_composites(df)
        expected = 2.0 + 1.5 + 0.5
        assert abs(result.iloc[0]["defensive_contrib"] - expected) < 1e-6

    def test_aerial_dominance(self):
        df = pd.DataFrame({
            "aerials_won": [50],
            "aerials_lost": [50],
            "minutes_played": [2700],
        })
        result = compute_composites(df)
        assert abs(result.iloc[0]["aerial_dominance"] - 0.5) < 1e-6

    def test_nan_propagation_in_composites(self):
        df = pd.DataFrame({
            "npxg_p90": [np.nan],
            "xag_p90": [0.3],
            "minutes_played": [2700],
        })
        result = compute_composites(df)
        assert np.isnan(result.iloc[0]["goal_threat"])

    def test_missing_columns_produce_nan(self):
        df = pd.DataFrame({
            "goals": [10],
            "minutes_played": [2700],
        })
        result = compute_composites(df)
        assert np.isnan(result.iloc[0]["goal_threat"])


class TestPercentileRanks:
    def test_percentile_distribution(self, sample_feature_df):
        pctl_cols = [c for c in sample_feature_df.columns if c.endswith("_pctl")]
        assert len(pctl_cols) > 0

        for col in pctl_cols:
            values = sample_feature_df[col].dropna()
            if len(values) > 0:
                assert values.min() >= 0
                assert values.max() <= 100

    def test_percentile_within_position_group(self, sample_player_df):
        from football_scout.pipeline.aggregate import add_per90_columns

        df = add_per90_columns(sample_player_df)
        df = compute_composites(df)
        result = compute_percentile_ranks(df, position_col="position_group")

        pctl_cols = [c for c in result.columns if c.endswith("_pctl")]
        assert len(pctl_cols) > 0

    def test_nan_stays_nan_in_percentiles(self):
        df = pd.DataFrame({
            "goals_p90": [1.0, 2.0, np.nan, 4.0],
            "position_group": ["CM", "CM", "CM", "CM"],
        })
        result = compute_percentile_ranks(df)
        assert np.isnan(result.iloc[2]["goals_p90_pctl"])

    def test_no_position_column(self):
        df = pd.DataFrame({
            "goals_p90": [1.0, 2.0, 3.0, 4.0],
        })
        result = compute_percentile_ranks(df, position_col="nonexistent")
        assert "goals_p90_pctl" in result.columns
