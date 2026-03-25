"""FBref adapter — degraded source for basic stats and metadata.

Post-January 2026, FBref lost all advanced stats when Opta terminated their
data feed. Only basic counting stats remain. This adapter provides bio metadata
and basic stats for cross-referencing.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from football_scout.adapters.base import PlayerStatsAdapter
from football_scout.cache.rate_limiter import rate_limiter
from football_scout.cache.store import CacheStore

logger = logging.getLogger(__name__)

# Map internal league names to FBref/soccerdata identifiers
LEAGUE_MAP: dict[str, str] = {
    "ENG-Premier League": "ENG-Premier League",
    "ESP-La Liga": "ESP-La Liga",
    "GER-Bundesliga": "GER-Bundesliga",
    "ITA-Serie A": "ITA-Serie A",
    "FRA-Ligue 1": "FRA-Ligue 1",
}


class FBrefAdapter(PlayerStatsAdapter):
    """Basic stats from FBref (degraded — no advanced metrics since Jan 2026)."""

    def __init__(self, cache: CacheStore | None = None):
        self.cache = cache or CacheStore()

    def source_name(self) -> str:
        return "fbref"

    def available_metrics(self) -> list[str]:
        return [
            "goals", "assists", "penalties_scored", "penalties_attempted",
            "minutes_played", "yellow_cards", "red_cards",
            "starts", "appearances", "age", "nationality",
        ]

    def get_player_season_stats(
        self, league: str, season: str, min_minutes: int = 900
    ) -> pd.DataFrame:
        fbref_league = LEAGUE_MAP.get(league)
        if fbref_league is None:
            logger.warning("League '%s' not mapped for FBref", league)
            return pd.DataFrame()

        rate_limiter.wait(self.source_name())

        try:
            import soccerdata as sd
            fbref = sd.FBref(leagues=fbref_league, seasons=season)
            raw = fbref.read_player_season_stats(stat_type="standard")
        except ImportError:
            logger.warning(
                "soccerdata not installed. Install with: pip install soccerdata"
            )
            return pd.DataFrame()
        except Exception as e:
            logger.error("Failed to fetch FBref data for %s/%s: %s", league, season, e)
            return pd.DataFrame()

        if raw.empty:
            return pd.DataFrame()

        return self._normalize(raw, league, season, min_minutes)

    def _normalize(
        self, raw: pd.DataFrame, league: str, season: str, min_minutes: int
    ) -> pd.DataFrame:
        """Convert FBref raw output to canonical schema."""
        # FBref DataFrames have multi-level indices; flatten
        df = raw.reset_index()

        # Rename columns to match canonical schema (FBref column names vary)
        col_map = {
            "player": "player_name",
            "squad": "team",
            "age": "age",
            "nation": "nationality",
            "pos": "position",
            "mp": "appearances",
            "starts": "starts",
            "min": "minutes_played",
            "gls": "goals",
            "ast": "assists",
            "pk": "penalties_scored",
            "pkatt": "penalties_attempted",
            "crdy": "yellow_cards",
            "crdr": "red_cards",
        }

        renamed = {}
        for old, new in col_map.items():
            # Try case-insensitive match
            for col in df.columns:
                if str(col).lower().replace(" ", "") == old.lower():
                    renamed[col] = new
                    break

        df = df.rename(columns=renamed)

        # Ensure minutes_played is numeric
        if "minutes_played" in df.columns:
            df["minutes_played"] = pd.to_numeric(
                df["minutes_played"].astype(str).str.replace(",", ""),
                errors="coerce",
            )
            df = df[df["minutes_played"] >= min_minutes].copy()

        # Extract age as integer
        if "age" in df.columns:
            df["age"] = pd.to_numeric(
                df["age"].astype(str).str.split("-").str[0],
                errors="coerce",
            ).astype("Int64")

        # Add standard columns
        df["league"] = league
        df["season"] = season
        df["data_source"] = self.source_name()
        df["player_id"] = "fb_" + df.index.astype(str)

        # Per-90 for available stats
        if "minutes_played" in df.columns:
            nineties = df["minutes_played"] / 90.0
            if "goals" in df.columns:
                df["goals_p90"] = pd.to_numeric(df["goals"], errors="coerce") / nineties
            if "assists" in df.columns:
                df["assists_p90"] = pd.to_numeric(df["assists"], errors="coerce") / nineties

        return df
