"""Enumerations for position groups, data sources, leagues, and event types."""

from enum import Enum


class PositionGroup(str, Enum):
    GK = "GK"
    CB = "CB"
    FB = "FB"
    CM = "CM"
    WG = "WG"
    ST = "ST"


class DataSource(str, Enum):
    STATSBOMB = "statsbomb"
    UNDERSTAT = "understat"
    FBREF = "fbref"
    TRANSFERMARKT = "transfermarkt"


class League(str, Enum):
    ENG = "ENG-Premier League"
    ESP = "ESP-La Liga"
    GER = "GER-Bundesliga"
    ITA = "ITA-Serie A"
    FRA = "FRA-Ligue 1"


class EventType(str, Enum):
    SHOT = "shot"
    PASS = "pass"
    CARRY = "carry"
    PRESSURE = "pressure"
    TACKLE = "tackle"
    INTERCEPTION = "interception"
    BLOCK = "block"
    DUEL = "duel"
    FOUL = "foul"
    SUBSTITUTION = "substitution"
    CARD = "card"
