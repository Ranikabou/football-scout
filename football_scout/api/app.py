"""FastAPI application for the Football Scout backend."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from football_scout.api.routes import clusters, players, reports, shortlist, similarity

logger = logging.getLogger(__name__)


def load_config(config_path: str = "config.yaml") -> dict:
    path = Path(config_path)
    if path.exists():
        with open(path) as f:
            return yaml.safe_load(f)
    return {}


def create_app(config_path: str = "config.yaml") -> FastAPI:
    """Create and configure the FastAPI application."""
    config = load_config(config_path)

    app = FastAPI(
        title="Football Scout API",
        description="Football player scouting and transfer market intelligence",
        version="1.0.0",
    )

    # CORS
    cors_origins = config.get("api", {}).get(
        "cors_origins", ["http://localhost:3000", "http://localhost:5173"]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store config in app state
    app.state.config = config

    # Include routers
    app.include_router(players.router, prefix="/api", tags=["players"])
    app.include_router(shortlist.router, prefix="/api", tags=["shortlist"])
    app.include_router(similarity.router, prefix="/api", tags=["similarity"])
    app.include_router(clusters.router, prefix="/api", tags=["clusters"])
    app.include_router(reports.router, prefix="/api", tags=["reports"])

    @app.get("/api/meta/leagues")
    async def get_leagues():
        return {"leagues": config.get("leagues", [])}

    @app.get("/api/meta/seasons")
    async def get_seasons():
        return {"seasons": config.get("seasons", [])}

    @app.get("/api/meta/positions")
    async def get_positions():
        return {"positions": config.get("position_mapping", {})}

    @app.get("/api/meta/sources")
    async def get_sources():
        sources = {}
        for source in ["statsbomb", "understat", "fbref", "transfermarkt"]:
            src_config = config.get(source, {})
            sources[source] = {
                "enabled": src_config.get("enabled", True),
                "mode": src_config.get("mode", "default"),
            }
        return {"sources": sources}

    @app.get("/health")
    async def health_check():
        return {"status": "ok"}

    return app


# Default app instance
app = create_app()
