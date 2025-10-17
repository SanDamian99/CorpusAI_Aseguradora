# services/risk_api.py
import numpy as np
import pandas as pd

def _sigmoid(x): return 1/(1+np.exp(-x))

def score_row(row, rng=None):
    rng = rng or np.random.default_rng()
    # Modelo lineal sintético con señales clínicas razonables
    lin = (
        0.015*(row.get("age", 50)-50) +
        0.03*(row.get("bmi", 27)-27) +
        0.25*(row.get("dm",0)) +
        0.20*(row.get("hta",0)) +
        0.18*(row.get("ckd",0)) +
        0.02*(row.get("smoker",0)) +
        -0.008*(row.get("egfr",80)-80) +
        0.06*(row.get("hba1c",6.5)-6.5) +
        0.04*(row.get("prev_event",0)) +
        0.02*(row.get("utilizations_12m",0))
    )
    rf = float(_sigmoid(lin) * 0.6)  # escala max ~0.6
    # Rango temporal más cercano si riesgo alto
    tw = [1, 6] if rf >= 0.3 else [6, 12]
    # Curva de “supervivencia” sintética (riesgo acumulado)
    months = np.arange(1, 13)
    cum = np.cumsum(np.full_like(months, rf/12))
    risk_curve = [{"month": int(m), "cum_risk": float(min(0.95, c))} for m,c in zip(months, cum)]
    # Explicabilidad dummy (top_features)
    feats = [
        ("eGFR bajo", max(0, 80 - row.get("egfr",80)) / 80),
        ("HbA1c alto", max(0, row.get("hba1c",6.5) - 6.5) / 6.5),
        ("HTA", row.get("hta",0)),
        ("DM", row.get("dm",0)),
        ("IMC alto", max(0, row.get("bmi",27) - 27) / 27),
    ]
    contribs = np.array([f[1] for f in feats], dtype=float)
    if contribs.sum() > 0:
        contribs = contribs / contribs.sum()
    features = [{"name": n, "contrib": float(v)} for (n,_), v in zip(feats, contribs)]

    # “Care gaps” sintéticos
    care_gaps = []
    if row.get("lab_recency_m", 99) > 12: care_gaps.append("Laboratorio desactualizado")
    if row.get("hta",0) and not "C09" in str(row.get("meds_atc","")): care_gaps.append("Sin IECA/ARA-II")
    if row.get("dm",0) and row.get("hba1c",7.5) > 8.0: care_gaps.append("HbA1c fuera de meta")

    return {
        "risk_factor": rf,
        "time_window_months": tw,
        "risk_curve": risk_curve,
        "top_features": features,
        "care_gaps": care_gaps,
        "cohort_label": "DM+ERC" if (row.get("dm",0) and row.get("ckd",0)) else "General"
    }

def score_batch(df, seed=123):
    rng = np.random.default_rng(seed)
    records = []
    for _,row in df.iterrows():
        r = score_row(row, rng)
        records.append(r)
    out = df.copy()
    out["risk_factor"] = [r["risk_factor"] for r in records]
    out["tw_start"] = [r["time_window_months"][0] for r in records]
    out["tw_end"] = [r["time_window_months"][1] for r in records]
    out["care_gaps"] = [", ".join(r["care_gaps"]) for r in records]
    out["cohort_label"] = [r["cohort_label"] for r in records]
    return out, records

def score_one(payload: dict):
    # payload simula lo que vendría desde formulario de suscripción
    return score_row(payload)
