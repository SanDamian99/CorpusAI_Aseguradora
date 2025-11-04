# services/risk_api.py
# ---------------------------------------------------------------------
# Mock de scoring contrastado y estable, 100% compatible con tu API:
# - Mantiene score_row / score_batch / score_one con el MISMO esquema.
# - Añade config global (pesos, uplift regional, escala, clip, umbral).
# - Curva de riesgo mensual con Weibull para separar claramente perfiles.
# - Incluye score_population (opcional) para páginas que lo usen.
# ---------------------------------------------------------------------

import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple, List, Any

# =========================
# Configuración por defecto
# =========================
DEFAULT_CONFIG: Dict[str, Any] = {
    "weights": {
        # intercepto controla la línea base
        "intercept": -2.2,
        # continuas
        "age": 0.015,           # por año
        "bmi": 0.030,           # por 1 unidad
        "hba1c": 0.22,          # por 1%
        "egfr": -0.012,         # por ml/min/1.73m2 (negativo)
        "utilizations_12m": 0.06,
        "lab_recency_m": -0.015,
        # binarias
        "smoker": 0.70,
        "hta": 0.35,
        "dm": 0.55,
        "ckd": 0.65,
        "prev_event": 0.90,
    },
    "region_uplift": {},        # p.ej. {"CDMX": 0.15, "Bogotá": 0.10}
    "scale": 1.0,               # >1 separa más; <1 aplasta
    "clip": (0.0, 0.92),        # tope de riesgo_factor
    "hi_cut": 0.30,             # umbral para ventana 1–6m (se mantiene 0.30 como tenías)
}

_CFG = DEFAULT_CONFIG.copy()

# ==========
# Utilidades
# ==========
def set_mock_config(cfg: Dict) -> None:
    """Actualiza la configuración global del mock de modo seguro."""
    global _CFG
    merged = DEFAULT_CONFIG.copy()
    for k, v in (cfg or {}).items():
        if isinstance(v, dict) and k in merged:
            tmp = merged[k].copy()
            tmp.update(v)
            merged[k] = tmp
        else:
            merged[k] = v
    _CFG = merged

def get_mock_config() -> Dict:
    return _CFG

def _sigmoid(x):  # mantiene tu firma original
    return 1.0 / (1.0 + np.exp(-x))

def _weibull_curve(c12: float, k: float, months: np.ndarray) -> np.ndarray:
    """
    Genera riesgo acumulado mensual F(t)=1-exp(-(λ t)^k)
    con λ tal que F(12)=c12.
    """
    c12 = float(np.clip(c12, 1e-6, 0.999))
    k = float(np.clip(k, 0.6, 1.7))
    lam = (-np.log(1.0 - c12)) ** (1.0 / k) / 12.0
    t = months.astype(float)
    return 1.0 - np.exp(-(lam * t) ** k)

def _ensure_columns(row: dict) -> dict:
    """Completa valores por defecto si faltan en el row."""
    defaults = {
        "age": 50.0, "bmi": 27.0, "dm": 0, "hta": 0, "ckd": 0, "smoker": 0,
        "egfr": 80.0, "hba1c": 6.5, "prev_event": 0, "utilizations_12m": 0,
        "lab_recency_m": 12, "region": None, "meds_atc": ""
    }
    out = defaults.copy()
    out.update({k: (v if v is not None else defaults.get(k)) for k, v in row.items()})
    return out

def _linear_score_df(df: pd.DataFrame, cfg: Dict) -> np.ndarray:
    """Score lineal vectorizado con pesos + uplift regional + escala global."""
    w = cfg["weights"]
    s = np.full(len(df), w.get("intercept", 0.0), dtype=float)

    # Variables (si faltara alguna, se rellena a 0/NaN->0)
    def col(name, default=0.0):
        return df.get(name, pd.Series(default, index=df.index)).astype(float)

    s += w["age"]              * col("age")
    s += w["bmi"]              * col("bmi")
    s += w["smoker"]           * col("smoker")
    s += w["hba1c"]            * col("hba1c")
    s += w["egfr"]             * col("egfr")      # peso negativo ya aplicado en w
    s += w["hta"]              * col("hta")
    s += w["dm"]               * col("dm")
    s += w["ckd"]              * col("ckd")
    s += w["prev_event"]       * col("prev_event")
    s += w["utilizations_12m"] * col("utilizations_12m")
    s += w["lab_recency_m"]    * col("lab_recency_m")

    # Uplift por región
    if "region" in df.columns and cfg.get("region_uplift"):
        uplift = df["region"].map(cfg["region_uplift"]).fillna(0.0).astype(float).values
        s += uplift

    # Escala global (separación)
    s = s * float(cfg.get("scale", 1.0))
    return s

