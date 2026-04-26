-- Migration v5: Sector Heat Score + Persistence + coloane noi scan_results
-- Rulează în Supabase SQL Editor după migration_v4

-- 1. Coloane noi în scan_results (pentru Sector Heat Score și RS)
ALTER TABLE scan_results ADD COLUMN IF NOT EXISTS rs_vs_sector      FLOAT;
ALTER TABLE scan_results ADD COLUMN IF NOT EXISTS sector_heat_score INTEGER DEFAULT 0;

-- 2. Coloane noi în enriched (fix score_fundamental era mereu 0)
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS score_fundamental    INTEGER DEFAULT 0;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS beta                 FLOAT;

-- 3. View pentru Sector Heat (agregare zilnică)
CREATE OR REPLACE VIEW v_sector_heat AS
SELECT
    u.sector,
    COUNT(DISTINCT s.ticker)          AS ticker_count,
    ROUND(AVG(s.vol_ratio)::numeric, 2) AS avg_vol_ratio,
    MAX(s.scan_date)                  AS last_seen,
    COUNT(DISTINCT s.ticker) >= 5     AS in_play
FROM scan_results s
JOIN universe u ON u.ticker = s.ticker
WHERE s.scan_date >= CURRENT_DATE - INTERVAL '1 day'
  AND u.sector IS NOT NULL
  AND u.sector != ''
GROUP BY u.sector
ORDER BY ticker_count DESC;

-- 4. View pentru Whale Persistence (fereastra 21 zile)
CREATE OR REPLACE VIEW v_persistence_signals AS
SELECT
    ticker,
    COUNT(DISTINCT scan_date)                    AS appearance_days,
    MIN(scan_date)                               AS first_seen,
    MAX(scan_date)                               AS last_seen,
    ROUND(AVG(vol_ratio)::numeric, 2)            AS avg_vol_ratio,
    COUNT(DISTINCT scan_date) >= 3               AS is_persistent
FROM scan_results
WHERE scan_date >= CURRENT_DATE - INTERVAL '21 days'
GROUP BY ticker
HAVING COUNT(DISTINCT scan_date) >= 2
ORDER BY appearance_days DESC;

-- 5. View enriched îmbunătățit cu persistence + sector heat
CREATE OR REPLACE VIEW enriched_view AS
SELECT
    e.*,
    COALESCE(NULLIF(e.company_name, ''), u.company_name, '')  AS company_name_display,
    u.sector                                                   AS universe_sector,
    COALESCE(p.appearance_days, 0)                            AS persistence_days,
    COALESCE(p.is_persistent, FALSE)                          AS is_persistent,
    COALESCE(sh.ticker_count, 0)                              AS sector_heat,
    COALESCE(sh.in_play, FALSE)                               AS sector_in_play
FROM enriched e
LEFT JOIN universe u          ON u.ticker  = e.ticker
LEFT JOIN v_persistence_signals p ON p.ticker = e.ticker
LEFT JOIN v_sector_heat sh    ON sh.sector = COALESCE(NULLIF(e.sector,''), u.sector);

-- Verificare
-- SELECT sector, ticker_count, avg_vol_ratio, in_play FROM v_sector_heat LIMIT 10;
-- SELECT ticker, appearance_days, is_persistent FROM v_persistence_signals LIMIT 10;
