# Home.py
import streamlit as st
from utils.auth import role_country_selector

st.set_page_config(page_title="Corpus AI | Piloto Aseguradoras", page_icon="💚", layout="wide")

st.title("Corpus AI — Piloto de Interacciones (Aseguradoras)")
st.write("Explora 4 aproximaciones de interfaz enfocadas en clientes **EPS (Colombia)** / **SGMM (México)**.")

country, role = role_country_selector()

st.markdown("""
### Módulos
1. **Dashboard Ejecutivo — Población & Riesgo**: Vista estratégica con KPIs, cohortes y tendencias.
2. **Worklist Operativa — Gestión de Casos**: A quién contactar hoy, brechas y acciones.
3. **Suscripción & Tarificación (SGMM)**: Cotizador con score y sensibilidad de prima.
4. **Simulador Financiero — ROI y ΔPMPM/Loss Ratio**: Escenarios de intervención.
""")

st.info(f"Contexto actual: **{country}** | Rol simulado: **{role}**. (Datos sintéticos)")
st.caption("Nota: Este piloto no usa datos reales ni se conecta a una API de backend.")
