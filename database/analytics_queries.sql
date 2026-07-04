-- ============================================================
-- F1 SQL Analytics Pipeline — Analytical Views
-- Power BI pages:
--   Page 1 — Season Overview
--   Page 2 — Driver Analysis
--   Page 3 — Circuit Insights
--   Page 4 — Weather & Upsets
--   Page 5 — Race Prediction Scores (uses predictions CSV)
--
-- Re-runnable: every view is dropped and recreated.
-- No view references another view (Power BI compatibility).
-- ============================================================


-- ============================================================
-- PAGE 1 — SEASON OVERVIEW
-- ============================================================

-- ------------------------------------------------------------
-- vw_team_points_trend
-- Championship points per team per season.
-- F1 points scale: 1→25, 2→18, 3→15, 4→12, 5→10,
--                  6→8,  7→6,  8→4,  9→2,  10→1
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_team_points_trend;
CREATE VIEW vw_team_points_trend AS
SELECT
    year,
    team,
    SUM(
        CASE position
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
        END
    ) AS total_points,
    COUNT(*)                                        AS total_entries,
    SUM(CASE WHEN position = 1 THEN 1 ELSE 0 END)  AS wins
FROM race_results
WHERE position IS NOT NULL
GROUP BY year, team
ORDER BY year, total_points DESC;


-- ------------------------------------------------------------
-- vw_team_season_stats
-- Per team per season: races, avg finish, avg quali,
-- DNF count, podium count.
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_team_season_stats;
CREATE VIEW vw_team_season_stats AS
SELECT
    rr.year,
    rr.team,
    COUNT(DISTINCT rr.raceId)                              AS races_entered,
    ROUND(AVG(rr.position), 2)                             AS avg_finish_pos,
    ROUND(AVG(qr.position), 2)                             AS avg_quali_pos,
    SUM(rr.dnf)                                            AS dnf_count,
    SUM(CASE WHEN rr.position <= 3 THEN 1 ELSE 0 END)      AS podium_count,
    SUM(CASE WHEN rr.position = 1  THEN 1 ELSE 0 END)      AS win_count
FROM race_results rr
LEFT JOIN qualifying_results qr
    ON rr.raceId           = qr.raceId
   AND rr.kaggle_driver_id = qr.kaggle_driver_id
GROUP BY rr.year, rr.team
ORDER BY rr.year, avg_finish_pos;


-- ------------------------------------------------------------
-- vw_teammate_comparison
-- Head-to-head within each team per race:
-- both drivers' qualifying and race positions, Q3 time gap.
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_teammate_comparison;
CREATE VIEW vw_teammate_comparison AS
SELECT
    a.year,
    a.raceId,
    a.track,
    a.team,
    a.kaggle_driver_id  AS driver1_id,
    da.driver_name      AS driver1_name,
    qa.position         AS driver1_quali_pos,
    a.position          AS driver1_race_pos,
    qa.q3_time_sec      AS driver1_q3_time,
    b.kaggle_driver_id  AS driver2_id,
    db.driver_name      AS driver2_name,
    qb.position         AS driver2_quali_pos,
    b.position          AS driver2_race_pos,
    qb.q3_time_sec      AS driver2_q3_time,
    CASE
        WHEN qa.q3_time_sec IS NOT NULL AND qb.q3_time_sec IS NOT NULL
        THEN ROUND(qa.q3_time_sec - qb.q3_time_sec, 3)
        ELSE NULL
    END AS q3_gap_sec   -- negative = driver1 faster
FROM race_results a
JOIN race_results b
    ON  a.raceId = b.raceId
    AND a.team   = b.team
    AND a.kaggle_driver_id < b.kaggle_driver_id   -- one row per pair
LEFT JOIN qualifying_results qa
    ON  qa.raceId           = a.raceId
    AND qa.kaggle_driver_id = a.kaggle_driver_id