# ===================================
# API principal (con la MISMA firma)
# ===================================
def score_row(row, rng=None):
    """
    -> Devuelve un dict con:
       - risk_factor: float
       - time_window_months: [ini, fin]
       - risk_curve: [{month, cum_risk}, ...] con Weibull (no lineal)
       - top_features: [{name, contrib}], suma ~1
       - care_gaps: list[str]
       - cohort_label: str
    """
    cfg = get_mock_config()
    rng = rng or np.random.default_rng()

    r = _ensure_columns(row)

    # Score lineal para una fila
    df1 = pd.DataFrame([r])
    s = _linear_score_df(df1, cfg)[0]
    risk = float(np.clip(_sigmoid(s), *cfg.get("clip", (0.0, 0.92))))

    # Ventana temporal (mantiene tu umbral por defecto 0.30)
    tw = [1, 6] if risk >= float(cfg.get("hi_cut", 0.30)) else [6, 12]

    # Curva mensual con Weibull: forma según magnitud de riesgo
    # - Bajo: k más alto (riesgo tardío)
    # - Alto: k más bajo (front-loaded)
    if   risk < 0.15: k = 1.35
    elif risk < 0.35: k = 1.10
    elif risk < 0.55: k = 1.00
    elif risk < 0.75: k = 0.90
    else:             k = 0.80
    # pequeño jitter estable
    k = float(np.clip(k + rng.normal(0, 0.03), 0.6, 1.7))

    months = np.arange(1, 13, dtype=int)
    c12 = float(np.clip(risk, 0.02, 0.95))
    cum = _weibull_curve(c12, k, months)
    risk_curve = [{"month": int(m), "cum_risk": float(min(0.95, c))} for m, c in zip(months, cum)]

    # Explicabilidad (mantiene nombres y estructura original)
    # Magnitudes relativas simples a partir de señales clínicas
    feats = [
        ("eGFR bajo", max(0.0, 80.0 - float(r["egfr"])) / 80.0),
        ("HbA1c alto", max(0.0, float(r["hba1c"]) - 6.5) / 6.5),
        ("HTA", float(r["hta"])),
        ("DM", float(r["dm"])),
        ("IMC alto", max(0.0, float(r["bmi"]) - 27.0) / 27.0),
    ]
    contribs = np.array([v for _, v in feats], dtype=float)
    total = contribs.sum()
    if total > 0:
        contribs = contribs / total
    features = [{"name": n, "contrib": float(v)} for (n, _), v in zip(feats, contribs)]

    # Care gaps (conserva tu lógica)
    care_gaps: List[str] = []
    if r.get("lab_recency_m", 99) > 12:
        care_gaps.append("Laboratorio desactualizado")
    if r.get("hta", 0) and ("C09" not in str(r.get("meds_atc", ""))):
        care_gaps.append("Sin IECA/ARA-II")
    if r.get("dm", 0) and float(r.get("hba1c", 7.5)) > 8.0:
        care_gaps.append("HbA1c fuera de meta")

    cohort_label = "DM+ERC" if (int(r.get("dm", 0)) and int(r.get("ckd", 0))) else "General"

    return {
        "risk_factor": risk,
        "time_window_months": tw,
        "risk_curve": risk_curve,
        "top_features": features,
        "care_gaps": care_gaps,
        "cohort_label": cohort_label,
    }

def score_batch(df, seed=123):
    """
    -> Devuelve (out_df, records):
       - out_df incluye columnas agregadas: risk_factor, tw_start, tw_end,
         care_gaps, cohort_label (igual que tu versión).
       - records: lista de dicts completos (incluye risk_curve, top_features).
    """
    rng = np.random.default_rng(seed)
    records = []
    for _, row in df.iterrows():
        r = score_row(row, rng)
        records.append(r)

    out = df.copy()
    out["risk_factor"] = [r["risk_factor"] for r in records]
    out["tw_start"] = [r["time_window_months"][0] for r in records]
    out["tw_end"]   = [r["time_window_months"][1] for r in records]
    out["care_gaps"] = [", ".join(r["care_gaps"]) for r in records]
    out["cohort_label"] = [r["cohort_label"] for r in records]
    return out, records

def score_one(payload: dict):
    """Mantiene tu firma: recibe un dict y retorna el dict de score_row."""
    return score_row(payload)

# ==============================================
# Extra opcional para páginas nuevas (no rompe)
# ==============================================
def score_population(df: pd.DataFrame, cfg: Optional[Dict] = None) -> pd.DataFrame:
    """
    Conveniencia para puntuar un DataFrame de manera vectorizada.
    Añade:
      - risk_factor
      - time_window_months (string "1–6 meses"/"6–12 meses")
    No interfiere con score_batch; puedes usarla en páginas nuevas.
    """
    if df is None or df.empty:
        return df

    if cfg:
        set_mock_config(cfg)
    cfg_eff = get_mock_config()

    s = _linear_score_df(df, cfg_eff)
    risk = _sigmoid(s)
    lo, hi = cfg_eff.get("clip", (0.0, 0.92))
    risk = np.clip(risk, lo, hi)

    hi_cut = float(cfg_eff.get("hi_cut", 0.30))
    tw = np.where(risk >= hi_cut, "1–6 meses", "6–12 meses")

    out = df.copy()
    out["risk_factor"] = risk
    out["time_window_months"] = tw
    return out
