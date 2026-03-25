"""Understat adapter — secondary source for current-season xG data."""

from __future__ import annotations

import json
import logging
import re

import numpy as np
import pandas as pd
import requests

from football_scout.adapters.base import PlayerStatsAdapter
from football_scout.cache.rate_limiter import rate_limiter
from football_scout.cache.store import CacheStore

logger = logging.getLogger(__name__)

# Map internal league names to Understat league slugs
LEAGUE_MAP: dict[str, str] = {
    "ENG-Premier League": "EPL",
    "ESP-La Liga": "La_Liga",
    "GER-Bundesliga": "Bundesliga",
    "ITA-Serie A": "Serie_A",
    "FRA-Ligue 1": "Ligue_1",
}

# Map season format: "2024-25" -> "2024"
def _season_to_year(season: str) -> str:
    return season.split("-")[0]


class UnderstatAdapter(PlayerStatsAdapter):
    """Scrapes aggregated player stats from Understat."""

    def __init__(self, cache: CacheStore | None = None):
        self.cache = cache or CacheStore()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        })

    def source_name(self) -> str:
        return "understat"

    def available_metrics(self) -> list[str]:
        return [
            "goals", "assists", "xg", "npxg", "xa", "shots", "key_passes",
            "yellow_cards", "red_cards", "minutes_played", "appearances",
            "xg_p90", "npxg_p90",
        ]

    def get_player_season_stats(
        self, league: str, season: str, min_minutes: int = 900
    ) -> pd.DataFrame:
        understat_league = LEAGUE_MAP.get(league)
        if understat_league is None:
            logger.warning(
                "League '%s' not available on Understat. "
                "Available: %s", league, list(LEAGUE_MAP.keys())
            )
            return pd.DataFrame()

        year = _season_to_year(season)
        url = f"https://understat.com/league/{understat_league}/{year}"

        # Try cache first
        cache_params = {"league": understat_league, "year": year}
        try:
            cached = self.cache.get(self.source_name(), "league_players", cache_params)
            if cached is not None:
                raw_data = json.loads(cached.decode("utf-8"))
                return self._parse_players(raw_data, league, season, min_minutes)
        except Exception:
            pass

        # Fetch from Understat
        rate_limiter.wait(self.source_name())
        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error("Failed to fetch Understat data for %s/%s: %s", league, season, e)
            return pd.DataFrame()

        # Extract JSON from embedded script tag
        raw_data = self._extract_players_data(resp.text)
        if raw_data is None:
            logger.warning("Could not extract player data from Understat for %s/%s", league, season)
            return pd.DataFrame()

        # Cache the raw data
        try:
            self.cache.put(
                self.source_name(), "league_players", cache_params,
                json.dumps(raw_data).encode("utf-8"),
                ttl_seconds=86400,
            )
        except Exception:
            pass

        return self._parse_players(raw_data, league, season, min_minutes)

    def _extract_players_data(self, html: str) -> list[dict] | None:
        """Extract playersData JSON from Understat page HTML."""
        pattern = r"var\s+playersData\s*=\s*JSON\.parse\(\'(.*?)\'\)"
        match = re.search(pattern, html)
        if not match:
            return None
        try:
            # Understat encodes the JSON string with escaped characters
            encoded = match.group(1)
            decoded = encoded.encode("utf-8").decode("unicode_escape")
            return json.loads(decoded)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning("Failed to parse Understat JSON: %s", e)
            return None

    def _parse_players(
        self,
        raw_data: list[dict],
        league: str,
        season: str,
        min_minutes: int,
    ) -> pd.DataFrame:
        """Convert Understat JSON to canonical DataFrame."""
        rows = []
        for p in raw_data:
            try:
                minutes = int(p.get("time", 0))
                if minutes < min_minutes:
                    continue

                nineties = minutes / 90.0
                xg = float(p.get("xG", 0))
                npxg = float(p.get("npxG", 0))
                xa = float(p.get("xA", 0))

                rows.append({
                    "player_id": f"us_{p.get('id', '')}",
                    "player_name": p.get("player_name", ""),
                    "team": p.get("team_title", ""),
                    "league": league,
                    "season": season,
                    "appearances": int(p.get("games", 0)),
                    "minutes_played": minutes,
                    "goals": int(p.get("goals", 0)),
                    "assists": int(p.get("assists", 0)),
                    "shots": int(p.get("shots", 0)),
                    "key_passes": int(p.get("key_passes", 0)),
                    "xg": xg,
                    "npxg": npxg,
                    "xa": xa,
                    "xg_understat": xg,
                    "xa_understat": xa,
                    "yellow_cards": int(p.get("yellow_cards", 0)),
                    "red_cards": int(p.get("red_cards", 0)),
                    "xg_p90": xg / nineties if nineties > 0 else np.nan,
                    "npxg_p90": npxg / nineties if nineties > 0 else np.nan,
                    "goals_p90": int(p.get("goals", 0)) / nineties if nineties > 0 else np.nan,
                    "data_source": self.source_name(),
                })
            except (ValueError, TypeError) as e:
                logger.debug("Skipping player record: %s", e)
                continue

        if not rows:
            return pd.DataFrame()

        return pd.DataFrame(rows)
