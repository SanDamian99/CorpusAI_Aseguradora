# pages/1_Dashboard.py
import streamlit as st
import pandas as pd
from utils.auth import role_country_selector
from services.data_io import generate_dummy_population
from services.risk_api import score_batch
from utils.kpis import compute_core_kpis
from components.cards import render_cards
from components.charts import risk_hist, region_heat, survival_deciles
from components.cohort_filters import cohort_builder

st.set_page_config(page_title="Dashboard Ejecutivo", page_icon="📊", layout="wide")

country, role = role_country_selector()

@st.cache_data(show_spinner=False)
def get_scored_population(country):
    df = generate_dummy_population(n=2500, country=country, seed=42)
    df_scored, _ = score_batch(df, seed=123)
    return df_scored

df = get_scored_population(country)

st.header("Dashboard Ejecutivo — Población & Riesgo")
kpis = compute_core_kpis(df, country)
render_cards(kpis)

st.divider()
mask, desc = cohort_builder(df)
df_cohort = df[mask].copy()
st.caption(f"Cohorte activa: {len(df_cohort):,} afiliados — {desc}")

col1, col2 = st.columns([1.1, 1])
with col1:
    st.subheader("Distribución de riesgo")
    risk_hist(df_cohort)
with col2:
    st.subheader("Riesgo por región (heat)")
    region_heat(df_cohort)

st.subheader("Curvas de riesgo acumulado por decil")
survival_deciles(df_cohort)

with st.expander("Tabla resumida de cohorte", expanded=False):
    st.dataframe(df_cohort[["patient_id","age","sex","region","risk_factor","tw_start","tw_end","cohort_label","care_gaps"]]
                 .sort_values("risk_factor", ascending=False)
                 .head(200), use_container_width=True)
