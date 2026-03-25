"""Similar players endpoint."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request

from football_scout.api.routes.players import _load_features, _row_to_summary
from football_scout.models.similarity import SimilarityEngine

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/players/{player_id}/similar")
async def get_similar_players(
    player_id: str,
    n: int = Query(10, le=50),
    request: Request = None,
):
    df = _load_features()
    if df.empty:
        raise HTTPException(status_code=404, detail="No data available")

    match = df[df["player_id"] == player_id]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"Player {player_id} not found")

    player = match.iloc[0]
    config = getattr(request.app.state, "config", {}) if request else {}

    engine = SimilarityEngine(df, config)
    similar = engine.find_similar(
        target=str(player["player_name"]),
        position_group=str(player.get("position_group", "")) if player.get("position_group") else None,
        n=n,
    )

    results = []
    for _, row in similar.iterrows():
        results.append({
            "player": _row_to_summary(row),
            "similarity_score": float(row.get("similarity_score", 0)),
            "shared_features_pct": float(row.get("shared_features_pct", 0)),
        })

    return {"similar_players": results}
