# pages/1_Dashboard.py (encabezado)
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

from utils.auth import role_country_selector
from services.data_io import generate_dummy_population
from services.risk_api import score_batch
from utils.kpis import compute_core_kpis
from components.cards import render_cards
from components.charts import risk_hist, region_heat, survival_deciles
from components.cohort_filters import cohort_builder

st.set_page_config(page_title="Dashboard Ejecutivo", page_icon="📊", layout="wide")

# Altair sin límite de filas (por si en algún momento pasas DF grandes)
try:
    alt.data_transformers.disable_max_rows()
except Exception:
    pass

country, role = role_country_selector()
debug = st.sidebar.toggle("Modo debug (curvas)", value=False)





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
    if df_cohort.empty:
        st.info("No hay datos para la cohorte seleccionada.")
    else:
        risk_hist(df_cohort)

with col2:
    st.subheader("Riesgo por región (heat)")
    if df_cohort.empty:
        st.info("No hay datos para la cohorte seleccionada.")
    else:
        region_heat(df_cohort)

st.subheader("Curvas de riesgo acumulado por decil")
if df_cohort.empty:
    st.info("No hay datos para la cohorte seleccionada.")
else:
    survival_deciles(df_cohort, debug=debug)


# ================================
# Exploraciones adicionales (5)
# ================================
st.divider()
st.subheader("Exploraciones adicionales (piloto)")

if df_cohort.empty:
    st.info("No hay datos para graficar visualizaciones adicionales.")
else:
    # 0) Derivados útiles
    # Banda de riesgo
    df_cohort = df_cohort.copy()
    df_cohort["risk_band"] = pd.cut(
        df_cohort["risk_factor"],
        bins=[0, 0.15, 0.3, 1.0],
        labels=["Bajo (<0.15)", "Medio (0.15–0.30)", "Alto (≥0.30)"],
        include_lowest=True
    )
    # Franjas etarias
    df_cohort["age_band"] = pd.cut(
        df_cohort["age"], bins=[18, 40, 55, 70, 90],
        labels=["18–39", "40–55", "56–70", "71–90"], include_lowest=True
    )
    # “Tiene brecha” (cualquier care_gap)
    df_cohort["has_gap"] = df_cohort["care_gaps"].fillna("").str.len().gt(0)

    # ========== (A) Conteo y riesgo medio por banda ==========
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**A. Conteo por banda de riesgo**")
        agg_cnt = df_cohort.groupby("risk_band", dropna=False, as_index=False).size()
        chart_a1 = alt.Chart(agg_cnt).mark_bar().encode(
            x=alt.X("risk_band:N", title="Banda de riesgo", sort=["Bajo (<0.15)","Medio (0.15–0.30)","Alto (≥0.30)"]),
            y=alt.Y("size:Q", title="Pacientes"),
            tooltip=["risk_band","size"]
        ).properties(height=240)
        st.altair_chart(chart_a1, use_container_width=True)

    with c2:
        st.markdown("**A2. Riesgo promedio por banda**")
        agg_mean = df_cohort.groupby("risk_band", dropna=False, as_index=False).agg(risk_mean=("risk_factor","mean"))
        chart_a2 = alt.Chart(agg_mean).mark_bar().encode(
            x=alt.X("risk_mean:Q", title="Riesgo promedio"),
            y=alt.Y("risk_band:N", title=None, sort=["Bajo (<0.15)","Medio (0.15–0.30)","Alto (≥0.30)"]),
            tooltip=["risk_band","risk_mean"]
        ).properties(height=240)
        st.altair_chart(chart_a2, use_container_width=True)

    # ========== (B) Riesgo vs eGFR con tendencia ==========
    st.markdown("**B. Riesgo vs eGFR (con tendencia)**")
    scatter = alt.Chart(df_cohort).mark_circle(size=30, opacity=0.35).encode(
        x=alt.X("egfr:Q", title="eGFR"),
        y=alt.Y("risk_factor:Q", title="Riesgo"),
        tooltip=["patient_id","egfr","risk_factor","age","region","risk_band"]
    )
    trend = scatter.transform_regression("egfr", "risk_factor").mark_line()
    st.altair_chart((scatter + trend).properties(height=260), use_container_width=True)

    # ========== (C) Boxplots por región ==========
    st.markdown("**C. Distribución de riesgo por región (boxplot)**")
    chart_box = alt.Chart(df_cohort).mark_boxplot().encode(
        x=alt.X("region:N", title="Región"),
        y=alt.Y("risk_factor:Q", title="Riesgo"),
        color=alt.Color("region:N", legend=None),
        tooltip=["region"]
    ).properties(height=260)
    st.altair_chart(chart_box, use_container_width=True)

    # ========== (D) Heatmap Utilizaciones vs Riesgo ==========
    st.markdown("**D. Uso de servicios vs Riesgo (heatmap binned)**")
    hmap = alt.Chart(df_cohort).mark_rect().encode(
        x=alt.X("utilizations_12m:Q", bin=alt.Bin(maxbins=20), title="Utilizaciones 12m (binned)"),
        y=alt.Y("risk_factor:Q",       bin=alt.Bin(maxbins=20), title="Riesgo (binned)"),
        color=alt.Color("count():Q", title="N"),
        tooltip=[
            alt.Tooltip("count():Q", title="N"),
        ],
    ).properties(height=260)
    st.altair_chart(hmap, use_container_width=True)

    # ========== (E) Brechas de cuidado por banda ==========
    st.markdown("**E. Brechas de cuidado por banda de riesgo**")
    agg_gap = df_cohort.groupby(["risk_band","has_gap"], as_index=False).size()
    # Formateo para apilado (stacked)
    agg_gap["has_gap_label"] = agg_gap["has_gap"].map({True:"Con brecha", False:"Sin brecha"})
    chart_gap = alt.Chart(agg_gap).mark_bar().encode(
        x=alt.X("risk_band:N", title="Banda", sort=["Bajo (<0.15)","Medio (0.15–0.30)","Alto (≥0.30)"]),
        y=alt.Y("size:Q", title="Pacientes"),
        color=alt.Color("has_gap_label:N", title="Estado"),
        tooltip=["risk_band","has_gap_label","size"]
    ).properties(height=260)
    st.altair_chart(chart_gap, use_container_width=True)
