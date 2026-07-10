-- ============================================================
-- F1 SQL Analytics Pipeline — Analytical Views (v2)
-- ============================================================
-- Page 1 — Race Results Browser
-- Page 2 — Season Overview
-- Page 3 — Driver Analysis
-- Page 4 — Circuit Insights
-- Page 5 — Weather & Model Results
--
-- Re-runnable: every view is dropped then recreated.
-- No view references another view (Power BI compatibility).
-- ============================================================


-- ============================================================
-- PAGE 1 — RACE RESULTS BROWSER
-- Select year + track to see the full race result.
-- ============================================================

DROP VIEW IF EXISTS vw_race_results_browser;
CREATE VIEW vw_race_results_browser AS
SELECT
    rr.year,
    r.round,
    rr.raceId,
    rr.track,
    d.driver_name,
    rr.team,
    qr.position         AS quali_pos,
    rr.starting_grid    AS grid_pos,
    rr.position         AS finish_pos,
    rr.dnf,
    rr.finished,
    rr.time_gap_sec,
    rr.laps_down,
    rr.rain,
    rr.sunny,
    -- Points scored in this race
    CASE rr.position
        WHEN 1  THEN 25
        WHEN 2  THEN 18
        WHEN 3  THEN 15
        WHEN 4  THEN 12
        WHEN 5  THEN 10
        WHEN 6  THEN 8
        WHEN 7  THEN 6
        WHEN 8  THEN 4
        WHEN 9  THEN 2
        WHEN 10 THEN 1
        ELSE 0
    END AS points_scored
FROM race_results rr
LEFT JOIN qualifying_results qr
    ON  qr.raceId           = rr.raceId
    AND qr.kaggle_driver_id = rr.kaggle_driver_id
LEFT JOIN drivers d
    ON  d.kaggle_driver_id  = rr.kaggle_driver_id
LEFT JOIN races r
    ON  r.raceId            = rr.raceId
ORDER BY rr.year, r.round, rr.raceId, rr.position;


-- ============================================================
-- PAGE 2 — SEASON OVERVIEW
-- ============================================================

-- ------------------------------------------------------------
-- vw_team_season_stats
-- Per team per season: races, avg finish, avg quali,
-- wins, podiums, DNFs.
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_team_season_stats;
CREATE VIEW vw_team_season_stats AS
SELECT
    rr.year,
    rr.team,
    COUNT(*)                                                AS total_entries,
    COUNT(DISTINCT rr.raceId)                               AS races_entered,
    ROUND(AVG(rr.position), 2)                              AS avg_finish_pos,
    ROUND(AVG(qr.position), 2)                              AS avg_quali_pos,
    SUM(CASE WHEN rr.position = 1  THEN 1 ELSE 0 END)       AS wins,
    SUM(CASE WHEN rr.position <= 3 THEN 1 ELSE 0 END)       AS podiums,
    SUM(rr.dnf)                                             AS dnf_count,
    SUM(CASE WHEN rr.finished = 1  THEN 1 ELSE 0 END)       AS finishes
FROM race_results rr
LEFT JOIN qualifying_results qr
    ON  qr.raceId           = rr.raceId
    AND qr.kaggle_driver_id = rr.kaggle_driver_id
GROUP BY rr.year, rr.team
ORDER BY rr.year, avg_finish_pos;


-- ------------------------------------------------------------
-- vw_team_points_trend
-- Total championship points per team per season (final standings).
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_team_points_trend;
CREATE VIEW vw_team_points_trend AS
SELECT
    year,
    team,
    SUM(
        CASE position
            WHEN 1  THEN 25 WHEN 2  THEN 18 WHEN 3  THEN 15
            WHEN 4  THEN 12 WHEN 5  THEN 10 WHEN 6  THEN 8
            WHEN 7  THEN 6  WHEN 8  THEN 4  WHEN 9  THEN 2
            WHEN 10 THEN 1  ELSE 0
        END
    )                                                       AS total_points,
    SUM(CASE WHEN position = 1  THEN 1 ELSE 0 END)         AS wins,
    SUM(CASE WHEN position <= 3 THEN 1 ELSE 0 END)         AS podiums,
    COUNT(*)                                                AS entries
FROM race_results
WHERE position IS NOT NULL
GROUP BY year, team
ORDER BY year, total_points DESC;


