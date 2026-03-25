"""Cosine similarity-based player matching engine."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

# Default feature columns for similarity computation
DEFAULT_FEATURES = [
    "goals_p90", "xg_p90", "npxg_p90", "xag_p90",
    "sca_p90", "gca_p90",
    "progressive_passes_p90", "progressive_carries_p90",
    "key_passes_p90", "pass_completion_pct",
    "tackles_won_p90", "interceptions_p90", "blocks_p90",
    "pressures_p90", "pressure_success_pct",
    "successful_dribbles_p90", "touches_p90",
    "pressing_intensity", "chance_creation", "defensive_contrib",
    "progressive_action", "goal_threat", "aerial_dominance",
]


class SimilarityEngine:
    """Find similar players using weighted cosine similarity."""

    def __init__(self, feature_df: pd.DataFrame, config: dict | None = None):
        self.df = feature_df.copy()
        config = config or {}
        self.weights = config.get("similarity_weights", {})

    def find_similar(
        self,
        target: str | dict,
        position_group: str | None = None,
        n: int = 10,
        leagues: list[str] | None = None,
        features: list[str] | None = None,
    ) -> pd.DataFrame:
        """Find top-N most similar players to target.

        Args:
            target: Player name (string) or ideal profile (dict of metric: value).
            position_group: Filter comparison pool to this position group.
            n: Number of similar players to return.
            leagues: Filter to specific leagues.
            features: Feature columns to use (defaults to DEFAULT_FEATURES).
        """
        pool = self.df.copy()

        # Filter pool
        if position_group and "position_group" in pool.columns:
            pool = pool[pool["position_group"] == position_group]
        if leagues and "league" in pool.columns:
            pool = pool[pool["league"].isin(leagues)]

        if pool.empty:
            logger.warning("Empty comparison pool after filtering")
            return pd.DataFrame()

        # Select features
        feature_cols = features or DEFAULT_FEATURES
        available_features = [f for f in feature_cols if f in pool.columns]
        if not available_features:
            logger.warning("No feature columns available for similarity")
            return pd.DataFrame()

        # Get target vector
        if isinstance(target, str):
            matches = pool[pool["player_name"].str.lower() == target.lower()]
            if matches.empty:
                # Try fuzzy
                matches = pool[
                    pool["player_name"].str.lower().str.contains(
                        target.lower(), na=False
                    )
                ]
            if matches.empty:
                logger.warning("Player '%s' not found in dataset", target)
                return pd.DataFrame()
            target_row = matches.iloc[0]
            target_vector = target_row[available_features].values.astype(float)
            target_idx = matches.index[0]
        elif isinstance(target, dict):
            target_vector = np.array([
                target.get(f, np.nan) for f in available_features
            ], dtype=float)
            target_idx = None
        else:
            raise ValueError("target must be a player name (str) or profile (dict)")

        # Build feature matrix
        feature_matrix = pool[available_features].values.astype(float)

        # Find mutually available features (non-NaN in both target and each candidate)
        target_mask = ~np.isnan(target_vector)

        scores = []
        for i in range(len(feature_matrix)):
            candidate_mask = ~np.isnan(feature_matrix[i])
            mutual = target_mask & candidate_mask

            if mutual.sum() < 3:  # Need at least 3 shared features
                scores.append(np.nan)
                continue

            t_vec = target_vector[mutual]
            c_vec = feature_matrix[i][mutual]

            # Apply weights
            weight_vec = self._get_weights(
                [available_features[j] for j in range(len(available_features)) if mutual[j]],
                position_group,
            )

            # Scale
            combined = np.vstack([t_vec, c_vec])
            if combined.std(axis=0).min() == 0:
                # Avoid division by zero in scaling
                scores.append(1.0 if np.allclose(t_vec, c_vec) else 0.0)
                continue

            scaler = StandardScaler()
            scaled = scaler.fit_transform(combined.T).T
            t_scaled = scaled[0] * weight_vec
            c_scaled = scaled[1] * weight_vec

            sim = cosine_similarity(
                t_scaled.reshape(1, -1), c_scaled.reshape(1, -1)
            )[0][0]
            scores.append(float(sim))

        pool = pool.copy()
        pool["similarity_score"] = scores
        pool["shared_features_pct"] = [
            (target_mask & ~np.isnan(feature_matrix[i])).sum() / len(available_features) * 100
            for i in range(len(feature_matrix))
        ]

        # Remove the target player itself
        if target_idx is not None:
            pool = pool.drop(index=target_idx, errors="ignore")

        # Sort and return top N
        result = pool.dropna(subset=["similarity_score"])
        result = result.sort_values("similarity_score", ascending=False).head(n)

        return result

    def _get_weights(
        self, feature_names: list[str], position_group: str | None
    ) -> np.ndarray:
        """Get feature weights for the given position group."""
        weights = np.ones(len(feature_names))

        if position_group and position_group in self.weights:
            pos_weights = self.weights[position_group]
            for i, feat in enumerate(feature_names):
                if feat in pos_weights:
                    weights[i] = pos_weights[feat]

        return weights
