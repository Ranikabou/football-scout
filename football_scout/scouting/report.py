"""Per-player scouting report generation (Markdown + radar chart)."""

from __future__ import annotations

import base64
import io
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from football_scout.models.similarity import SimilarityEngine

logger = logging.getLogger(__name__)

# Percentile tier thresholds
TIER_THRESHOLDS = {
    "Elite": 90,
    "Green": 66,
    "Amber": 33,
    "Red": 0,
}

# Composite metrics for radar chart
RADAR_METRICS = [
    "pressing_intensity", "chance_creation", "defensive_contrib",
    "progressive_action", "goal_threat", "aerial_dominance",
]


def _get_tier(pctl: float | None) -> str:
    if pctl is None or np.isnan(pctl):
        return "Gray"
    if pctl >= 90:
        return "Elite"
    if pctl >= 66:
        return "Green"
    if pctl >= 33:
        return "Amber"
    return "Red"


def _generate_radar_chart(
    player_values: dict[str, float],
    median_values: dict[str, float],
    player_name: str,
) -> str | None:
    """Generate a radar chart PNG as base64 string."""
    try:
        import matplotlib.pyplot as plt
        from matplotlib.patches import FancyBboxPatch

        metrics = list(player_values.keys())
        n = len(metrics)
        if n < 3:
            return None

        angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
        angles += angles[:1]

        player_vals = [player_values.get(m, 0) or 0 for m in metrics]
        player_vals += player_vals[:1]
        median_vals = [median_values.get(m, 0) or 0 for m in metrics]
        median_vals += median_vals[:1]

        fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
        ax.plot(angles, player_vals, "o-", linewidth=2, label=player_name, color="#1f77b4")
        ax.fill(angles, player_vals, alpha=0.25, color="#1f77b4")
        ax.plot(angles, median_vals, "o--", linewidth=1.5, label="Position Median", color="#aaa")
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(metrics, size=9)
        ax.set_title(f"{player_name} - Composite Profile", size=14, pad=20)
        ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))

        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", dpi=100)
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("utf-8")
    except ImportError:
        logger.warning("matplotlib not installed, skipping radar chart")
        return None
    except Exception as e:
        logger.warning("Failed to generate radar chart: %s", e)
        return None


def generate_report(
    player_name: str,
    feature_df: pd.DataFrame,
    config: dict | None = None,
    output_dir: str | None = None,
) -> dict:
    """Generate a structured scouting report for a player.

    Returns a dict matching the ScoutingReport schema.
    """
    config = config or {}

    # Find player
    matches = feature_df[
        feature_df["player_name"].str.lower() == player_name.lower()
    ]
    if matches.empty:
        matches = feature_df[
            feature_df["player_name"].str.lower().str.contains(
                player_name.lower(), na=False
            )
        ]
    if matches.empty:
        raise ValueError(f"Player '{player_name}' not found")

    player = matches.iloc[0]
    position_group = player.get("position_group", "")

    # Bio section
    bio = {
        "player_name": str(player.get("player_name", "")),
        "age": int(player["age"]) if pd.notna(player.get("age")) else None,
        "team": str(player.get("team", "")),
        "league": str(player.get("league", "")),
        "nationality": str(player.get("nationality", "")) if pd.notna(player.get("nationality")) else None,
        "position_group": str(position_group),
        "contract_expiry": str(player.get("contract_expiry", "")) if pd.notna(player.get("contract_expiry")) else None,
        "minutes_played": int(player["minutes_played"]) if pd.notna(player.get("minutes_played")) else None,
        "data_completeness_pct": float(player.get("data_completeness_pct", 0)),
    }

    # Radar chart: composite metrics vs positional median
    if position_group and "position_group" in feature_df.columns:
        pos_df = feature_df[feature_df["position_group"] == position_group]
    else:
        pos_df = feature_df

    player_radar = {}
    median_radar = {}
    for metric in RADAR_METRICS:
        pctl_col = f"{metric}_pctl"
        if pctl_col in player.index and pd.notna(player[pctl_col]):
            player_radar[metric] = float(player[pctl_col])
            median_radar[metric] = 50.0  # Median is always 50th percentile
        elif metric in player.index and pd.notna(player[metric]):
            player_radar[metric] = float(player[metric])
            median_radar[metric] = float(pos_df[metric].median()) if metric in pos_df.columns else 0

    radar_base64 = _generate_radar_chart(player_radar, median_radar, bio["player_name"])

    # Percentile table
    pctl_cols = [c for c in player.index if c.endswith("_pctl")]
    percentile_table = []
    for pctl_col in pctl_cols:
        metric = pctl_col.replace("_pctl", "")
        raw_val = float(player[metric]) if metric in player.index and pd.notna(player.get(metric)) else None
        pctl_val = float(player[pctl_col]) if pd.notna(player[pctl_col]) else None
        percentile_table.append({
            "metric": metric,
            "value": raw_val,
            "percentile": pctl_val,
            "tier": _get_tier(pctl_val),
        })

    percentile_table.sort(key=lambda x: x.get("percentile") or 0, reverse=True)

    # Similar players
    similar_players = []
    try:
        engine = SimilarityEngine(feature_df, config)
        similar_df = engine.find_similar(
            target=player_name,
            position_group=str(position_group) if position_group else None,
            n=5,
        )
        for _, sim_row in similar_df.iterrows():
            similar_players.append({
                "player": {
                    "player_name": str(sim_row.get("player_name", "")),
                    "team": str(sim_row.get("team", "")),
                    "league": str(sim_row.get("league", "")),
                    "age": int(sim_row["age"]) if pd.notna(sim_row.get("age")) else None,
                },
                "similarity_score": float(sim_row.get("similarity_score", 0)),
                "shared_features_pct": float(sim_row.get("shared_features_pct", 0)),
            })
    except Exception as e:
        logger.warning("Failed to find similar players: %s", e)

    # Value assessment
    value_assessment = {
        "market_value_eur": float(player["market_value_eur"]) if pd.notna(player.get("market_value_eur")) else None,
        "predicted_value_eur": float(player["predicted_value_eur"]) if pd.notna(player.get("predicted_value_eur")) else None,
        "value_ratio": float(player["value_ratio"]) if pd.notna(player.get("value_ratio")) else None,
        "undervalued": bool(player.get("undervalued", False)) if pd.notna(player.get("undervalued")) else False,
    }

    # Provenance
    provenance = {}
    if "data_sources" in player.index:
        ds = player["data_sources"]
        if isinstance(ds, dict):
            provenance = {k: str(v) for k, v in ds.items()}
    if "data_source" in player.index:
        provenance["primary"] = str(player["data_source"])

    report = {
        "bio": bio,
        "radar_chart_base64": radar_base64 or "",
        "percentile_table": percentile_table,
        "similar_players": similar_players,
        "value_assessment": value_assessment,
        "shap_chart_base64": None,
        "provenance": provenance,
    }

    # Save Markdown if output_dir specified
    if output_dir:
        _save_markdown(report, output_dir)

    return report


