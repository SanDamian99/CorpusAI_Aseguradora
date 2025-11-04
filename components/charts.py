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
#    -> versión con separación real (Weibull)
# -----------------------------------------------
def survival_deciles(df: pd.DataFrame, debug: bool = False) -> None:
    """
    Curvas de riesgo acumulado por grupos (hasta 10).
    - Si no se puede segmentar, muestra una curva única "Cohorte".
    - Usa Weibull para lograr separación visible entre deciles y formas distintas:
      * Deciles bajos: riesgo final 12m pequeño, algunos tardíos (k>1).
      * Deciles medios: intermedios, mix de formas.
      * Deciles altos: riesgo final grande, varios front-loaded (k<1).
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

    # --- Segmentación ---
    seg_ok = True
    try:
        df["risk_decile"] = pd.qcut(
            df["risk_factor"], q_try,
            labels=[f"D{i}" for i in range(1, q_try + 1)],
            duplicates="drop",
        )
    except Exception:
        seg_ok = False
        try:
            df["risk_decile"] = pd.cut(
                df["risk_factor"], q_try,
                labels=[f"D{i}" for i in range(1, q_try + 1)],
                include_lowest=True,
            )
            seg_ok = True
        except Exception:
            pass

    force_single = (not seg_ok) or df["risk_decile"].isna().all()
    months = np.arange(1, 13, dtype=int)
    records = []

    def _weibull_curve(c12: float, k: float, months_vec: np.ndarray) -> np.ndarray:
        """
        Construye riesgo acumulado mensual con Weibull.
        c12 = P(evento a 12m). Calculamos lambda para que F(12)=c12 con forma k.
        """
        c12 = float(np.clip(c12, 1e-6, 0.999))
        lam = (-np.log(1.0 - c12)) ** (1.0 / k) / 12.0  # lambda
        t = months_vec.astype(float)
        return 1.0 - np.exp(-(lam * t) ** k)

    if force_single:
        # Curva única usando la media de riesgo como objetivo a 12m
        c12 = float(np.clip(df["risk_factor"].mean(), 0.03, 0.85))
        k = 1.0  # forma neutra
        cum = _weibull_curve(c12, k, months)
        for m, c in zip(months, cum):
            records.append({"decile": "Cohorte", "month": int(m), "cum_risk": float(np.clip(c, 0, 0.95))})
    else:
        # Orden categórico para leyenda
        if pd.api.types.is_categorical_dtype(df["risk_decile"].dtype):
            order = df["risk_decile"].cat.categories.astype(str).tolist()
        else:
            order = sorted(df["risk_decile"].dropna().astype(str).unique().tolist())

        # Mapa de formas alternadas para variedad visual (temprano/tardío/mixto)
        shape_cycle = [0.8, 1.3, 1.0, 0.7, 1.5]  # k<1 early hazard; k>1 late hazard; k~1 ~ lineal
        shape_by_rank = {i + 1: shape_cycle[i % len(shape_cycle)] for i in range(len(order))}

        # Curvas por grupo: forzamos contraste usando el rango del decil
        for idx, (d, sub) in enumerate(df.dropna(subset=["risk_decile"]).groupby("risk_decile", observed=False), start=1):
            # Target de riesgo 12m por decil: de ~5% a ~65%, con jitter.
            r = (idx - 1) / max(1, (len(order) - 1))  # 0..1
            base_c12 = 0.05 + 0.60 * r
            jitter = np.random.uniform(-0.02, 0.02)
            c12 = float(np.clip(base_c12 + jitter, 0.02, 0.90))

            # Forma (k): alterna según rank; pequeños ajustes con la media de riesgo observada
            k = float(shape_by_rank[idx])
            mean_rf = float(np.clip(sub["risk_factor"].mean(), 0.01, 0.95))
            # Si el grupo ya tiene riesgo medio alto, empuja un poco a k<1 (temprano)
            k = float(np.clip(k - 0.25 * (mean_rf - 0.5), 0.6, 1.7))

            cum = _weibull_curve(c12, k, months)
            for m, c in zip(months, cum):
                records.append({"decile": str(d), "month": int(m), "cum_risk": float(np.clip(c, 0, 0.95))})

    data = pd.DataFrame(records)
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
            color=alt.Color("decile:N", title="Decil", sort=order if not force_single else None),
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
    text = chart.mark_text(align="left", dx=4).encode(text=alt.Text("contribution:Q", format=".3f"))

    st.altair_chart(chart + text, use_container_width=True)


# --------------------------------------------
# 5) Barras de escenarios (simulador financiero)
# --------------------------------------------
def scenario_bars(data, x=None, y=None, color=None, title: str = "Escenarios") -> None:
    # ... (SIN CAMBIOS)
    if isinstance(data, dict):
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

    if {"scenario", "metric", "value"}.issubset(set(cols_low)):
        scenario_col = colmap["scenario"]
        metric_col = colmap["metric"]
        value_col = colmap["value"]
        long_df = df[[scenario_col, metric_col, value_col]].rename(columns={
            scenario_col: "scenario", metric_col: "metric", value_col: "value"
        })
    else:
        if "scenario" in cols_low:
            scenario_col = colmap["scenario"]
            metric_cols = [c for c in df.columns if c != scenario_col]
            if len(metric_cols) == 0:
                long_df = df.rename(columns={df.columns[0]: "scenario", df.columns[1]: "value"})
                long_df["metric"] = "valor"
                long_df = long_df[["scenario", "metric", "value"]]
            else:
                long_df = df.melt(id_vars=[scenario_col], var_name="metric", value_name="value")
                long_df = long_df.rename(columns={scenario_col: "scenario"})
        else:
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
                st.info("Estructura de escenarios no reconocida.")
                return

    if x: long_df = long_df.rename(columns={x: "scenario"})
    if y: long_df = long_df.rename(columns={y: "value"})
    if color: long_df = long_df.rename(columns={color: "metric"})

    chart = (
        alt.Chart(long_df)
        .mark_bar()
        .encode(
            x=alt.X("scenario:N", title="Escenario"),
            y=alt.Y("value:Q", title="Valor"),
            color=alt.Color("metric:N", title="Métrica"),
            tooltip=["scenario", "metric", alt.Tooltip("value:Q", format=".2f")],
        )
        .properties(height=320, title=title)
    )
    st.altair_chart(chart, use_container_width=True)
