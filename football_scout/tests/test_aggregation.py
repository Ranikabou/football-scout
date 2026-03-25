"""Tests for event-to-season aggregation and per-90 computation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from football_scout.pipeline.aggregate import add_per90_columns, compute_per90


class TestPer90:
    def test_basic_per90(self):
        df = pd.DataFrame({
            "goals": [10, 5, 0],
            "minutes_played": [2700, 1800, 900],
        })
        result = compute_per90(df, "goals")
        expected = [10 / 30, 5 / 20, 0 / 10]
        np.testing.assert_array_almost_equal(result, expected)

    def test_zero_minutes_returns_nan(self):
        df = pd.DataFrame({
            "goals": [5],
            "minutes_played": [0],
        })
        result = compute_per90(df, "goals")
        assert np.isnan(result[0])


class TestAddPer90Columns:
    def test_adds_all_per90_columns(self, sample_player_df):
        result = add_per90_columns(sample_player_df)
        assert "goals_p90" in result.columns
        assert "xg_p90" in result.columns
        assert "tackles_won_p90" in result.columns

    def test_per90_values_correct(self):
        df = pd.DataFrame({
            "goals": [10],
            "assists": [5],
            "xg": [8.5],
            "npxg": [7.0],
            "xag": [4.0],
            "sca": [30],
            "gca": [3],
            "progressive_passes": [50],
            "progressive_carries": [30],
            "key_passes": [20],
            "tackles_won": [40],
            "interceptions": [25],
            "blocks": [15],
            "pressures": [200],
            "pressures_att_third": [80],
            "successful_dribbles": [20],
            "touches": [1500],
            "minutes_played": [2700],
            "passes_completed": [800],
            "passes_attempted": [1000],
            "pressure_successes": [60],
        })
        result = add_per90_columns(df)

        nineties = 2700 / 90.0
        assert abs(result.iloc[0]["goals_p90"] - 10 / nineties) < 1e-6
        assert abs(result.iloc[0]["xg_p90"] - 8.5 / nineties) < 1e-6

    def test_pass_completion_pct(self):
        df = pd.DataFrame({
            "passes_completed": [800],
            "passes_attempted": [1000],
            "minutes_played": [2700],
        })
        result = add_per90_columns(df)
        assert abs(result.iloc[0]["pass_completion_pct"] - 80.0) < 1e-6

    def test_nan_propagation(self):
        df = pd.DataFrame({
            "goals": [np.nan],
            "minutes_played": [2700],
        })
        result = add_per90_columns(df)
        assert np.isnan(result.iloc[0]["goals_p90"])

    def test_no_minutes_column(self):
        df = pd.DataFrame({"goals": [10]})
        result = add_per90_columns(df)
        assert "goals_p90" not in result.columns
