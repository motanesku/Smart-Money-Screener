-- Smart Money Screener - migration incrementală
-- NU șterge datele existente.

ALTER TABLE enriched ADD COLUMN IF NOT EXISTS price NUMERIC(10,2);
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS volume BIGINT;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS avg_volume_20d BIGINT;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS vol_ratio NUMERIC(8,4);
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS market_cap BIGINT;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS sector TEXT;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS industry TEXT;

ALTER TABLE enriched ADD COLUMN IF NOT EXISTS score_volume INTEGER DEFAULT 0;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS score_insider INTEGER DEFAULT 0;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS score_short_interest INTEGER DEFAULT 0;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS score_fundamental INTEGER DEFAULT 0;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS score_penalty INTEGER DEFAULT 0;

ALTER TABLE enriched ADD COLUMN IF NOT EXISTS volume_signal TEXT;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS insider_signal TEXT;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS short_signal TEXT;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS thesis TEXT;

CREATE INDEX IF NOT EXISTS idx_enriched_ticker ON enriched(ticker);
CREATE INDEX IF NOT EXISTS idx_enriched_date_ticker ON enriched(enrich_date DESC, ticker);
