"""Canonical event schema for event-level data (shots, passes, carries, etc.)."""

from __future__ import annotations

from pydantic import BaseModel

from football_scout.schema.enums import EventType


class MatchEvent(BaseModel):
    """Canonical event record normalized from any source."""

    event_id: str
    match_id: str
    event_type: EventType
    player_id: str | None = None
    player_name: str | None = None
    team: str | None = None
    minute: int | None = None
    second: int | None = None
    period: int | None = None

    # Location
    location_x: float | None = None
    location_y: float | None = None
    end_location_x: float | None = None
    end_location_y: float | None = None

    # Outcome
    outcome: str | None = None

    # Shot-specific
    xg: float | None = None
    shot_type: str | None = None
    body_part: str | None = None

    # Pass-specific
    pass_type: str | None = None
    pass_length: float | None = None
    pass_angle: float | None = None
    recipient: str | None = None
    is_progressive: bool | None = None
    is_key_pass: bool | None = None

    # Carry-specific
    carry_distance: float | None = None
    is_progressive_carry: bool | None = None

    # Duel-specific
    duel_type: str | None = None
    duel_outcome: str | None = None

    class Config:
        use_enum_values = True
