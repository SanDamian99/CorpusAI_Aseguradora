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

def survival_deciles(df):
    """Curvas acumuladas por 'deciles' (robusta a cohortes pequeños o pocos valores únicos)."""
    if df.empty or "risk_factor" not in df:
        st.info("No hay datos de cohorte para graficar.")
        return

    df = df.copy()
    # Número de quantiles posible (máx 10, mín 2)
    unique_vals = df["risk_factor"].nunique(dropna=True)
    q = int(max(2, min(10, unique_vals, len(df))))  # asegura al menos 2 líneas

    try:
        df["risk_decile"] = pd.qcut(
            df["risk_factor"],
            q,
            labels=[f"D{i}" for i in range(1, q+1)],
            duplicates="drop"
        )
    except Exception:
        # Fallback a 'cut' equiespaciado si qcut falla por bordes duplicados
        df["risk_decile"] = pd.cut(
            df["risk_factor"],
            q,
            labels=[f"D{i}" for i in range(1, q+1)]
        )

    # Si todo quedó NaN (caso extremo), mostramos 1 sola curva “cohorte”
    if df["risk_decile"].isna().all():
        base = float(df["risk_factor"].mean() or 0.05)
        months = np.arange(1, 13)
        cum = np.cumsum(np.full_like(months, base/12))
        data = pd.DataFrame({
            "decile": ["Cohorte"] * len(months),
            "month": months.astype(int),
            "cum_risk": np.minimum(cum, 0.95).astype(float)
        })
    else:
        months = np.arange(1, 13)
        recs = []
        for d, sub in df.dropna(subset=["risk_decile"]).groupby("risk_decile"):
            base = float(sub["risk_factor"].mean() or 0.05)
            cum = np.cumsum(np.full_like(months, base/12))
            for m, c in zip(months, cum):
                recs.append({"decile": str(d), "month": int(m), "cum_risk": float(min(c, 0.95))})
        data = pd.DataFrame(recs)

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
