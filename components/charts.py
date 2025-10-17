import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

def survival_deciles(df: pd.DataFrame, debug: bool = False) -> None:
    """
    Curvas de riesgo acumulado por grupos (hasta 10).
    - Si no se puede segmentar, muestra una curva única "Cohorte".
    - Con debug=True, muestra paneles con métricas y head de la data graficada.
    """
    # --- Guardas ---
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

    # --- Preparación ---
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

    if debug:
        with st.expander("DEBUG — survival_deciles (insumos)", expanded=True):
            st.write(f"Registros (original → drop NaN): {before} → {after}")
            st.write(f"Registros válidos n={n}")
            st.write(f"Valores únicos risk_factor: {nunique}")
            st.write(f"Grupos (q) a intentar: {q_try}")
            st.write("describe(risk_factor):", df["risk_factor"].describe().to_frame().T)
            try:
                qtiles = df["risk_factor"].quantile(np.linspace(0, 1, q_try + 1)).round(6)
                st.write("Quantiles estimados:", qtiles)
            except Exception as e:
                st.write("Fallo al calcular quantiles:", repr(e))

    # --- Segmentación ---
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
                st.write("qcut falló → uso cut. Error:", repr(e))
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

    # --- Construcción de curvas ---
    months = np.arange(1, 13)
    records = []

    if not seg_ok or force_single:
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

        # ✅ ROBUSTO: construir seg_counts sin depender de nombres implícitos
        vc = df["risk_decile"].value_counts(dropna=False)
        seg_counts = pd.DataFrame({"group": vc.index.astype(str), "n": vc.values})

        # Preservar orden de categorías si aplica (evita 'D1','D10','D2' desordenado)
        if pd.api.types.is_categorical_dtype(df["risk_decile"].dtype):
            order = df["risk_decile"].cat.categories.astype(str).tolist()
            seg_counts["group"] = pd.Categorical(seg_counts["group"], categories=order, ordered=True)
            seg_counts = seg_counts.sort_values("group")

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
            y=alt.Y("cum_risk:Q", title="Riesgo acumulado", scale=alt.Scale(domain=[0, 1])),
            color=alt.Color("decile:N", title="Decil"),
            tooltip=["decile", "month", alt.Tooltip("cum_risk:Q", format=".3f")],
        )
        .properties(height=260)
    )
    st.altair_chart(chart, use_container_width=True)
