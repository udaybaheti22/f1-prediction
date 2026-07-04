"""
Feature: f1-sql-analytics-pipeline
Property 2: ETL Numeric Cast — Non-Finite Values Become NULL
Property 3: Driver Deduplication — Most Recent Season Retained
Validates: Requirements 6.4, 5.1
"""

from __future__ import annotations

import csv
import sqlite3
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.etl import cast_numeric, load_drivers


# ---------------------------------------------------------------------------
# Property 2 — cast_numeric: Non-Finite Values Become NULL
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    st.one_of(
        st.just(float("nan")),
        st.just(float("inf")),
        st.just(float("-inf")),
    )
)
def test_cast_numeric_nonfinite(value):
    """**Validates: Requirements 6.4**
    Non-finite floats (NaN, +Inf, -Inf) must be cast to None.
    """
    assert cast_numeric(value) is None


@pytest.mark.parametrize("value", [None, "", " ", "\\N", "NA", "N/A"])
def test_cast_numeric_null_sentinels(value):
    """**Validates: Requirements 6.4**
    Known null-sentinel strings and None must all return None.
    """
    assert cast_numeric(value) is None


@settings(max_examples=100)
@given(
    st.floats(min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False)
)
def test_cast_numeric_valid_float(value):
    """**Validates: Requirements 6.4**
    Finite floats within range must round-trip through cast_numeric unchanged.
    """
    result = cast_numeric(value)
    assert result is not None
    assert result == pytest.approx(value)


@settings(max_examples=100)
@given(st.integers(min_value=-10000, max_value=10000))
def test_cast_numeric_valid_int(value):
    """**Validates: Requirements 6.4**
    Integer strings must be cast to the correct int value.
    """
    assert cast_numeric(str(value), int) == value


# ---------------------------------------------------------------------------
# Property 3 — Driver Deduplication: Most Recent Season Retained
# ---------------------------------------------------------------------------

def _build_driver_csv(tmp_dir: Path, year: int, rows: list[dict]) -> Path:
    """Write a driver CSV file for the given year under tmp_dir."""
    # load_drivers globs "f1*season_drivers_processed.csv"
    filepath = tmp_dir / f"f1{year}season_drivers_processed.csv"
    fieldnames = ["kaggle_driver_id", "Driver", "Team"]
    with filepath.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "kaggle_driver_id": row["kaggle_driver_id"],
                "Driver": row["driver_name"],
                "Team": row["team"],
            })
    return filepath


# Strategy: generate a list of driver records with controlled kaggle_driver_id
_driver_record_strategy = st.fixed_dictionaries({
    "kaggle_driver_id": st.integers(min_value=1, max_value=5),
    "year": st.integers(min_value=2019, max_value=2025),
    "driver_name": st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters=" "),
        min_size=1,
        max_size=30,
    ).map(str.strip).filter(lambda s: len(s) >= 1),
    "team": st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters=" "),
        min_size=1,
        max_size=30,
    ).map(str.strip).filter(lambda s: len(s) >= 1),
})


@settings(max_examples=50)
@given(st.lists(_driver_record_strategy, min_size=1, max_size=20))
def test_driver_dedup_keeps_max_year(driver_records):
    """**Validates: Requirements 5.1**
    After load_drivers, the stored team for each kaggle_driver_id must match
    the team from the row with the maximum year for that driver in the input.
    Uses a real temp directory on disk (required for CSV I/O).
    """
    import tempfile
    import shutil

    # Build the schema in a temp SQLite DB
    schema_path = Path(__file__).parent.parent / "database" / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(schema_sql)

    tmp_dir = Path(tempfile.mkdtemp())
    try:
        # Organise records by year so we can write one CSV per year
        years_to_records: dict[int, list[dict]] = {}
        for rec in driver_records:
            years_to_records.setdefault(rec["year"], []).append(rec)

        # Create the driver_dataset_final directory inside tmp_dir
        driver_dir = tmp_dir / "driver_dataset_final"
        driver_dir.mkdir(parents=True, exist_ok=True)

        for year, recs in years_to_records.items():
            _build_driver_csv(driver_dir, year, recs)

        # Run load_drivers (no filler file → enrichment is skipped, that's fine)
        load_drivers(conn, tmp_dir)

        # Proper computation: group by driver_id, find max-year entry
        from collections import defaultdict
        grouped: dict[int, list[dict]] = defaultdict(list)
        for rec in driver_records:
            grouped[rec["kaggle_driver_id"]].append(rec)

        expected: dict[int, str] = {}
        for kid, recs in grouped.items():
            best = max(recs, key=lambda r: r["year"])
            expected[kid] = best["team"].strip()

        # Query the DB and verify
        db_rows = conn.execute(
            "SELECT kaggle_driver_id, team FROM drivers"
        ).fetchall()
        stored = {row[0]: row[1] for row in db_rows}

        for kid, expected_team in expected.items():
            assert kid in stored, f"kaggle_driver_id={kid} not found in drivers table"
            assert stored[kid] == expected_team, (
                f"kaggle_driver_id={kid}: expected team={expected_team!r}, "
                f"got={stored[kid]!r}"
            )
    finally:
        conn.close()
        shutil.rmtree(tmp_dir, ignore_errors=True)