def _save_markdown(report: dict, output_dir: str) -> None:
    """Save report as Markdown file."""
    bio = report["bio"]
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)

    safe_name = bio["player_name"].replace(" ", "_").replace("/", "_")
    filepath = path / f"{safe_name}_report.md"

    lines = [
        f"# Scouting Report: {bio['player_name']}",
        "",
        "## Bio",
        f"- **Age:** {bio.get('age', 'N/A')}",
        f"- **Club:** {bio.get('team', 'N/A')}",
        f"- **League:** {bio.get('league', 'N/A')}",
        f"- **Nationality:** {bio.get('nationality', 'N/A')}",
        f"- **Position:** {bio.get('position_group', 'N/A')}",
        f"- **Minutes:** {bio.get('minutes_played', 'N/A')}",
        f"- **Data Completeness:** {bio.get('data_completeness_pct', 0):.1f}%",
        "",
    ]

    if report.get("radar_chart_base64"):
        lines.append("## Radar Chart")
        lines.append(f"![Radar](data:image/png;base64,{report['radar_chart_base64']})")
        lines.append("")

    lines.append("## Percentile Rankings")
    lines.append("| Metric | Value | Percentile | Tier |")
    lines.append("|--------|-------|-----------|------|")
    for row in report.get("percentile_table", []):
        val = f"{row['value']:.2f}" if row['value'] is not None else "N/A"
        pctl = f"{row['percentile']:.0f}" if row['percentile'] is not None else "N/A"
        lines.append(f"| {row['metric']} | {val} | {pctl} | {row['tier']} |")
    lines.append("")

    if report.get("similar_players"):
        lines.append("## Similar Players")
        for sp in report["similar_players"]:
            p = sp["player"]
            lines.append(
                f"- **{p['player_name']}** ({p.get('team', '?')}) — "
                f"Similarity: {sp['similarity_score']:.3f}"
            )
        lines.append("")

    va = report.get("value_assessment", {})
    if va.get("market_value_eur"):
        lines.append("## Value Assessment")
        lines.append(f"- **Market Value:** EUR {va['market_value_eur']:,.0f}")
        if va.get("predicted_value_eur"):
            lines.append(f"- **Predicted Value:** EUR {va['predicted_value_eur']:,.0f}")
        if va.get("value_ratio"):
            lines.append(f"- **Value Ratio:** {va['value_ratio']:.2f}")
            lines.append(f"- **Undervalued:** {'Yes' if va.get('undervalued') else 'No'}")
        lines.append("")

    if report.get("provenance"):
        lines.append("## Data Provenance")
        for k, v in report["provenance"].items():
            lines.append(f"- {k}: {v}")

    filepath.write_text("\n".join(lines))
    logger.info("Saved report to %s", filepath)
