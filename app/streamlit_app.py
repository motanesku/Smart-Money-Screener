import streamlit as st
import pandas as pd

# -------------------------------------------------
# CONFIG APLICAȚIE
# -------------------------------------------------
st.set_page_config(
    page_title="Smart Money Screener",
    page_icon="💰",
    layout="wide"
)

# -------------------------------------------------
# CSS CUSTOM (fără dark/light custom)
# -------------------------------------------------
st.markdown("""
<style>

html, body, [class*="css"]  {
    font-family: 'Inter', sans-serif;
}

.section-title {
    font-size: 26px;
    font-weight: 700;
    margin-bottom: 10px;
}

.card {
    background: rgba(255,255,255,0.1);
    padding: 20px;
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,0.15);
    backdrop-filter: blur(8px);
}

.metric-label {
    font-size: 14px;
    opacity: 0.8;
}

.metric-value {
    font-size: 32px;
    font-weight: 700;
    margin-top: -5px;
}

</style>
""", unsafe_allow_html=True)

# -------------------------------------------------
# FUNCTIILE TALE – LOGICA EXISTENTĂ
# -------------------------------------------------
# TODO:
# Aici lipești importurile și funcțiile tale existente:
# - funcții de scraping
# - funcții de prelucrare
# - funcții de scoring
# - orice load_data(), run_screener(), etc.
#
# Exemplu:
#
# from core.screener import run_screener
# from core.data import load_universe
#
# def get_screener_results(sector, min_score, ...):
#     ...

# -------------------------------------------------
# FUNCTIE WRAPPER PENTRU A LUA DATELE REALE
# -------------------------------------------------
@st.cache_data(show_spinner=True)
def load_results(sector_filter: str, min_score: int):
    """
    TODO:
    Înlocuiește conținutul acestei funcții cu logica ta reală.
    Trebuie să returneze un DataFrame cu rezultatele screener-ului.
    Coloane recomandate: Ticker, Score, Insider Buys, Volume Spike, Sector etc.
    """

    # EXEMPLU PROVIZORIU – DOAR CA SĂ NU PICE APLICAȚIA
    data = {
        "Ticker": ["AAPL", "MSFT", "NVDA", "TSLA"],
        "Score": [88, 92, 75, 81],
        "Insider Buys": [3, 1, 0, 2],
        "Volume Spike": ["Yes", "Yes", "No", "Yes"],
        "Sector": ["Tech", "Tech", "Tech", "Auto"]
    }
    df = pd.DataFrame(data)

    if sector_filter != "All":
        df = df[df["Sector"] == sector_filter]

    df = df[df["Score"] >= min_score]

    return df

# -------------------------------------------------
# SIDEBAR – FILTRE
# -------------------------------------------------
st.sidebar.title("🔍 Filtre")

sector = st.sidebar.selectbox("Sector", ["All", "Tech", "Energy", "Finance", "Auto"])
min_score = st.sidebar.slider("Scor minim", 0, 100, 50)

st.sidebar.markdown("---")
st.sidebar.write("💡 Tema light/dark se schimbă din meniul Streamlit (dreapta sus).")

# Poți adăuga aici și alte filtre specifice logicii tale:
# ex: tip semnal, volum minim, market cap etc.

# -------------------------------------------------
# HEADER
# -------------------------------------------------
st.markdown("<h1 class='section-title'>Smart Money Screener Dashboard</h1>", unsafe_allow_html=True)
st.write("Analiză automată a fluxurilor de capital, insider trading și semnale instituționale.")

# -------------------------------------------------
# ÎNCĂRCARE DATE REALE
# -------------------------------------------------
with st.spinner("Încarc rezultatele..."):
    df_results = load_results(sector, min_score)

# -------------------------------------------------
# CARDURI STATISTICI – DIN DATELE REALE
# -------------------------------------------------
total_signals = len(df_results)
strong_signals = (df_results["Score"] >= 80).sum() if not df_results.empty else 0
insider_buys = df_results["Insider Buys"].sum() if "Insider Buys" in df_results.columns else 0
active_tickers = df_results["Ticker"].nunique() if not df_results.empty else 0

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(
        f"<div class='card'><div class='metric-label'>Total semnale</div>"
        f"<div class='metric-value'>{total_signals}</div></div>",
        unsafe_allow_html=True
    )

with col2:
    st.markdown(
        f"<div class='card'><div class='metric-label'>Semnale puternice (Score ≥ 80)</div>"
        f"<div class='metric-value'>{strong_signals}</div></div>",
        unsafe_allow_html=True
    )

with col3:
    st.markdown(
        f"<div class='card'><div class='metric-label'>Insider Buys</div>"
        f"<div class='metric-value'>{insider_buys}</div></div>",
        unsafe_allow_html=True
    )

with col4:
    st.markdown(
        f"<div class='card'><div class='metric-label'>Tickere active</div>"
        f"<div class='metric-value'>{active_tickers}</div></div>",
        unsafe_allow_html=True
    )

st.markdown("---")

# -------------------------------------------------
# LAYOUT PRINCIPAL: FILTRE AVANSATE + TABEL / GRAFICE
# -------------------------------------------------
left, right = st.columns([1, 2])

with left:
    st.markdown("<h2 class='section-title'>📊 Filtre avansate</h2>", unsafe_allow_html=True)

    # TODO:
    # Aici poți muta filtrele tale existente (tip semnal, volum, market cap etc.)
    signal_type = st.selectbox("Tip semnal", ["Toate", "Buy", "Sell"])
    institution_type = st.selectbox("Tip instituție", ["Toate", "Hedge Funds", "Banks", "Pension Funds"])
    volume_min = st.slider("Volum minim", 0, 1_000_000, 100_000)
    mcap_min = st.slider("Market Cap minim", 0, 1_000_000_000_000, 1_000_000_000)

    st.markdown("Poți conecta aceste filtre la logica ta în `load_results()`.")

with right:
    st.markdown("<h2 class='section-title'>📈 Rezultate</h2>", unsafe_allow_html=True)

    if df_results.empty:
        st.warning("Nu există rezultate pentru filtrele selectate.")
    else:
        # TODO:
        # Dacă ai deja un DataFrame final în codul tău, înlocuiește df_results cu el.
        st.dataframe(df_results, use_container_width=True)

        # TODO (opțional):
        # Aici poți adăuga grafice (ex: distribuția scorurilor, volume spike etc.)
        # Exemplu:
        if "Score" in df_results.columns:
            st.bar_chart(df_results.set_index("Ticker")["Score"])
