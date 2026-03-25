"""StatsBomb adapter — primary data source using event-level data."""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np
import pandas as pd

from football_scout.adapters.base import PlayerStatsAdapter
from football_scout.cache.rate_limiter import rate_limiter
from football_scout.cache.store import CacheStore

logger = logging.getLogger(__name__)

# StatsBomb open data competition/season mappings
COMPETITION_MAP: dict[str, int] = {
    "ESP-La Liga": 11,
    "ENG-Premier League": 2,
    "GER-Bundesliga": 9,
    "ITA-Serie A": 12,
    "FRA-Ligue 1": 7,
    "FIFA World Cup": 43,
    "UEFA Champions League": 16,
    "ENG-FA WSL": 37,
}

# Hardcoded season name -> season_id mapping for StatsBomb open data.
# sb.competitions() does not exist in statsbombpy>=1.0; season IDs are fixed
# for the open-data repository and do not change.
OPEN_DATA_SEASONS: dict[int, dict[str, int]] = {
    11: {  # ESP-La Liga
        "2017-18": 1,
        "2018-19": 2,
        "2019-20": 25,
        "2020-21": 90,
        "2021-22": 37,
        "2022-23": 281,
        "2023-24": 317,
    },
    2: {  # ENG-Premier League
        "2003-04": 44,
    },
    9: {  # GER-Bundesliga
        "2015-16": 27,
    },
    12: {  # ITA-Serie A
        "2015-16": 27,
    },
    7: {  # FRA-Ligue 1
        "2015-16": 27,
    },
    43: {  # FIFA World Cup
        "2018": 3,
        "2022": 106,
    },
    16: {  # UEFA Champions League
        "2018-19": 4,
        "2020-21": 90,
        "2021-22": 37,
    },
    37: {  # ENG-FA WSL
        "2018-19": 4,
        "2019-20": 42,
        "2020-21": 90,
        "2021-22": 37,
    },
}


