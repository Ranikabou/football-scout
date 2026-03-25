"""CLI entry point for Football Scout system."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click
import yaml

# Expose FastAPI app at module level so Railway/uvicorn can find it
from football_scout.api.app import app  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def load_config(config_path: str = "config.yaml") -> dict:
    path = Path(config_path)
    if path.exists():
        with open(path) as f:
            return yaml.safe_load(f)
    logger.warning("Config file not found at %s, using defaults", config_path)
    return {}


@click.group()
@click.option("--config", default="config.yaml", help="Path to config file")
@click.pass_context
def cli(ctx: click.Context, config: str) -> None:
    """Football Scout — Multi-source scouting and transfer intelligence."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = load_config(config)


@cli.command()
@click.option("--leagues", "-l", multiple=True, help="League codes (e.g., ENG ESP)")
@click.option("--seasons", "-s", multiple=True, help="Seasons (e.g., 2024-25)")
@click.pass_context
def ingest(ctx: click.Context, leagues: tuple, seasons: tuple) -> None:
    """Ingest data from all configured sources."""
    from football_scout.pipeline.ingest import build_unified_dataset

    config = ctx.obj["config"]
    if leagues:
        # Map short codes to full names
        league_map = {
            "ENG": "ENG-Premier League",
            "ESP": "ESP-La Liga",
            "GER": "GER-Bundesliga",
            "ITA": "ITA-Serie A",
            "FRA": "FRA-Ligue 1",
        }
        config["leagues"] = [league_map.get(l, l) for l in leagues]
    if seasons:
        config["seasons"] = list(seasons)

    df = build_unified_dataset(config)
    click.echo(f"Ingested {len(df)} player records")


@cli.command()
@click.pass_context
def features(ctx: click.Context) -> None:
    """Compute features and percentile ranks."""
    import pandas as pd

    from football_scout.pipeline.features import compute_all_features
    from football_scout.pipeline.normalize import normalize_and_save

    unified_path = Path("data/processed/unified_players.parquet")
    if not unified_path.exists():
        click.echo("No unified dataset found. Run 'ingest' first.", err=True)
        sys.exit(1)

    df = pd.read_parquet(unified_path)
    df = compute_all_features(df)
    df = normalize_and_save(df)
    click.echo(f"Computed features for {len(df)} players")


@cli.command()
@click.option("--player", "-p", required=True, help="Player name")
@click.option("--top", "-n", default=10, help="Number of similar players")
@click.option("--position", help="Filter by position group")
@click.pass_context
def similar(ctx: click.Context, player: str, top: int, position: str | None) -> None:
    """Find similar players."""
    import pandas as pd

    from football_scout.models.similarity import SimilarityEngine

    features_path = Path("data/processed/player_features.parquet")
    if not features_path.exists():
        click.echo("No features found. Run 'features' first.", err=True)
        sys.exit(1)

    df = pd.read_parquet(features_path)
    engine = SimilarityEngine(df, ctx.obj["config"])
    result = engine.find_similar(target=player, position_group=position, n=top)

    if result.empty:
        click.echo(f"No similar players found for '{player}'")
        return

    cols = ["player_name", "team", "league", "similarity_score"]
    available = [c for c in cols if c in result.columns]
    click.echo(result[available].to_string(index=False))


@cli.command()
@click.option("--position", "-p", required=True, help="Position group (CM, ST, etc.)")
@click.option("--max-age", default=26, help="Maximum age")
@click.option("--undervalued", is_flag=True, help="Only show undervalued players")
@click.option("--leagues", "-l", multiple=True, help="Filter by leagues")
@click.pass_context
def shortlist(
    ctx: click.Context,
    position: str,
    max_age: int,
    undervalued: bool,
    leagues: tuple,
) -> None:
    """Generate a scouting shortlist."""
    import pandas as pd

    from football_scout.scouting.shortlist import ScoutingQuery, run_shortlist

    features_path = Path("data/processed/player_features.parquet")
    if not features_path.exists():
        click.echo("No features found. Run 'features' first.", err=True)
        sys.exit(1)

    df = pd.read_parquet(features_path)
    query = ScoutingQuery(
        position_group=position,
        max_age=max_age,
        undervalued_only=undervalued,
        leagues=list(leagues) if leagues else None,
    )
    result = run_shortlist(query, df, ctx.obj["config"])

    if result.empty:
        click.echo("No players match the criteria")
        return

    click.echo(result.to_string(index=False))


@cli.command()
@click.option("--player", "-p", required=True, help="Player name")
@click.option("--output", "-o", default="reports/", help="Output directory")
@click.pass_context
def report(ctx: click.Context, player: str, output: str) -> None:
    """Generate a scouting report for a player."""
    import pandas as pd

    from football_scout.scouting.report import generate_report

    features_path = Path("data/processed/player_features.parquet")
    if not features_path.exists():
        click.echo("No features found. Run 'features' first.", err=True)
        sys.exit(1)

    df = pd.read_parquet(features_path)
    try:
        report_data = generate_report(player, df, ctx.obj["config"], output_dir=output)
        click.echo(f"Report generated for {report_data['bio']['player_name']}")
        click.echo(f"Saved to {output}")
    except ValueError as e:
        click.echo(str(e), err=True)
        sys.exit(1)


@cli.command()
@click.option("--position", "-p", required=True, help="Position group")
@click.option("--output", "-o", default="viz/", help="Output directory")
@click.pass_context
def cluster(ctx: click.Context, position: str, output: str) -> None:
    """Cluster players into archetypes."""
    import pandas as pd

    from football_scout.models.clustering import ArchetypeClusterer

    features_path = Path("data/processed/player_features.parquet")
    if not features_path.exists():
        click.echo("No features found. Run 'features' first.", err=True)
        sys.exit(1)

    df = pd.read_parquet(features_path)
    clusterer = ArchetypeClusterer()
    result = clusterer.cluster(df, position, output_dir=output)

    if "cluster_label" in result.columns:
        counts = result["cluster_label"].value_counts()
        click.echo(f"Clustered {len(result)} players into {len(counts)} archetypes:")
        for label, count in counts.items():
            click.echo(f"  {label}: {count}")


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=8000, help="Port to listen on")
@click.pass_context
def serve(ctx: click.Context, host: str, port: int) -> None:
    """Start the FastAPI server."""
    import uvicorn

    config = ctx.obj["config"]
    api_config = config.get("api", {})
    host = api_config.get("host", host)
    port = api_config.get("port", port)

    click.echo(f"Starting Football Scout API on {host}:{port}")
    uvicorn.run(
        "football_scout.api.app:app",
        host=host,
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    cli()
