"""Abstract base for all data source adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class PlayerStatsAdapter(ABC):
    """Protocol for data source adapters.

    All adapters must return DataFrames conforming to the canonical schema.
    Missing metrics must be NaN, never zero.
    """

    @abstractmethod
    def get_player_season_stats(
        self, league: str, season: str, min_minutes: int = 900
    ) -> pd.DataFrame:
        """Return DataFrame conforming to canonical schema.

        Missing metrics must be NaN, never zero.
        """
        ...

    @abstractmethod
    def available_metrics(self) -> list[str]:
        """Metric columns this adapter can populate."""
        ...

    @abstractmethod
    def source_name(self) -> str:
        """Identifier for cache keying and provenance."""
        ...
