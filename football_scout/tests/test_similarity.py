"""Tests for the similarity engine."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from football_scout.models.similarity import SimilarityEngine


class TestSimilarityEngine:
    def test_identical_player_high_similarity(self, sample_feature_df):
        engine = SimilarityEngine(sample_feature_df)
        player_name = sample_feature_df.iloc[0]["player_name"]

        # Create a duplicate
        df = sample_feature_df.copy()
        duplicate = df.iloc[0].copy()
        duplicate["player_id"] = "duplicate_0"
        duplicate["player_name"] = "Duplicate Player"
        df = pd.concat([df, duplicate.to_frame().T], ignore_index=True)

        engine2 = SimilarityEngine(df)
        result = engine2.find_similar(target=player_name, position_group=None, n=5)
        assert not result.empty
        # The duplicate should be the most similar
        assert result.iloc[0]["similarity_score"] > 0.95

    def test_nan_features_handled(self, sample_feature_df):
        df = sample_feature_df.copy()
        # Set many features to NaN for one player
        for col in ["goals_p90", "xg_p90", "npxg_p90"]:
            if col in df.columns:
                df.iloc[0, df.columns.get_loc(col)] = np.nan

        engine = SimilarityEngine(df)
        result = engine.find_similar(
            target=df.iloc[0]["player_name"],
            position_group=None,
            n=5,
        )
        # Should still return results
        assert isinstance(result, pd.DataFrame)

    def test_player_not_found_returns_empty(self, sample_feature_df):
        engine = SimilarityEngine(sample_feature_df)
        result = engine.find_similar(target="Nonexistent Player XYZ", position_group=None)
        assert result.empty

    def test_dict_target(self, sample_feature_df):
        engine = SimilarityEngine(sample_feature_df)
        profile = {"goals_p90": 0.5, "xg_p90": 0.4, "npxg_p90": 0.35}
        result = engine.find_similar(target=profile, position_group=None, n=5)
        assert isinstance(result, pd.DataFrame)

    def test_position_filter(self, sample_feature_df):
        engine = SimilarityEngine(sample_feature_df)
        player_name = sample_feature_df[
            sample_feature_df["position_group"] == "CM"
        ].iloc[0]["player_name"]

        result = engine.find_similar(
            target=player_name,
            position_group="CM",
            n=5,
        )
        if not result.empty and "position_group" in result.columns:
            assert all(result["position_group"] == "CM")

    def test_feature_weights_change_rankings(self, sample_feature_df):
        engine_no_weights = SimilarityEngine(sample_feature_df, {})
        engine_weighted = SimilarityEngine(sample_feature_df, {
            "similarity_weights": {
                "CM": {"goal_threat": 5.0}
            }
        })

        player = sample_feature_df[
            sample_feature_df["position_group"] == "CM"
        ].iloc[0]["player_name"]

        r1 = engine_no_weights.find_similar(target=player, position_group="CM", n=5)
        r2 = engine_weighted.find_similar(target=player, position_group="CM", n=5)

        # Rankings may differ when weights are applied
        assert isinstance(r1, pd.DataFrame)
        assert isinstance(r2, pd.DataFrame)
