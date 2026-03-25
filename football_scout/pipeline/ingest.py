"""Pipeline orchestration — merge data from multiple adapters into a unified dataset."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from fuzzywuzzy import fuzz

from football_scout.adapters.base import PlayerStatsAdapter
from football_scout.adapters.fbref_adapter import FBrefAdapter
from football_scout.adapters.statsbomb_adapter import StatsBombAdapter
from football_scout.adapters.transfermarkt import TransfermarktAdapter
from football_scout.adapters.understat_adapter import UnderstatAdapter
from football_scout.cache.store import CacheStore
from football_scout.schema.enums import DataSource

logger = logging.getLogger(__name__)

OVERRIDE_FILE = Path("data/reference/player_id_overrides.csv")


def _load_overrides() -> dict[str, str]:
    """Load manual player ID overrides: maps (source_player_id -> canonical_name)."""
    if not OVERRIDE_FILE.exists():
        return {}
    try:
        df = pd.read_csv(OVERRIDE_FILE)
        return dict(zip(df["source_player_id"], df["canonical_name"]))
    except Exception:
        return {}


def _init_adapters(config: dict) -> list[PlayerStatsAdapter]:
    """Initialize adapters based on config priority and enabled flags."""
    cache = CacheStore(config.get("cache", {}).get("database", "data/cache.sqlite"))
    adapters: list[PlayerStatsAdapter] = []

    for source in config.get("source_priority", ["statsbomb", "understat", "fbref"]):
        if source == "statsbomb":
            sb_config = config.get("statsbomb", {})
            adapters.append(StatsBombAdapter(
                mode=sb_config.get("mode", "open"),
                credentials=sb_config.get("credentials"),
                cache=cache,
            ))
        elif source == "understat":
            if config.get("understat", {}).get("enabled", True):
                adapters.append(UnderstatAdapter(cache=cache))
        elif source == "fbref":
            if config.get("fbref", {}).get("enabled", True):
                adapters.append(FBrefAdapter(cache=cache))

    return adapters


def _fuzzy_match_players(
    primary_df: pd.DataFrame,
    secondary_df: pd.DataFrame,
    overrides: dict[str, str],
    threshold: int = 85,
) -> pd.DataFrame:
    """Merge secondary data into primary using fuzzy name matching within same team/season."""
    if primary_df.empty or secondary_df.empty:
        return primary_df

    merged = primary_df.copy()

    # Build lookup from secondary: (team_lower, player_name) -> row
    secondary_by_team: dict[str, list[tuple[str, pd.Series]]] = {}
    for _, row in secondary_df.iterrows():
        team_key = str(row.get("team", "")).lower().strip()
        if team_key not in secondary_by_team:
            secondary_by_team[team_key] = []
        secondary_by_team[team_key].append(
            (str(row.get("player_name", "")), row)
        )

    match_log: list[dict] = []

    for idx, primary_row in merged.iterrows():
        primary_name = str(primary_row.get("player_name", ""))
        primary_team = str(primary_row.get("team", "")).lower().strip()
        primary_pid = str(primary_row.get("player_id", ""))

        # Check overrides first
        if primary_pid in overrides:
            override_name = overrides[primary_pid]
            # Find exact match by override name
            for team_key, players in secondary_by_team.items():
                for sec_name, sec_row in players:
                    if sec_name.lower() == override_name.lower():
                        _merge_row(merged, idx, sec_row, match_log, primary_name, sec_name, 100)
                        break

            continue

        # Fuzzy match within same team
        best_match = None
        best_score = 0
        candidates = secondary_by_team.get(primary_team, [])

        # Also try partial team name matching
        if not candidates:
            for team_key, players in secondary_by_team.items():
                if primary_team in team_key or team_key in primary_team:
                    candidates.extend(players)

        for sec_name, sec_row in candidates:
            score = fuzz.token_sort_ratio(primary_name, sec_name)
            if score > best_score and score >= threshold:
                best_score = score
                best_match = (sec_name, sec_row)

        if best_match is not None:
            sec_name, sec_row = best_match
            _merge_row(merged, idx, sec_row, match_log, primary_name, sec_name, best_score)

    if match_log:
        logger.info(
            "Fuzzy matched %d players (avg score: %.1f)",
            len(match_log),
            sum(m["score"] for m in match_log) / len(match_log),
        )
        for m in match_log:
            logger.debug(
                "  %s ↔ %s (score: %d)", m["primary"], m["secondary"], m["score"]
            )

    return merged


def _merge_row(
    df: pd.DataFrame,
    idx: int,
    sec_row: pd.Series,
    match_log: list[dict],
    primary_name: str,
    sec_name: str,
    score: int,
) -> None:
    """Merge a secondary row into the primary DataFrame at the given index."""
    match_log.append({
        "primary": primary_name,
        "secondary": sec_name,
        "score": score,
    })

    # Fill NaN values in primary with secondary values
    for col in sec_row.index:
        if col in ("player_id", "data_source"):
            continue
        if col in df.columns:
            current = df.at[idx, col]
            if pd.isna(current) and pd.notna(sec_row[col]):
                df.at[idx, col] = sec_row[col]
        else:
            df.at[idx, col] = sec_row[col]


def build_unified_dataset(config: dict) -> pd.DataFrame:
    """Orchestrate all adapters and merge into a unified dataset.

    1. Initialize adapters based on config
    2. For each (league, season) pair, pull from all adapters
    3. Merge using fuzzy name matching
    4. Merge Transfermarkt valuations
    5. Validate and save
    """
    adapters = _init_adapters(config)
    overrides = _load_overrides()

    leagues = config.get("leagues", [])
    seasons = config.get("seasons", [])
    min_minutes = config.get("min_minutes", 900)

    all_data: list[pd.DataFrame] = []

    for league in leagues:
        for season in seasons:
            logger.info("Processing %s / %s", league, season)

            # Pull from all adapters
            adapter_results: list[pd.DataFrame] = []
            for adapter in adapters:
                try:
                    df = adapter.get_player_season_stats(league, season, min_minutes)
                    if not df.empty:
                        logger.info(
                            "  %s: %d players", adapter.source_name(), len(df)
                        )
                        adapter_results.append(df)
                    else:
                        logger.info("  %s: no data", adapter.source_name())
                except Exception as e:
                    logger.error(
                        "  %s failed: %s", adapter.source_name(), e
                    )

            if not adapter_results:
                continue

            # Use first adapter result as primary, merge others
            primary = adapter_results[0]
            for secondary in adapter_results[1:]:
                primary = _fuzzy_match_players(primary, secondary, overrides)

            all_data.append(primary)

    if not all_data:
        logger.warning("No data collected from any source")
        return pd.DataFrame()

    unified = pd.concat(all_data, ignore_index=True)

    # Merge Transfermarkt valuations
    tm_config = config.get("transfermarkt", {})
    if tm_config.get("enabled", True):
        cache = CacheStore(config.get("cache", {}).get("database", "data/cache.sqlite"))
        tm_adapter = TransfermarktAdapter(
            fallback_csv=tm_config.get("fallback_csv", "data/reference/transfermarkt_values.csv"),
            cache=cache,
        )
        for league in leagues:
            for season in seasons:
                try:
                    tm_df = tm_adapter.get_player_season_stats(league, season)
                    if not tm_df.empty:
                        unified = _fuzzy_match_players(unified, tm_df, overrides)
                except Exception as e:
                    logger.error("Transfermarkt merge failed for %s/%s: %s", league, season, e)

    # Compute data completeness
    metric_cols = [
        "goals", "assists", "xg", "npxg", "xag", "xa",
        "progressive_passes", "progressive_carries", "key_passes",
        "tackles_won", "interceptions", "blocks", "pressures",
        "aerials_won", "aerials_lost", "sca", "gca",
        "market_value_eur",
    ]
    available_metrics = [c for c in metric_cols if c in unified.columns]
    if available_metrics:
        unified["data_completeness_pct"] = (
            unified[available_metrics].notna().sum(axis=1) / len(available_metrics) * 100
        ).round(1)
    else:
        unified["data_completeness_pct"] = 0.0

    # Log coverage stats
    logger.info("Unified dataset: %d players", len(unified))
    for col in available_metrics:
        coverage = unified[col].notna().sum() / len(unified) * 100
        logger.info("  %s: %.1f%% coverage", col, coverage)

    # Save to parquet
    output_path = Path("data/processed/unified_players.parquet")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    unified.to_parquet(output_path, index=False)
    logger.info("Saved to %s", output_path)

    return unified
