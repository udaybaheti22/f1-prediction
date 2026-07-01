-- F1 Analytics Pipeline — SQLite Schema
-- Usage note: PRAGMA foreign_keys = ON must be executed at connection open time
-- (e.g. conn.execute("PRAGMA foreign_keys = ON")) to enforce FK constraints.

-- ============================================================
-- Reference / lookup tables first (no FK dependencies)
-- ============================================================

CREATE TABLE IF NOT EXISTS circuits (
    circuit_id   INTEGER PRIMARY KEY,
    circuit_name TEXT,
    location     TEXT,
    country      TEXT,
    lat          REAL,
    lng          REAL,
    alt          REAL
);

CREATE TABLE IF NOT EXISTS drivers (
    kaggle_driver_id INTEGER PRIMARY KEY,
    driver_name      TEXT,
    nationality      TEXT,
    dob              TEXT,
    driver_code      TEXT,
    team             TEXT
);

CREATE TABLE IF NOT EXISTS races (
    raceId     INTEGER PRIMARY KEY,
    year       INTEGER,
    round      INTEGER,
    circuit_id INTEGER,
    race_name  TEXT,
    race_date  TEXT,   -- ISO 8601
    FOREIGN KEY (circuit_id) REFERENCES circuits (circuit_id)
);

CREATE TABLE IF NOT EXISTS weather (
    raceId INTEGER PRIMARY KEY,
    year   INTEGER,
    rain   INTEGER,   -- 0/1
    sunny  INTEGER    -- 0/1
);

-- ============================================================
-- Main result tables (reference circuits / drivers / races)
-- ============================================================

CREATE TABLE IF NOT EXISTS race_results (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    raceId           INTEGER,
    year             INTEGER,
    kaggle_driver_id INTEGER,
    team             TEXT,
    track            TEXT,
    position         INTEGER,   -- NULL if DNF/NC
    starting_grid    INTEGER,
    finished         INTEGER,   -- 0/1
    dnf              INTEGER,   -- 0/1
    laps_down        REAL,      -- NULL if N/A
    time_gap_sec     REAL,      -- NULL if leader or DNF
    rain             INTEGER,   -- 0/1
    sunny            INTEGER,   -- 0/1
    UNIQUE (raceId, kaggle_driver_id),
    FOREIGN KEY (raceId)           REFERENCES races   (raceId),
    FOREIGN KEY (kaggle_driver_id) REFERENCES drivers (kaggle_driver_id)
);

CREATE TABLE IF NOT EXISTS qualifying_results (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    raceId           INTEGER,
    year             INTEGER,
    kaggle_driver_id INTEGER,
    team             TEXT,
    track            TEXT,
    position         INTEGER,
    participated_q2  INTEGER,   -- 0/1
    participated_q3  INTEGER,   -- 0/1
    q1_time_sec      REAL,      -- NULL if no time
    q2_time_sec      REAL,      -- NULL if not in Q2
    q3_time_sec      REAL,      -- NULL if not in Q3
    rain             INTEGER,   -- 0/1
    sunny            INTEGER,   -- 0/1
    UNIQUE (raceId, kaggle_driver_id)
);

CREATE TABLE IF NOT EXISTS sprint_results (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    raceId           INTEGER,
    year             INTEGER,
    kaggle_driver_id INTEGER,
    team             TEXT,
    track            TEXT,
    position         INTEGER,   -- NULL if DNF/NC
    starting_grid    INTEGER,
    finished         INTEGER,   -- 0/1
    dnf              INTEGER,   -- 0/1
    laps_down        REAL,      -- NULL if N/A
    time_gap_sec     REAL,      -- NULL if leader or DNF
    rain             INTEGER,   -- 0/1
    sunny            INTEGER,   -- 0/1
    UNIQUE (raceId, kaggle_driver_id)
);

CREATE TABLE IF NOT EXISTS sprint_qualifying_results (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    raceId           INTEGER,
    year             INTEGER,
    kaggle_driver_id INTEGER,
    team             TEXT,
    track            TEXT,
    position         INTEGER,
    participated_q2  INTEGER,   -- 0/1
    participated_q3  INTEGER,   -- 0/1
    q1_time_sec      REAL,      -- NULL if no time
    q2_time_sec      REAL,      -- NULL if not in Q2
    q3_time_sec      REAL,      -- NULL if not in Q3
    rain             INTEGER,   -- 0/1
    sunny            INTEGER,   -- 0/1
    UNIQUE (raceId, kaggle_driver_id)
);
