"""
F1 SQL Analytics Pipeline — ETL Script
=======================================
Usage:
    python database/etl.py [--db-path PATH]

Loads all processed F1 CSV datasets into a SQLite database defined by
database/schema.sql.  Re-running is safe: every loader uses INSERT OR IGNORE
so no rows are duplicated.
"""

from __future__ import annotations

import csv
import logging
import math
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 2.1  cast_numeric
# ---------------------------------------------------------------------------

def cast_numeric(value, dtype=float):
    """Cast *value* to *dtype* (default ``float``).

    Returns ``None`` for:
    - ``None`` / ``""`` / ``"\\N"`` (Kaggle null sentinel)
    - ``NaN``, ``+Inf``, ``-Inf`` (after conversion)
    - Any value that cannot be parsed as *dtype*

    Parameters
    ----------
    value:
        Raw value from a CSV cell.
    dtype:
        Target numeric type (``float`` or ``int``).  Defaults to ``float``.

    Returns
    -------
    dtype | None
    """
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped in ("", r"\N", "\\N", "NA", "N/A"):
            return None
        value = stripped

    try:
        result = dtype(value)
    except (ValueError, TypeError):
        return None

    # Reject non-finite floats (NaN, ±Inf)
    try:
        if not math.isfinite(result):
            return None
    except TypeError:
        # isfinite not defined for int — that's fine
        pass

    return result


# ---------------------------------------------------------------------------
# 2.3  discover_files
# ---------------------------------------------------------------------------

def discover_files(base_dir: str, patterns: list[str]) -> list[Path]:
    """Return all files under *base_dir* that match any of *patterns*.

    Patterns are evaluated with :py:meth:`pathlib.Path.glob`, so you can
    use standard shell-style wildcards (``*``, ``**``, ``?``).

    Parameters
    ----------
    base_dir:
        Root directory to search.  May be an absolute or relative path string.
    patterns:
        List of glob patterns, e.g.
        ``["formula1_*season_raceResults.csv",
           "Formula1_*Season_RaceResults.csv"]``.

    Returns
    -------
    list[Path]
        Sorted list of matching :class:`pathlib.Path` objects.
        Returns an empty list (and logs a WARNING) when *base_dir* does not
        exist or is not a directory.
    """
    base = Path(base_dir)

    if not base.exists() or not base.is_dir():
        logger.warning(
            "discover_files: '%s' does not exist or is not a directory — "
            "returning empty list.",
            base,
        )
        return []

    matches: list[Path] = []
    for pattern in patterns:
        matches.extend(base.glob(pattern))

    # Deduplicate (a file could match multiple patterns) then sort
    return sorted(set(matches))


# ---------------------------------------------------------------------------
# 2.4  map_race_result_row / map_qualifying_row
# ---------------------------------------------------------------------------

def map_race_result_row(row: dict) -> dict:
    """Map a raw CSV row to ``race_results`` table column names and types.

    Reads from ``csv.DictReader`` output (all values are strings).  Integer
    columns use ``cast_numeric(value, int)``.  Real columns use
    ``cast_numeric(value, float)``.  Text columns are stripped of leading /
    trailing whitespace.

    ``position`` is allowed to be NULL (e.g. DNF / non-classified entries
    that cannot be cast to int).

    Parameters
    ----------
    row:
        Raw dict from :class:`csv.DictReader`.

    Returns
    -------
    dict
        Keys match the ``race_results`` table column names exactly.
    """
    return {
        "raceId":           cast_numeric(row.get("raceId"), int),
        "year":             cast_numeric(row.get("year"), int),
        "kaggle_driver_id": cast_numeric(row.get("kaggle_driver_id"), int),
        "team":             str(row.get("Team", "") or "").strip(),
        "track":            str(row.get("Track", "") or "").strip(),
        "position":         cast_numeric(row.get("Position"), int),   # NULL if not castable
        "starting_grid":    cast_numeric(row.get("Starting Grid"), int),
        "finished":         cast_numeric(row.get("finished"), int),
        "dnf":              cast_numeric(row.get("dnf"), int),
        "laps_down":        cast_numeric(row.get("laps_down"), float),
        "time_gap_sec":     cast_numeric(row.get("time_gap_sec"), float),
        "rain":             cast_numeric(row.get("rain"), int),
        "sunny":            cast_numeric(row.get("sunny"), int),
    }


