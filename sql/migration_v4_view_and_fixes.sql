-- Migration v4: creează enriched_view și adaugă company_name în enriched
-- Rulează în Supabase SQL Editor

-- 1. Adaugă company_name în enriched (dacă nu există deja)
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS company_name TEXT DEFAULT '';

-- 2. Creează sau înlocuiește enriched_view
-- Join enriched cu universe pentru a aduce company_name chiar dacă nu e în enriched
CREATE OR REPLACE VIEW enriched_view AS
SELECT
    e.*,
    COALESCE(NULLIF(e.company_name, ''), u.company_name, '') AS company_name_display
FROM enriched e
LEFT JOIN universe u ON u.ticker = e.ticker;

-- 3. Verificare rapidă
-- SELECT COUNT(*) FROM enriched;
-- SELECT COUNT(*) FROM enriched_view;
