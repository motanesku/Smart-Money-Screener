DROP TABLE IF EXISTS watchlist CASCADE;
DROP TABLE IF EXISTS enriched CASCADE;
DROP TABLE IF EXISTS scan_results CASCADE;
DROP TABLE IF EXISTS universe CASCADE;

CREATE TABLE universe (
    ticker              TEXT PRIMARY KEY,
    company_name        TEXT,
    exchange            TEXT,
    sector              TEXT,
    industry            TEXT,
    market_cap          BIGINT,
    avg_volume_20d      BIGINT,
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE scan_results (
    id                  BIGSERIAL PRIMARY KEY,
    scan_date           DATE NOT NULL,
    ticker              TEXT NOT NULL,
    price               NUMERIC(10,2),
    volume              BIGINT,
    avg_volume_20d      BIGINT,
    vol_ratio           NUMERIC(8,4),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(scan_date, ticker)
);

CREATE TABLE enriched (
    id                  BIGSERIAL PRIMARY KEY,
    enrich_date         DATE NOT NULL,
    ticker              TEXT NOT NULL,
    price               NUMERIC(10,2),
    volume              BIGINT,
    avg_volume_20d      BIGINT,
    vol_ratio           NUMERIC(8,4),
    insider_buys_90d    INTEGER DEFAULT 0,
    insider_buy_value   NUMERIC(15,2) DEFAULT 0,
    insider_sells_90d   INTEGER DEFAULT 0,
    inst_ownership_pct  NUMERIC(8,4),
    pe_ratio            NUMERIC(10,4),
    short_interest_pct  NUMERIC(8,4),
    market_cap          BIGINT,
    sector              TEXT,
    industry            TEXT,
    score               INTEGER DEFAULT 0,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(enrich_date, ticker)
);

CREATE TABLE watchlist (
    ticker      TEXT PRIMARY KEY,
    added_at    TIMESTAMPTZ DEFAULT NOW(),
    notes       TEXT
);

CREATE INDEX idx_scan_date ON scan_results(scan_date DESC);
CREATE INDEX idx_scan_ticker ON scan_results(ticker);
CREATE INDEX idx_enrich_date ON enriched(enrich_date DESC);
CREATE INDEX idx_enrich_score ON enriched(score DESC);
CREATE INDEX idx_enrich_ticker ON enriched(ticker);

ALTER TABLE universe DISABLE ROW LEVEL SECURITY;
ALTER TABLE scan_results DISABLE ROW LEVEL SECURITY;
ALTER TABLE enriched DISABLE ROW LEVEL SECURITY;
ALTER TABLE watchlist DISABLE ROW LEVEL SECURITY;
