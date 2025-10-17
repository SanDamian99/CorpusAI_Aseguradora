# components/charts.py
# -----------------------------------------------
# Gráficos reutilizables para el piloto de CorpusAI
# -----------------------------------------------

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st


# ---------------------------
# 1) Histograma de riesgo
# ---------------------------
def risk_hist(df: pd.DataFrame) -> None:
    """Histograma de risk_factor con bins automáticos."""
    if df is None or df.empty or "risk_factor" not in df.columns:
        st.info("No hay datos de riesgo para graficar el histograma.")
        return

    data = df[["risk_factor"]].dropna()
    if data.empty:
        st.info("No hay valores válidos de 'risk_factor' para el histograma.")
        return

    chart = (
        alt.Chart(data)
        .mark_bar()
        .encode(
            x=alt.X("risk_factor:Q", bin=alt.Bin(maxbins=30), title="Riesgo"),
            y=alt.Y("count():Q", title="Pacientes"),
            tooltip=[alt.Tooltip("count():Q", title="N")],
        )
        .properties(height=260)
    )
    st.altair_chart(chart, use_container_width=True)


# ---------------------------
# 2) “Heat” por región
# ---------------------------
def region_heat(df: pd.DataFrame) -> None:
    """Barra coloreada por región según riesgo promedio (heat simple)."""
    if (
        df is None
        or df.empty
        or "region" not in df.columns
        or "risk_factor" not in df.columns
    ):
        st.info("No hay datos suficientes para graficar el 'heat' por región.")
        return

    agg = (
        df.groupby("region", as_index=False, observed=False)
        .agg(risk_mean=("risk_factor", "mean"), n=("patient_id", "count"))
        .sort_values("risk_mean", ascending=False)
    )

    if agg.empty:
        st.info("No hay agregaciones para mostrar por región.")
        return

    chart = (
        alt.Chart(agg)
        .mark_bar()
        .encode(
            y=alt.Y("region:N", title="Región", sort="-x"),
            x=alt.X("risk_mean:Q", title="Riesgo promedio"),
            color=alt.Color(
                "risk_mean:Q", title="Riesgo promedio", scale=alt.Scale(scheme="blues")
            ),
            tooltip=["region", "n", alt.Tooltip("risk_mean:Q", format=".3f")],
        )
        .properties(height=260)
    )
    st.altair_chart(chart, use_container_width=True)


# -----------------------------------------------
# 3) Curvas acumuladas por (hasta) 10 “deciles”
#    (versión robusta con panel de debug opcional)
# -----------------------------------------------
def survival_deciles(df: pd.DataFrame, debug: bool = False) -> None:
    """
    Dibuja curvas de riesgo acumulado por grupos (hasta 10).
    - Si la segmentación por quantiles no es posible, muestra una curva única "Cohorte".
    - Con debug=True, muestra paneles con métricas, quantiles y head de la data graficada.
    """
    # --- Guardas básicas ---
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

    # --- Preparación: coerción numérica y limpieza ---
    df = df.copy()
    df["risk_factor"] = pd.to_numeric(df["risk_factor"], errors="coerce")
    before = len(df)
    df = df.dropna(subset=["risk_factor"])
    after = len(df)

    n = len(df)
    if n == 0:
        st.info("No hay 'risk_factor' válido para graficar.")
        if debug:
            with st.expander("DEBUG — survival_deciles", expanded=True):
                st.write(f"Registros (original → válidos): {before} → {after} → {n}")
        return

    nunique = df["risk_factor"].nunique(dropna=True)
    q_try = int(max(2, min(10, nunique, n)))  # 2..10 grupos

    rf_desc = df["risk_factor"].describe()
    if debug:
        with st.expander("DEBUG — survival_deciles (insumos)", expanded=True):
            st.write(f"Registros (original → drop NaN): {before} → {after}")
            st.write(f"Registros válidos n={n}")
            st.write(f"Valores únicos de risk_factor: {nunique}")
            st.write(f"Grupos (q) que se intentarán: {q_try}")
            st.write("describe(risk_factor):", rf_desc.to_frame().T)
            try:
                qtiles = df["risk_factor"].quantile(np.linspace(0, 1, q_try + 1)).round(6)
                st.write("Quantiles estimados:", qtiles)
            except Exception as e:
                st.write("Fallo al calcular quantiles:", repr(e))

    # --- Segmentación por quantiles (qcut) con fallback a cut ---
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

    force_single = df["risk_decile"].isna().all()

    # --- Construcción de datos de salida ---
    months = np.arange(1, 13)
    records = []

    if not seg_ok or force_single:
        # Curva única (Cohorte)
        base = float(df["risk_factor"].mean() or 0.05)
        cum = np.cumsum(np.full_like(months, base / 12.0))
        for m, c in zip(months, cum):
            records.append(
                {"decile": "Cohorte", "month": int(m), "cum_risk": float(min(c, 0.95))}
            )
        seg_counts = None
    else:
        for d, sub in df.dropna(subset=["risk_decile"]).groupby(
            "risk_decile", observed=False
        ):
            base = float(sub["risk_factor"].mean() or 0.05)
            cum = np.cumsum(np.full_like(months, base / 12.0))
            for m, c in zip(months, cum):
                records.append(
                    {
                        "decile": str(d),
                        "month": int(m),
                        "cum_risk": float(min(c, 0.95)),
                    }
                )

        # ✅ ROBUSTO: nombra siempre la columna del índice como 'group'
        seg_counts = (
            df["risk_decile"]
            .value_counts(dropna=False)
            .rename("n")
            .rename_axis("group")   # <- aquí definimos el nombre del índice
            .reset_index()          # <- ahora 'group' es columna segura
            .sort_values("group")
        )

    data = pd.DataFrame(records)

    # --- Debug de salida ---
    if debug:
        with st.expander("DEBUG — survival_deciles (salida)", expanded=True):
            st.write("¿Segmentación OK?:", seg_ok, " — ¿Curva única?:", force_single)
            if seg_counts is not None:
                st.write("Conteos por grupo:", seg_counts)
            st.write("Head de 'data' (lo que se grafica):", data.head())

    if data.empty:
        st.warning("No fue posible construir la curva de riesgo acumulado (data vacía).")
        return

    # --- Gráfico ---
    chart = (
        alt.Chart(data)
        .mark_line()
        .encode(
            x=alt.X("month:Q", title="Mes"),
            y=alt.Y(
                "cum_risk:Q", title="Riesgo acumulado", scale=alt.Scale(domain=[0, 1])
            ),
            color=alt.Color("decile:N", title="Decil"),
            tooltip=["decile", "month", alt.Tooltip("cum_risk:Q", format=".3f")],
        )
        .properties(height=260)
    )
    st.altair_chart(chart, use_container_width=True)