def map_qualifying_row(row: dict) -> dict:
    """Map a raw CSV row to ``qualifying_results`` table column names and types.

    Reads from ``csv.DictReader`` output.  Any key that starts with
    ``"Unnamed"`` is silently dropped before mapping — sprint qualifying CSVs
    include an ``Unnamed: 0`` pandas index column that must not be forwarded
    to the database.

    Parameters
    ----------
    row:
        Raw dict from :class:`csv.DictReader`.

    Returns
    -------
    dict
        Keys match the ``qualifying_results`` table column names exactly.
    """
    # Drop any Unnamed index columns produced by pandas CSV exports
    cleaned: dict = {k: v for k, v in row.items() if not k.startswith("Unnamed")}

    return {
        "raceId":           cast_numeric(cleaned.get("raceId"), int),
        "year":             cast_numeric(cleaned.get("year"), int),
        "kaggle_driver_id": cast_numeric(cleaned.get("kaggle_driver_id"), int),
        "team":             str(cleaned.get("Team", "") or "").strip(),
        "track":            str(cleaned.get("Track", "") or "").strip(),
        "position":         cast_numeric(cleaned.get("Position"), int),
        "participated_q2":  cast_numeric(cleaned.get("participated_q2"), int),
        "participated_q3":  cast_numeric(cleaned.get("participated_q3"), int),
        "q1_time_sec":      cast_numeric(cleaned.get("q1_time_sec"), float),
        "q2_time_sec":      cast_numeric(cleaned.get("q2_time_sec"), float),
        "q3_time_sec":      cast_numeric(cleaned.get("q3_time_sec"), float),
        "rain":             cast_numeric(cleaned.get("rain"), int),
        "sunny":            cast_numeric(cleaned.get("sunny"), int),
    }


# ---------------------------------------------------------------------------
# 2.5  upsert_rows
# ---------------------------------------------------------------------------

def upsert_rows(
    conn,
    table: str,
    rows: list[dict],
    conflict_cols: list[str],
) -> tuple[int, int]:
    """Batch-insert *rows* into *table* using ``INSERT OR IGNORE``.

    Duplicate rows (as determined by the table's UNIQUE constraint) are
    silently skipped.  The *conflict_cols* parameter is accepted for API
    compatibility only — ``INSERT OR IGNORE`` handles all conflicts
    automatically via the table's UNIQUE constraint.

    Parameters
    ----------
    conn:
        An open :mod:`sqlite3` connection.
    table:
        Target table name.  Trusted internal value — used directly in the
        SQL structure via string formatting.
    rows:
        List of dicts where each key is a column name and each value is the
        data to insert.  All dicts must have identical key sets.
    conflict_cols:
        Accepted for API compatibility; not used in the SQL itself.

    Returns
    -------
    tuple[int, int]
        ``(inserted_count, skipped_count)`` where
        ``inserted_count + skipped_count == len(rows)``.
    """
    if not rows:
        return (0, 0)

    cols = list(rows[0].keys())
    placeholders = ", ".join("?" for _ in cols)
    col_list = ", ".join(cols)
    sql = f"INSERT OR IGNORE INTO {table} ({col_list}) VALUES ({placeholders})"

    params = [tuple(row[col] for col in cols) for row in rows]

    changes_before = conn.total_changes
    conn.executemany(sql, params)
    inserted_count = conn.total_changes - changes_before
    skipped_count = len(rows) - inserted_count

    return (inserted_count, skipped_count)


# ---------------------------------------------------------------------------
# 3.1  load_race_results
# ---------------------------------------------------------------------------


