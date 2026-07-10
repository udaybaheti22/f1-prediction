-- ============================================================
-- F1 SQL Analytics Pipeline — Analytical Views (PostgreSQL)
-- ============================================================
-- PostgreSQL-specific version:
--   - ROUND uses NUMERIC cast: ROUND(CAST(x AS NUMERIC), n)
--   - HAVING uses full expressions, not aliases
--   - GROUP BY includes all non-aggregate SELECT columns
--   - CREATE OR REPLACE VIEW instead of DROP+CREATE
-- ============================================================


-- ============================================================
-- PAGE 1 — RACE RESULTS BROWSER
-- ============================================================

CREATE OR REPLACE VIEW vw_race_results_browser AS
SELECT
    rr.year,
    r.round,
    rr.raceid,
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
    ON  qr.raceid           = rr.raceid
    AND qr.kaggle_driver_id = rr.kaggle_driver_id
LEFT JOIN drivers d
    ON  d.kaggle_driver_id  = rr.kaggle_driver_id
LEFT JOIN races r
    ON  r.raceid            = rr.raceid
ORDER BY rr.year, r.round, rr.raceid, rr.position;


-- ============================================================
-- PAGE 2 — SEASON OVERVIEW
-- ============================================================

CREATE OR REPLACE VIEW vw_team_season_stats AS
SELECT
    rr.year,
    rr.team,
    COUNT(*)                                                AS total_entries,
    COUNT(DISTINCT rr.raceid)                               AS races_entered,
    ROUND(CAST(AVG(rr.position) AS NUMERIC), 2)             AS avg_finish_pos,
    ROUND(CAST(AVG(qr.position) AS NUMERIC), 2)             AS avg_quali_pos,
    SUM(CASE WHEN rr.position = 1  THEN 1 ELSE 0 END)       AS wins,
    SUM(CASE WHEN rr.position <= 3 THEN 1 ELSE 0 END)       AS podiums,
    SUM(rr.dnf)                                             AS dnf_count,
    SUM(CASE WHEN rr.finished = 1  THEN 1 ELSE 0 END)       AS finishes
FROM race_results rr
LEFT JOIN qualifying_results qr
    ON  qr.raceid           = rr.raceid
    AND qr.kaggle_driver_id = rr.kaggle_driver_id
GROUP BY rr.year, rr.team
ORDER BY rr.year, ROUND(CAST(AVG(rr.position) AS NUMERIC), 2);


CREATE OR REPLACE VIEW vw_team_points_trend AS
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


CREATE OR REPLACE VIEW vw_team_points_by_round AS
SELECT
    rr.year,
    r.round,
    rr.raceid,
    rr.track,
    rr.team,
    SUM(
        CASE rr.position
            WHEN 1  THEN 25 WHEN 2  THEN 18 WHEN 3  THEN 15
            WHEN 4  THEN 12 WHEN 5  THEN 10 WHEN 6  THEN 8
            WHEN 7  THEN 6  WHEN 8  THEN 4  WHEN 9  THEN 2
            WHEN 10 THEN 1  ELSE 0
        END
    )                                                       AS round_points,
    (
        SELECT SUM(
            CASE r2.position
                WHEN 1  THEN 25 WHEN 2  THEN 18 WHEN 3  THEN 15
                WHEN 4  THEN 12 WHEN 5  THEN 10 WHEN 6  THEN 8
                WHEN 7  THEN 6  WHEN 8  THEN 4  WHEN 9  THEN 2
                WHEN 10 THEN 1  ELSE 0
            END)
        FROM race_results r2
        JOIN races ra2 ON ra2.raceid = r2.raceid
        WHERE r2.year  = rr.year
          AND r2.team  = rr.team
          AND ra2.round <= r.round
          AND r2.position IS NOT NULL
    )                                                       AS cumulative_points
FROM race_results rr
JOIN races r ON r.raceid = rr.raceid
WHERE rr.position IS NOT NULL
  AND r.round     IS NOT NULL
GROUP BY rr.year, r.round, rr.raceid, rr.track, rr.team
ORDER BY rr.year, r.round, cumulative_points DESC;


CREATE OR REPLACE VIEW vw_teammate_comparison AS
SELECT
    a.year,
    a.raceid,
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
        THEN ROUND(CAST(qa.q3_time_sec - qb.q3_time_sec AS NUMERIC), 3)
        ELSE NULL
    END                         AS q3_gap_sec
FROM race_results a
JOIN race_results b
    ON  a.raceid = b.raceid
    AND a.team   = b.team
    AND a.kaggle_driver_id < b.kaggle_driver_id
LEFT JOIN qualifying_results qa
    ON  qa.raceid = a.raceid AND qa.kaggle_driver_id = a.kaggle_driver_id
