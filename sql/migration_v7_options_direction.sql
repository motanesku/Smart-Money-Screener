-- Migration v7: Options Flow + Direction + Institutional data
-- Rulează în Supabase SQL Editor după migration_v6

-- 1. Options flow columns
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS call_volume           BIGINT  DEFAULT 0;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS put_volume            BIGINT  DEFAULT 0;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS pc_ratio              FLOAT;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS call_vol_oi_ratio     FLOAT;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS unusual_call_strikes  INTEGER DEFAULT 0;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS unusual_put_strikes   INTEGER DEFAULT 0;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS options_signal        TEXT    NOT NULL DEFAULT '';
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS options_direction     TEXT    NOT NULL DEFAULT '';
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS options_signal_text   TEXT    NOT NULL DEFAULT '';

-- 2. Direction field (BULLISH / BEARISH / DISTRIBUTION / NEUTRAL)
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS direction             TEXT    NOT NULL DEFAULT 'NEUTRAL';

-- 3. Score restructuring (options înlocuiește insider în scor)
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS score_options         INTEGER DEFAULT 0;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS score_short           INTEGER DEFAULT 0;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS score_sideways        INTEGER DEFAULT 0;

-- 4. Institutional data (din yfinance — fără API key nou)
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS inst_own_pct          FLOAT;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS short_float_pct       FLOAT;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS short_ratio_days      FLOAT;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS float_shares          BIGINT;

-- 5. Volume în USD (large cap fix)
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS vol_usd               NUMERIC(18,0) DEFAULT 0;

-- 6. Index pe direction pentru filtrare rapidă în UI
CREATE INDEX IF NOT EXISTS idx_enriched_direction ON enriched(direction, enrich_date DESC);

-- Verificare
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'enriched'
  AND column_name IN (
    'direction','options_signal','pc_ratio','call_volume','put_volume',
    'score_options','inst_own_pct','short_float_pct','vol_usd'
  )
ORDER BY column_name;
