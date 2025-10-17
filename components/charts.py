# components/charts.py (solo la función survival_deciles)
import altair as alt
import pandas as pd
import numpy as np
import streamlit as st

def survival_deciles(df, debug: bool = False):
    """Curvas acumuladas por 'deciles' (robusta a cohortes pequeños o pocos valores únicos).
    Si debug=True, imprime trazas y muestra info en la UI.
    """
    if df is None or df.empty:
        if debug: st.write("DEBUG: df vacío"); print("[survival_deciles] df vacío")
        st.info("No hay datos de cohorte para graficar.")
        return

    if "risk_factor" not in df.columns:
        if debug: st.write("DEBUG: falta 'risk_factor'"); print("[survival_deciles] falta 'risk_factor'")
        st.info("No hay columna 'risk_factor' en la cohorte.")
        return

    df = df.copy()
    df["risk_factor"] = pd.to_numeric(df["risk_factor"], errors="coerce")
    df = df.dropna(subset=["risk_factor"])
    if df.empty:
        if debug: st.write("DEBUG: risk_factor quedó NaN"); print("[survival_deciles] risk_factor NaN")
        st.info("No hay 'risk_factor' válido para graficar.")
        return

    unique_vals = df["risk_factor"].nunique(dropna=True)
    q = int(max(2, min(10, unique_vals, len(df))))  # 2..10 grupos
    if debug:
        st.caption(f"DEBUG — n={len(df)}, unique_vals={unique_vals}, q={q}, mean_rf={df['risk_factor'].mean():.4f}")
        print(f"[survival_deciles] n={len(df)} unique={unique_vals} q={q}")

    try:
        df["risk_decile"] = pd.qcut(
            df["risk_factor"], q,
            labels=[f"D{i}" for i in range(1, q+1)],
            duplicates="drop"
        )
    except Exception as e:
        if debug: st.write("DEBUG: qcut falló → cut"); print("[survival_deciles] qcut fail:", repr(e))
        df["risk_decile"] = pd.cut(
            df["risk_factor"], q,
            labels=[f"D{i}" for i in range(1, q+1)]
        )

    # Si no se pudo segmentar, curva única
    if df["risk_decile"].isna().all():
        base = float(df["risk_factor"].mean() or 0.05)
        months = np.arange(1, 13)
        cum = np.cumsum(np.full_like(months, base/12.0))
        data = pd.DataFrame({
            "decile": ["Cohorte"] * len(months),
            "month": months.astype(int),
            "cum_risk": np.minimum(cum, 0.95).astype(float)
        })
        if debug: st.write("DEBUG: fallback curva única — base", base); print("[survival_deciles] fallback base", base)
    else:
        months = np.arange(1, 13)
        recs = []
        # observed=False para mantener compatibilidad y evitar FutureWarning
        for d, sub in df.dropna(subset=["risk_decile"]).groupby("risk_decile", observed=False):
            base = float(sub["risk_factor"].mean() or 0.05)
            cum = np.cumsum(np.full_like(months, base/12.0))
            for m, c in zip(months, cum):
                recs.append({"decile": str(d), "month": int(m), "cum_risk": float(min(c, 0.95))})
        data = pd.DataFrame(recs)
        if debug:
            counts = df["risk_decile"].value_counts(dropna=False).to_frame("n")
            st.write("DEBUG: grupos por decil", counts)
            print("[survival_deciles] grupos:\n", counts.to_string())

    if data.empty:
        if debug: st.write("DEBUG: data vacío"); print("[survival_deciles] data vacío")
        st.info("No fue posible construir la curva de supervivencia.")
        return

    if debug: st.write("DEBUG: muestra data", data.head()); print("[survival_deciles] head:\n", data.head().to_string())

    chart = alt.Chart(data).mark_line().encode(
        x=alt.X("month:Q", title="Mes"),
        y=alt.Y("cum_risk:Q", title="Riesgo acumulado", scale=alt.Scale(domain=[0, 1])),
        color=alt.Color("decile:N", title="Decil"),
        tooltip=["decile","month","cum_risk"]
    ).properties(height=260)
    st.altair_chart(chart, use_container_width=True)
