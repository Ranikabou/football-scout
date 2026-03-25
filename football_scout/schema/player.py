"""Canonical player season record model."""

from __future__ import annotations

from pydantic import BaseModel, Field

from football_scout.schema.enums import DataSource, PositionGroup


class PlayerSeasonRecord(BaseModel):
    """Canonical player season record.

    Every field from advanced stats is Optional[float] so adapters that
    can't provide it leave it as None. Never use zero for missing data.
    """

    # Identity
    player_id: str = Field(description="Unique player identifier (source-prefixed)")
    player_name: str
    team: str
    league: str
    season: str
    age: int | None = None
    nationality: str | None = None
    position: str | None = None
    position_group: PositionGroup | None = None
    contract_expiry: str | None = None

    # Appearances
    appearances: int | None = None
    starts: int | None = None
    minutes_played: int | None = None

    # Goals & shooting
    goals: int | None = None
    assists: int | None = None
    penalties_scored: int | None = None
    penalties_attempted: int | None = None
    shots: int | None = None
    shots_on_target: int | None = None
    xg: float | None = None
    npxg: float | None = None
    xg_statsbomb: float | None = None
    xg_understat: float | None = None

    # Passing
    passes_completed: int | None = None
    passes_attempted: int | None = None
    pass_completion_pct: float | None = None
    progressive_passes: int | None = None
    key_passes: int | None = None
    xag: float | None = None
    xa: float | None = None
    xa_statsbomb: float | None = None
    xa_understat: float | None = None

    # Shot-creating actions
    sca: int | None = None
    gca: int | None = None

    # Carrying
    progressive_carries: int | None = None
    touches: int | None = None
    successful_dribbles: int | None = None
    attempted_dribbles: int | None = None
    miscontrols: int | None = None

    # Defensive
    tackles: int | None = None
    tackles_won: int | None = None
    interceptions: int | None = None
    blocks: int | None = None
    clearances: int | None = None

    # Pressures
    pressures: int | None = None
    pressure_successes: int | None = None
    pressures_att_third: int | None = None

    # Aerials
    aerials_won: int | None = None
    aerials_lost: int | None = None

    # Discipline
    yellow_cards: int | None = None
    red_cards: int | None = None

    # Per-90 rates (computed in pipeline)
    goals_p90: float | None = None
    assists_p90: float | None = None
    xg_p90: float | None = None
    npxg_p90: float | None = None
    xag_p90: float | None = None
    sca_p90: float | None = None
    gca_p90: float | None = None
    progressive_passes_p90: float | None = None
    progressive_carries_p90: float | None = None
    key_passes_p90: float | None = None
    tackles_won_p90: float | None = None
    interceptions_p90: float | None = None
    blocks_p90: float | None = None
    pressures_p90: float | None = None
    pressures_att_third_p90: float | None = None
    pressure_success_pct: float | None = None
    successful_dribbles_p90: float | None = None
    touches_p90: float | None = None

    # Market value (from Transfermarkt)
    market_value_eur: float | None = None
    predicted_value_eur: float | None = None
    value_ratio: float | None = None

    # Composite metrics (computed in features.py)
    pressing_intensity: float | None = None
    chance_creation: float | None = None
    defensive_contrib: float | None = None
    progressive_action: float | None = None
    goal_threat: float | None = None
    aerial_dominance: float | None = None

    # Provenance: maps metric name to the source that provided it
    data_sources: dict[str, DataSource] = Field(default_factory=dict)
    data_completeness_pct: float = 0.0

    class Config:
        use_enum_values = True