-- ------------------------------------------------------------
-- vw_team_points_by_round
-- Cumulative championship points per team per round within
-- each season. Powers a line chart showing the title battle
-- building race by race.
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_team_points_by_round;
CREATE VIEW vw_team_points_by_round AS
SELECT
    rr.year,
    r.round,
    rr.raceId,
    rr.track,
    rr.team,
    -- Points in this round
    SUM(
        CASE rr.position
            WHEN 1  THEN 25 WHEN 2  THEN 18 WHEN 3  THEN 15
            WHEN 4  THEN 12 WHEN 5  THEN 10 WHEN 6  THEN 8
            WHEN 7  THEN 6  WHEN 8  THEN 4  WHEN 9  THEN 2
            WHEN 10 THEN 1  ELSE 0
        END
    )                                                       AS round_points,
    -- Cumulative points up to and including this round
    (
        SELECT SUM(
            CASE r2.position
                WHEN 1  THEN 25 WHEN 2  THEN 18 WHEN 3  THEN 15
                WHEN 4  THEN 12 WHEN 5  THEN 10 WHEN 6  THEN 8
                WHEN 7  THEN 6  WHEN 8  THEN 4  WHEN 9  THEN 2
                WHEN 10 THEN 1  ELSE 0
            END)
        FROM race_results r2
        JOIN races ra2 ON ra2.raceId = r2.raceId
        WHERE r2.year  = rr.year
          AND r2.team  = rr.team
          AND ra2.round <= r.round
          AND r2.position IS NOT NULL
    )                                                       AS cumulative_points
FROM race_results rr
JOIN races r ON r.raceId = rr.raceId
WHERE rr.position IS NOT NULL
  AND r.round     IS NOT NULL
GROUP BY rr.year, r.round, rr.raceId, rr.track, rr.team
ORDER BY rr.year, r.round, cumulative_points DESC;


-- ============================================================
-- PAGE 3 — DRIVER ANALYSIS
-- ============================================================

-- ------------------------------------------------------------
-- vw_driver_season_stats
-- Per driver per season: races, avg finish, avg quali,
-- best finish, wins, podiums, DNFs.
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_driver_season_stats;
CREATE VIEW vw_driver_season_stats AS
SELECT
    rr.year,
    rr.kaggle_driver_id,
    d.driver_name,
    rr.team,
    COUNT(DISTINCT rr.raceId)                               AS races_entered,
    ROUND(AVG(rr.position), 2)                              AS avg_finish_pos,
    ROUND(AVG(qr.position), 2)                              AS avg_quali_pos,
    MIN(rr.position)                                        AS best_finish,
    SUM(CASE WHEN rr.position = 1  THEN 1 ELSE 0 END)      AS wins,
    SUM(CASE WHEN rr.position <= 3 THEN 1 ELSE 0 END)      AS podiums,
    SUM(rr.dnf)                                             AS dnf_count
FROM race_results rr
LEFT JOIN qualifying_results qr
    ON  qr.raceId           = rr.raceId
    AND qr.kaggle_driver_id = rr.kaggle_driver_id
LEFT JOIN drivers d ON d.kaggle_driver_id = rr.kaggle_driver_id
GROUP BY rr.year, rr.kaggle_driver_id, rr.team
ORDER BY rr.year, avg_finish_pos;


-- ------------------------------------------------------------
-- vw_driver_quali_race_avg
-- Career averages per driver: avg qualifying pos,
-- avg race finish pos, and avg delta (places gained/lost).
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_driver_quali_race_avg;
CREATE VIEW vw_driver_quali_race_avg AS
SELECT
    rr.kaggle_driver_id,
    d.driver_name,
    COUNT(*)                                                AS races_with_both,
    ROUND(AVG(qr.position), 2)                              AS avg_quali_pos,
    ROUND(AVG(rr.position), 2)                              AS avg_race_pos,
    ROUND(AVG(qr.position - rr.position), 3)                AS avg_delta
FROM race_results rr
JOIN qualifying_results qr
    ON  qr.raceId           = rr.raceId
    AND qr.kaggle_driver_id = rr.kaggle_driver_id
LEFT JOIN drivers d ON d.kaggle_driver_id = rr.kaggle_driver_id
WHERE rr.position  IS NOT NULL
  AND qr.position  IS NOT NULL
GROUP BY rr.kaggle_driver_id, d.driver_name
HAVING races_with_both >= 5
ORDER BY avg_race_pos;


-- ------------------------------------------------------------
-- vw_quali_conversion_rate
-- Per driver: % of top-10 grid starts that converted
-- to a top-10 finish (points).
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_quali_conversion_rate;
CREATE VIEW vw_quali_conversion_rate AS
SELECT
    rr.kaggle_driver_id,
    d.driver_name,
    COUNT(*)                                                AS top10_starts,
    SUM(CASE WHEN rr.position <= 10 THEN 1 ELSE 0 END)     AS top10_finishes,
    ROUND(
        100.0 * SUM(CASE WHEN rr.position <= 10 THEN 1 ELSE 0 END)
        / COUNT(*), 1
    )                                                       AS conversion_pct
