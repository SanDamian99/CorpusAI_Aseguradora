# utils/auth.py
import streamlit as st
from typing import Dict

# -----------------------------
# Configuración y mapeos globales
# -----------------------------
ROLES = [
    "Director Médico / VP Salud",
    "Actuario / CFO",
    "Gestor de Casos",
    "Auditor Médico",
]

# Opción combinada País/Modelo (compatible con tu código existente)
COUNTRIES = ["México - SGMM", "Colombia - EPS"]

# Metadatos derivados por opción
_COUNTRY_META: Dict[str, Dict[str, str]] = {
    "México - SGMM":   {"country_name": "México",   "country_code": "MX", "payer_model": "SGMM"},
    "Colombia - EPS":  {"country_name": "Colombia",  "country_code": "CO", "payer_model": "EPS"},
}
# Para hidratar desde query param ?country=MX|CO
_CODE_TO_OPTION = {"MX": "México - SGMM", "CO": "Colombia - EPS"}

_DEFAULT_OPTION = "México - SGMM"  # ← México default como pediste
_DEFAULT_ROLE = ROLES[0]


# -----------------------------
# Helpers internos
# -----------------------------
def _apply_country(choice: str) -> None:
    """Escribe en session_state la selección y sus derivados."""
    meta = _COUNTRY_META.get(choice, _COUNTRY_META[_DEFAULT_OPTION])
    st.session_state["country"] = choice                       # cadena combinada (p.ej. "México - SGMM")
    st.session_state["country_name"] = meta["country_name"]    # "México" | "Colombia"
    st.session_state["country_code"] = meta["country_code"]    # "MX" | "CO"
    st.session_state["payer_model"] = meta["payer_model"]      # "SGMM" | "EPS"
    # Mantén sincronizado el valor del selectbox si existe
    st.session_state["country_select"] = choice


def _hydrate_from_url() -> None:
    """Lee ?country=MX|CO|texto y aplica país una sola vez si corresponde."""
    try:
        qp = dict(st.query_params)
    except Exception:
        qp = {}
    raw = qp.get("country")
    if not raw:
        return
    if isinstance(raw, list):
        raw = raw[0]
    raw = str(raw).strip()
    # Acepta códigos y etiquetas completas
    if raw.upper() in _CODE_TO_OPTION:
        _apply_country(_CODE_TO_OPTION[raw.upper()])
    elif raw in COUNTRIES:
        _apply_country(raw)


def _on_country_change():
    """Callback cuando cambia el select de País/Modelo."""
    choice = st.session_state.get("country_select", _DEFAULT_OPTION)
    _apply_country(choice)
    # Escribe código corto en la URL para persistir entre páginas
    try:
        st.query_params.update({"country": st.session_state["country_code"]})
    except Exception:
        pass
    st.rerun()


def _on_role_change():
    """Callback para reflejar el cambio de rol en session_state."""
    st.session_state["role"] = st.session_state.get("role_select", _DEFAULT_ROLE)


# -----------------------------
# API pública
# -----------------------------
def ensure_context(default_country: str = _DEFAULT_OPTION, default_role: str = _DEFAULT_ROLE) -> None:
    """
    Garantiza que el contexto (país/rol y derivados) exista en session_state.
    - default_country acepta exactamente valores de COUNTRIES.
    """
    # Hidrata desde URL la primera vez, si aplica
    if "country" not in st.session_state:
        _hydrate_from_url()

    # Establece defaults si aún no hay país/rol
    if "country" not in st.session_state:
        _apply_country(default_country)
    else:
        # Asegura que los derivados estén presentes (por si venían de versiones anteriores)
        _apply_country(st.session_state["country"])

    st.session_state.setdefault("role", default_role)
    # Mantén sincronizado el widget role_select si existe
    st.session_state.setdefault("role_select", st.session_state["role"])


def role_country_selector(place: str = "sidebar"):
    """
    Dibuja los selectores de País/Modelo y Rol.
    - `place="sidebar"` (default) o cualquier otro valor para dibujar en el cuerpo.
    - Devuelve (country, role) para compatibilidad con código antiguo.
    """
    ensure_context()  # asegura estado antes de renderizar

    container = st.sidebar if place == "sidebar" else st

    # Índices actuales para no forzar index=0 en cada render
    try:
        c_idx = COUNTRIES.index(st.session_state["country"])
    except ValueError:
        c_idx = COUNTRIES.index(_DEFAULT_OPTION)

    try:
        r_idx = ROLES.index(st.session_state["role"])
    except ValueError:
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

    # Devuelve valores para compatibilidad
    return st.session_state["country"], st.session_state["role"]


def get_context() -> Dict[str, str]:
    """
    Devuelve un dict con:
      - country        (ej. 'México - SGMM')
      - country_name   ('México'|'Colombia')
      - country_code   ('MX'|'CO')
      - payer_model    ('SGMM'|'EPS')
      - role           (rol seleccionado)
    """
    ensure_context()
    return {
        "country": st.session_state["country"],
        "country_name": st.session_state["country_name"],
        "country_code": st.session_state["country_code"],
        "payer_model": st.session_state["payer_model"],
        "role": st.session_state["role"],
    }
