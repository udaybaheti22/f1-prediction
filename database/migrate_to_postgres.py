"""
Migrate f1_analytics.db (SQLite) → f1_analytics (PostgreSQL)

- Creates all 8 tables with PostgreSQL-compatible DDL
- Migrates all rows in batches
- Creates all 15 analytical views
- Safe to re-run (drops and recreates tables)

Usage:
    python database/migrate_to_postgres.py
"""
import sqlite3
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

# ── Connection settings ───────────────────────────────────────────────────────
PG_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "f1_analytics",
    "user":     "postgres",
    "password": "uday123",
}
SQLITE_PATH = Path("database/f1_analytics.db")
ANALYTICS_SQL = Path("database/analytics_queries_pg.sql")
BATCH_SIZE = 500

# ── PostgreSQL DDL ────────────────────────────────────────────────────────────
# SQLite INTEGER PRIMARY KEY AUTOINCREMENT → SERIAL PRIMARY KEY
# SQLite REAL → DOUBLE PRECISION
# SQLite TEXT → TEXT
# SQLite INTEGER → INTEGER

PG_DDL = """
DROP TABLE IF EXISTS sprint_qualifying_results CASCADE;
DROP TABLE IF EXISTS sprint_results           CASCADE;
DROP TABLE IF EXISTS qualifying_results       CASCADE;
DROP TABLE IF EXISTS race_results             CASCADE;
DROP TABLE IF EXISTS weather                  CASCADE;
DROP TABLE IF EXISTS races                    CASCADE;
DROP TABLE IF EXISTS drivers                  CASCADE;
DROP TABLE IF EXISTS circuits                 CASCADE;

CREATE TABLE circuits (
    circuit_id   INTEGER PRIMARY KEY,
    circuit_name TEXT,
    location     TEXT,
    country      TEXT,
    lat          DOUBLE PRECISION,
    lng          DOUBLE PRECISION,
    alt          DOUBLE PRECISION
);

CREATE TABLE drivers (
    kaggle_driver_id INTEGER PRIMARY KEY,
    driver_name      TEXT,
    nationality      TEXT,
    dob              TEXT,
    driver_code      TEXT,
    team             TEXT
);

CREATE TABLE races (
    raceId     INTEGER PRIMARY KEY,
    year       INTEGER,
    round      INTEGER,
    circuit_id INTEGER REFERENCES circuits(circuit_id),
    race_name  TEXT,
    race_date  TEXT
);

CREATE TABLE weather (
    raceId INTEGER PRIMARY KEY,
    year   INTEGER,
    rain   INTEGER,
    sunny  INTEGER
);

CREATE TABLE race_results (
    id               SERIAL PRIMARY KEY,
    raceId           INTEGER REFERENCES races(raceId),
    year             INTEGER,
    kaggle_driver_id INTEGER REFERENCES drivers(kaggle_driver_id),
    team             TEXT,
    track            TEXT,
    position         INTEGER,
    starting_grid    INTEGER,
    finished         INTEGER,
    dnf              INTEGER,
    laps_down        DOUBLE PRECISION,
    time_gap_sec     DOUBLE PRECISION,
    rain             INTEGER,
    sunny            INTEGER,
    UNIQUE (raceId, kaggle_driver_id)
);

CREATE TABLE qualifying_results (
    id               SERIAL PRIMARY KEY,
    raceId           INTEGER,
    year             INTEGER,
    kaggle_driver_id INTEGER,
    team             TEXT,
    track            TEXT,
    position         INTEGER,
    participated_q2  INTEGER,
    participated_q3  INTEGER,
    q1_time_sec      DOUBLE PRECISION,
    q2_time_sec      DOUBLE PRECISION,
    q3_time_sec      DOUBLE PRECISION,
    rain             INTEGER,
    sunny            INTEGER,
    UNIQUE (raceId, kaggle_driver_id)
);

CREATE TABLE sprint_results (
    id               SERIAL PRIMARY KEY,
    raceId           INTEGER,
    year             INTEGER,
    kaggle_driver_id INTEGER,
    team             TEXT,
    track            TEXT,
    position         INTEGER,
    starting_grid    INTEGER,
    finished         INTEGER,
    dnf              INTEGER,
    laps_down        DOUBLE PRECISION,
    time_gap_sec     DOUBLE PRECISION,
    rain             INTEGER,
    sunny            INTEGER,
    UNIQUE (raceId, kaggle_driver_id)
);

CREATE TABLE sprint_qualifying_results (
    id               SERIAL PRIMARY KEY,
    raceId           INTEGER,
    year             INTEGER,
    kaggle_driver_id INTEGER,
    team             TEXT,
    track            TEXT,
    position         INTEGER,
    participated_q2  INTEGER,
    participated_q3  INTEGER,
    q1_time_sec      DOUBLE PRECISION,
    q2_time_sec      DOUBLE PRECISION,
    q3_time_sec      DOUBLE PRECISION,
    rain             INTEGER,
    sunny            INTEGER,
    UNIQUE (raceId, kaggle_driver_id)
);
"""