FROM race_results rr
JOIN qualifying_results qr
    ON  qr.raceId           = rr.raceId
    AND qr.kaggle_driver_id = rr.kaggle_driver_id
LEFT JOIN drivers d ON d.kaggle_driver_id = rr.kaggle_driver_id
WHERE qr.position  <= 10
  AND rr.position  IS NOT NULL
GROUP BY rr.kaggle_driver_id, d.driver_name
HAVING top10_starts >= 5
ORDER BY conversion_pct DESC;


-- ------------------------------------------------------------
-- vw_teammate_comparison
-- Head-to-head within each team per race:
-- qualifying positions, race positions, Q3 time gap.
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_teammate_comparison;
CREATE VIEW vw_teammate_comparison AS
SELECT
    a.year,
    a.raceId,
    a.track,
    a.team,
    a.kaggle_driver_id          AS driver1_id,
    da.driver_name              AS driver1_name,
    qa.position                 AS driver1_quali_pos,
    a.position                  AS driver1_race_pos,
    qa.q3_time_sec              AS driver1_q3_time,
    b.kaggle_driver_id          AS driver2_id,
    db.driver_name              AS driver2_name,
    qb.position                 AS driver2_quali_pos,
    b.position                  AS driver2_race_pos,
    qb.q3_time_sec              AS driver2_q3_time,
    CASE
        WHEN qa.q3_time_sec IS NOT NULL AND qb.q3_time_sec IS NOT NULL
        THEN ROUND(qa.q3_time_sec - qb.q3_time_sec, 3)
        ELSE NULL
    END                         AS q3_gap_sec
FROM race_results a
JOIN race_results b
    ON  a.raceId = b.raceId
    AND a.team   = b.team
    AND a.kaggle_driver_id < b.kaggle_driver_id
LEFT JOIN qualifying_results qa
    ON  qa.raceId = a.raceId AND qa.kaggle_driver_id = a.kaggle_driver_id
LEFT JOIN qualifying_results qb
    ON  qb.raceId = b.raceId AND qb.kaggle_driver_id = b.kaggle_driver_id
LEFT JOIN drivers da ON da.kaggle_driver_id = a.kaggle_driver_id
LEFT JOIN drivers db ON db.kaggle_driver_id = b.kaggle_driver_id
ORDER BY a.year, a.raceId, a.team;


-- ============================================================
-- PAGE 4 — CIRCUIT INSIGHTS
-- ============================================================

-- ------------------------------------------------------------
-- vw_circuit_stats
-- Per circuit: total races, total entries, DNF rate,
-- average finishing spread (std dev proxy), dominant winner.
-- DNF rate = DNFs / ALL entries (including DNFs).
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_circuit_stats;
CREATE VIEW vw_circuit_stats AS
SELECT
    track,
    COUNT(DISTINCT raceId)                                  AS race_count,
    COUNT(*)                                                AS total_entries,
    SUM(dnf)                                                AS total_dnfs,
    ROUND(CAST(SUM(dnf) AS REAL) / COUNT(*), 4)             AS dnf_rate,
    ROUND(AVG(position), 2)                                 AS avg_finish_pos,
    -- Most frequent race winner at this circuit
    (
        SELECT team FROM race_results r2
        WHERE r2.track    = race_results.track
          AND r2.position = 1
        GROUP BY team
        ORDER BY COUNT(*) DESC
        LIMIT 1
    )                                                       AS most_successful_team,
    SUM(CASE WHEN position = 1 THEN 1 ELSE 0 END)          AS total_wins_recorded
FROM race_results
GROUP BY track
ORDER BY race_count DESC, dnf_rate DESC;


-- ------------------------------------------------------------
-- vw_circuit_dnf_rate
-- Per circuit per season: DNF rate breakdown.
-- DNF rate = DNFs / ALL entries (including DNFs).
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_circuit_dnf_rate;
CREATE VIEW vw_circuit_dnf_rate AS
SELECT
    year,
    track,
    COUNT(*)                                                AS total_entries,
    SUM(dnf)                                                AS total_dnfs,
    ROUND(CAST(SUM(dnf) AS REAL) / COUNT(*), 4)             AS dnf_rate
FROM race_results
GROUP BY year, track
ORDER BY dnf_rate DESC, year, track;


-- ------------------------------------------------------------
-- vw_circuit_dominant_teams
-- Per circuit: teams ranked by average finishing position.
-- Only teams with 3+ entries at that circuit.
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_circuit_dominant_teams;
CREATE VIEW vw_circuit_dominant_teams AS
SELECT
    track,
    team,
    COUNT(*)                                                AS entries,
    ROUND(AVG(position), 2)                                 AS avg_finish_pos,
    SUM(CASE WHEN position = 1  THEN 1 ELSE 0 END)         AS wins,
    SUM(CASE WHEN position <= 3 THEN 1 ELSE 0 END)         AS podiums,
    SUM(dnf)                                                AS dnfs