LEFT JOIN qualifying_results qb
    ON  qb.raceId           = b.raceId
    AND qb.kaggle_driver_id = b.kaggle_driver_id
LEFT JOIN drivers da ON da.kaggle_driver_id = a.kaggle_driver_id
LEFT JOIN drivers db ON db.kaggle_driver_id = b.kaggle_driver_id
ORDER BY a.year, a.raceId, a.team;


-- ============================================================
-- PAGE 2 — DRIVER ANALYSIS
-- ============================================================

-- ------------------------------------------------------------
-- vw_driver_season_stats
-- Per driver per season: races, avg finish, avg quali,
-- DNF count, best finish, podium count.
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_driver_season_stats;
CREATE VIEW vw_driver_season_stats AS
SELECT
    rr.year,
    rr.kaggle_driver_id,
    d.driver_name,
    rr.team,
    COUNT(DISTINCT rr.raceId)                              AS races_entered,
    ROUND(AVG(rr.position), 2)                             AS avg_finish_pos,
    ROUND(AVG(qr.position), 2)                             AS avg_quali_pos,
    MIN(rr.position)                                       AS best_finish,
    SUM(rr.dnf)                                            AS dnf_count,
    SUM(CASE WHEN rr.position <= 3 THEN 1 ELSE 0 END)      AS podium_count,
    SUM(CASE WHEN rr.position = 1  THEN 1 ELSE 0 END)      AS win_count
FROM race_results rr
LEFT JOIN qualifying_results qr
    ON  rr.raceId           = qr.raceId
    AND rr.kaggle_driver_id = qr.kaggle_driver_id
LEFT JOIN drivers d ON d.kaggle_driver_id = rr.kaggle_driver_id
GROUP BY rr.year, rr.kaggle_driver_id, rr.team
ORDER BY rr.year, avg_finish_pos;


-- ------------------------------------------------------------
-- vw_quali_race_delta
-- Per driver per race: positions gained/lost from grid.
-- Positive = improved (started 5th, finished 3rd → delta +2).
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_quali_race_delta;
CREATE VIEW vw_quali_race_delta AS
SELECT
    rr.raceId,
    rr.year,
    rr.track,
    rr.kaggle_driver_id,
    d.driver_name,
    rr.team,
    qr.position                        AS quali_pos,
    rr.position                        AS race_pos,
    (qr.position - rr.position)        AS delta,   -- positive = gained places
    rr.rain,
    rr.sunny
FROM race_results rr
JOIN qualifying_results qr
    ON  rr.raceId           = qr.raceId
    AND rr.kaggle_driver_id = qr.kaggle_driver_id
LEFT JOIN drivers d ON d.kaggle_driver_id = rr.kaggle_driver_id
WHERE rr.position IS NOT NULL
  AND qr.position IS NOT NULL;


-- ------------------------------------------------------------
-- vw_driver_quali_race_avg
-- Career averages per driver across all seasons:
-- avg delta, avg qualifying pos, avg race pos.
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_driver_quali_race_avg;
CREATE VIEW vw_driver_quali_race_avg AS
SELECT
    kaggle_driver_id,
    driver_name,
    COUNT(*)                    AS races_with_both,
    ROUND(AVG(delta), 3)        AS avg_delta,
    ROUND(AVG(quali_pos), 2)    AS avg_quali_pos,
    ROUND(AVG(race_pos), 2)     AS avg_race_pos
FROM vw_quali_race_delta
GROUP BY kaggle_driver_id, driver_name
ORDER BY avg_race_pos;


-- ------------------------------------------------------------
-- vw_quali_conversion_rate
-- Per driver: % of top-10 starts that converted to top-10 finish.
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_quali_conversion_rate;
CREATE VIEW vw_quali_conversion_rate AS
SELECT
    rr.kaggle_driver_id,
    d.driver_name,
    COUNT(*)  AS top10_starts,
    SUM(CASE WHEN rr.position <= 10 THEN 1 ELSE 0 END)  AS top10_finishes,
    ROUND(
        100.0 * SUM(CASE WHEN rr.position <= 10 THEN 1 ELSE 0 END) / COUNT(*),
        1
    )  AS conversion_pct
