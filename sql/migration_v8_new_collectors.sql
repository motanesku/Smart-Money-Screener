-- Migration v8: Add new collectors (news, SIC, earnings)
-- Added 2026-05-06

ALTER TABLE enriched ADD COLUMN IF NOT EXISTS days_to_earnings  integer;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS earnings_date     text;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS earnings_source   text;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS sic_code          integer;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS sic_description   text;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS news_signal       text;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS news_headline     text;
ALTER TABLE enriched ADD COLUMN IF NOT EXISTS news_category     text;
