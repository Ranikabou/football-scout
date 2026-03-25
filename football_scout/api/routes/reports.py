"""Report generation endpoint."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from football_scout.api.routes.players import _load_features
from football_scout.scouting.report import generate_report

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/reports/{player_id}")
async def get_report(
    player_id: str,
    format: str = Query("json", pattern="^(json|markdown)$"),
    request: Request = None,
):
    df = _load_features()
    if df.empty:
        raise HTTPException(status_code=404, detail="No data available")

    match = df[df["player_id"] == player_id]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"Player {player_id} not found")

    player_name = str(match.iloc[0]["player_name"])
    config = getattr(request.app.state, "config", {}) if request else {}

    try:
        report = generate_report(player_name, df, config)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Report generation failed: %s", e)
        raise HTTPException(status_code=500, detail="Report generation failed")

    if format == "markdown":
        md = _report_to_markdown(report)
        return PlainTextResponse(content=md, media_type="text/markdown")

    return report


def _report_to_markdown(report: dict) -> str:
    """Convert report dict to Markdown string."""
    bio = report.get("bio", {})
    lines = [
        f"# Scouting Report: {bio.get('player_name', 'Unknown')}",
        "",
        "## Bio",
        f"- **Age:** {bio.get('age', 'N/A')}",
        f"- **Club:** {bio.get('team', 'N/A')}",
        f"- **League:** {bio.get('league', 'N/A')}",
        f"- **Nationality:** {bio.get('nationality', 'N/A')}",
        f"- **Position:** {bio.get('position_group', 'N/A')}",
        "",
        "## Percentile Rankings",
        "| Metric | Value | Percentile | Tier |",
        "|--------|-------|-----------|------|",
    ]

    for row in report.get("percentile_table", []):
        val = f"{row['value']:.2f}" if row.get("value") is not None else "N/A"
        pctl = f"{row['percentile']:.0f}" if row.get("percentile") is not None else "N/A"
        lines.append(f"| {row.get('metric', '')} | {val} | {pctl} | {row.get('tier', '')} |")

    return "\n".join(lines)
