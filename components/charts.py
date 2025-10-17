# components/charts.py
# -----------------------------------------------
# Gráficos reutilizables para el piloto de CorpusAI
# -----------------------------------------------

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

__all__ = ["risk_hist", "region_heat", "survival_deciles", "top_features_bar", "scenario_bars"]

# Altair sin límite de filas (por si pasas DF grandes)
try:
    alt.data_transformers.disable_max_rows()
except Exception:
    pass


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
    months = np.arange(1, 13, dtype=int)
    records = []

    def _cum_from_base(base: float) -> np.ndarray:
        # ✅ MUY IMPORTANTE: crear vector en FLOAT para evitar truncamiento a 0
        step = float(base) / 12.0
        return np.cumsum(np.full(len(months), step, dtype=float))

    if not seg_ok or force_single:
        base = float(df["risk_factor"].mean() or 0.05)
        cum = _cum_from_base(base)
        for m, c in zip(months, cum):
            records.append({"decile": "Cohorte", "month": int(m), "cum_risk": float(min(c, 0.95))})
        seg_counts = None
    else:
        # Curvas por grupo
        for d, sub in df.dropna(subset=["risk_decile"]).groupby("risk_decile", observed=False):
            base = float(sub["risk_factor"].mean() or 0.05)
            cum = _cum_from_base(base)
            for m, c in zip(months, cum):
                records.append({"decile": str(d), "month": int(m), "cum_risk": float(min(c, 0.95))})

        # Conteo robusto (y preserva orden de categorías)
        vc = df["risk_decile"].value_counts(dropna=False)
        seg_counts = pd.DataFrame({"group": vc.index.astype(str), "n": vc.values})
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


# ---------------------------------------------------
# 4) Barras de “feature contributions” (suscripción)
# ---------------------------------------------------
def top_features_bar(contribs, top_n: int = 10, title: str = "Contribución al riesgo (±)") -> None:
    """
    Dibuja barras horizontales con contribuciones (positivas/negativas).
    - `contribs` puede ser dict {feature: value} o DataFrame con
      columnas ['feature', 'contribution'] (se intentan inferencias).
    """
    # Normalización de input
    if isinstance(contribs, dict):
        df = pd.DataFrame({"feature": list(contribs.keys()), "contribution": list(contribs.values())})
    else:
        df = pd.DataFrame(contribs).copy()
        # Intento de inferir nombres
        cols = {c.lower(): c for c in df.columns}
        fcol = cols.get("feature") or cols.get("name") or list(df.columns)[0]
        vcol = cols.get("contribution") or cols.get("value") or list(df.columns)[1]
        df = df.rename(columns={fcol: "feature", vcol: "contribution"})[["feature", "contribution"]]

    if df.empty:
        st.info("No hay contribuciones para mostrar.")
        return

    df["abs"] = df["contribution"].abs()
    df = df.sort_values("abs", ascending=False).head(top_n)
    df["sign"] = np.where(df["contribution"] >= 0, "Aumenta riesgo", "Disminuye riesgo")

    chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("contribution:Q", title="Contribución"),
            y=alt.Y("feature:N", sort="-x", title=None),
            color=alt.Color("sign:N", title="Signo", scale=alt.Scale(domain=["Aumenta riesgo","Disminuye riesgo"], range=["#1f77b4", "#aec7e8"])),
            tooltip=["feature", alt.Tooltip("contribution:Q", format=".4f"), "sign"],
        )
        .properties(height=28 * len(df) + 20, title=title)
    )

    # Etiquetas al final de las barras
    text = chart.mark_text(
        align="left",
        dx=4
    ).encode(
        text=alt.Text("contribution:Q", format=".3f")
    )

    st.altair_chart(chart + text, use_container_width=True)


# --------------------------------------------
# 5) Barras de escenarios (simulador financiero)
# --------------------------------------------
def scenario_bars(data, x=None, y=None, color=None, title: str = "Escenarios") -> None:
    """
    Dibuja barras comparativas de escenarios.
    Acepta:
      - list[dict], dict, o DataFrame.
    Modos:
      - Largo (recomendado): columnas ['scenario','metric','value'].
      - Ancho: columnas ['scenario', <métricas...>] -> se "melt".
      - Sencillo: columnas ['name','value'] o dict simple -> una sola métrica.
    Parámetros x/y/color se infieren si no se pasan.
    """
    # Normaliza a DataFrame
    if isinstance(data, dict):
        # dict simple -> una métrica
        df = pd.DataFrame([{"scenario": k, "value": v} for k, v in data.items()])
    elif isinstance(data, list):
        df = pd.DataFrame(data)
    else:
        df = pd.DataFrame(data).copy()

    if df.empty:
        st.info("No hay datos de escenarios para graficar.")
        return

    cols_low = [c.lower() for c in df.columns]
    colmap = {c.lower(): c for c in df.columns}

    # Intento automático de forma larga
    if {"scenario", "metric", "value"}.issubset(set(cols_low)):
        scenario_col = colmap["scenario"]
        metric_col = colmap["metric"]
        value_col = colmap["value"]
        long_df = df[[scenario_col, metric_col, value_col]].rename(columns={
            scenario_col: "scenario", metric_col: "metric", value_col: "value"
        })
    else:
        # ¿Ancho con 'scenario'?
        if "scenario" in cols_low:
            scenario_col = colmap["scenario"]
            metric_cols = [c for c in df.columns if c != scenario_col]
            if len(metric_cols) == 0:
                # Sencillo: renombrar como value
                long_df = df.rename(columns={df.columns[0]: "scenario", df.columns[1]: "value"})
                long_df["metric"] = "valor"
                long_df = long_df[["scenario", "metric", "value"]]
            else:
                long_df = df.melt(id_vars=[scenario_col], var_name="metric", value_name="value")
                long_df = long_df.rename(columns={scenario_col: "scenario"})
        else:
            # Sencillo: columnas ['name','value'] o dos columnas cualquiera
            if set(["name", "value"]).issubset(set(cols_low)):
                long_df = df.rename(columns={colmap["name"]: "scenario", colmap["value"]: "value"})
                long_df["metric"] = "valor"
                long_df = long_df[["scenario", "metric", "value"]]
            elif df.shape[1] >= 2:
                long_df = df.iloc[:, :2].copy()
                long_df.columns = ["scenario", "value"]
                long_df["metric"] = "valor"
                long_df = long_df[["scenario", "metric", "value"]]
            else:
                st.info("Estructura de esce
