"""
Feature: f1-sql-analytics-pipeline
Property 1: ETL Idempotency
Validates: Requirements 2.3, 3.3, 4.3, 5.4, 6.1
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.etl import upsert_rows


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

def _race_result_row(race_id: int, driver_id: int) -> dict:
    """Build a minimal race_results row dict for the given (raceId, kaggle_driver_id)."""
    return {
        "raceId": race_id,
        "year": 2023,
        "kaggle_driver_id": driver_id,
        "team": "Test Team",
        "track": "Test Track",
        "position": 1,
        "starting_grid": 1,
        "finished": 1,
        "dnf": 0,
        "laps_down": None,
        "time_gap_sec": None,
        "rain": 0,
        "sunny": 1,
    }


# Strategy: generate a list of unique (raceId, kaggle_driver_id) pairs
@st.composite
def unique_race_result_rows(draw) -> list[dict]:
    """Generate a list of race_result rows with no duplicate (raceId, driver_id) pairs."""
    n = draw(st.integers(min_value=1, max_value=15))
    pairs = draw(
        st.lists(
            st.tuples(
                st.integers(min_value=1, max_value=10),
                st.integers(min_value=1, max_value=20),
            ),
            min_size=n,
            max_size=n,
            unique=True,
        )
    )
    return [_race_result_row(race_id, driver_id) for race_id, driver_id in pairs]


# ---------------------------------------------------------------------------
# Shared fixture: schema SQL
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def schema_sql() -> str:
    schema_path = Path(__file__).parent.parent / "database" / "schema.sql"
    return schema_path.read_text(encoding="utf-8")


@pytest.fixture
def tmp_db(schema_sql: str):
    """In-memory SQLite connection with schema applied and FK enforcement ON."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = OFF")  # race_results has FK to races/drivers; disable for isolation
    conn.executescript(schema_sql)
    yield conn
    conn.close()


def _make_db(schema_sql: str):
    """Create a fresh in-memory DB with schema applied (FK OFF for isolation)."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript(schema_sql)
    return conn


# ---------------------------------------------------------------------------
# Property 1a — Idempotency: inserting the same rows twice leaves count unchanged
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(unique_race_result_rows())
def test_upsert_idempotency_race_results(rows):
    """**Validates: Requirements 2.3, 3.3, 4.3, 5.4, 6.1**

    Inserting the same set of rows a second time must not change the row
    count, and no (raceId, kaggle_driver_id) pair must appear more than once.
    """
    schema_path = Path(__file__).parent.parent / "database" / "schema.sql"
    schema = schema_path.read_text(encoding="utf-8")
    conn = _make_db(schema)
    try:
        # First insert
        upsert_rows(conn, "race_results", rows, ["raceId", "kaggle_driver_id"])
        count_after_first = conn.execute("SELECT COUNT(*) FROM race_results").fetchone()[0]

        # Second insert (identical rows)
        upsert_rows(conn, "race_results", rows, ["raceId", "kaggle_driver_id"])
        count_after_second = conn.execute("SELECT COUNT(*) FROM race_results").fetchone()[0]

        assert count_after_second == count_after_first, (
            f"Row count changed on second insert: {count_after_first} → {count_after_second}"
        )

        # No duplicate (raceId, kaggle_driver_id) pairs
        dup_count = conn.execute(
            "SELECT COUNT(*) FROM ("
            "  SELECT raceId, kaggle_driver_id FROM race_results"
            "  GROUP BY raceId, kaggle_driver_id HAVING COUNT(*) > 1"
            ")"
        ).fetchone()[0]
        assert dup_count == 0, f"Found {dup_count} duplicate (raceId, kaggle_driver_id) pairs"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Property 1b — upsert_rows returns correct inserted/skipped counts
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(unique_race_result_rows())
def test_upsert_returns_correct_counts(rows):
    """**Validates: Requirements 2.3, 6.1**

    First call: inserted == N, skipped == 0.
    Second call with same rows: inserted == 0, skipped == N.
    """
    schema_path = Path(__file__).parent.parent / "database" / "schema.sql"
    schema = schema_path.read_text(encoding="utf-8")
    conn = _make_db(schema)
    try:
        n = len(rows)

        inserted, skipped = upsert_rows(conn, "race_results", rows, ["raceId", "kaggle_driver_id"])
        assert inserted == n, f"First insert: expected inserted={n}, got {inserted}"
        assert skipped == 0, f"First insert: expected skipped=0, got {skipped}"

        inserted2, skipped2 = upsert_rows(conn, "race_results", rows, ["raceId", "kaggle_driver_id"])
        assert inserted2 == 0, f"Second insert: expected inserted=0, got {inserted2}"
        assert skipped2 == n, f"Second insert: expected skipped={n}, got {skipped2}"
    finally:
        conn.close()
