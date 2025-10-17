# components/charts.py
import altair as alt
import pandas as pd
import numpy as np
import streamlit as st

def risk_hist(df):
    data = df[["risk_factor"]].copy()
    data["bin"] = (data["risk_factor"]*10).astype(int)/10
    agg = data.groupby("bin", as_index=False).size()
    chart = alt.Chart(agg).mark_bar().encode(
        x=alt.X("bin:Q", title="Riesgo (binned, 0-1)", bin=alt.Bin(step=0.1)),
        y=alt.Y("size:Q", title="Pacientes"),
        tooltip=["bin","size"]
    ).properties(height=200)
    st.altair_chart(chart, use_container_width=True)

def region_heat(df):
    # Mapa abstracto tipo heat (no geográfico), por región
    agg = df.groupby("region", as_index=False).agg(
        avg_risk=("risk_factor","mean"),
        n=("patient_id","count"),
    )
    chart = alt.Chart(agg).mark_rect(cornerRadius=6).encode(
        x=alt.X("region:N", title="Región"),
        y=alt.Y("n:Q", title="Tamaño cohorte", scale=alt.Scale(type="sqrt")),
        color=alt.Color("avg_risk:Q", title="Riesgo prom.", scale=alt.Scale(scheme="orangered")),
        tooltip=["region","n","avg_risk"]
    ).properties(height=200)
    st.altair_chart(chart, use_container_width=True)


def survival_deciles(df, debug: bool = False):
    """Curvas acumuladas por 'deciles' (robusta a cohortes pequeños o pocos valores únicos).
    Si debug=True, imprime trazas (en logs) y muestra st.write con info.
    """
    if df is None or df.empty:
        if debug: 
            print("[survival_deciles] df vacío")
            st.write("DEBUG: df vacío")
        st.info("No hay datos de cohorte para graficar.")
        return

    if "risk_factor" not in df.columns:
        if debug:
            print("[survival_deciles] 'risk_factor' no está en columnas:", df.columns.tolist())
            st.write("DEBUG: 'risk_factor' no está en columnas")
        st.info("No hay columna 'risk_factor' en la cohorte.")
        return

    # Asegurar tipo numérico
    df = df.copy()
    df["risk_factor"] = pd.to_numeric(df["risk_factor"], errors="coerce")
    df = df.dropna(subset=["risk_factor"])
    if df.empty:
        if debug:
            print("[survival_deciles] Todos los 'risk_factor' son NaN tras conversión.")
            st.write("DEBUG: 'risk_factor' quedó sin datos tras coerción")
        st.info("No hay 'risk_factor' válido para graficar.")
        return

    unique_vals = df["risk_factor"].nunique(dropna=True)
    q = int(max(2, min(10, unique_vals, len(df))))  # al menos 2 grupos

    if debug:
        print(f"[survival_deciles] n={len(df)}, unique_vals={unique_vals}, q={q}, mean_rf={df['risk_factor'].mean():.4f}")
        st.caption(f"DEBUG — n={len(df)}, unique_vals={unique_vals}, q={q}, mean_rf={df['risk_factor'].mean():.4f}")

    # Intentar qcut; si falla, usar cut
    try:
        df["risk_decile"] = pd.qcut(
            df["risk_factor"], q,
            labels=[f"D{i}" for i in range(1, q+1)],
            duplicates="drop"
        )
    except Exception as e:
        if debug:
            print("[survival_deciles] qcut falló:", repr(e))
            st.write("DEBUG: qcut falló → uso cut")
        df["risk_decile"] = pd.cut(
            df["risk_factor"], q,
            labels=[f"D{i}" for i in range(1, q+1)]
        )

    if df["risk_decile"].isna().all():
        # Fallback: curva única de cohorte
        base = float(df["risk_factor"].mean() if pd.notnull(df["risk_factor"].mean()) else 0.05)
        months = np.arange(1, 13)
        cum = np.cumsum(np.full_like(months, base/12.0))
        data = pd.DataFrame({
            "decile": ["Cohorte"] * len(months),
            "month": months.astype(int),
            "cum_risk": np.minimum(cum, 0.95).astype(float)
        })
        if debug:
            print("[survival_deciles] fallback única curva — base=", base)
            st.write("DEBUG: fallback única curva — base=", base)
    else:
        # Construir curvas por grupo
        months = np.arange(1, 13)
        recs = []
        for d, sub in df.dropna(subset=["risk_decile"]).groupby("risk_decile", observed=False):
            base = float(sub["risk_factor"].mean() if pd.notnull(sub["risk_factor"].mean()) else 0.05)
            cum = np.cumsum(np.full_like(months, base/12.0))
            for m, c in zip(months, cum):
                recs.append({"decile": str(d), "month": int(m), "cum_risk": float(min(c, 0.95))})
        data = pd.DataFrame(recs)
        if debug:
            # Muestra conteos por decil
            counts = df["risk_decile"].value_counts(dropna=False).to_frame("n")
            print("[survival_deciles] grupos:\n", counts.to_string())
            st.write("DEBUG: grupos por decil", counts)

    if data.empty:
        if debug:
            print("[survival_deciles] 'data' resultó vacío tras construcción")
            st.write("DEBUG: 'data' vacío")
        st.info("No fue posible construir la curva de supervivencia.")
        return

    if debug:
        print("[survival_deciles] muestra data:\n", data.head().to_string())
        st.write("DEBUG: muestra 'data'", data.head())

    chart = alt.Chart(data).mark_line().encode(
        x=alt.X("month:Q", title="Mes"),
        y=alt.Y("cum_risk:Q", title="Riesgo acumulado", scale=alt.Scale(domain=[0, 1])),
        color=alt.Color("decile:N", title="Decil"),
        tooltip=["decile","month","cum_risk"]
    ).properties(height=260)
    st.altair_chart(chart, use_container_width=True)

    
def top_features_bar(top_features):
    df = pd.DataFrame(top_features)
    if df.empty: return
    chart = alt.Chart(df).mark_bar().encode(
        x=alt.X("contrib:Q", title="Contribución"),
        y=alt.Y("name:N", sort="-x", title="Factor"),
        tooltip=["name","contrib"]
    ).properties(height=180)
    st.altair_chart(chart, use_container_width=True)

def scenario_bars(summary_df):
    chart = alt.Chart(summary_df).mark_bar().encode(
        x=alt.X("scenario:N", title="Escenario"),
        y=alt.Y("value:Q", title="Valor"),
        tooltip=["metric","value"],
        color="metric:N"
    ).properties(height=240)
    st.altair_chart(chart, use_container_width=True)
