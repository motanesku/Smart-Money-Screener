CREATE TABLE IF NOT EXISTS universe (
    ticker          TEXT PRIMARY KEY,
    company_name    TEXT,
    exchange        TEXT,
    sector          TEXT,
    industry        TEXT,
    market_cap      BIGINT,
    avg_volume      BIGINT,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS scan_results (
    id              BIGSERIAL PRIMARY KEY,
    scan_date       DATE NOT NULL,
    ticker          TEXT NOT NULL,
    price           NUMERIC(10,2),
    volume          BIGINT,
    avg_volume_20d  BIGINT,
    vol_ratio       NUMERIC(6,2),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(scan_date, ticker)
);

CREATE TABLE IF NOT EXISTS enriched (
    id                  BIGSERIAL PRIMARY KEY,
    enrich_date         DATE NOT NULL,
    ticker              TEXT NOT NULL,
    insider_buys_90d    INTEGER DEFAULT 0,
    insider_buy_value   NUMERIC(15,2) DEFAULT 0,
    insider_sells_90d   INTEGER DEFAULT 0,
    inst_ownership_pct  NUMERIC(5,2),
    pe_ratio            NUMERIC(8,2),
    short_interest_pct  NUMERIC(8,4),
    score               INTEGER DEFAULT 0,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(enrich_date, ticker)
);

CREATE TABLE IF NOT EXISTS watchlist (
    ticker      TEXT PRIMARY KEY,
    added_at    TIMESTAMPTZ DEFAULT NOW(),
    notes       TEXT
);

CREATE INDEX IF NOT EXISTS idx_scan_date    ON scan_results(scan_date DESC);
CREATE INDEX IF NOT EXISTS idx_enrich_date  ON enriched(enrich_date DESC);
CREATE INDEX IF NOT EXISTS idx_enrich_score ON enriched(score DESC);
