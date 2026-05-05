-- Migration v9: add raw_perf to scan_results and price_change_pct to enriched
-- raw_perf: raw daily performance from scanner (close/prev_close - 1), e.g. 0.032 = +3.2%
-- price_change_pct: same value * 100, stored in enriched for UI display

ALTER TABLE scan_results
  ADD COLUMN IF NOT EXISTS raw_perf NUMERIC(8, 4);

ALTER TABLE enriched
  ADD COLUMN IF NOT EXISTS price_change_pct NUMERIC(8, 2);

COMMENT ON COLUMN scan_results.raw_perf IS 'Daily return fraction from scanner: (close/prev_close - 1). 0.032 = +3.2%';
COMMENT ON COLUMN enriched.price_change_pct IS 'Daily price change percent: raw_perf * 100. 3.2 = +3.2%';
