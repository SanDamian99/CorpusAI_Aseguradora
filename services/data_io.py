# services/data_io.py
import numpy as np
import pandas as pd
from typing import Dict, Optional

REGIONS_CO = ["Bogotá", "Antioquia", "Valle", "Atlántico", "Santander"]
REGIONS_MX = ["CDMX", "Edomex", "Jalisco", "Nuevo León", "Puebla"]

CIE10 = ["I10", "E11", "N18", "I21", "E78"]  # HTA, DM2, ERC, IAM, Dislipidemia
ATC = ["C09", "A10", "B01", "C10", "N05"]    # ARA-II/IECA, antidiabéticos, antiagregantes, estatinas, psi

def generate_dummy_population(
    n: int = 2000,
    country: str = "Colombia - EPS",
    seed: int = 42,
    *,
    # Prevalencias opcionales
    p_smoker: Optional[float] = None,
    p_dm: Optional[float] = None,
    p_hta: Optional[float] = None,
    p_ckd: Optional[float] = None,
    p_prev_event: Optional[float] = None,
    # Medias/SD opcionales
    bmi_mean: Optional[float] = None, bmi_sd: Optional[float] = None,
    hba1c_mean: Optional[float] = None, hba1c_sd: Optional[float] = None,
    egfr_mean: Optional[float] = None, egfr_sd: Optional[float] = None,
    # Pesos de muestreo por región (normalizados internamente)
    region_weights: Optional[Dict[str, float]] = None,
) -> pd.DataFrame:
    """
    Genera población sintética. Si no pasas parámetros, usa tus defaults previos.
    """
    rng = np.random.default_rng(seed)

    is_mx = "Colombia" not in country
    regions = REGIONS_CO if not is_mx else REGIONS_MX

    # --- Pesos por región (si vienen) ---
    if region_weights:
        weights = np.array([float(region_weights.get(r, 1.0)) for r in regions], dtype=float)
        weights = np.clip(weights, 1e-6, None)
        weights = weights / weights.sum()
    else:
        weights = None

    df = pd.DataFrame({
        "patient_id": [f"P{100000+i}" for i in range(n)],
        "age": rng.integers(18, 90, size=n),
        "sex": rng.choice(["F","M"], size=n, p=[0.55, 0.45]),
        "region": rng.choice(regions, size=n, p=weights),
        "bmi": rng.normal(bmi_mean if bmi_mean is not None else 28,
                          bmi_sd if bmi_sd is not None else 4.5, size=n).clip(16, 48),
        "smoker": rng.choice([0,1], size=n, p=[1 - (p_smoker or 0.30), (p_smoker or 0.30)]),
        "hba1c": rng.normal(hba1c_mean if hba1c_mean is not None else 6.8,
                            hba1c_sd if hba1c_sd is not None else 1.6, size=n).clip(4.8, 12.5),
        "egfr": rng.normal(egfr_mean if egfr_mean is not None else 78,
                           egfr_sd if egfr_sd is not None else 25, size=n).clip(10, 120),
        "hta": rng.choice([0,1], size=n, p=[1 - (p_hta or 0.5), (p_hta or 0.5)]),
        "dm": rng.choice([0,1], size=n, p=[1 - (p_dm or 0.30), (p_dm or 0.30)]),
        "ckd": rng.choice([0,1], size=n, p=[1 - (p_ckd or 0.15), (p_ckd or 0.15)]),
        "prev_event": rng.choice([0,1], size=n, p=[1 - (p_prev_event or 0.10), (p_prev_event or 0.10)]),
        "lab_recency_m": rng.integers(1, 24, size=n),
        "utilizations_12m": rng.integers(0, 15, size=n),
        "cost_12m": rng.gamma(2.0, 450_000, size=n).clip(0, 15_000_000).round(0),
        "hta_control": rng.choice([0,1], size=n, p=[0.45, 0.55]),
        "cost_event": rng.normal(5_500_000, 1_500_000, size=n).clip(1_500_000, 15_000_000).round(0)
    })

    # diagnósticos y fármacos sintéticos (listas como strings)
    df["dx_cie10"] = df.apply(
        lambda r: ",".join(sorted(set(np.random.choice(CIE10, size=np.random.randint(1,4))))), axis=1
    )
    df["meds_atc"] = df.apply(
        lambda r: ",".join(sorted(set(np.random.choice(ATC, size=np.random.randint(1,3))))), axis=1
    )
    return df