LEFT JOIN qualifying_results qb
    ON  qb.raceid = b.raceid AND qb.kaggle_driver_id = b.kaggle_driver_id
LEFT JOIN drivers da ON da.kaggle_driver_id = a.kaggle_driver_id
LEFT JOIN drivers db ON db.kaggle_driver_id = b.kaggle_driver_id
ORDER BY a.year, a.raceid, a.team;


-- ============================================================
-- PAGE 3 — DRIVER ANALYSIS
-- ============================================================

CREATE OR REPLACE VIEW vw_driver_season_stats AS
SELECT
    rr.year,
    rr.kaggle_driver_id,
    MAX(d.driver_name)                                      AS driver_name,
    rr.team,
    COUNT(DISTINCT rr.raceid)                               AS races_entered,
    ROUND(CAST(AVG(rr.position) AS NUMERIC), 2)             AS avg_finish_pos,
    ROUND(CAST(AVG(qr.position) AS NUMERIC), 2)             AS avg_quali_pos,
    MIN(rr.position)                                        AS best_finish,
    SUM(CASE WHEN rr.position = 1  THEN 1 ELSE 0 END)      AS wins,
    SUM(CASE WHEN rr.position <= 3 THEN 1 ELSE 0 END)      AS podiums,
    SUM(rr.dnf)                                             AS dnf_count
FROM race_results rr
LEFT JOIN qualifying_results qr
    ON  qr.raceid           = rr.raceid
    AND qr.kaggle_driver_id = rr.kaggle_driver_id
LEFT JOIN drivers d ON d.kaggle_driver_id = rr.kaggle_driver_id
GROUP BY rr.year, rr.kaggle_driver_id, rr.team
ORDER BY rr.year, avg_finish_pos;


CREATE OR REPLACE VIEW vw_driver_quali_race_avg AS
SELECT
    rr.kaggle_driver_id,
    MAX(d.driver_name)                                      AS driver_name,
    COUNT(*)                                                AS races_with_both,
    ROUND(CAST(AVG(qr.position) AS NUMERIC), 2)             AS avg_quali_pos,
    ROUND(CAST(AVG(rr.position) AS NUMERIC), 2)             AS avg_race_pos,
    ROUND(CAST(AVG(qr.position - rr.position) AS NUMERIC), 3) AS avg_delta
FROM race_results rr
JOIN qualifying_results qr
    ON  qr.raceid           = rr.raceid
    AND qr.kaggle_driver_id = rr.kaggle_driver_id
LEFT JOIN drivers d ON d.kaggle_driver_id = rr.kaggle_driver_id
WHERE rr.position  IS NOT NULL
  AND qr.position  IS NOT NULL
GROUP BY rr.kaggle_driver_id
HAVING COUNT(*) >= 5
ORDER BY avg_race_pos;


CREATE OR REPLACE VIEW vw_quali_conversion_rate AS
SELECT
    rr.kaggle_driver_id,
    MAX(d.driver_name)                                      AS driver_name,
    COUNT(*)                                                AS top10_starts,
    SUM(CASE WHEN rr.position <= 10 THEN 1 ELSE 0 END)     AS top10_finishes,
    ROUND(
        CAST(100.0 * SUM(CASE WHEN rr.position <= 10 THEN 1 ELSE 0 END)
        / COUNT(*) AS NUMERIC), 1
    )                                                       AS conversion_pct
FROM race_results rr
JOIN qualifying_results qr
    ON  qr.raceid           = rr.raceid
    AND qr.kaggle_driver_id = rr.kaggle_driver_id
LEFT JOIN drivers d ON d.kaggle_driver_id = rr.kaggle_driver_id
WHERE qr.position  <= 10
  AND rr.position  IS NOT NULL
GROUP BY rr.kaggle_driver_id
HAVING COUNT(*) >= 5
ORDER BY conversion_pct DESC;


-- ============================================================
-- PAGE 4 — CIRCUIT INSIGHTS
-- ============================================================

CREATE OR REPLACE VIEW vw_circuit_stats AS
SELECT
    track,
    COUNT(DISTINCT raceid)                                  AS race_count,
    COUNT(*)                                                AS total_entries,
    SUM(dnf)                                                AS total_dnfs,
    ROUND(CAST(SUM(dnf) AS NUMERIC) / COUNT(*), 4)          AS dnf_rate,
    ROUND(CAST(AVG(position) AS NUMERIC), 2)                AS avg_finish_pos,
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


CREATE OR REPLACE VIEW vw_circuit_dnf_rate AS
SELECT
    year,
    track,
    COUNT(*)                                                AS total_entries,
    SUM(dnf)                                                AS total_dnfs,
    ROUND(CAST(SUM(dnf) AS NUMERIC) / COUNT(*), 4)          AS dnf_rate
