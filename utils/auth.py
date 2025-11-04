# utils/auth.py
import unicodedata
import streamlit as st
from typing import Dict

ROLES = [
    "Director Médico / VP Salud",
    "Actuario / CFO",
    "Gestor de Casos",
    "Auditor Médico",
]

COUNTRIES = ["México - SGMM", "Colombia - EPS"]  # opciones canónicas
_DEFAULT_OPTION = "México - SGMM"
_DEFAULT_ROLE = ROLES[0]

_COUNTRY_META: Dict[str, Dict[str, str]] = {
    "México - SGMM":  {"country_name": "México",  "country_code": "MX", "payer_model": "SGMM"},
    "Colombia - EPS": {"country_name": "Colombia","country_code": "CO", "payer_model": "EPS"},
}
_CODE_TO_OPTION = {"MX": "México - SGMM", "CO": "Colombia - EPS"}

def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = s.encode("ascii", "ignore").decode("ascii")
    return s.strip().lower()

def _resolve_country_option(raw: str) -> str:
    """Mapea 'México'|'MX'|'Colombia'|'CO' o ya canónico a una opción de COUNTRIES."""
    if not raw:
        return _DEFAULT_OPTION
    s = str(raw).strip()
    if s in COUNTRIES:
        return s
    up = s.upper()
    if up in _CODE_TO_OPTION:
        return _CODE_TO_OPTION[up]
    n = _norm(s)
    if n in ("mexico", "mexico - sgmm"):
        return "México - SGMM"
    if n in ("colombia", "colombia - eps"):
        return "Colombia - EPS"
    # fallback seguro
    return _DEFAULT_OPTION

def _apply_country(choice: str) -> None:
    """Escribe en session_state la selección canónica y derivados."""
    opt = _resolve_country_option(choice)
    meta = _COUNTRY_META[opt]
    st.session_state["country"] = opt                    # SIEMPRE en formato canónico
    st.session_state["country_name"] = meta["country_name"]
    st.session_state["country_code"] = meta["country_code"]
    st.session_state["payer_model"] = meta["payer_model"]
    st.session_state["country_select"] = opt

def _hydrate_from_url() -> None:
    try:
        qp = dict(st.query_params)
    except Exception:
        qp = {}
    raw = qp.get("country")
    if not raw:
        return
    if isinstance(raw, list):
        raw = raw[0]
    _apply_country(raw)

def _on_country_change():
    choice = st.session_state.get("country_select", _DEFAULT_OPTION)
    _apply_country(choice)
    try:
        st.query_params.update({"country": st.session_state["country_code"]})
    except Exception:
        pass
    st.rerun()

def _on_role_change():
    st.session_state["role"] = st.session_state.get("role_select", _DEFAULT_ROLE)

def ensure_context(default_country: str = _DEFAULT_OPTION, default_role: str = _DEFAULT_ROLE) -> None:
    # Hidrata una sola vez desde URL si no hay país en estado
    if "country" not in st.session_state:
        _hydrate_from_url()
    # Normaliza cualquier valor previo (e.g., "México", "MX") al formato canónico
    if "country" in st.session_state:
        _apply_country(st.session_state["country"])
    else:
        _apply_country(default_country)

    st.session_state.setdefault("role", default_role)
    st.session_state.setdefault("role_select", st.session_state["role"])

def role_country_selector(place: str = "sidebar"):
    ensure_context()
    container = st.sidebar if place == "sidebar" else st

    try:
        c_idx = COUNTRIES.index(st.session_state["country"])
    except Exception:
        _apply_country(_DEFAULT_OPTION)
        c_idx = COUNTRIES.index(_DEFAULT_OPTION)

    try:
        r_idx = ROLES.index(st.session_state["role"])
    except Exception:
        st.session_state["role"] = _DEFAULT_ROLE
        r_idx = ROLES.index(_DEFAULT_ROLE)

    container.selectbox(
        "País / Modelo",
        COUNTRIES,
        index=c_idx,
        key="country_select",
        on_change=_on_country_change,
        help="Alterna textos, métricas y KPIs (SGMM en México, EPS en Colombia).",
    )
    container.selectbox(
        "Rol",
        ROLES,
        index=r_idx,
        key="role_select",
        on_change=_on_role_change,
    )
    container.caption("Vista piloto con datos sintéticos (no reales).")

    return st.session_state["country"], st.session_state["role"]

def get_context() -> Dict[str, str]:
    ensure_context()
    return {
        "country": st.session_state["country"],             # p.ej. "México - SGMM"
        "country_name": st.session_state["country_name"],   # "México" | "Colombia"
        "country_code": st.session_state["country_code"],   # "MX" | "CO"
        "payer_model": st.session_state["payer_model"],     # "SGMM" | "EPS"
        "role": st.session_state["role"],
    }