class StatsBombAdapter(PlayerStatsAdapter):
    """Adapter for StatsBomb open/paid event data."""

    def __init__(
        self,
        mode: str = "open",
        credentials: dict[str, str] | None = None,
        cache: CacheStore | None = None,
    ):
        self.mode = mode
        self.creds = credentials or {}
        self.cache = cache or CacheStore()
        self._sb = None

    def _get_sb(self) -> Any:
        if self._sb is None:
            import statsbombpy as sb
            self._sb = sb
        return self._sb

    def source_name(self) -> str:
        return "statsbomb"

    def available_metrics(self) -> list[str]:
        return [
            "goals", "assists", "shots", "shots_on_target", "xg", "npxg",
            "passes_completed", "passes_attempted", "progressive_passes",
            "key_passes", "xag",
            "progressive_carries", "touches", "successful_dribbles",
            "attempted_dribbles", "miscontrols",
            "tackles", "tackles_won", "interceptions", "blocks", "clearances",
            "pressures", "pressure_successes", "pressures_att_third",
            "aerials_won", "aerials_lost",
            "sca", "gca",
            "minutes_played",
        ]

    def _get_available_seasons(self, competition_id: int) -> list[str]:
        """Return the list of available season names for a competition using
        the hardcoded open-data mapping (sb.competitions() does not exist in
        current statsbombpy releases)."""
        seasons_map = OPEN_DATA_SEASONS.get(competition_id, {})
        return list(seasons_map.keys())

    def _find_season_id(
        self, competition_id: int, season: str
    ) -> int | None:
        """Look up the StatsBomb season_id from the hardcoded open-data mapping."""
        seasons_map = OPEN_DATA_SEASONS.get(competition_id, {})
        return seasons_map.get(season)

    def get_player_season_stats(
        self, league: str, season: str, min_minutes: int = 900
    ) -> pd.DataFrame:
        competition_id = COMPETITION_MAP.get(league)
        if competition_id is None:
            logger.warning(
                "League '%s' not mapped to StatsBomb competition ID", league
            )
            return pd.DataFrame()

        sb = self._get_sb()
        season_id = self._find_season_id(competition_id, season)
        if season_id is None:
            available = self._get_available_seasons(competition_id)
            logger.warning(
                "Season '%s' not available for %s in StatsBomb open data. "
                "Available seasons: %s",
                season, league, available,
            )
            return pd.DataFrame()

        # Get matches
        try:
            matches = sb.matches(
                competition_id=competition_id,
                season_id=season_id,
                **({"creds": self.creds} if self.mode == "paid" else {}),
            )
        except Exception as e:
            logger.error("Failed to fetch matches: %s", e)
            return pd.DataFrame()

        if matches.empty:
            return pd.DataFrame()

        # Aggregate events across all matches
        all_player_stats: list[dict] = []
        for _, match_row in matches.iterrows():
            match_id = int(match_row["match_id"])
            rate_limiter.wait(self.source_name())
            try:
                events = sb.events(
                    match_id=match_id,
                    split=True,
                    flatten_attrs=True,
                    **({"creds": self.creds} if self.mode == "paid" else {}),
                )
                match_stats = self._aggregate_match_events(events, match_id)
                all_player_stats.extend(match_stats)
            except Exception as e:
                logger.warning("Failed to process match %d: %s", match_id, e)
                continue

        if not all_player_stats:
            return pd.DataFrame()

        # Combine per-match stats into season totals
        df = pd.DataFrame(all_player_stats)
        season_df = self._aggregate_season(df, min_minutes)
        season_df["league"] = league
        season_df["season"] = season
        season_df["data_source"] = self.source_name()
        return season_df

    def _aggregate_match_events(
        self, events: dict[str, pd.DataFrame], match_id: int
    ) -> list[dict]:
        """Aggregate event-level data from a single match into per-player stats."""
        player_stats: dict[str, dict] = {}

        def _ensure_player(player_id: str, player_name: str, team: str) -> None:
            if player_id not in player_stats:
                player_stats[player_id] = {
                    "player_id": str(player_id),
                    "player_name": player_name,
                    "team": team,
                    "match_id": match_id,
                    "minutes": 0,
                    "goals": 0, "shots": 0, "shots_on_target": 0,
                    "xg": 0.0, "npxg": 0.0,
                    "passes_completed": 0, "passes_attempted": 0,
                    "progressive_passes": 0, "key_passes": 0, "xag": 0.0,
                    "carries": 0, "progressive_carries": 0,
                    "touches": 0, "successful_dribbles": 0,
                    "attempted_dribbles": 0, "miscontrols": 0,
                    "tackles": 0, "tackles_won": 0,
                    "interceptions": 0, "blocks": 0, "clearances": 0,
                    "pressures": 0, "pressure_successes": 0,
                    "pressures_att_third": 0,
                    "aerials_won": 0, "aerials_lost": 0,
                    "sca": 0, "gca": 0,
                    "yellow_cards": 0, "red_cards": 0,
                }

        # Process shots
        if "shots" in events and not events["shots"].empty:
            shots_df = events["shots"]
            for _, shot in shots_df.iterrows():
                pid = str(shot.get("player_id", ""))
                pname = shot.get("player", "")
                team = shot.get("team", "")
                if not pid:
                    continue
                _ensure_player(pid, pname, team)
                player_stats[pid]["shots"] += 1
                xg_val = shot.get("shot_statsbomb_xg", 0.0)
                if pd.notna(xg_val):
                    player_stats[pid]["xg"] += float(xg_val)
                outcome = str(shot.get("shot_outcome", "")).lower()
                if outcome == "goal":
                    player_stats[pid]["goals"] += 1
                if outcome in ("goal", "saved", "saved to post"):
                    player_stats[pid]["shots_on_target"] += 1
                shot_type = str(shot.get("shot_type", ""))
                if shot_type != "Penalty" and pd.notna(xg_val):
                    player_stats[pid]["npxg"] += float(xg_val)

        # Process passes
        if "passes" in events and not events["passes"].empty:
            passes_df = events["passes"]
            for _, p in passes_df.iterrows():
                pid = str(p.get("player_id", ""))
                pname = p.get("player", "")
                team = p.get("team", "")
                if not pid:
                    continue
                _ensure_player(pid, pname, team)
                player_stats[pid]["passes_attempted"] += 1
                outcome = str(p.get("pass_outcome", ""))
                if outcome == "" or outcome == "nan" or pd.isna(p.get("pass_outcome")):
                    player_stats[pid]["passes_completed"] += 1

                # Progressive pass: moves ball >=10m toward goal
                if self._is_progressive_pass(p):
                    player_stats[pid]["progressive_passes"] += 1

                # Key pass: leads to a shot
                if p.get("pass_shot_assist") is True or p.get("pass_goal_assist") is True:
                    player_stats[pid]["key_passes"] += 1
                    player_stats[pid]["sca"] += 1
                if p.get("pass_goal_assist") is True:
                    player_stats[pid]["gca"] += 1

                xa_val = p.get("pass_xa", 0.0)
                if pd.notna(xa_val):
                    player_stats[pid]["xag"] += float(xa_val)

        # Process carries/dribbles
        if "carries" in events and not events["carries"].empty:
            for _, c in events["carries"].iterrows():
                pid = str(c.get("player_id", ""))
                pname = c.get("player", "")
                team = c.get("team", "")
                if not pid:
                    continue
                _ensure_player(pid, pname, team)
                player_stats[pid]["touches"] += 1
                if self._is_progressive_carry(c):
                    player_stats[pid]["progressive_carries"] += 1

        if "dribbles" in events and not events["dribbles"].empty:
            for _, d in events["dribbles"].iterrows():
                pid = str(d.get("player_id", ""))
                pname = d.get("player", "")
                team = d.get("team", "")
                if not pid:
                    continue
                _ensure_player(pid, pname, team)
                player_stats[pid]["attempted_dribbles"] += 1
                outcome = str(d.get("dribble_outcome", "")).lower()
                if outcome == "complete":
                    player_stats[pid]["successful_dribbles"] += 1

        # Process pressures
        if "pressures" in events and not events["pressures"].empty:
            for _, pr in events["pressures"].iterrows():
                pid = str(pr.get("player_id", ""))
                pname = pr.get("player", "")
                team = pr.get("team", "")
                if not pid:
                    continue
                _ensure_player(pid, pname, team)
                player_stats[pid]["pressures"] += 1
                # Check location for attacking third (x > 80 on StatsBomb pitch 120x80)
                loc = pr.get("location")
                if isinstance(loc, (list, tuple)) and len(loc) >= 1:
                    if loc[0] > 80:
                        player_stats[pid]["pressures_att_third"] += 1

        # Process tackles, interceptions, blocks
        if "tactics" in events:
            pass  # tactics are lineup info, handled separately

        # Defensive actions from general events
        for event_type_key in ["tackles", "interceptions", "blocks", "clearances"]:
            if event_type_key in events and not events[event_type_key].empty:
                for _, ev in events[event_type_key].iterrows():
                    pid = str(ev.get("player_id", ""))
                    pname = ev.get("player", "")
                    team = ev.get("team", "")
                    if not pid:
                        continue
                    _ensure_player(pid, pname, team)
                    if event_type_key == "tackles":
                        player_stats[pid]["tackles"] += 1
                        outcome = str(ev.get("tackle_outcome", "")).lower()
                        if outcome in ("won", "success"):
                            player_stats[pid]["tackles_won"] += 1
                    elif event_type_key == "interceptions":
                        player_stats[pid]["interceptions"] += 1
                    elif event_type_key == "blocks":
                        player_stats[pid]["blocks"] += 1
                    elif event_type_key == "clearances":
                        player_stats[pid]["clearances"] += 1

        # Process duels (aerials)
        if "duels" in events and not events["duels"].empty:
            for _, d in events["duels"].iterrows():
                pid = str(d.get("player_id", ""))
                pname = d.get("player", "")
                team = d.get("team", "")
                if not pid:
                    continue
                duel_type = str(d.get("duel_type", "")).lower()
                if "aerial" not in duel_type:
                    continue
                _ensure_player(pid, pname, team)
                outcome = str(d.get("duel_outcome", "")).lower()
                if outcome in ("won", "success"):
                    player_stats[pid]["aerials_won"] += 1
                else:
                    player_stats[pid]["aerials_lost"] += 1

        # Process cards
        if "foul_committed" in events and not events["foul_committed"].empty:
            for _, f in events["foul_committed"].iterrows():
                pid = str(f.get("player_id", ""))
                pname = f.get("player", "")
                team = f.get("team", "")
                if not pid:
                    continue
                _ensure_player(pid, pname, team)
                card = str(f.get("foul_committed_card", "")).lower()
                if "yellow" in card:
                    player_stats[pid]["yellow_cards"] += 1
                elif "red" in card or "second yellow" in card:
                    player_stats[pid]["red_cards"] += 1

        # Estimate minutes from lineups (simplified: 90 min per starter, adjust for subs)
        self._estimate_minutes(events, player_stats)

        return list(player_stats.values())

    def _is_progressive_pass(self, pass_row: pd.Series) -> bool:
        """A pass is progressive if it moves the ball >=10m toward the opponent's goal."""
        loc = pass_row.get("location")
        end_loc = pass_row.get("pass_end_location")
        if not isinstance(loc, (list, tuple)) or not isinstance(end_loc, (list, tuple)):
            return False
        if len(loc) < 2 or len(end_loc) < 2:
            return False
        # StatsBomb pitch: 120x80, goal at x=120
        start_dist = math.sqrt((120 - loc[0]) ** 2 + (40 - loc[1]) ** 2)
        end_dist = math.sqrt((120 - end_loc[0]) ** 2 + (40 - end_loc[1]) ** 2)
        return (start_dist - end_dist) >= 10

    def _is_progressive_carry(self, carry_row: pd.Series) -> bool:
        """A carry is progressive if it moves the ball >=10m toward the opponent's goal."""
        loc = carry_row.get("location")
        end_loc = carry_row.get("carry_end_location")
        if not isinstance(loc, (list, tuple)) or not isinstance(end_loc, (list, tuple)):
            return False
        if len(loc) < 2 or len(end_loc) < 2:
            return False
        start_dist = math.sqrt((120 - loc[0]) ** 2 + (40 - loc[1]) ** 2)
        end_dist = math.sqrt((120 - end_loc[0]) ** 2 + (40 - end_loc[1]) ** 2)
        return (start_dist - end_dist) >= 10

    def _estimate_minutes(
        self, events: dict[str, pd.DataFrame], player_stats: dict[str, dict]
    ) -> None:
        """Estimate minutes played from substitution events."""
        # Default: all players get 90 minutes (simplified)
        for pid in player_stats:
            player_stats[pid]["minutes"] = 90

        # Adjust for substitutions
        if "substitutions" in events and not events["substitutions"].empty:
            for _, sub in events["substitutions"].iterrows():
                # Player being substituted off
                pid_off = str(sub.get("player_id", ""))
                minute = sub.get("minute", 90)
                if pid_off in player_stats and pd.notna(minute):
                    player_stats[pid_off]["minutes"] = int(minute)

                # Player coming on
                pid_on = str(sub.get("substitution_replacement_id", ""))
                pname_on = sub.get("substitution_replacement", "")
                team = sub.get("team", "")
                if pid_on:
                    if pid_on not in player_stats:
                        # Initialize the sub player
                        player_stats[pid_on] = {
                            "player_id": pid_on,
                            "player_name": str(pname_on),
                            "team": str(team),
                            "match_id": sub.get("match_id", ""),
                            "minutes": 0,
                            "goals": 0, "shots": 0, "shots_on_target": 0,
                            "xg": 0.0, "npxg": 0.0,
                            "passes_completed": 0, "passes_attempted": 0,
                            "progressive_passes": 0, "key_passes": 0, "xag": 0.0,
                            "carries": 0, "progressive_carries": 0,
                            "touches": 0, "successful_dribbles": 0,
                            "attempted_dribbles": 0, "miscontrols": 0,
                            "tackles": 0, "tackles_won": 0,
                            "interceptions": 0, "blocks": 0, "clearances": 0,
                            "pressures": 0, "pressure_successes": 0,
                            "pressures_att_third": 0,
                            "aerials_won": 0, "aerials_lost": 0,
                            "sca": 0, "gca": 0,
                            "yellow_cards": 0, "red_cards": 0,
                        }
                    if pd.notna(minute):
                        player_stats[pid_on]["minutes"] = 90 - int(minute)

    def _aggregate_season(
        self, match_df: pd.DataFrame, min_minutes: int
    ) -> pd.DataFrame:
        """Combine per-match stats into season totals and compute per-90 rates."""
        sum_cols = [
            "minutes", "goals", "shots", "shots_on_target",
            "xg", "npxg", "passes_completed", "passes_attempted",
            "progressive_passes", "key_passes", "xag",
            "progressive_carries", "touches", "successful_dribbles",
            "attempted_dribbles", "miscontrols",
            "tackles", "tackles_won", "interceptions", "blocks", "clearances",
            "pressures", "pressure_successes", "pressures_att_third",
            "aerials_won", "aerials_lost", "sca", "gca",
            "yellow_cards", "red_cards",
        ]

        agg_dict = {col: "sum" for col in sum_cols if col in match_df.columns}
        agg_dict["match_id"] = "count"  # appearances

        season = match_df.groupby(["player_id", "player_name", "team"]).agg(
            agg_dict
        ).reset_index()
        season = season.rename(columns={
            "match_id": "appearances",
            "minutes": "minutes_played",
        })

        # Filter by minimum minutes
        season = season[season["minutes_played"] >= min_minutes].copy()

        # Compute per-90 rates
        nineties = season["minutes_played"] / 90.0
        per90_map = {
            "goals_p90": "goals",
            "xg_p90": "xg",
            "npxg_p90": "npxg",
            "xag_p90": "xag",
            "sca_p90": "sca",
            "gca_p90": "gca",
            "progressive_passes_p90": "progressive_passes",
            "progressive_carries_p90": "progressive_carries",
            "key_passes_p90": "key_passes",
            "tackles_won_p90": "tackles_won",
            "interceptions_p90": "interceptions",
            "blocks_p90": "blocks",
            "pressures_p90": "pressures",
            "pressures_att_third_p90": "pressures_att_third",
            "successful_dribbles_p90": "successful_dribbles",
            "touches_p90": "touches",
            "assists_p90": "xag",  # approximate assists with xag for SB
        }
        for p90_col, raw_col in per90_map.items():
            if raw_col in season.columns:
                season[p90_col] = season[raw_col] / nineties
            else:
                season[p90_col] = np.nan

        # Pass completion percentage
        if "passes_attempted" in season.columns:
            season["pass_completion_pct"] = np.where(
                season["passes_attempted"] > 0,
                season["passes_completed"] / season["passes_attempted"] * 100,
                np.nan,
            )

        # Pressure success percentage
        if "pressures" in season.columns:
            season["pressure_success_pct"] = np.where(
                season["pressures"] > 0,
                season["pressure_successes"] / season["pressures"] * 100,
                np.nan,
            )

        # Prefix player_id with source
        season["player_id"] = "sb_" + season["player_id"].astype(str)

        return season
