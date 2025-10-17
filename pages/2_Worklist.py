# pages/2_Worklist.py
import streamlit as st
import pandas as pd
from utils.auth import role_country_selector
from services.data_io import generate_dummy_population
from services.risk_api import score_batch
from components.cohort_filters import cohort_builder

st.set_page_config(page_title="Worklist Operativa", page_icon="🗂️", layout="wide")

country, role = role_country_selector()

@st.cache_data(show_spinner=False)
def get_scored_population(country):
    df = generate_dummy_population(n=1500, country=country, seed=7)
    df_scored, _ = score_batch(df, seed=55)
    # “Proximidad temporal” sintética para ordenar: menor tw_start primero
    df_scored["urgency"] = df_scored["risk_factor"] * (1.0 / (df_scored["tw_start"] + 0.1))
    return df_scored

df = get_scored_population(country)
st.header("Worklist Operativa — Gestión de Casos")

mask, desc = cohort_builder(df)
sub = df[mask].copy()
st.caption(f"Filtro: {desc}")

# Orden priorizado
sub = sub.sort_values(["tw_start","risk_factor","urgency"], ascending=[True, False, False])

# Tabla editable con “siguiente acción”
actions = ["Llamar", "Agendar control", "Recordatorio SMS", "Referir a nefrología", "Sin acción"]
if "actions_log" not in st.session_state:
    st.session_state["actions_log"] = []

st.write("**Bandeja priorizada (Top 300)**")
edit_cols = ["patient_id","age","sex","region","risk_factor","tw_start","tw_end","care_gaps","next_action","nota"]
view = sub.head(300).copy()
view["next_action"] = ""
view["nota"] = ""
edited = st.data_editor(
    view[edit_cols],
    use_container_width=True,
    num_rows="fixed",
    column_config={
        "risk_factor": st.column_config.NumberColumn(format="%.3f"),
        "next_action": st.column_config.SelectboxColumn(options=actions),
        "nota": st.column_config.TextColumn(max_chars=120),
    },
    key="worklist_table"
)

with st.form("commit_actions"):
    st.write("Selecciona filas y registra las acciones.")
    selected_rows = st.multiselect("Filas seleccionadas (índices)", options=edited.index.tolist())
    submitted = st.form_submit_button("Registrar acciones")
    if submitted:
        for idx in selected_rows:
            row = edited.loc[idx].to_dict()
            st.session_state["actions_log"].append({
                "patient_id": row["patient_id"],
                "action": row["next_action"],
                "note": row["nota"],
                "risk_factor": row["risk_factor"],
                "tw": (row["tw_start"], row["tw_end"])
            })
        st.success(f"Acciones registradas: {len(selected_rows)}")

with st.expander("Bitácora de acciones", expanded=False):
    if st.session_state["actions_log"]:
        st.dataframe(pd.DataFrame(st.session_state["actions_log"]), use_container_width=True)
    else:
        st.caption("Aún no hay acciones registradas.")
