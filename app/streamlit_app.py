import streamlit as st
import pandas as pd
# ... (importurile tale de db.py) ...

def show_whale_narrative(df):
    st.write("---")
    st.markdown("### 🌊 Market Narrative (Sector Flow)")
    if 'sector' in df.columns and not df.empty:
        heat = df.groupby('sector').size().reset_index(name='Activity')
        heat = heat.sort_values('Activity', ascending=False)
        
        c1, c2 = st.columns([1, 2])
        with c1:
            st.dataframe(heat, hide_index=True, use_container_width=True)
        with c2:
            st.bar_chart(data=heat, x='sector', y='Activity', color="#0969da")

# După afișarea Watchlist-ului principal:
# df_enriched = pd.DataFrame(get_enriched())
# if not df_enriched.empty:
#     show_whale_narrative(df_enriched)
