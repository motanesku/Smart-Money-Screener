-- ============================================================
-- RESET COMPLET v10 + REBUILD
-- Rulează în Supabase SQL Editor
-- Include toate coloanele din Enricher v3 + AI Thesis
-- ============================================================

DROP VIEW  IF EXISTS enriched_view          CASCADE;
DROP VIEW  IF EXISTS v_persistence_signals  CASCADE;
DROP VIEW  IF EXISTS v_sector_heat          CASCADE;
DROP TABLE IF EXISTS enriched               CASCADE;
DROP TABLE IF EXISTS scan_results           CASCADE;
DROP TABLE IF EXISTS universe               CASCADE;
DROP TABLE IF EXISTS watchlist              CASCADE;

CREATE TABLE universe (
    ticker          TEXT PRIMARY KEY,
    company_name    TEXT    NOT NULL DEFAULT '',
    exchange        TEXT    NOT NULL DEFAULT '',
    sector          TEXT    NOT NULL DEFAULT '',
    industry        TEXT    NOT NULL DEFAULT '',
    market_cap      BIGINT  NOT NULL DEFAULT 0,
    avg_volume      BIGINT  NOT NULL DEFAULT 0,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE scan_results (
    id              BIGSERIAL PRIMARY KEY,
    scan_date       DATE    NOT NULL,
    ticker          TEXT    NOT NULL,
    price           NUMERIC(12,4),
    volume          BIGINT  DEFAULT 0,
    avg_volume_20d  BIGINT  DEFAULT 0,
    vol_ratio       NUMERIC(10,4),
    rs_vs_sector    FLOAT,
    sector_heat_score INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(scan_date, ticker)
);

CREATE TABLE enriched (
    id                      BIGSERIAL PRIMARY KEY,
    enrich_date             DATE          NOT NULL,
    ticker                  TEXT          NOT NULL,

    -- Companie
    company_name            TEXT          NOT NULL DEFAULT '',
    sector                  TEXT          NOT NULL DEFAULT '',
    industry                TEXT          NOT NULL DEFAULT '',
    market_cap              BIGINT        NOT NULL DEFAULT 0,

    -- Volume data
    price                   NUMERIC(12,4),
    volume                  BIGINT        DEFAULT 0,
    avg_volume_20d          BIGINT        DEFAULT 0,
    vol_ratio               NUMERIC(10,4),

    -- Sector context (din scanner)
    rs_vs_sector            FLOAT,
    sector_heat_score       INTEGER       DEFAULT 0,

    -- Insider (Form 4 real — buy vs sell distinct)
    insider_buys_90d        INTEGER       NOT NULL DEFAULT 0,
    insider_buy_value       NUMERIC(18,2) NOT NULL DEFAULT 0,
    insider_sells_90d       INTEGER       NOT NULL DEFAULT 0,
    insider_sell_value      NUMERIC(18,2) NOT NULL DEFAULT 0,
    top_insider_role        TEXT          NOT NULL DEFAULT '',
    net_insider_signal      TEXT          NOT NULL DEFAULT '',   -- ACCUMULATION/DISTRIBUTION/MIXED/NEUTRAL
    is_10b5_plan            BOOLEAN       NOT NULL DEFAULT FALSE,
    insider_quality_score   INTEGER       NOT NULL DEFAULT 0,

    -- Institutional
    inst_ownership_pct      NUMERIC(8,4),

    -- Ownership 13D/13G
    ownership_form          TEXT          NOT NULL DEFAULT '',
    ownership_holder        TEXT          NOT NULL DEFAULT '',
    ownership_pct           NUMERIC(8,4),
    ownership_signal        TEXT          NOT NULL DEFAULT '',
    ownership_signal_text   TEXT          NOT NULL DEFAULT '',

    -- Short (FINRA real)
    short_interest_pct      NUMERIC(8,4),
    short_sale_volume       BIGINT        DEFAULT 0,
    total_volume_reported   BIGINT        DEFAULT 0,
    short_sale_ratio        NUMERIC(8,4),
    avg_short_ratio_5d      FLOAT,
    squeeze_setup           BOOLEAN       NOT NULL DEFAULT FALSE,
    short_flow_signal       TEXT          NOT NULL DEFAULT '',
    short_signal            TEXT          NOT NULL DEFAULT '',
    short_squeeze_signal    TEXT          NOT NULL DEFAULT '',

    -- Accumulation pattern
    sideways_signal         TEXT          NOT NULL DEFAULT '',

    -- Fundamentals
    pe_ratio                NUMERIC(10,4),
    beta                    NUMERIC(8,4),

    -- Scoruri: Volume(40) + Insider(30) + Persistence(20) + Short(30) + Sideways(15) - Penalty
    score                   INTEGER       NOT NULL DEFAULT 0,
    score_volume            INTEGER       NOT NULL DEFAULT 0,
    score_insider           INTEGER       NOT NULL DEFAULT 0,
    score_insider_quality   INTEGER       NOT NULL DEFAULT 0,
    score_ownership         INTEGER       NOT NULL DEFAULT 0,
    score_short_interest    INTEGER       NOT NULL DEFAULT 0,
    score_short_flow        INTEGER       NOT NULL DEFAULT 0,
    score_fundamental       INTEGER       NOT NULL DEFAULT 0,
    score_penalty           INTEGER       NOT NULL DEFAULT 0,

    -- Semnale text
    volume_signal           TEXT          NOT NULL DEFAULT '',
    insider_signal          TEXT          NOT NULL DEFAULT '',
    short_signal_text       TEXT          NOT NULL DEFAULT '',
    thesis                  TEXT          NOT NULL DEFAULT '',

    -- AI Analysis (Claude Haiku — generată dacă score >= 60)
    ai_thesis_ro            TEXT          NOT NULL DEFAULT '',

    created_at              TIMESTAMPTZ   DEFAULT NOW(),
    UNIQUE(enrich_date, ticker)
);

CREATE TABLE watchlist (
    ticker      TEXT PRIMARY KEY,
    added_at    TIMESTAMPTZ DEFAULT NOW(),
    notes       TEXT NOT NULL DEFAULT ''
);

-- ── Indexes ──────────────────────────────────────────────────────────────────

CREATE INDEX idx_scan_date            ON scan_results(scan_date DESC);
CREATE INDEX idx_scan_ticker_date     ON scan_results(ticker, scan_date DESC);
CREATE INDEX idx_enriched_date        ON enriched(enrich_date DESC);
CREATE INDEX idx_enriched_score       ON enriched(score DESC);
CREATE INDEX idx_enriched_ticker      ON enriched(ticker, enrich_date DESC);
CREATE INDEX idx_enriched_sector      ON enriched(sector);
CREATE INDEX idx_enriched_ai          ON enriched(ai_thesis_ro) WHERE ai_thesis_ro != '';

-- ── Views ─────────────────────────────────────────────────────────────────────

-- Whale Persistence: câte zile a apărut un ticker în ultimele 21 zile
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

-- Sector Heat: sectoare cu tickers active (agregare zilnică)
CREATE OR REPLACE VIEW v_sector_heat AS
SELECT
    COALESCE(NULLIF(e.sector,''), u.sector, 'Unknown') AS sector,
    COUNT(DISTINCT e.ticker)                            AS ticker_count,
    ROUND(AVG(e.vol_ratio)::numeric, 2)                AS avg_vol_ratio,
    ROUND(AVG(e.score)::numeric, 1)                    AS avg_score,
    MAX(e.enrich_date)                                  AS last_seen,
    COUNT(DISTINCT e.ticker) >= 5                       AS in_play
FROM enriched e
LEFT JOIN universe u ON u.ticker = e.ticker
WHERE e.enrich_date >= CURRENT_DATE - INTERVAL '1 day'
  AND (e.sector != '' OR u.sector IS NOT NULL)
GROUP BY 1
ORDER BY ticker_count DESC;

-- Enriched view: cel mai recent record per ticker + persistence + sector context
CREATE OR REPLACE VIEW enriched_view AS
SELECT DISTINCT ON (e.ticker)
    e.*,
    COALESCE(NULLIF(e.company_name, ''), u.company_name, '') AS company_name_display,
    COALESCE(p.appearance_days, 0)                           AS persistence_days,
    COALESCE(p.is_persistent, FALSE)                         AS is_persistent,
    COALESCE(sh.ticker_count, 0)                             AS sector_heat,
    COALESCE(sh.in_play, FALSE)                              AS sector_in_play
FROM enriched e
LEFT JOIN universe u              ON u.ticker  = e.ticker
LEFT JOIN v_persistence_signals p ON p.ticker  = e.ticker
LEFT JOIN v_sector_heat sh        ON sh.sector = COALESCE(NULLIF(e.sector,''), u.sector)
ORDER BY e.ticker, e.enrich_date DESC, e.id DESC;

-- ── Disable RLS ───────────────────────────────────────────────────────────────

ALTER TABLE universe     DISABLE ROW LEVEL SECURITY;
ALTER TABLE scan_results DISABLE ROW LEVEL SECURITY;
ALTER TABLE enriched     DISABLE ROW LEVEL SECURITY;
ALTER TABLE watchlist    DISABLE ROW LEVEL SECURITY;

-- ── Verificare ────────────────────────────────────────────────────────────────

SELECT 'universe'     AS tbl, COUNT(*) FROM universe
UNION ALL
SELECT 'scan_results' AS tbl, COUNT(*) FROM scan_results
UNION ALL
SELECT 'enriched'     AS tbl, COUNT(*) FROM enriched
UNION ALL
SELECT 'watchlist'    AS tbl, COUNT(*) FROM watchlist;
