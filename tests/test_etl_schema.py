"""
Feature: f1-sql-analytics-pipeline
Smoke tests — schema correctness, FK enforcement, uniqueness, ETL creation
Validates: Requirements 1.1–1.9, 4.4, 6.3
"""

from __future__ import annotations

import csv
import sqlite3
import sys
from pathlib import Path

import pytest

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.etl import map_qualifying_row, run_etl, upsert_rows


# ---------------------------------------------------------------------------
# Fixtures (local; conftest.py fixtures are also available via pytest auto-use)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def schema_sql() -> str:
    schema_path = Path(__file__).parent.parent / "database" / "schema.sql"
    return schema_path.read_text(encoding="utf-8")


@pytest.fixture
def tmp_db(schema_sql: str):
    """In-memory SQLite DB with schema applied and FK enforcement ON."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(schema_sql)
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# 1. All 8 tables exist
# ---------------------------------------------------------------------------

EXPECTED_TABLES = {
    "circuits",
    "drivers",
    "races",
    "weather",
    "race_results",
    "qualifying_results",
    "sprint_results",
    "sprint_qualifying_results",
}


def test_all_tables_exist(tmp_db):
    """All 8 expected tables must be present in the schema."""
    rows = tmp_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    found = {row[0] for row in rows}
    assert EXPECTED_TABLES.issubset(found), (
        f"Missing tables: {EXPECTED_TABLES - found}"
    )


# ---------------------------------------------------------------------------
# 2. race_results columns (14 expected)
# ---------------------------------------------------------------------------

RACE_RESULTS_COLUMNS = {
    "id", "raceId", "year", "kaggle_driver_id", "team", "track",
    "position", "starting_grid", "finished", "dnf", "laps_down",
    "time_gap_sec", "rain", "sunny",
}


def test_race_results_columns(tmp_db):
    """race_results must have all 14 expected columns."""
    rows = tmp_db.execute("PRAGMA table_info(race_results)").fetchall()
    found = {row[1] for row in rows}  # row[1] = column name
    assert RACE_RESULTS_COLUMNS.issubset(found), (
        f"Missing columns in race_results: {RACE_RESULTS_COLUMNS - found}"
    )
    assert len(found) == 14, f"Expected 14 columns, found {len(found)}: {found}"


# ---------------------------------------------------------------------------
# 3. qualifying_results columns (14 expected)
# ---------------------------------------------------------------------------

QUALIFYING_RESULTS_COLUMNS = {
    "id", "raceId", "year", "kaggle_driver_id", "team", "track",
    "position", "participated_q2", "participated_q3",
    "q1_time_sec", "q2_time_sec", "q3_time_sec", "rain", "sunny",
}


def test_qualifying_results_columns(tmp_db):
    """qualifying_results must have all 14 expected columns."""
    rows = tmp_db.execute("PRAGMA table_info(qualifying_results)").fetchall()
    found = {row[1] for row in rows}
    assert QUALIFYING_RESULTS_COLUMNS.issubset(found), (
        f"Missing columns in qualifying_results: {QUALIFYING_RESULTS_COLUMNS - found}"
    )
    assert len(found) == 14, f"Expected 14 columns, found {len(found)}: {found}"


# ---------------------------------------------------------------------------
# 4. FK violation raises IntegrityError
# ---------------------------------------------------------------------------

def _insert_circuit(conn, circuit_id: int = 1) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO circuits (circuit_id, circuit_name, location, country) "
        "VALUES (?, 'Test Circuit', 'Testville', 'Testland')",
        (circuit_id,),
    )


def _insert_driver(conn, driver_id: int) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO drivers (kaggle_driver_id, driver_name) VALUES (?, 'Test Driver')",
        (driver_id,),
    )


def test_fk_violation_raises(tmp_db):
    """Inserting a race_results row with a non-existent raceId must raise IntegrityError."""
    _insert_circuit(tmp_db, circuit_id=1)
    # Insert a race so FK chain is partial — but we intentionally use a raceId that has NO
    # corresponding row in races to trigger the FK violation.
    _insert_driver(tmp_db, driver_id=99)

    with pytest.raises(sqlite3.IntegrityError):
        tmp_db.execute(
            "INSERT INTO race_results "
            "(raceId, year, kaggle_driver_id, team, track, position, starting_grid, "
            " finished, dnf, laps_down, time_gap_sec, rain, sunny) "
            "VALUES (9999, 2023, 99, 'TeamX', 'TrackX', 1, 1, 1, 0, NULL, NULL, 0, 1)"
        )


# ---------------------------------------------------------------------------
# 5. UNIQUE constraint on race_results silently ignores duplicates (INSERT OR IGNORE)
# ---------------------------------------------------------------------------

def _insert_race_result_ignore(conn, race_id: int, driver_id: int) -> None:
    """Insert a race_results row using INSERT OR IGNORE (bypasses FK for test isolation)."""
    conn.execute(
        "INSERT OR IGNORE INTO race_results "
        "(raceId, year, kaggle_driver_id, team, track, position, starting_grid, "
        " finished, dnf, laps_down, time_gap_sec, rain, sunny) "
        "VALUES (?, 2023, ?, 'TeamA', 'TrackA', 1, 1, 1, 0, NULL, NULL, 0, 1)",
        (race_id, driver_id),
    )


def test_unique_constraint_race_results(schema_sql):
    """Inserting the same (raceId, kaggle_driver_id) twice must keep count at 1."""
    # Use FK=OFF so we don't need a races/drivers row
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript(schema_sql)

    _insert_race_result_ignore(conn, race_id=1, driver_id=10)
    _insert_race_result_ignore(conn, race_id=1, driver_id=10)  # duplicate

    count = conn.execute("SELECT COUNT(*) FROM race_results").fetchone()[0]
    assert count == 1, f"Expected 1 row, got {count}"
    conn.close()


# ---------------------------------------------------------------------------
# 6. run_etl creates the .db file even when data_root doesn't exist
# ---------------------------------------------------------------------------

def test_etl_creates_db_when_missing(tmp_path):
    """run_etl must create the database file even if data_root has no data."""
    db_path = tmp_path / "new.db"
    nonexistent_data_root = tmp_path / "no_data_here"
    # data_root does NOT exist; loaders will log warnings and skip

    run_etl(db_path, nonexistent_data_root)

    assert db_path.exists(), f"Expected database file to be created at {db_path}"
    assert db_path.stat().st_size > 0, "Database file should not be empty (schema must be written)"


# ---------------------------------------------------------------------------
# 7. map_qualifying_row drops Unnamed: 0 column
# ---------------------------------------------------------------------------

def test_unnamed_column_absent_after_sprint_quali_load(tmp_path):
    """map_qualifying_row must drop 'Unnamed: 0' columns from sprint qualifying CSVs."""
    # Create a fake sprint qualifying CSV with an Unnamed: 0 column
    sprint_quali_csv = tmp_path / "sprint_quali_test.csv"
    fieldnames = [
        "Unnamed: 0", "raceId", "year", "kaggle_driver_id", "Team", "Track",
        "Position", "participated_q2", "participated_q3",
        "q1_time_sec", "q2_time_sec", "q3_time_sec", "rain", "sunny",
    ]
    with sprint_quali_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow({
            "Unnamed: 0": "0",
            "raceId": "1",
            "year": "2023",
            "kaggle_driver_id": "10",
            "Team": "Red Bull",
            "Track": "Bahrain",
            "Position": "1",
            "participated_q2": "1",
            "participated_q3": "1",
            "q1_time_sec": "88.0",
            "q2_time_sec": "87.5",
            "q3_time_sec": "87.1",
            "rain": "0",
            "sunny": "1",
        })

    # Read back the CSV and call map_qualifying_row as load_sprint_results would
    with sprint_quali_csv.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        row = next(iter(reader))

    result = map_qualifying_row(row)

    assert "Unnamed: 0" not in result, (
        f"'Unnamed: 0' key must not appear in map_qualifying_row output, got keys: {list(result.keys())}"
    )
