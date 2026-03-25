"""Transfermarkt adapter — market valuations and contract metadata."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from football_scout.adapters.base import PlayerStatsAdapter
from football_scout.cache.rate_limiter import rate_limiter
from football_scout.cache.store import CacheStore

logger = logging.getLogger(__name__)

WORLDFOOTBALLR_CSV_URL = (
    "https://raw.githubusercontent.com/JaseZiv/worldfootballR_data/"
    "master/raw-data/transfermarkt_valuations/all_player_valuations.csv"
)


class TransfermarktAdapter(PlayerStatsAdapter):
    """Market valuations from Transfermarkt with CSV fallback."""

    def __init__(
        self,
        fallback_csv: str = "data/reference/transfermarkt_values.csv",
        cache: CacheStore | None = None,
    ):
        self.fallback_csv = Path(fallback_csv)
        self.cache = cache or CacheStore()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        })

    def source_name(self) -> str:
        return "transfermarkt"

    def available_metrics(self) -> list[str]:
        return [
            "market_value_eur", "contract_expiry", "age", "nationality",
            "position",
        ]

    def get_player_season_stats(
        self, league: str, season: str, min_minutes: int = 900
    ) -> pd.DataFrame:
        """Fetch Transfermarkt valuations. Falls back to local CSV if scraping fails."""
        # Try fetching from worldfootballR data repo
        df = self._fetch_from_worldfootballr(league, season)

        if df is None or df.empty:
            # Fall back to local CSV
            df = self._load_fallback_csv(league, season)

        if df is None or df.empty:
            logger.warning(
                "No Transfermarkt data available for %s/%s", league, season
            )
            return pd.DataFrame()

        df["league"] = league
        df["season"] = season
        df["data_source"] = self.source_name()
        return df

    def _fetch_from_worldfootballr(
        self, league: str, season: str
    ) -> pd.DataFrame | None:
        """Attempt to fetch valuations from worldfootballR GitHub data."""
        rate_limiter.wait(self.source_name())

        cache_params = {"league": league, "season": season, "source": "worldfootballr"}
        try:
            cached = self.cache.get(self.source_name(), "valuations", cache_params)
            if cached is not None:
                return pd.read_json(cached.decode("utf-8"))
        except Exception:
            pass

        try:
            resp = self.session.get(WORLDFOOTBALLR_CSV_URL, timeout=60)
            resp.raise_for_status()

            from io import StringIO
            full_df = pd.read_csv(StringIO(resp.text))

            # Filter to relevant league and season
            df = self._filter_valuations(full_df, league, season)
            if df is not None and not df.empty:
                try:
                    self.cache.put(
                        self.source_name(), "valuations", cache_params,
                        df.to_json().encode("utf-8"),
                        ttl_seconds=86400 * 7,  # 7-day TTL for valuations
                    )
                except Exception:
                    pass
            return df

        except Exception as e:
            logger.warning("Failed to fetch worldfootballR data: %s", e)
            return None

    def _filter_valuations(
        self, full_df: pd.DataFrame, league: str, season: str
    ) -> pd.DataFrame | None:
        """Filter the full valuations dataset to a specific league/season."""
        # The worldfootballR CSV has columns like:
        # player_name, comp_name, market_value_eur, player_club, date_of_birth, etc.
        league_short = league.split("-")[-1] if "-" in league else league

        # Filter by competition name (fuzzy match)
        if "comp_name" in full_df.columns:
            mask = full_df["comp_name"].str.contains(
                league_short, case=False, na=False
            )
            df = full_df[mask].copy()
        else:
            df = full_df.copy()

        if df.empty:
            return None

        # Normalize column names
        rename_map = {
            "player_name": "player_name",
            "player_club": "team",
            "market_value_eur": "market_value_eur",
            "date_of_birth": "date_of_birth",
            "player_club_country": "nationality",
            "player_position": "position",
        }
        for old, new in rename_map.items():
            if old in df.columns and old != new:
                df = df.rename(columns={old: new})

        # Parse market value
        if "market_value_eur" in df.columns:
            df["market_value_eur"] = pd.to_numeric(
                df["market_value_eur"], errors="coerce"
            )

        # Get most recent valuation per player
        if "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
            df = df.sort_values("datetime", ascending=False)
            df = df.drop_duplicates(subset=["player_name"], keep="first")

        df["player_id"] = "tm_" + df.index.astype(str)
        return df

    def _load_fallback_csv(
        self, league: str, season: str
    ) -> pd.DataFrame | None:
        """Load pre-prepared local CSV with Transfermarkt valuations."""
        if not self.fallback_csv.exists():
            logger.info(
                "Fallback CSV not found at %s. "
                "Place a CSV with columns: player_name, team, market_value_eur, "
                "contract_expiry, position, age, nationality",
                self.fallback_csv,
            )
            return None

        try:
            df = pd.read_csv(self.fallback_csv)
            league_short = league.split("-")[-1] if "-" in league else league

            if "league" in df.columns:
                df = df[df["league"].str.contains(league_short, case=False, na=False)]
            if "season" in df.columns:
                df = df[df["season"] == season]

            df["player_id"] = "tm_" + df.index.astype(str)
            return df
        except Exception as e:
            logger.error("Failed to load fallback CSV: %s", e)
            return None
