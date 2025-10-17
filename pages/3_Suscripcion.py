# pages/3_Suscripcion.py
import streamlit as st
import pandas as pd
from utils.auth import role_country_selector
from services.risk_api import score_one
from components.charts import top_features_bar

st.set_page_config(page_title="Suscripción & Tarificación", page_icon="🧮", layout="wide")

country, role = role_country_selector()
st.header("Suscripción & Tarificación — Cotiza con IA (Piloto)")

plan = st.selectbox("Plan", ["Básico", "Estándar", "Premium"], index=1)
deducible = st.slider("Deducible (USD o COP equiv.)", 0, 5000, 500, step=250)
coaseguro = st.slider("Coaseguro (%)", 0, 40, 20, step=5)

with st.form("cotizador"):
    c1, c2, c3 = st.columns(3)
    with c1:
        age = st.number_input("Edad", min_value=18, max_value=90, value=45, step=1)
        sex = st.selectbox("Sexo", ["F","M"])
        bmi = st.number_input("IMC (BMI)", min_value=14.0, max_value=60.0, value=28.0, step=0.1)
        smoker = st.selectbox("Tabaquismo", [0,1], format_func=lambda x: "Sí" if x==1 else "No")
    with c2:
        hta = st.selectbox("Hipertensión (HTA)", [0,1], format_func=lambda x: "Sí" if x==1 else "No")
        dm = st.selectbox("Diabetes (DM)", [0,1], format_func=lambda x: "Sí" if x==1 else "No")
        ckd = st.selectbox("Enfermedad Renal (ERC)", [0,1], format_func=lambda x: "Sí" if x==1 else "No")
        prev_event = st.selectbox("Evento CV previo", [0,1], format_func=lambda x: "Sí" if x==1 else "No")
    with c3:
        hba1c = st.number_input("HbA1c", min_value=4.5, max_value=14.0, value=6.8, step=0.1)
        egfr = st.number_input("eGFR", min_value=8.0, max_value=140.0, value=80.0, step=1.0)
        util = st.number_input("Utilizaciones 12m", min_value=0, max_value=30, value=2, step=1)
        lab_recency = st.number_input("Meses desde último lab", min_value=0, max_value=48, value=6, step=1)

    submitted = st.form_submit_button("Calcular prima y riesgo")

if submitted:
    payload = {
        "age": age, "sex": sex, "bmi": bmi, "smoker": smoker,
        "hta": hta, "dm": dm, "ckd": ckd, "prev_event": prev_event,
        "hba1c": hba1c, "egfr": egfr, "utilizations_12m": util,
        "lab_recency_m": lab_recency, "meds_atc": "C09,A10"
    }
    res = score_one(payload)
    rf = res["risk_factor"]
    tw = res["time_window_months"]

    st.subheader("Resultado")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Risk factor", f"{rf:.3f}")
    with c2:
        st.metric("Rango temporal", f"{tw[0]}–{tw[1]} meses")
    with c3:
        prima_base = 1200 if plan=="Premium" else (900 if plan=="Estándar" else 700)
        # Ajuste muy simple por riesgo y deducible/coaseguro
        adj = (1+rf) * (1 - deducible/10000) * (1 - coaseguro/100)
        prima = max(25, prima_base * adj)
        st.metric("Prima sugerida (sim.)", f"${prima:,.0f}")

    st.caption("Top factores (explicabilidad simulada)")
    top_features_bar(res["top_features"])

    st.subheader("Sensibilidad de prima")
    import altair as alt
    df = pd.DataFrame({
        "deducible": [0, 1000, 2000, 3000, 4000, 5000],
        "coaseguro": [0, 10, 20, 30, 40, 40],
    })
    df["prima"] = [max(25, prima_base*(1+rf)*(1-d/10000)*(1-c/100)) for d,c in zip(df["deducible"], df["coaseguro"])]
    chart = alt.Chart(df).mark_line(point=True).encode(
        x=alt.X("deducible:Q", title="Deducible"),
        y=alt.Y("prima:Q", title="Prima (simulada)"),
        color=alt.value("#08d19f"),
        tooltip=["deducible","coaseguro","prima"]
    ).properties(height=240)
    st.altair_chart(chart, use_container_width=True)
else:
    st.info("Completa el formulario y pulsa **Calcular prima y riesgo**.")
