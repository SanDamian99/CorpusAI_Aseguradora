# components/cohort_filters.py
import streamlit as st
import pandas as pd

def cohort_builder(df: pd.DataFrame):
    with st.expander("Filtros de cohorte", expanded=True):
        age_min, age_max = st.slider("Edad", 18, 90, (40, 75))
        sex = st.multiselect("Sexo", options=["F","M"], default=["F","M"])
        region = st.multiselect("Región", options=sorted(df["region"].unique().tolist()),
                                default=sorted(df["region"].unique().tolist()))
        dx = st.multiselect("Diagnósticos (CIE-10)", options=["I10","E11","N18","I21","E78"], default=[])
        risk_band = st.select_slider("Banda de riesgo", options=["Todos","Bajo (<0.15)","Medio (0.15-0.3)","Alto (≥0.3)"], value="Todos")

    mask = (
        (df["age"].between(age_min, age_max)) &
        (df["sex"].isin(sex)) &
        (df["region"].isin(region))
    )
    if dx:
        mask &= df["dx_cie10"].str.contains("|".join(dx))
    if risk_band == "Bajo (<0.15)":
        mask &= df["risk_factor"] < 0.15
    elif risk_band == "Medio (0.15-0.3)":
        mask &= df["risk_factor"].between(0.15, 0.3)
    elif risk_band == "Alto (≥0.3)":
        mask &= df["risk_factor"] >= 0.3

    desc = f"Edad {age_min}-{age_max}, Sexos {','.join(sex)}, Regiones {len(region)}, Dx {','.join(dx) if dx else '—'}, Banda {risk_band}"
    return mask, desc
