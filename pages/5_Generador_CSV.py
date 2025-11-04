# pages/5_Generador_CSV.py
import io
import numpy as np
import pandas as pd
import streamlit as st

from utils.auth import ensure_context, role_country_selector, get_context
from services.data_io import generate_dummy_population, REGIONS_CO, REGIONS_MX
from services.risk_api import score_population, set_mock_config, get_mock_config

st.set_page_config(page_title="Generador CSV Sintético", page_icon="📥", layout="wide")

# Contexto y selector coherente con el resto de la app
ensure_context(default_country="México")
role_country_selector(place="sidebar")
ctx = get_context()

st.title("📥 Generador de CSV sintético (con sesgos parametrizables)")
st.caption("Crea una cohorte dummy y aplica un mock de riesgo configurable para explorar efectos en las curvas por decil y KPIs. **Sin PHI**.")

with st.form("gen_form"):
    colA, colB, colC = st.columns([1,1,1])

    with colA:
        n = st.number_input("Tamaño de la cohorte", min_value=200, max_value=10000, value=2500, step=100)
        seed = st.number_input("Semilla (reproducible)", min_value=0, max_value=999999, value=42, step=1)

        st.markdown("**Prevalencias (0–1)**")
        p_smoker = st.slider("Fumador", 0.0, 1.0, 0.30, 0.01)
        p_dm     = st.slider("Diabetes (DM2)", 0.0, 1.0, 0.30, 0.01)
        p_hta    = st.slider("Hipertensión (HTA)", 0.0, 1.0, 0.50, 0.01)
        p_ckd    = st.slider("Enfermedad renal (ERC)", 0.0, 1.0, 0.15, 0.01)
        p_prev   = st.slider("Evento previo (MACE)", 0.0, 1.0, 0.10, 0.01)

    with colB:
        st.markdown("**Distribuciones clínicas**")
        bmi_mean = st.number_input("IMC media", value=28.0, step=0.1)
        bmi_sd   = st.number_input("IMC sd", value=4.5, step=0.1, min_value=0.1)

        hba1c_mean = st.number_input("HbA1c media", value=6.8, step=0.1)
        hba1c_sd   = st.number_input("HbA1c sd", value=1.6, step=0.1, min_value=0.1)

        egfr_mean = st.number_input("eGFR media", value=78.0, step=1.0)
        egfr_sd   = st.number_input("eGFR sd", value=25.0, step=1.0, min_value=1.0)

    with colC:
        st.markdown("**Uplift por región en el score (mock)**")
        regions = REGIONS_MX if ctx["country_name"] == "México" else REGIONS_CO
        uplift_inputs = {}
        for r in regions:
            uplift_inputs[r] = st.slider(f"{r}", -0.50, 0.50, 0.00, 0.01, help="Ajuste aditivo al score lineal")

        st.markdown("**Pesos del mock (escala global)**")
        scale = st.slider("Escala de separación (≥1 = más contraste)", 0.2, 3.0, 1.2, 0.1)

    st.markdown("---")
    st.markdown("**Ajuste fino de pesos (opcional)**")
    wcols = st.columns(4)
    # Valores por defecto (para mostrar en UI); si los cambias, se aplican
    default_w = get_mock_config()["weights"].copy()
    keys = list(default_w.keys())
    # Repartimos los sliders en columnas
    sliders = {}
    for i, k in enumerate(keys):
        with wcols[i % 4]:
            # Rango razonable por tipo
            if k in ("intercept",):
                sliders[k] = st.slider(f"{k}", -5.0, 5.0, float(default_w[k]), 0.05)
            elif k in ("egfr","lab_recency_m"):
                sliders[k] = st.slider(f"{k}", -0.2, 0.2, float(default_w[k]), 0.005)
            elif k in ("age","bmi","hba1c"):
                sliders[k] = st.slider(f"{k}", -0.2, 0.3, float(default_w[k]), 0.005)
            elif k in ("utilizations_12m",):
                sliders[k] = st.slider(f"{k}", 0.0, 0.30, float(default_w[k]), 0.005)
            else:
                sliders[k] = st.slider(f"{k}", 0.0, 1.5, float(default_w[k]), 0.01)

    submitted = st.form_submit_button("Generar y puntuar CSV")

if submitted:
    # 1) Generar población
    df = generate_dummy_population(
        n=int(n),
        country = f"{ctx['country_name']} - {ctx['payer_model']}",
        seed=int(seed),
        p_smoker=float(p_smoker),
        p_dm=float(p_dm),
        p_hta=float(p_hta),
        p_ckd=float(p_ckd),
        p_prev_event=float(p_prev),
        bmi_mean=float(bmi_mean), bmi_sd=float(bmi_sd),
        hba1c_mean=float(hba1c_mean), hba1c_sd=float(hba1c_sd),
        egfr_mean=float(egfr_mean), egfr_sd=float(egfr_sd),
        region_weights=None  # si quisieras sesgar la cantidad por región, podrías exponer sliders aparte
    )

    # 2) Configurar mock de riesgo y puntuar
    cfg = {
        "weights": sliders,
        "region_uplift": {k: float(v) for k, v in uplift_inputs.items() if abs(v) > 1e-9},
        "scale": float(scale),
        "clip": (0.0, 0.92),
    }
    set_mock_config(cfg)
    scored = score_population(df)

    # 3) Muestra y descarga
    st.success("¡Listo! Datos generados y puntuados.")
    st.dataframe(scored.head(25), use_container_width=True)

    # Pequeño resumen por decil para verificar separación
    try:
        deciles = pd.qcut(scored["risk_factor"], 10, labels=[f"D{i}" for i in range(1,11)], duplicates="drop")
        summary = scored.assign(decile=deciles).groupby("decile", observed=False).agg(
            n=("patient_id","count"),
            risk_mean=("risk_factor","mean"),
            risk_p75=("risk_factor", lambda s: s.quantile(0.75)),
            risk_p25=("risk_factor", lambda s: s.quantile(0.25))
        ).reset_index()
        st.subheader("Resumen por decil (verifica la separación)")
        st.dataframe(summary, use_container_width=True)
    except Exception as e:
        st.info(f"No se pudo calcular deciles: {e!r}")

    # Descargar CSV
    buf = io.StringIO()
    scored.to_csv(buf, index=False)
    st.download_button(
        "📥 Descargar CSV",
        data=buf.getvalue().encode("utf-8"),
        file_name=f"cohorte_sintetica_{ctx['country_code']}_{int(n)}.csv",
        mime="text/csv"
    )

else:
    st.info("Configura los parámetros y pulsa **Generar y puntuar CSV** para crear tu archivo.")
