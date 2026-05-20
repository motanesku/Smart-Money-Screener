-- ============================================================
-- Schema v2 — Witness-Based Smart Money Detection
-- Rulează în Supabase SQL Editor
-- ============================================================

-- ── UNIVERSE: adaugă index_member dacă nu există ─────────────
ALTER TABLE universe ADD COLUMN IF NOT EXISTS index_member TEXT DEFAULT '';

-- ── ENRICHED V2 ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS enriched_v2 (
    id                  BIGSERIAL PRIMARY KEY,
    enrich_date         DATE        NOT NULL,
    ticker              TEXT        NOT NULL,

    -- Profil companie (din universe)
    company_name        TEXT        DEFAULT '',
    sector              TEXT        DEFAULT '',
    market_cap          BIGINT      DEFAULT 0,

    -- Preț
    price               NUMERIC(12,4),
    price_change_pct    NUMERIC(8,4),   -- % schimbare față de ieri
    high_52w            NUMERIC(12,4),
    low_52w             NUMERIC(12,4),

    -- Volum brut
    vol_today           BIGINT,
    vol_avg_20d         BIGINT,
    vol_avg_63d         BIGINT,

    -- Martor volum structural (Z-Score medie 21d vs baseline 63d)
    vol_zscore_21v63    NUMERIC(8,3),   -- σ față de media 63d; >1.5 = anomalie
    vol_witness         TEXT,           -- CERERE / OFERTĂ / AMBIGUU / NEUTRU
    close_position      NUMERIC(5,3),   -- 0=jos, 1=sus în range-ul zilei

    -- Martor volatilitate (ATR percentile)
    atr_14              NUMERIC(12,6),  -- ATR actual
    atr_pct_63d         NUMERIC(6,2),   -- percentila 0-100; <15 = compresie extremă

    -- Martor range (sideways accumulation)
    range_width_21d     NUMERIC(8,4),   -- % lățime range 21 zile; <7% = lateral

    -- Martor forță relativă vs sector
    rs_defense_score    NUMERIC(5,3),   -- 0-1; >0.5 = rezistă pe zile down
    rs_defense_days     INTEGER DEFAULT 0,
    sector_etf          TEXT    DEFAULT '',

    -- Martor Wyckoff
    wyckoff_witness     TEXT    DEFAULT 'NONE', -- SPRING / PHASE_B / DISTRIBUTION / NONE
    spring_date         DATE,

    -- Profil volum (Point of Control)
    poc_1y              NUMERIC(12,4),  -- preț POC pe 1 an
    vah_1y              NUMERIC(12,4),  -- Value Area High 1 an
    val_1y              NUMERIC(12,4),  -- Value Area Low 1 an
    poc_3m              NUMERIC(12,4),  -- preț POC pe 3 luni
    dist_poc_1y_pct     NUMERIC(8,3),   -- % distanță față de POC 1 an (+ = deasupra)
    dist_poc_3m_pct     NUMERIC(8,3),   -- % distanță față de POC 3 luni

    -- Eticheta finală derivată din convergența martorilor
    trend_label         TEXT    DEFAULT 'FĂRĂ SEMNAL',
    -- Valori posibile:
    --   GATA DE BREAKOUT   — Spring + RS confirmat
    --   ACUMULARE ASCUNSĂ  — ATR comprimat + cerere + lateral
    --   DISTRIBUȚIE        — ofertă + prețul sus față de POC
    --   EPUIZARE           — volatilitate explodată + ofertă
    --   CONSOLIDARE NEUTRĂ — lateral fără semnal de cerere/ofertă
    --   FĂRĂ SEMNAL        — nicio convergență detectată

    created_at          TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(enrich_date, ticker)
);

-- Indexuri pentru query-urile din Streamlit
CREATE INDEX IF NOT EXISTS idx_ev2_date        ON enriched_v2(enrich_date DESC);
CREATE INDEX IF NOT EXISTS idx_ev2_label       ON enriched_v2(trend_label);
CREATE INDEX IF NOT EXISTS idx_ev2_ticker      ON enriched_v2(ticker);
CREATE INDEX IF NOT EXISTS idx_ev2_date_label  ON enriched_v2(enrich_date DESC, trend_label);
CREATE INDEX IF NOT EXISTS idx_ev2_sector      ON enriched_v2(sector, enrich_date DESC);

-- ── WATCHLIST V2 ──────────────────────────────────────────────
-- Extinde watchlist-ul existent cu snapshot la momentul adăugării
ALTER TABLE watchlist ADD COLUMN IF NOT EXISTS trend_label_at_add  TEXT DEFAULT '';
ALTER TABLE watchlist ADD COLUMN IF NOT EXISTS poc_1y_at_add       NUMERIC(12,4);
ALTER TABLE watchlist ADD COLUMN IF NOT EXISTS price_at_add        NUMERIC(12,4);