def load_race_results(conn, data_root: Path) -> None:
    """Load all main race result CSV files into the ``race_results`` table.

    Discovers files under ``data_root / "main_race_result(processed)"`` that
    match either of the two known filename patterns (lower-case and mixed-case
    season prefix), maps every row through :func:`map_race_result_row`, and
    upserts the results with :func:`upsert_rows`.

    Re-running is safe: duplicate ``(raceId, kaggle_driver_id)`` pairs are
    silently skipped (``INSERT OR IGNORE``).

    Parameters
    ----------
    conn:
        An open :mod:`sqlite3` connection with the schema already applied.
    data_root:
        Root directory of the processed datasets.  The function looks inside
        ``data_root / "main_race_result(processed)"`` for CSV files.
    """
    base_dir = data_root / "main_race_result(processed)"
    patterns = [
        "formula1_*season_raceResults.csv",
        "Formula1_*Season_RaceResults.csv",
    ]

    files = discover_files(str(base_dir), patterns)

    total_inserted = 0
    total_skipped = 0

    for file_path in files:
        rows: list[dict] = []
        try:
            with open(file_path, newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    rows.append(map_race_result_row(row))
        except Exception as exc:
            logger.warning("WARNING: skipping %s — %s", file_path, exc)
            continue

        inserted, skipped = upsert_rows(conn, "race_results", rows, ["raceId", "kaggle_driver_id"])
        total_inserted += inserted
        total_skipped += skipped
        logger.info(
            "race_results: %d inserted, %d skipped from %s",
            inserted,
            skipped,
            file_path.name,
        )

    logger.info(
        "race_results total: %d inserted, %d skipped across %d file(s)",
        total_inserted,
        total_skipped,
        len(files),
    )


# ---------------------------------------------------------------------------
# 3.2  load_qualifying_results
# ---------------------------------------------------------------------------

def load_qualifying_results(conn, data_root: Path) -> None:
    """Load qualifying results CSVs into the ``qualifying_results`` table.

    Discovers all ``race_quali_*.csv`` files inside
    ``<data_root>/quali_both_result(processed)/``, maps each row with
    :func:`map_qualifying_row`, and upserts into ``qualifying_results``
    using ``(raceId, kaggle_driver_id)`` as the conflict key.

    Per-file inserted/skipped counts are logged at INFO level.  If a file
    raises any exception it is logged at WARNING level and processing
    continues with the next file.

    Parameters
    ----------
    conn:
        An open :mod:`sqlite3` connection with the schema already applied.
    data_root:
        Root directory of the processed datasets.  The qualifying files are
        expected under ``data_root / "quali_both_result(processed)"``.
    """
    import csv

    base_dir = data_root / "quali_both_result(processed)"
    patterns = ["race_quali_*.csv"]

    files = discover_files(base_dir, patterns)

    if not files:
        logger.warning(
            "load_qualifying_results: no files matched in '%s'", base_dir
        )
        return

    for path in files:
        try:
            with open(path, newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                rows = [map_qualifying_row(row) for row in reader]

            inserted, skipped = upsert_rows(
                conn,
                "qualifying_results",
                rows,
                ["raceId", "kaggle_driver_id"],
            )
            logger.info(
                "load_qualifying_results: %s — inserted=%d, skipped=%d",
                path.name,
                inserted,
                skipped,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "load_qualifying_results: skipping '%s' — %s: %s",
                path,
                type(exc).__name__,
                exc,
            )


# ---------------------------------------------------------------------------
# 4.1  load_sprint_results
# ---------------------------------------------------------------------------

def load_sprint_results(conn, data_root) -> None:
    """Load sprint race and sprint qualifying results into the database.

    Sprint race results
    -------------------
    Discovers files matching ``sprint_race_result(processed)/sprint_*_result.csv``,
    reads each with :class:`csv.DictReader`, maps rows via
    :func:`map_race_result_row`, and upserts into the ``sprint_results`` table.

    Sprint qualifying results
    -------------------------
    Discovers files matching ``quali_both_result(processed)/sprint_quali_*.csv``,
    reads each with :class:`csv.DictReader`, maps rows via
    :func:`map_qualifying_row` (which already drops ``Unnamed:`` columns), and
    upserts into the ``sprint_qualifying_results`` table.

    Inserted and skipped row counts are logged per file.

    Parameters
    ----------
    conn:
        An open :mod:`sqlite3` connection.
    data_root:
        Root directory that contains the processed data subdirectories.
        May be a :class:`~pathlib.Path` or a string.
    """
    import csv

    data_root = Path(data_root)

    # ------------------------------------------------------------------
    # Sprint race results  →  sprint_results
    # ------------------------------------------------------------------
    sprint_race_files = discover_files(
        data_root / "sprint_race_result(processed)",
        ["sprint_*_result.csv"],
    )

    for filepath in sprint_race_files:
        try:
            with open(filepath, newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                rows = [map_race_result_row(row) for row in reader]
        except OSError as exc:
            logger.warning(
                "load_sprint_results: skipping '%s' — %s", filepath, exc
            )
            continue

        inserted, skipped = upsert_rows(
            conn, "sprint_results", rows, ["raceId", "kaggle_driver_id"]
        )
        logger.info(
            "sprint_results | %s → inserted=%d, skipped=%d",
            filepath.name, inserted, skipped,
        )

    # ------------------------------------------------------------------
    # Sprint qualifying results  →  sprint_qualifying_results
    # ------------------------------------------------------------------
    sprint_quali_files = discover_files(
        data_root / "quali_both_result(processed)",
        ["sprint_quali_*.csv"],
    )

    for filepath in sprint_quali_files:
        try:
            with open(filepath, newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                rows = [map_qualifying_row(row) for row in reader]
        except OSError as exc:
            logger.warning(
                "load_sprint_results: skipping '%s' — %s", filepath, exc
            )
            continue

        inserted, skipped = upsert_rows(
            conn, "sprint_qualifying_results", rows, ["raceId", "kaggle_driver_id"]
        )
        logger.info(
            "sprint_qualifying_results | %s → inserted=%d, skipped=%d",
            filepath.name, inserted, skipped,
        )


# ---------------------------------------------------------------------------
# 4.2  load_drivers
# ---------------------------------------------------------------------------

def load_drivers(conn, data_root: Path) -> None:
    """Load driver records into the ``drivers`` table.

    Steps
    -----
    1. Glob all ``f1*season_drivers_processed.csv`` files under
       ``data_root / "driver_dataset_final"``.
    2. Read every file with :class:`csv.DictReader`; extract the season
       *year* from each filename via ``r"f1(\\d{4})season"``.
    3. Deduplicate by ``kaggle_driver_id``, keeping the row with the highest
       *year* (most-recent team / name).
    4. Optionally enrich with ``filler-datasets(kaggle)/drivers.csv`` for
       ``nationality``, ``dob``, and ``driver_code`` — joined on normalised
       driver name (lowercase, NFKD accent-stripped).  Unmatched drivers
       receive ``None`` for those fields.
    5. Insert via :func:`upsert_rows` with conflict column
       ``["kaggle_driver_id"]`` and log the result.

    Parameters
    ----------
    conn:
        Open :mod:`sqlite3` connection with the schema already applied.
    data_root:
        Repository root directory containing ``driver_dataset_final/`` and
        ``filler-datasets(kaggle)/``.
    """
    import csv
    import re
    import unicodedata

    driver_dir = data_root / "driver_dataset_final"
    filler_path = data_root / "filler-datasets(kaggle)" / "drivers.csv"

    # ------------------------------------------------------------------
    # 1. Discover season CSV files
    # ------------------------------------------------------------------
    csv_files = sorted(driver_dir.glob("f1*season_drivers_processed.csv"))
    if not csv_files:
        logger.warning("load_drivers: no season files found in '%s'", driver_dir)
        return

    # ------------------------------------------------------------------
    # 2 & 3. Read all rows, annotate with year, deduplicate
    # ------------------------------------------------------------------
    year_pattern = re.compile(r"f1(\d{4})season")

    # best[kaggle_driver_id] = (year, row_dict)
    best: dict[int, tuple[int, dict]] = {}

    for csv_path in csv_files:
        m = year_pattern.search(csv_path.name)
        if not m:
            logger.warning("load_drivers: cannot extract year from '%s', skipping", csv_path.name)
            continue
        year = int(m.group(1))

        with csv_path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                row["year"] = year
                kid = cast_numeric(row.get("kaggle_driver_id"), int)
                if kid is None:
                    continue
                existing = best.get(kid)
                if existing is None or year > existing[0]:
                    best[kid] = (year, row)

    deduplicated_rows = [item[1] for item in best.values()]
    logger.info("load_drivers: %d unique drivers found across season files", len(deduplicated_rows))

    # ------------------------------------------------------------------
    # 4. Enrich from filler CSV
    # ------------------------------------------------------------------
    def _normalise(name: str) -> str:
        """Lowercase + strip accents via NFKD decomposition."""
        nfkd = unicodedata.normalize("NFKD", name)
        return "".join(ch for ch in nfkd if not unicodedata.combining(ch)).lower().strip()

    # Build lookup: normalised_full_name -> {nationality, dob, driver_code}
    filler_lookup: dict[str, dict] = {}
    if filler_path.exists():
        with filler_path.open(newline="", encoding="utf-8") as fh:
            for frow in csv.DictReader(fh):
                forename = frow.get("forename", "").strip()
                surname = frow.get("surname", "").strip()
                full_name = f"{forename} {surname}"
                key = _normalise(full_name)
                filler_lookup[key] = {
                    "nationality": frow.get("nationality") or None,
                    "dob":         frow.get("dob") or None,
                    "driver_code": frow.get("code") or None,
                }
    else:
        logger.warning("load_drivers: filler file not found at '%s' — enrichment skipped", filler_path)

    # ------------------------------------------------------------------
    # 5. Build final row dicts for DB insertion
    # ------------------------------------------------------------------
    insert_rows: list[dict] = []
    for row in deduplicated_rows:
        driver_name = str(row.get("Driver", "") or "").strip()
        enrichment = filler_lookup.get(_normalise(driver_name), {})

        insert_rows.append({
            "kaggle_driver_id": cast_numeric(row.get("kaggle_driver_id"), int),
            "driver_name":      driver_name,
            "team":             str(row.get("Team", "") or "").strip(),
            "nationality":      enrichment.get("nationality"),
            "dob":              enrichment.get("dob"),
            "driver_code":      enrichment.get("driver_code"),
        })

    # ------------------------------------------------------------------
    # 6 & 7. Upsert and log
    # ------------------------------------------------------------------
    inserted, skipped = upsert_rows(conn, "drivers", insert_rows, ["kaggle_driver_id"])
    logger.info(
        "load_drivers: inserted=%d  skipped/duplicate=%d  total=%d",
        inserted,
        skipped,
        len(insert_rows),
    )


# ---------------------------------------------------------------------------
# 4.4  load_reference_tables
# ---------------------------------------------------------------------------

def load_reference_tables(conn, data_root: Path) -> None:
    """Load reference tables: ``circuits``, ``races``, and ``weather``.

    Reads two source files and populates three tables:

    1. ``filler-datasets(kaggle)/circuits.csv`` → ``circuits`` table  (loaded first
       because ``races`` has a FK → ``circuits.circuit_id``).
    2. ``races_with_weather.csv`` (at *data_root* root level) → ``races`` and
       ``weather`` tables.

    The Kaggle null sentinel ``"\\N"`` is replaced with ``None`` before any
    type casting.  All inserts use ``INSERT OR IGNORE`` (via
    :func:`upsert_rows`) so re-running is safe.

    Parameters
    ----------
    conn:
        An open :mod:`sqlite3` connection with the schema already applied.
    data_root:
        Root directory of the datasets.  ``races_with_weather.csv`` is
        expected directly under *data_root*; ``circuits.csv`` is expected
        under ``data_root / "filler-datasets(kaggle)"``.
    """
    # circuits must be loaded before races (FK: races.circuit_id → circuits.circuit_id)
    _load_circuits(conn, data_root)
    _load_races_and_weather(conn, data_root)


def _null_sentinel(value: str | None) -> str | None:
    """Return ``None`` when *value* is the Kaggle null sentinel ``\\N``."""
    if isinstance(value, str) and value.strip() in (r"\N", "\\N"):
        return None
    return value


def _load_races_and_weather(conn, data_root: Path) -> None:
    """Internal helper: load ``races`` and ``weather`` from ``races_with_weather.csv``."""
    csv_path = data_root / "races_with_weather.csv"

    if not csv_path.exists():
        logger.warning(
            "_load_races_and_weather: '%s' not found — skipping races and weather.",
            csv_path,
        )
        return

    race_rows: list[dict] = []
    weather_rows: list[dict] = []

    try:
        with open(csv_path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                # Replace Kaggle null sentinel before any casting
                cleaned = {k: _null_sentinel(v) for k, v in row.items()}

                race_rows.append({
                    "raceId":      cast_numeric(cleaned.get("raceId"), int),
                    "year":        cast_numeric(cleaned.get("year"), int),
                    "round":       cast_numeric(cleaned.get("round"), int),
                    "circuit_id":  cast_numeric(cleaned.get("circuitId"), int),
                    "race_name":   str(cleaned.get("name") or "").strip(),
                    "race_date":   str(cleaned.get("date") or "").strip(),
                })

                weather_rows.append({
                    "raceId": cast_numeric(cleaned.get("raceId"), int),
                    "year":   cast_numeric(cleaned.get("year"), int),
                    "rain":   cast_numeric(cleaned.get("rain"), int),
                    "sunny":  cast_numeric(cleaned.get("sunny"), int),
                })
    except Exception as exc:
        logger.warning(
            "_load_races_and_weather: error reading '%s' — %s: %s",
            csv_path,
            type(exc).__name__,
            exc,
        )
        return

    inserted, skipped = upsert_rows(conn, "races", race_rows, ["raceId"])
    logger.info(
        "races: %d inserted, %d skipped from %s",
        inserted,
        skipped,
        csv_path.name,
    )

    inserted, skipped = upsert_rows(conn, "weather", weather_rows, ["raceId"])
    logger.info(
        "weather: %d inserted, %d skipped from %s",
        inserted,
        skipped,
        csv_path.name,
    )


def _load_circuits(conn, data_root: Path) -> None:
    """Internal helper: load ``circuits`` from ``filler-datasets(kaggle)/circuits.csv``."""
    csv_path = data_root / "filler-datasets(kaggle)" / "circuits.csv"

    if not csv_path.exists():
        logger.warning(
            "_load_circuits: '%s' not found — skipping circuits.",
            csv_path,
        )
        return

    circuit_rows: list[dict] = []

    try:
        with open(csv_path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                # Replace Kaggle null sentinel before any casting
                cleaned = {k: _null_sentinel(v) for k, v in row.items()}

                circuit_rows.append({
                    "circuit_id":   cast_numeric(cleaned.get("circuitId"), int),
                    "circuit_name": str(cleaned.get("name") or "").strip(),
                    "location":     str(cleaned.get("location") or "").strip(),
                    "country":      str(cleaned.get("country") or "").strip(),
                    "lat":          cast_numeric(cleaned.get("lat"), float),
                    "lng":          cast_numeric(cleaned.get("lng"), float),
                    "alt":          cast_numeric(cleaned.get("alt"), float),
                })
    except Exception as exc:
        logger.warning(
            "_load_circuits: error reading '%s' — %s: %s",
            csv_path,
            type(exc).__name__,
            exc,
        )
        return

    inserted, skipped = upsert_rows(conn, "circuits", circuit_rows, ["circuit_id"])
    logger.info(
        "circuits: %d inserted, %d skipped from %s",
        inserted,
        skipped,
        csv_path.name,
    )


# ---------------------------------------------------------------------------
# 5  run_etl  (orchestrator)
# ---------------------------------------------------------------------------

def run_etl(db_path: Path, data_root: Path) -> None:
    """Orchestrate the full ETL: create schema, load all tables, print summary.

    Steps
    -----
    1. Read ``database/schema.sql`` from the same directory as this file.
       Raises :class:`FileNotFoundError` if the file does not exist.
    2. Open (or create) a SQLite connection to *db_path*.
    3. Enable foreign-key enforcement and execute the schema DDL.
    4. Load tables in dependency order:
       ``load_reference_tables`` → ``load_drivers`` → ``load_race_results``
       → ``load_qualifying_results`` → ``load_sprint_results``
    5. Print a per-table row-count summary for all 8 tables.
    6. Commit and close.

    Parameters
    ----------
    db_path:
        Path to the target SQLite database file.  Created automatically by
        ``sqlite3.connect()`` if it does not already exist.
    data_root:
        Root directory of the processed source datasets.
    """
    import sqlite3

    schema_path = Path(__file__).parent / "schema.sql"
    if not schema_path.exists():
        raise FileNotFoundError(
            f"run_etl: schema.sql not found at '{schema_path}'"
        )

    schema_sql = schema_path.read_text(encoding="utf-8")

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(schema_sql)

        # Load reference tables first (no FK dependencies on result tables)
        load_reference_tables(conn, data_root)
        load_drivers(conn, data_root)
        load_race_results(conn, data_root)
        load_qualifying_results(conn, data_root)
        load_sprint_results(conn, data_root)

        conn.commit()

        # ------------------------------------------------------------------
        # Per-table row count summary
        # ------------------------------------------------------------------
        tables = [
            "circuits",
            "races",
            "weather",
            "drivers",
            "race_results",
            "qualifying_results",
            "sprint_results",
            "sprint_qualifying_results",
        ]
        print("\n=== ETL complete — row counts ===")
        for table in tables:
            (count,) = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            print(f"  {table:<30} {count:>8} rows")
        print("=================================\n")

    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="F1 SQL Analytics Pipeline — ETL loader",
    )
    parser.add_argument(
        "--db-path",
        default="database/f1_analytics.db",
        help="Path to the target SQLite database (default: database/f1_analytics.db)",
    )
    parser.add_argument(
        "--data-root",
        default=".",
        help="Root directory of the processed source datasets (default: current working directory)",
    )
    args = parser.parse_args()

    run_etl(Path(args.db_path), Path(args.data_root))
