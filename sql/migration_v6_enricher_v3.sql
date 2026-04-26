-- Migration v6: Coloane noi din Enricher v3 + AI Thesis
-- Rulează în Supabase SQL Editor după migration_v5
-- Adaugă câmpurile salvate de enricher.py v3 care lipseau din schema

-- 1. Coloane insider extinse
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS net_insider_signal   TEXT    NOT NULL DEFAULT '';
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS is_10b5_plan         BOOLEAN NOT NULL DEFAULT FALSE;

-- 2. Sector context (din scanner)
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS rs_vs_sector         FLOAT;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS sector_heat_score    INTEGER DEFAULT 0;

-- 3. Short interest detaliat (din FINRA)
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS avg_short_ratio_5d   FLOAT;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS squeeze_setup        BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS short_squeeze_signal TEXT    NOT NULL DEFAULT '';

-- 4. Sideways accumulation pattern
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS sideways_signal      TEXT    NOT NULL DEFAULT '';

-- 5. AI Thesis Haiku (câmpul principal din enricher v3)
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS ai_thesis_ro         TEXT    NOT NULL DEFAULT '';

-- 6. Coloana insider_sell_value dacă lipsea din versiuni vechi
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS insider_sell_value   NUMERIC(18,2) NOT NULL DEFAULT 0;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS top_insider_role     TEXT    NOT NULL DEFAULT '';

-- Verificare coloane adăugate
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'enriched'
  AND column_name IN (
    'net_insider_signal','is_10b5_plan','rs_vs_sector','sector_heat_score',
    'avg_short_ratio_5d','squeeze_setup','short_squeeze_signal',
    'sideways_signal','ai_thesis_ro','insider_sell_value','top_insider_role'
  )
ORDER BY column_name;