FROM race_results
GROUP BY year, track
ORDER BY dnf_rate DESC, year, track;


CREATE OR REPLACE VIEW vw_circuit_dominant_teams AS
SELECT
    track,
    team,
    COUNT(*)                                                AS entries,
    ROUND(CAST(AVG(position) AS NUMERIC), 2)                AS avg_finish_pos,
    SUM(CASE WHEN position = 1  THEN 1 ELSE 0 END)         AS wins,
    SUM(CASE WHEN position <= 3 THEN 1 ELSE 0 END)         AS podiums,
    SUM(dnf)                                                AS dnfs
FROM race_results
WHERE position IS NOT NULL
GROUP BY track, team
HAVING COUNT(*) >= 3
ORDER BY track, avg_finish_pos;


-- ============================================================
-- PAGE 5 — WEATHER & MODEL RESULTS
-- ============================================================

CREATE OR REPLACE VIEW vw_weather_impact_summary AS
SELECT
    team,
    rain,
    COUNT(*)                                                AS entries,
    ROUND(CAST(AVG(position) AS NUMERIC), 2)                AS avg_finish_pos,
    SUM(CASE WHEN position <= 3 THEN 1 ELSE 0 END)         AS podiums,
    SUM(dnf)                                                AS dnfs
FROM race_results
WHERE position IS NOT NULL
GROUP BY team, rain
ORDER BY rain DESC, avg_finish_pos;


CREATE OR REPLACE VIEW vw_rain_race_upsets AS
SELECT
    pole.year,
    pole.raceid,
    pole.track,
    pole.rain,
    pole.sunny,
    dp.driver_name                                          AS pole_driver,
    dp_team.team                                            AS pole_team,
    dw.driver_name                                          AS winner_driver,
    dw_team.team                                            AS winner_team
FROM race_results pole
JOIN race_results winner
    ON  winner.raceid    = pole.raceid
    AND winner.position  = 1
JOIN drivers dp      ON dp.kaggle_driver_id      = pole.kaggle_driver_id
JOIN drivers dw      ON dw.kaggle_driver_id      = winner.kaggle_driver_id
JOIN (SELECT DISTINCT kaggle_driver_id, team FROM race_results) dp_team
    ON dp_team.kaggle_driver_id = pole.kaggle_driver_id
JOIN (SELECT DISTINCT kaggle_driver_id, team FROM race_results) dw_team
    ON dw_team.kaggle_driver_id = winner.kaggle_driver_id
WHERE pole.starting_grid = 1
  AND pole.rain = 1
  AND pole.kaggle_driver_id != winner.kaggle_driver_id
GROUP BY pole.year, pole.raceid, pole.track, pole.rain, pole.sunny,
         dp.driver_name, dp_team.team, dw.driver_name, dw_team.team
ORDER BY pole.year, pole.raceid;


CREATE OR REPLACE VIEW vw_driver_wet_vs_dry AS
SELECT
    rr.kaggle_driver_id,
    MAX(d.driver_name)                                              AS driver_name,
    SUM(CASE WHEN rr.rain = 1 THEN 1 ELSE 0 END)                   AS wet_races,
    ROUND(CAST(AVG(CASE WHEN rr.rain = 1 THEN rr.position END) AS NUMERIC), 2) AS avg_pos_wet,
    SUM(CASE WHEN rr.rain = 0 THEN 1 ELSE 0 END)                   AS dry_races,
    ROUND(CAST(AVG(CASE WHEN rr.rain = 0 THEN rr.position END) AS NUMERIC), 2) AS avg_pos_dry,
    ROUND(CAST(
        AVG(CASE WHEN rr.rain = 0 THEN rr.position END) -
        AVG(CASE WHEN rr.rain = 1 THEN rr.position END)
    AS NUMERIC), 2)                                                 AS dry_minus_wet
FROM race_results rr
LEFT JOIN drivers d ON d.kaggle_driver_id = rr.kaggle_driver_id
WHERE rr.position IS NOT NULL
GROUP BY rr.kaggle_driver_id
HAVING SUM(CASE WHEN rr.rain = 1 THEN 1 ELSE 0 END) >= 3
ORDER BY dry_minus_wet DESC;


CREATE OR REPLACE VIEW vw_model_predictions AS
SELECT
    NULL::INTEGER           AS raceid,
    NULL::INTEGER           AS year,
    NULL::TEXT              AS track,
    NULL::INTEGER           AS kaggle_driver_id,
    NULL::TEXT              AS driver_name,
    NULL::TEXT              AS team,
    NULL::INTEGER           AS predicted_rank,
    NULL::INTEGER           AS actual_position,
    NULL::DOUBLE PRECISION  AS prediction_error
WHERE 1 = 0;
