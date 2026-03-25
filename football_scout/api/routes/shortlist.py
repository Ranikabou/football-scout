"""Shortlist query endpoint."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Request

from football_scout.api.routes.players import _load_features, _row_to_detail
from football_scout.api.schemas import ShortlistQuery, ShortlistResult
from football_scout.scouting.shortlist import ScoutingQuery, run_shortlist

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/shortlist")
async def create_shortlist(query: ShortlistQuery, request: Request):
    df = _load_features()
    if df.empty:
        return ShortlistResult(players=[], total_matches=0).model_dump()

    config = getattr(request.app.state, "config", {})

    # Convert API query to internal query
    metric_thresholds = None
    if query.metric_thresholds:
        metric_thresholds = {
            k: (v[0], float(v[1])) for k, v in query.metric_thresholds.items()
        }

    scouting_query = ScoutingQuery(
        position_group=query.position_group,
        max_age=query.max_age,
        min_minutes=query.min_minutes,
        leagues=query.leagues,
        max_market_value_eur=query.max_market_value_eur,
        metric_thresholds=metric_thresholds,
        similarity_to=query.similarity_to,
        undervalued_only=query.undervalued_only,
        sort_by=query.sort_by,
        top_n=query.top_n,
    )

    result_df = run_shortlist(scouting_query, df, config)

    players = [_row_to_detail(row) for _, row in result_df.iterrows()]

    # Coverage stats
    data_coverage = {}
    for source in ["statsbomb", "understat", "fbref", "transfermarkt"]:
        if "data_source" in df.columns:
            data_coverage[source] = float(
                (df["data_source"] == source).sum() / len(df) * 100
            )

    return ShortlistResult(
        players=players,
        total_matches=len(result_df),
        data_coverage=data_coverage,
    ).model_dump()