FROM race_results rr
JOIN qualifying_results qr
    ON  rr.raceId           = qr.raceId
    AND rr.kaggle_driver_id = qr.kaggle_driver_id
LEFT JOIN drivers d ON d.kaggle_driver_id = rr.kaggle_driver_id
WHERE qr.position <= 10
  AND rr.position IS NOT NULL
GROUP BY rr.kaggle_driver_id, d.driver_name
HAVING top10_starts >= 5
ORDER BY conversion_pct DESC;


-- ============================================================
-- PAGE 3 — CIRCUIT INSIGHTS
-- ============================================================

-- ------------------------------------------------------------
-- vw_circuit_overtake_index
-- Per circuit: average positions gained from grid to finish.
-- Higher = more overtaking opportunity.
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_circuit_overtake_index;
CREATE VIEW vw_circuit_overtake_index AS
SELECT
    rr.track,
    COUNT(*)                                            AS total_entries,
    ROUND(AVG(rr.starting_grid - rr.position), 2)      AS overtake_index,
    COUNT(DISTINCT rr.raceId)                           AS race_count
FROM race_results rr
WHERE rr.position      IS NOT NULL
  AND rr.starting_grid IS NOT NULL
GROUP BY rr.track
ORDER BY overtake_index DESC;


-- ------------------------------------------------------------
-- vw_circuit_dnf_rate
-- Per circuit: DNF rate = DNFs / total entries.
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_circuit_dnf_rate;
CREATE VIEW vw_circuit_dnf_rate AS
SELECT
    track,
    COUNT(*)                                  AS total_entries,
    SUM(dnf)                                  AS total_dnfs,
    ROUND(CAST(SUM(dnf) AS REAL) / COUNT(*), 4) AS dnf_rate
FROM race_results
GROUP BY track
ORDER BY dnf_rate DESC;


-- ------------------------------------------------------------
-- vw_circuit_dominant_teams
-- Per circuit: top 3 teams ranked by average finishing position.
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_circuit_dominant_teams;
CREATE VIEW vw_circuit_dominant_teams AS
SELECT
    track,
    team,
    COUNT(*)                        AS entries,
    ROUND(AVG(position), 2)         AS avg_finish_pos,
    SUM(CASE WHEN position = 1 THEN 1 ELSE 0 END) AS wins
FROM race_results
WHERE position IS NOT NULL
GROUP BY track, team
HAVING entries >= 3
ORDER BY track, avg_finish_pos;


-- ============================================================
-- PAGE 4 — WEATHER & UPSETS
-- ============================================================

-- ------------------------------------------------------------
-- vw_weather_impact_summary
-- Per team: avg grid-to-finish delta in wet vs dry races.
-- Shows which teams benefit most (or suffer most) in rain.
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_weather_impact_summary;
CREATE VIEW vw_weather_impact_summary AS
SELECT
    rr.team,
    rr.rain,
    rr.sunny,
    COUNT(*)                                            AS entries,
    ROUND(AVG(rr.starting_grid - rr.position), 3)      AS avg_position_gain,
    ROUND(AVG(rr.position), 2)                          AS avg_finish_pos,
    SUM(rr.dnf)                                         AS dnf_count
FROM race_results rr
WHERE rr.position      IS NOT NULL
  AND rr.starting_grid IS NOT NULL
GROUP BY rr.team, rr.rain, rr.sunny
ORDER BY rr.rain DESC, avg_position_gain DESC;


