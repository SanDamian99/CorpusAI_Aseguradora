# pages/4_Simulador.py
import streamlit as st
import pandas as pd
from utils.auth import role_country_selector
from services.data_io import generate_dummy_population
from services.risk_api import score_batch
from components.cohort_filters import cohort_builder
from components.charts import scenario_bars
from utils.kpis import quick_roi

st.set_page_config(page_title="Simulador Financiero", page_icon="🧪", layout="wide")

country, role = role_country_selector()

@st.cache_data(show_spinner=False)
def get_scored_population(country):
    df = generate_dummy_population(n=1800, country=country, seed=111)
    sdf, _ = score_batch(df, seed=222)
    return sdf

df = get_scored_population(country)
st.header("Simulador Financiero — Escenarios de Intervención")

mask, desc = cohort_builder(df)
cohort = df[mask].copy()
st.caption(f"Cohorte activa: {len(cohort):,} — {desc}")

c1, c2, c3 = st.columns(3)
with c1:
    reduccion = st.slider("Reducción de hazard (efecto del programa)", 0, 50, 20, step=5)
with c2:
    costo_evento = st.number_input("Costo por evento (moneda local)", 500_000, 15_000_000, 5_500_000, step=250_000)
with c3:
    costo_programa = st.number_input("Costo del programa (mes / cohorte)", 5_000_000, 300_000_000, 60_000_000, step=5_000_000)

st.markdown("**Supuesto simple:** eventos esperados ≈ suma(risk_factor) en la cohorte (piloto).")

def simular(df, reduccion_pct, cost_event, cost_prog):
    ev_esp = df["risk_factor"].sum()
    ev_ev = ev_esp * (reduccion_pct/100.0)
    ahorro, roi = quick_roi(ev_ev, cost_event, cost_prog)
    out = pd.DataFrame([
        {"scenario": "Base", "metric":"Eventos", "value": ev_esp},
        {"scenario": "Escenario", "metric":"Eventos", "value": ev_esp - ev_ev},
        {"scenario": "Escenario", "metric":"Ahorro", "value": ahorro},
        {"scenario": "Escenario", "metric":"ROI", "value": roi},
    ])
    return ev_esp, ev_ev, ahorro, roi, out

ev_esp, ev_ev, ahorro, roi, summary = simular(cohort, reduccion, costo_evento, costo_programa)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Eventos esperados (12m)", f"{ev_esp:,.1f}")
m2.metric("Eventos evitados (sim.)", f"{ev_ev:,.1f}")
m3.metric("Ahorro neto (sim.)", f"${ahorro:,.0f}")
m4.metric("ROI (sim.)", f"{roi:.2f}x")

scenario_bars(summary)

with st.expander("Tabla de cohorte (top 100 por riesgo)", expanded=False):
    st.dataframe(cohort.sort_values("risk_factor", ascending=False).head(100)[
        ["patient_id","age","sex","region","risk_factor","tw_start","tw_end","cohort_label","cost_event"]
    ], use_container_width=True)
