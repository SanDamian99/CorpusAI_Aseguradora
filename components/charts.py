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
        st.info("No hay columndef survival_deciles(df, debug: bool = False):
    """Curvas acumuladas por 'deciles' (robusta y con panel de debug opcional)."""
    # ---------- Guardas ----------
    if df is None or df.empty:
        st.info("No hay datos de cohorte para graficar.")
        if debug:
            with st.expander("DEBUG — survival_deciles", expanded=True):
                st.write("df es None o vacío.")
        return
    if "risk_factor" not in df.columns:
        st.info("No hay columna 'risk_factor' en la cohorte.")
        if debug:
            with st.expander("DEBUG — survival_deciles", expanded=True):
                st.write("Columnas disponibles:", list(df.columns))
        return

    # ---------- Preparación ----------
    df = df.copy()
    # Coerción numérica y limpieza
    df["risk_factor"] = pd.to_numeric(df["risk_factor"], errors="coerce")
    before = len(df)
    df = df.dropna(subset=["risk_factor"])
    after = len(df)

    # Métricas base para debug
    n = len(df)
    nunique = df["risk_factor"].nunique(dropna=True)
    rf_desc = df["risk_factor"].describe() if n else None
    q_try = int(max(2, min(10, nunique, n)))  # 2..10

    # ---------- Panel de debug (previo) ----------
    qtiles = None
    if debug:
        with st.expander("DEBUG — survival_deciles (insumos)", expanded=True):
            st.write(f"Registros (original/coerción/NaN drop): {before} → {after} → {n}")
            st.write(f"Valores únicos risk_factor: {nunique}")
            st.write(f"q (número de grupos): {q_try}")
            if rf_desc is not None:
                st.write("describe(risk_factor):", rf_desc.to_frame().T)
            # quantiles “target” que intentará qcut
            try:
                qtiles = df["risk_factor"].quantile(np.linspace(0, 1, q_try + 1)).round(6)
                st.write("Quantiles estimados:", qtiles)
            except Exception as e:
                st.write("Fallo al calcular quantiles:", repr(e))

    if n == 0:
        st.info("No hay 'risk_factor' válido para graficar.")
        return

    # ---------- Segmentación por 'deciles' (o grupos) ----------
    seg_ok = True
    try:
        df["risk_decile"] = pd.qcut(
            df["risk_factor"],
            q_try,
            labels=[f"D{i}" for i in range(1, q_try + 1)],
            duplicates="drop",
        )
    except Exception as e:
        seg_ok = False
        if debug:
            with st.expander("DEBUG — survival_deciles (segmentación)", expanded=True):
                st.write("qcut falló → usar cut. Error:", repr(e))
        # Fallback por rangos equiespaciados
        try:
            df["risk_decile"] = pd.cut(
                df["risk_factor"],
                q_try,
                labels=[f"D{i}" for i in range(1, q_try + 1)],
                include_lowest=True,
            )
            seg_ok = True
        except Exception as e2:
            if debug:
                st.write("cut también falló:", repr(e2))

    # Si tras segmentar todo quedó NaN, forzamos curva única
    force_single = df["risk_decile"].isna().all()

    # ---------- Construcción de la data a graficar ----------
    months = np.arange(1, 13)
    records = []

    if not seg_ok or force_single:
        # Curva única (Cohorte)
        base = float(df["risk_factor"].mean() or 0.05)
        cum = np.cumsum(np.full_like(months, base / 12.0))
        for m, c in zip(months, cum):
            records.append({"decile": "Cohorte", "month": int(m), "cum_risk": float(min(c, 0.95))})
        seg_counts = None
    else:
        # Curvas por grupo
        for d, sub in df.dropna(subset=["risk_decile"]).groupby("risk_decile", observed=False):
            base = float(sub["risk_factor"].mean() or 0.05)
            cum = np.cumsum(np.full_like(months, base / 12.0))
            for m, c in zip(months, cum):
                records.append({"decile": str(d), "month": int(m), "cum_risk": float(min(c, 0.95))})
        # Conteos por grupo para debug
        seg_counts = (
            df["risk_decile"].value_counts(dropna=False)
            .rename("n")
            .to_frame()
            .reset_index()
            .rename(columns={"index": "group"})
            .sort_values("group")
        )

    data = pd.DataFrame(records)

    # ---------- Panel de debug (posterior) ----------
    if debug:
        with st.expander("DEBUG — survival_deciles (salida)", expanded=True):
            st.write("¿Segmentación OK?:", seg_ok, " — ¿Curva única?:", force_single)
            if seg_counts is not None:
                st.write("Conteos por grupo:", seg_counts)
            st.write("Head de 'data' que se grafica:", data.head())

    # ---------- Guardas finales ----------
    if data.empty:
        st.warning("No fue posible construir la curva de riesgo acumulado (data vacía).")
        return

    # ---------- Gráfico ----------
    chart = alt.Chart(data).mark_line().encode(
        x=alt.X("month:Q", title="Mes"),
        y=alt.Y("cum_risk:Q", title="Riesgo acumulado", scale=alt.Scale(domain=[0, 1])),
        color=alt.Color("decile:N", title="Decil"),
        tooltip=["decile", "month", "cum_risk"],
    ).properties(height=260)

    st.altair_chart(chart, use_container_width=True)