FROM race_results
WHERE position IS NOT NULL
GROUP BY track, team
HAVING entries >= 3
ORDER BY track, avg_finish_pos;


-- ============================================================
-- PAGE 5 — WEATHER & MODEL RESULTS
-- ============================================================

-- ------------------------------------------------------------
-- vw_weather_impact_summary
-- Per team: avg finish in wet vs dry races.
-- Shows which constructors benefit or suffer in rain.
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_weather_impact_summary;
CREATE VIEW vw_weather_impact_summary AS
SELECT
    team,
    rain,
    COUNT(*)                                                AS entries,
    ROUND(AVG(position), 2)                                 AS avg_finish_pos,
    SUM(CASE WHEN position <= 3 THEN 1 ELSE 0 END)         AS podiums,
    SUM(dnf)                                                AS dnfs
FROM race_results
WHERE position IS NOT NULL
GROUP BY team, rain
ORDER BY rain DESC, avg_finish_pos;


-- ------------------------------------------------------------
-- vw_rain_race_upsets
-- Races where the pole-sitter did NOT win,
-- grouped by weather condition.
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_rain_race_upsets;
CREATE VIEW vw_rain_race_upsets AS
SELECT
    pole.year,
    pole.raceId,
    pole.track,
    pole.rain,
    pole.sunny,
    dp.driver_name                                          AS pole_driver,
    dp_team.team                                            AS pole_team,
    dw.driver_name                                          AS winner_driver,
    dw_team.team                                            AS winner_team
FROM race_results pole
JOIN race_results winner
    ON  winner.raceId    = pole.raceId
    AND winner.position  = 1
JOIN drivers dp      ON dp.kaggle_driver_id      = pole.kaggle_driver_id
JOIN drivers dw      ON dw.kaggle_driver_id      = winner.kaggle_driver_id
-- get current team from race_results for display
JOIN (SELECT DISTINCT kaggle_driver_id, team FROM race_results) dp_team
    ON dp_team.kaggle_driver_id = pole.kaggle_driver_id
JOIN (SELECT DISTINCT kaggle_driver_id, team FROM race_results) dw_team
    ON dw_team.kaggle_driver_id = winner.kaggle_driver_id
WHERE pole.starting_grid = 1
  AND pole.rain = 1                                         -- only wet race upsets
  AND pole.kaggle_driver_id != winner.kaggle_driver_id
GROUP BY pole.raceId
ORDER BY pole.year, pole.raceId;


-- ------------------------------------------------------------
-- vw_driver_wet_vs_dry
-- Per driver: avg finish in rain vs dry races.
-- Only drivers with 3+ wet race appearances included.
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_driver_wet_vs_dry;
CREATE VIEW vw_driver_wet_vs_dry AS
SELECT
    rr.kaggle_driver_id,
    d.driver_name,
    SUM(CASE WHEN rr.rain = 1 THEN 1 ELSE 0 END)           AS wet_races,
    ROUND(AVG(CASE WHEN rr.rain = 1 THEN rr.position END), 2) AS avg_pos_wet,
    SUM(CASE WHEN rr.rain = 0 THEN 1 ELSE 0 END)           AS dry_races,
    ROUND(AVG(CASE WHEN rr.rain = 0 THEN rr.position END), 2) AS avg_pos_dry,
    ROUND(
        AVG(CASE WHEN rr.rain = 0 THEN rr.position END) -
        AVG(CASE WHEN rr.rain = 1 THEN rr.position END),
    2)                                                      AS dry_minus_wet
FROM race_results rr
LEFT JOIN drivers d ON d.kaggle_driver_id = rr.kaggle_driver_id
WHERE rr.position IS NOT NULL
GROUP BY rr.kaggle_driver_id, d.driver_name
HAVING wet_races >= 3
ORDER BY dry_minus_wet DESC;


-- ------------------------------------------------------------
-- vw_model_predictions
-- Stub view — populated once the XGBoost model produces
-- predictions/predictions_output.csv loaded into a
-- predictions table. Returns empty until then.
-- Replace this with actual predictions table query after
-- the model is run.
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_model_predictions;
CREATE VIEW vw_model_predictions AS
SELECT
    NULL AS raceId,
    NULL AS year,
    NULL AS track,
    NULL AS kaggle_driver_id,
    NULL AS driver_name,
    NULL AS team,
    NULL AS predicted_rank,
    NULL AS actual_position,
    NULL AS prediction_error
WHERE 1 = 0;   -- empty until predictions table exists
