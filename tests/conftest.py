"""
Shared pytest fixtures for the F1 SQL Analytics Pipeline test suite.

Validates: Requirements 1.1–1.9, 6.3
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# schema_sql
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def schema_sql() -> str:
    """Return the content of ``database/schema.sql`` as a string."""
    schema_path = Path(__file__).parent.parent / "database" / "schema.sql"
    return schema_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# tmp_db
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db(schema_sql: str):
    """Yield an in-memory SQLite connection with the schema already applied.

    The connection has ``PRAGMA foreign_keys = ON`` set and the full schema
    executed via ``executescript``.  The connection is closed after each test.
    """
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(schema_sql)
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# sample_race_rows
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_race_rows() -> list[dict]:
    """Return 3 minimal dicts matching the ``race_results`` table columns."""
    return [
        {
            "raceId": 1,
            "year": 2023,
            "kaggle_driver_id": 10,
            "team": "Red Bull",
            "track": "Bahrain",
            "position": 1,
            "starting_grid": 1,
            "finished": 1,
            "dnf": 0,
            "laps_down": None,
            "time_gap_sec": None,
            "rain": 0,
            "sunny": 1,
        },
        {
            "raceId": 1,
            "year": 2023,
            "kaggle_driver_id": 11,
            "team": "Red Bull",
            "track": "Bahrain",
            "position": 2,
            "starting_grid": 3,
            "finished": 1,
            "dnf": 0,
            "laps_down": None,
            "time_gap_sec": 5.4,
            "rain": 0,
            "sunny": 1,
        },
        {
            "raceId": 1,
            "year": 2023,
            "kaggle_driver_id": 12,
            "team": "Mercedes",
            "track": "Bahrain",
            "position": 3,
            "starting_grid": 2,
            "finished": 1,
            "dnf": 0,
            "laps_down": None,
            "time_gap_sec": 8.1,
            "rain": 0,
            "sunny": 1,
        },
    ]


# ---------------------------------------------------------------------------
# sample_qualifying_rows
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_qualifying_rows() -> list[dict]:
    """Return 3 minimal dicts matching the ``qualifying_results`` table columns."""
    return [
        {
            "raceId": 1,
            "year": 2023,
            "kaggle_driver_id": 10,
            "team": "Red Bull",
            "track": "Bahrain",
            "position": 1,
            "participated_q2": 1,
            "participated_q3": 1,
            "q1_time_sec": 88.0,
            "q2_time_sec": 87.5,
            "q3_time_sec": 87.1,
            "rain": 0,
            "sunny": 1,
        },
        {
            "raceId": 1,
            "year": 2023,
            "kaggle_driver_id": 11,
            "team": "Red Bull",
            "track": "Bahrain",
            "position": 3,
            "participated_q2": 1,
            "participated_q3": 1,
            "q1_time_sec": 88.2,
            "q2_time_sec": 87.8,
            "q3_time_sec": 87.4,
            "rain": 0,
            "sunny": 1,
        },
        {
            "raceId": 1,
            "year": 2023,
            "kaggle_driver_id": 12,
            "team": "Mercedes",
            "track": "Bahrain",
            "position": 2,
            "participated_q2": 1,
            "participated_q3": 1,
            "q1_time_sec": 88.1,
            "q2_time_sec": 87.6,
            "q3_time_sec": 87.2,
            "rain": 0,
            "sunny": 1,
        },
    ]


# ---------------------------------------------------------------------------
# sample_circuits_rows
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_circuits_rows() -> list[dict]:
    """Return 2 circuit row dicts matching the ``circuits`` table columns."""
    return [
        {
            "circuit_id": 1,
            "circuit_name": "Bahrain International Circuit",
            "location": "Sakhir",
            "country": "Bahrain",
            "lat": 26.0325,
            "lng": 50.5106,
            "alt": 7.0,
        },
        {
            "circuit_id": 2,
            "circuit_name": "Jeddah Corniche Circuit",
            "location": "Jeddah",
            "country": "Saudi Arabia",
            "lat": 21.6319,
            "lng": 39.1044,
            "alt": 15.0,
        },
    ]


# ---------------------------------------------------------------------------
# sample_races_rows
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_races_rows() -> list[dict]:
    """Return 1 race row dict matching the ``races`` table columns."""
    return [
        {
            "raceId": 1,
            "year": 2023,
            "round": 1,
            "circuit_id": 1,
            "race_name": "Bahrain Grand Prix",
            "race_date": "2023-03-05",
        },
    ]


# ---------------------------------------------------------------------------
# sample_weather_rows
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_weather_rows() -> list[dict]:
    """Return 1 weather row dict matching the ``weather`` table columns."""
    return [
        {
            "raceId": 1,
            "year": 2023,
            "rain": 0,
            "sunny": 1,
        },
    ]


# ---------------------------------------------------------------------------
# sample_driver_rows
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_driver_rows() -> list[dict]:
    """Return 3 driver row dicts matching kaggle_driver_ids 10, 11, and 12."""
    return [
        {
            "kaggle_driver_id": 10,
            "driver_name": "Max Verstappen",
            "nationality": "Dutch",
            "dob": "1997-09-30",
            "driver_code": "VER",
            "team": "Red Bull",
        },
        {
            "kaggle_driver_id": 11,
            "driver_name": "Sergio Perez",
            "nationality": "Mexican",
            "dob": "1990-01-26",
            "driver_code": "PER",
            "team": "Red Bull",
        },
        {
            "kaggle_driver_id": 12,
            "driver_name": "Lewis Hamilton",
            "nationality": "British",
            "dob": "1985-01-07",
            "driver_code": "HAM",
            "team": "Mercedes",
        },
    ]
