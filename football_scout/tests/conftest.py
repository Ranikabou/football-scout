"""Shared test fixtures using StatsBomb open data and synthetic data."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from football_scout.schema.enums import PositionGroup


@pytest.fixture
def sample_player_df() -> pd.DataFrame:
    """Create a sample player DataFrame for testing."""
    np.random.seed(42)
    n = 50

    positions = list(PositionGroup)
    data = {
        "player_id": [f"test_{i}" for i in range(n)],
        "player_name": [f"Player {i}" for i in range(n)],
        "team": [f"Team {i % 5}" for i in range(n)],
        "league": ["ENG-Premier League"] * 25 + ["ESP-La Liga"] * 25,
        "season": ["2023-24"] * n,
        "age": np.random.randint(18, 35, n),
        "nationality": ["Country"] * n,
        "position_group": [positions[i % len(positions)].value for i in range(n)],
        "minutes_played": np.random.randint(900, 3400, n),
        "appearances": np.random.randint(10, 38, n),
        # Counting stats
        "goals": np.random.randint(0, 20, n),
        "assists": np.random.randint(0, 15, n),
        "shots": np.random.randint(10, 100, n),
        "shots_on_target": np.random.randint(5, 50, n),
        "xg": np.random.uniform(0, 15, n),
        "npxg": np.random.uniform(0, 12, n),
        "xag": np.random.uniform(0, 10, n),
        "xa": np.random.uniform(0, 8, n),
        "passes_completed": np.random.randint(200, 2000, n),
        "passes_attempted": np.random.randint(250, 2200, n),
        "progressive_passes": np.random.randint(10, 200, n),
        "progressive_carries": np.random.randint(5, 150, n),
        "key_passes": np.random.randint(5, 80, n),
        "sca": np.random.randint(10, 100, n),
        "gca": np.random.randint(0, 20, n),
        "tackles": np.random.randint(10, 100, n),
        "tackles_won": np.random.randint(5, 70, n),
        "interceptions": np.random.randint(5, 80, n),
        "blocks": np.random.randint(5, 50, n),
        "pressures": np.random.randint(50, 500, n),
        "pressure_successes": np.random.randint(10, 200, n),
        "pressures_att_third": np.random.randint(10, 150, n),
        "aerials_won": np.random.randint(0, 100, n),
        "aerials_lost": np.random.randint(0, 80, n),
        "touches": np.random.randint(300, 3000, n),
        "successful_dribbles": np.random.randint(0, 80, n),
        "market_value_eur": np.random.uniform(1e6, 100e6, n),
        "data_source": ["statsbomb"] * n,
    }

    df = pd.DataFrame(data)

    # Introduce some NaN values to test NaN handling
    for col in ["xg", "npxg", "xag", "pressures_att_third"]:
        mask = np.random.random(n) < 0.1
        df.loc[mask, col] = np.nan

    return df


@pytest.fixture
def sample_feature_df(sample_player_df: pd.DataFrame) -> pd.DataFrame:
    """Create a feature-engineered DataFrame."""
    from football_scout.pipeline.features import compute_all_features
    from football_scout.pipeline.normalize import compute_percentile_ranks

    df = compute_all_features(sample_player_df)
    df = compute_percentile_ranks(df)
    return df


@pytest.fixture
def sample_transfermarkt_csv(tmp_path) -> str:
    """Create a sample Transfermarkt CSV for testing."""
    data = {
        "player_name": ["Player 0", "Player 1", "Player 2"],
        "team": ["Team 0", "Team 1", "Team 2"],
        "league": ["Premier League", "Premier League", "La Liga"],
        "season": ["2023-24", "2023-24", "2023-24"],
        "market_value_eur": [50000000, 30000000, 20000000],
        "contract_expiry": ["2026-06", "2025-06", "2027-06"],
        "position": ["CM", "ST", "CB"],
        "age": [25, 23, 28],
        "nationality": ["England", "France", "Spain"],
    }
    path = tmp_path / "transfermarkt_values.csv"
    pd.DataFrame(data).to_csv(path, index=False)
    return str(path)
