-- ============================================================
-- RESET COMPLET v9 + REBUILD
-- Rulează în Supabase SQL Editor
-- ============================================================

DROP VIEW  IF EXISTS enriched_view CASCADE;
DROP TABLE IF EXISTS enriched       CASCADE;
DROP TABLE IF EXISTS scan_results   CASCADE;
DROP TABLE IF EXISTS universe       CASCADE;
DROP TABLE IF EXISTS watchlist      CASCADE;

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
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(scan_date, ticker)
);

CREATE TABLE enriched (
    id                      BIGSERIAL PRIMARY KEY,
    enrich_date             DATE          NOT NULL,
    ticker                  TEXT          NOT NULL,
    company_name            TEXT          NOT NULL DEFAULT '',
    sector                  TEXT          NOT NULL DEFAULT '',
    industry                TEXT          NOT NULL DEFAULT '',
    market_cap              BIGINT        NOT NULL DEFAULT 0,
    price                   NUMERIC(12,4),
    volume                  BIGINT        DEFAULT 0,
    avg_volume_20d          BIGINT        DEFAULT 0,
    vol_ratio               NUMERIC(10,4),
    -- Insider (INFO ONLY, nu în scor)
    insider_buys_90d        INTEGER       NOT NULL DEFAULT 0,
    insider_buy_value       NUMERIC(18,2) NOT NULL DEFAULT 0,
    insider_sells_90d       INTEGER       NOT NULL DEFAULT 0,
    insider_sell_value      NUMERIC(18,2) NOT NULL DEFAULT 0,
    top_insider_role        TEXT          NOT NULL DEFAULT '',
    insider_quality_score   INTEGER       NOT NULL DEFAULT 0,
    -- Institutional
    inst_ownership_pct      NUMERIC(8,4),
    -- Ownership 13D/13G
    ownership_form          TEXT          NOT NULL DEFAULT '',
    ownership_holder        TEXT          NOT NULL DEFAULT '',
    ownership_pct           NUMERIC(8,4),
    ownership_signal        TEXT          NOT NULL DEFAULT '',
    ownership_signal_text   TEXT          NOT NULL DEFAULT '',
    -- Short
    short_interest_pct      NUMERIC(8,4),
    short_sale_volume       BIGINT        DEFAULT 0,
    total_volume_reported   BIGINT        DEFAULT 0,
    short_sale_ratio        NUMERIC(8,4),
    short_flow_signal       TEXT          NOT NULL DEFAULT '',
    -- Fundamentals
    pe_ratio                NUMERIC(10,4),
    beta                    NUMERIC(8,4),
    -- Score: Volume(40) + ShortFlow(25) + ShortInterest(20) + Ownership(15)
    score                   INTEGER       NOT NULL DEFAULT 0,
    score_volume            INTEGER       NOT NULL DEFAULT 0,
    score_insider           INTEGER       NOT NULL DEFAULT 0,
    score_insider_quality   INTEGER       NOT NULL DEFAULT 0,
    score_ownership         INTEGER       NOT NULL DEFAULT 0,
    score_short_interest    INTEGER       NOT NULL DEFAULT 0,
    score_short_flow        INTEGER       NOT NULL DEFAULT 0,
    score_fundamental       INTEGER       NOT NULL DEFAULT 0,
    score_penalty           INTEGER       NOT NULL DEFAULT 0,
    -- Signals
    volume_signal           TEXT          NOT NULL DEFAULT '',
    insider_signal          TEXT          NOT NULL DEFAULT '',
    short_signal            TEXT          NOT NULL DEFAULT '',
    thesis                  TEXT          NOT NULL DEFAULT '',
    created_at              TIMESTAMPTZ   DEFAULT NOW(),
    UNIQUE(enrich_date, ticker)
);

CREATE TABLE watchlist (
    ticker      TEXT PRIMARY KEY,
    added_at    TIMESTAMPTZ DEFAULT NOW(),
    notes       TEXT NOT NULL DEFAULT ''
);

-- Indexes
CREATE INDEX idx_scan_date       ON scan_results(scan_date DESC);
CREATE INDEX idx_enriched_date   ON enriched(enrich_date DESC);
CREATE INDEX idx_enriched_score  ON enriched(score DESC);
CREATE INDEX idx_enriched_ticker ON enriched(ticker, enrich_date DESC);

-- enriched_view: cel mai recent enrich per ticker (DISTINCT ON = deduplicare)
CREATE OR REPLACE VIEW enriched_view AS
SELECT DISTINCT ON (ticker) *
FROM enriched
ORDER BY ticker, enrich_date DESC, id DESC;

-- Disable RLS
ALTER TABLE universe     DISABLE ROW LEVEL SECURITY;
ALTER TABLE scan_results DISABLE ROW LEVEL SECURITY;
ALTER TABLE enriched     DISABLE ROW LEVEL SECURITY;
ALTER TABLE watchlist    DISABLE ROW LEVEL SECURITY;

-- Verificare
SELECT 'universe'     AS tbl, COUNT(*) FROM universe
UNION ALL
SELECT 'scan_results' AS tbl, COUNT(*) FROM scan_results
UNION ALL
SELECT 'enriched'     AS tbl, COUNT(*) FROM enriched
UNION ALL
SELECT 'watchlist'    AS tbl, COUNT(*) FROM watchlist;
