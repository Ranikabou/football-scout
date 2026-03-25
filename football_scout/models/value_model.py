"""Market value regression model with SHAP explainability."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

# Feature columns for valuation model
VALUE_FEATURES = [
    "goals_p90", "npxg_p90", "xag_p90", "sca_p90", "gca_p90",
    "progressive_passes_p90", "progressive_carries_p90",
    "key_passes_p90", "tackles_won_p90", "interceptions_p90",
    "blocks_p90", "pressures_p90", "pressure_success_pct",
    "successful_dribbles_p90", "aerial_dominance",
    "pressing_intensity", "chance_creation", "defensive_contrib",
    "progressive_action", "goal_threat",
    "age",
]

# League tier ordinal encoding
LEAGUE_TIERS: dict[str, int] = {
    "ENG-Premier League": 1,
    "ESP-La Liga": 1,
    "GER-Bundesliga": 2,
    "ITA-Serie A": 2,
    "FRA-Ligue 1": 3,
}

PARAM_DISTRIBUTIONS = {
    "n_estimators": [100, 300, 500],
    "max_depth": [3, 5, 7],
    "learning_rate": [0.01, 0.05, 0.1],
    "subsample": [0.7, 0.8, 0.9],
}


class ValueModel:
    """Market value prediction with SHAP-based explanations."""

    def __init__(self):
        self.model: GradientBoostingRegressor | None = None
        self.explainer = None
        self.scaler = StandardScaler()
        self.feature_names: list[str] = []

    def train(self, feature_df: pd.DataFrame) -> dict:
        """Train the valuation model.

        Returns dict with training metrics.
        """
        df = feature_df.copy()

        # Target: log(market_value_eur)
        if "market_value_eur" not in df.columns:
            raise ValueError("market_value_eur column required for training")

        df = df[df["market_value_eur"].notna() & (df["market_value_eur"] > 0)].copy()
        if len(df) < 30:
            raise ValueError(f"Need at least 30 players with valuations, got {len(df)}")

        y = np.log(df["market_value_eur"].values)

        # Add league tier
        if "league" in df.columns:
            df["league_tier"] = df["league"].map(LEAGUE_TIERS).fillna(3)
        else:
            df["league_tier"] = 3

        # Select features
        all_features = VALUE_FEATURES + ["league_tier"]
        available = [f for f in all_features if f in df.columns]

        # Drop columns with >30% NaN
        keep = []
        for col in available:
            if df[col].notna().sum() / len(df) > 0.7:
                keep.append(col)
        self.feature_names = keep

        if len(self.feature_names) < 3:
            raise ValueError(f"Too few features available: {self.feature_names}")

        X = df[self.feature_names].copy()

        # Impute remaining NaN with median
        for col in self.feature_names:
            X[col] = X[col].fillna(X[col].median())

        X_scaled = self.scaler.fit_transform(X)

        # Stratified CV by position group (binned)
        if "position_group" in df.columns:
            strat = df["position_group"].astype(str).values
        else:
            strat = np.zeros(len(df))

        # Handle edge case where a group has <2 members
        from collections import Counter
        counts = Counter(strat)
        for i, s in enumerate(strat):
            if counts[s] < 2:
                strat[i] = "other"

        cv = StratifiedKFold(n_splits=min(5, len(df) // 6), shuffle=True, random_state=42)

        base_model = GradientBoostingRegressor(random_state=42)
        search = RandomizedSearchCV(
            base_model,
            PARAM_DISTRIBUTIONS,
            n_iter=20,
            cv=cv,
            scoring="neg_mean_squared_error",
            random_state=42,
            n_jobs=-1,
        )
        search.fit(X_scaled, y)

        self.model = search.best_estimator_
        logger.info("Best params: %s", search.best_params_)
        logger.info("Best CV score (neg MSE): %.4f", search.best_score_)

        # SHAP explainer
        try:
            import shap
            self.explainer = shap.TreeExplainer(self.model)
        except ImportError:
            logger.warning("shap not installed, explanations unavailable")

        return {
            "best_params": search.best_params_,
            "best_cv_score": float(search.best_score_),
            "n_features": len(self.feature_names),
            "n_samples": len(df),
            "features": self.feature_names,
        }

    def predict_and_flag(self, feature_df: pd.DataFrame) -> pd.DataFrame:
        """Predict market values and flag undervalued players."""
        if self.model is None:
            raise RuntimeError("Model not trained. Call train() first.")

        df = feature_df.copy()

        # Add league tier
        if "league" in df.columns:
            df["league_tier"] = df["league"].map(LEAGUE_TIERS).fillna(3)
        else:
            df["league_tier"] = 3

        available = [f for f in self.feature_names if f in df.columns]
        if len(available) != len(self.feature_names):
            missing = set(self.feature_names) - set(available)
            logger.warning("Missing features for prediction: %s", missing)
            for col in missing:
                df[col] = np.nan

        X = df[self.feature_names].copy()
        for col in self.feature_names:
            X[col] = X[col].fillna(X[col].median())

        X_scaled = self.scaler.transform(X)

        log_predicted = self.model.predict(X_scaled)
        df["predicted_value_eur"] = np.exp(log_predicted)

        # Value ratio: predicted / actual
        if "market_value_eur" in df.columns:
            df["value_ratio"] = np.where(
                df["market_value_eur"] > 0,
                df["predicted_value_eur"] / df["market_value_eur"],
                np.nan,
            )
            df["undervalued"] = df["value_ratio"] > 1.4
        else:
            df["value_ratio"] = np.nan
            df["undervalued"] = False

        return df

    def explain_player(self, player_features: np.ndarray):
        """Return SHAP values for a single player."""
        if self.explainer is None:
            raise RuntimeError("SHAP explainer not available")

        if player_features.ndim == 1:
            player_features = player_features.reshape(1, -1)

        scaled = self.scaler.transform(player_features)
        return self.explainer(scaled)
