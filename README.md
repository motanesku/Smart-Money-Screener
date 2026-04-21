# Smart Money Screener

Screener pentru semnale smart money pe mid/small cap NYSE+NASDAQ.
Detecteaza volume spikes + insider buying + short interest pentru ~1500 tickers.

## Arhitectura

```
GitHub Actions (cron)
    ├── Duminica 20:00 UTC  → universe_builder  (rebuild lista tickers)
    ├── Luni-Vineri 13:00   → scanner           (volume spike scan)
    ├── Luni-Vineri 13:45   → enricher          (insider + financials)
    └── Luni-Vineri 21:30   → enricher          (update dupa inchidere)

Supabase PostgreSQL
    ├── universe            (tickers eligibili ~1500)
    ├── scan_results        (candidati zilnici)
    ├── enriched            (date complete + score)
    └── watchlist           (salvate de user)

Streamlit Community Cloud
    └── UI read-only din Supabase
```

## Setup (ordine obligatorie)

### 1. Supabase
1. Mergi pe https://supabase.com → New project
2. Din SQL Editor, ruleaza continutul din `sql/schema.sql`
3. Copiaza din Settings → API: `Project URL` si `anon public key`

### 2. Finnhub
1. Mergi pe https://finnhub.io → Sign up gratuit
2. Copiaza API key din dashboard

### 3. FMP (Financial Modeling Prep)
1. Mergi pe https://financialmodelingprep.com → Sign up gratuit
2. Copiaza API key (planul gratuit: 250 req/zi)

### 4. GitHub repo
1. Fork sau clone acest repo
2. Mergi in repo → Settings → Secrets and variables → Actions
3. Adauga aceste secrets:
   - `SUPABASE_URL` — Project URL din Supabase
   - `SUPABASE_KEY` — anon public key din Supabase
   - `FINNHUB_KEY` — API key Finnhub
   - `FMP_KEY` — API key FMP

### 5. Primul run (manual)
In GitHub → Actions → Smart Money Screener → Run workflow:
1. Selecteaza `universe` → Run (asteapta ~10 min)
2. Selecteaza `scan` → Run
3. Selecteaza `enrich` → Run (asteapta ~5-10 min)

### 6. Streamlit Cloud
1. Mergi pe https://share.streamlit.io
2. Connect GitHub → selecteaza repo
3. Main file path: `app/streamlit_app.py`
4. Advanced settings → Secrets:
```toml
SUPABASE_URL = "https://xxxx.supabase.co"
SUPABASE_KEY = "eyJxxx..."
```

## Structura fișiere

```
├── collectors/
│   ├── universe_builder.py   # Rebuild lista tickers (1x/saptamana)
│   ├── scanner.py            # Volume spike scan (zilnic dimineata)
│   ├── enricher.py           # Insider + financials (2x/zi)
│   └── run.py                # Orchestrator apelat de GitHub Actions
├── app/
│   ├── streamlit_app.py      # UI Streamlit
│   └── db.py                 # Toate operatiunile cu Supabase
├── sql/
│   └── schema.sql            # Schema baza de date
├── .github/workflows/
│   └── screener.yml          # GitHub Actions cron jobs
└── requirements.txt
```

## Score methodology

| Semnal | Puncte |
|--------|--------|
| Volume spike 5x+ | 25 |
| Volume spike 3-5x | 15 |
| Insider buy $1M+ | 35 |
| Insider buy $250k+ | 20 |
| Short interest scazut (<5%) | 10 |
| Institutional ownership >60% | 10 |
| P/E rezonabil (5-25) | 10 |

Score >= 70 = semnal puternic
Score 45-70 = semnal moderat
Score < 45 = slab / zgomot
