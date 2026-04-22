-- Incremental upgrade for follow-the-smart-money features
-- Safe: adds columns only, preserves existing data

ALTER TABLE enriched ADD COLUMN IF NOT EXISTS score_insider_quality INTEGER DEFAULT 0;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS score_ownership INTEGER DEFAULT 0;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS score_short_flow INTEGER DEFAULT 0;

ALTER TABLE enriched ADD COLUMN IF NOT EXISTS top_insider_role TEXT;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS ownership_form TEXT;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS ownership_holder TEXT;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS ownership_pct NUMERIC(8,4);
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS ownership_signal TEXT;

ALTER TABLE enriched ADD COLUMN IF NOT EXISTS short_sale_volume BIGINT;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS total_volume_reported BIGINT;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS short_sale_ratio NUMERIC(8,4);
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS short_flow_signal TEXT;

CREATE INDEX IF NOT EXISTS idx_enriched_ownership_form ON enriched(ownership_form);
CREATE INDEX IF NOT EXISTS idx_enriched_short_sale_ratio ON enriched(short_sale_ratio);
