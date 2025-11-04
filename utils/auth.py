# utils/auth.py
import streamlit as st

ROLES = ["Director Médico / VP Salud", "Actuario / CFO", "Gestor de Casos", "Auditor Médico"]
COUNTRIES = ["México - SGMM", "Colombia - EPS" ]

def role_country_selector():
    with st.sidebar:
        country = st.selectbox("País / Modelo", COUNTRIES, index=0, key="country_select")
        role = st.selectbox("Rol", ROLES, index=0, key="role_select")
        st.caption("Vista piloto con datos sintéticos (no reales).")
    st.session_state.setdefault("country", country)
    st.session_state.setdefault("role", role)
    return country, role