-- ------------------------------------------------------------
-- vw_rain_race_upsets
-- Races where the pole-sitter did NOT win,
-- grouped by weather condition.
-- Quantifies how often rain reshuffles the winner.
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_rain_race_upsets;
CREATE VIEW vw_rain_race_upsets AS
SELECT
    rr.raceId,
    rr.year,
    rr.track,
    rr.rain,
    rr.sunny,
    pole.kaggle_driver_id   AS pole_driver_id,
    dp.driver_name          AS pole_driver_name,
    winner.kaggle_driver_id AS winner_driver_id,
    dw.driver_name          AS winner_driver_name
FROM race_results rr
-- pole sitter: race_results row where starting_grid = 1
JOIN race_results pole
    ON  pole.raceId        = rr.raceId
    AND pole.starting_grid = 1
-- race winner: race_results row where position = 1
JOIN race_results winner
    ON  winner.raceId    = rr.raceId
    AND winner.position  = 1
LEFT JOIN drivers dp ON dp.kaggle_driver_id = pole.kaggle_driver_id
LEFT JOIN drivers dw ON dw.kaggle_driver_id = winner.kaggle_driver_id
WHERE pole.kaggle_driver_id != winner.kaggle_driver_id  -- upset: pole didn't win
GROUP BY rr.raceId   -- one row per race
ORDER BY rr.year, rr.raceId;


-- ------------------------------------------------------------
-- vw_driver_wet_vs_dry
-- Per driver: avg finish in rain vs dry races.
-- Only includes drivers with 3+ wet race appearances.
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_driver_wet_vs_dry;
CREATE VIEW vw_driver_wet_vs_dry AS
SELECT
    rr.kaggle_driver_id,
    d.driver_name,
    SUM(CASE WHEN rr.rain = 1 THEN 1 ELSE 0 END)               AS wet_races,
    ROUND(AVG(CASE WHEN rr.rain = 1 THEN rr.position END), 2)   AS avg_pos_wet,
    SUM(CASE WHEN rr.rain = 0 THEN 1 ELSE 0 END)               AS dry_races,
    ROUND(AVG(CASE WHEN rr.rain = 0 THEN rr.position END), 2)   AS avg_pos_dry,
    ROUND(
        AVG(CASE WHEN rr.rain = 0 THEN rr.position END) -
        AVG(CASE WHEN rr.rain = 1 THEN rr.position END),
        2
    ) AS dry_minus_wet   -- positive = driver is relatively better in wet
FROM race_results rr
LEFT JOIN drivers d ON d.kaggle_driver_id = rr.kaggle_driver_id
WHERE rr.position IS NOT NULL
GROUP BY rr.kaggle_driver_id, d.driver_name
HAVING wet_races >= 3
ORDER BY dry_minus_wet DESC;


-- ------------------------------------------------------------
-- vw_driver_sprint_vs_race
-- Per driver: avg sprint position vs avg main race position
-- for seasons where sprint data exists (2021–2025).
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_driver_sprint_vs_race;
CREATE VIEW vw_driver_sprint_vs_race AS
SELECT
    rr.kaggle_driver_id,
    d.driver_name,
    COUNT(DISTINCT rr.raceId)           AS main_races,
    ROUND(AVG(rr.position), 2)          AS avg_main_race_pos,
    COUNT(DISTINCT sr.raceId)           AS sprint_races,
    ROUND(AVG(sr.position), 2)          AS avg_sprint_pos,
    ROUND(AVG(rr.position) - AVG(sr.position), 2) AS race_minus_sprint
    -- positive = performs relatively better in sprint than race
FROM race_results rr
JOIN sprint_results sr
    ON  sr.kaggle_driver_id = rr.kaggle_driver_id
    AND sr.year             = rr.year
LEFT JOIN drivers d ON d.kaggle_driver_id = rr.kaggle_driver_id
WHERE rr.year BETWEEN 2021 AND 2025
  AND rr.position IS NOT NULL
  AND sr.position IS NOT NULL
GROUP BY rr.kaggle_driver_id, d.driver_name
HAVING sprint_races >= 3
ORDER BY avg_sprint_pos;
