"""Tests for data source adapters."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from football_scout.adapters.base import PlayerStatsAdapter
from football_scout.adapters.statsbomb_adapter import StatsBombAdapter
from football_scout.adapters.understat_adapter import UnderstatAdapter
from football_scout.adapters.fbref_adapter import FBrefAdapter
from football_scout.adapters.transfermarkt import TransfermarktAdapter


class TestAdapterProtocol:
    """Test that all adapters implement the protocol correctly."""

    @pytest.mark.parametrize("adapter_cls", [
        StatsBombAdapter,
        UnderstatAdapter,
        FBrefAdapter,
        TransfermarktAdapter,
    ])
    def test_implements_protocol(self, adapter_cls):
        adapter = adapter_cls()
        assert isinstance(adapter, PlayerStatsAdapter)
        assert isinstance(adapter.source_name(), str)
        assert isinstance(adapter.available_metrics(), list)
        assert len(adapter.available_metrics()) > 0

    @pytest.mark.parametrize("adapter_cls,expected_name", [
        (StatsBombAdapter, "statsbomb"),
        (UnderstatAdapter, "understat"),
        (FBrefAdapter, "fbref"),
        (TransfermarktAdapter, "transfermarkt"),
    ])
    def test_source_name(self, adapter_cls, expected_name):
        adapter = adapter_cls()
        assert adapter.source_name() == expected_name


class TestStatsBombAdapter:
    def test_unavailable_league_returns_empty(self):
        adapter = StatsBombAdapter(mode="open")
        df = adapter.get_player_season_stats("FAKE-League", "2023-24")
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_progressive_pass_detection(self):
        adapter = StatsBombAdapter(mode="open")
        # Pass moving 15m toward goal
        pass_row = pd.Series({
            "location": [50, 40],
            "pass_end_location": [65, 40],
        })
        assert adapter._is_progressive_pass(pass_row) is True

        # Pass moving sideways
        pass_row2 = pd.Series({
            "location": [50, 20],
            "pass_end_location": [50, 60],
        })
        assert adapter._is_progressive_pass(pass_row2) is False

    def test_progressive_carry_detection(self):
        adapter = StatsBombAdapter(mode="open")
        carry_row = pd.Series({
            "location": [50, 40],
            "carry_end_location": [65, 40],
        })
        assert adapter._is_progressive_carry(carry_row) is True


class TestUnderstatAdapter:
    def test_unavailable_league_returns_empty(self):
        adapter = UnderstatAdapter()
        df = adapter.get_player_season_stats("FAKE-League", "2023-24")
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_extract_players_data_no_match(self):
        adapter = UnderstatAdapter()
        result = adapter._extract_players_data("<html>no data here</html>")
        assert result is None


class TestTransfermarktAdapter:
    def test_fallback_csv(self, sample_transfermarkt_csv):
        adapter = TransfermarktAdapter(fallback_csv=sample_transfermarkt_csv)
        df = adapter._load_fallback_csv("ENG-Premier League", "2023-24")
        assert df is not None
        assert len(df) > 0
        assert "market_value_eur" in df.columns

    def test_missing_fallback_returns_none(self, tmp_path):
        adapter = TransfermarktAdapter(fallback_csv=str(tmp_path / "nonexistent.csv"))
        df = adapter._load_fallback_csv("ENG-Premier League", "2023-24")
        assert df is None