# Tables to migrate in FK-safe order, with their column lists (excluding 'id')
TABLES = [
    ("circuits",                 ["circuit_id","circuit_name","location","country","lat","lng","alt"]),
    ("drivers",                  ["kaggle_driver_id","driver_name","nationality","dob","driver_code","team"]),
    ("races",                    ["raceId","year","round","circuit_id","race_name","race_date"]),
    ("weather",                  ["raceId","year","rain","sunny"]),
    ("race_results",             ["raceId","year","kaggle_driver_id","team","track","position","starting_grid","finished","dnf","laps_down","time_gap_sec","rain","sunny"]),
    ("qualifying_results",       ["raceId","year","kaggle_driver_id","team","track","position","participated_q2","participated_q3","q1_time_sec","q2_time_sec","q3_time_sec","rain","sunny"]),
    ("sprint_results",           ["raceId","year","kaggle_driver_id","team","track","position","starting_grid","finished","dnf","laps_down","time_gap_sec","rain","sunny"]),
    ("sprint_qualifying_results",["raceId","year","kaggle_driver_id","team","track","position","participated_q2","participated_q3","q1_time_sec","q2_time_sec","q3_time_sec","rain","sunny"]),
]


def adapt_views_for_postgres(sql: str) -> str:
    """Convert SQLite view SQL to PostgreSQL-compatible syntax."""
    import re
    # SQLite: DROP VIEW IF EXISTS → PostgreSQL: DROP VIEW IF EXISTS (same, fine)
    # SQLite: CREATE VIEW → PostgreSQL: CREATE OR REPLACE VIEW
    sql = re.sub(
        r'\bCREATE VIEW\b',
        'CREATE OR REPLACE VIEW',
        sql
    )
    # SQLite CAST(x AS REAL) → PostgreSQL CAST(x AS DOUBLE PRECISION)
    sql = sql.replace("CAST(SUM(dnf) AS REAL)", "CAST(SUM(dnf) AS DOUBLE PRECISION)")
    # SQLite doesn't need schema prefix, PostgreSQL is fine with unqualified names too
    return sql


def migrate_table(sqlite_conn, pg_cur, table, columns):
    """Read all rows from SQLite table and bulk-insert into PostgreSQL."""
    col_list = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))

    # Fetch from SQLite
    rows = sqlite_conn.execute(f"SELECT {col_list} FROM {table}").fetchall()
    if not rows:
        print(f"  {table:<35} 0 rows (empty)")
        return

    insert_sql = f"INSERT INTO {table} ({col_list}) VALUES %s ON CONFLICT DO NOTHING"

    # Batch insert
    total = 0
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        execute_values(pg_cur, insert_sql, batch)
        total += len(batch)

    print(f"  {table:<35} {total:>6} rows migrated")


def main():
    print("Connecting to PostgreSQL...")
    pg_conn = psycopg2.connect(**PG_CONFIG)
    pg_conn.autocommit = False
    pg_cur = pg_conn.cursor()

    print("Connecting to SQLite...")
    sqlite_conn = sqlite3.connect(SQLITE_PATH)

    try:
        # ── 1. Create tables ──────────────────────────────────────────────────
        print("\nCreating PostgreSQL tables...")
        pg_cur.execute(PG_DDL)
        pg_conn.commit()
        print("  Tables created.")

        # ── 2. Migrate data ───────────────────────────────────────────────────
        print("\nMigrating data:")
        for table, columns in TABLES:
            migrate_table(sqlite_conn, pg_cur, table, columns)
            pg_conn.commit()

        # ── 3. Create analytical views ────────────────────────────────────────
        print("\nCreating analytical views...")
        # Drop any stale views from previous runs first
        pg_cur.execute("""
            DO $$ DECLARE r RECORD;
            BEGIN
                FOR r IN SELECT viewname FROM pg_views WHERE schemaname = 'public'
                LOOP
                    EXECUTE 'DROP VIEW IF EXISTS ' || r.viewname || ' CASCADE';
                END LOOP;
            END $$;
        """)
        pg_conn.commit()

        raw_sql = ANALYTICS_SQL.read_text(encoding="utf-8")
        pg_sql = adapt_views_for_postgres(raw_sql)

        # Split on DROP VIEW / CREATE OR REPLACE VIEW boundaries and execute each block
        import re
        # Execute the full script — psycopg2 can't use executescript like sqlite3,
        # so split on statement boundaries
        statements = [s.strip() for s in re.split(r';\s*\n', pg_sql) if s.strip()]
        for stmt in statements:
            if stmt:
                try:
                    pg_cur.execute(stmt)
                except Exception as e:
                    print(f"  Warning on view statement: {e}")
                    pg_conn.rollback()
                    pg_cur = pg_conn.cursor()
                    continue
        pg_conn.commit()
        print("  Views created.")

        # ── 4. Row count summary ──────────────────────────────────────────────
        print("\n=== Migration complete — row counts ===")
        for table, _ in TABLES:
            pg_cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = pg_cur.fetchone()[0]
            print(f"  {table:<35} {count:>8} rows")

        print("\n=== Views created ===")
        pg_cur.execute("SELECT viewname FROM pg_views WHERE schemaname = 'public' ORDER BY viewname")
        for (v,) in pg_cur.fetchall():
            print(f"  {v}")

    except Exception as e:
        pg_conn.rollback()
        print(f"\nERROR: {e}")
        raise
    finally:
        sqlite_conn.close()
        pg_cur.close()
        pg_conn.close()
        print("\nConnections closed.")


if __name__ == "__main__":
    main()
