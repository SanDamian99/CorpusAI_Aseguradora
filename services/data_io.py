# services/data_io.py
import numpy as np
import pandas as pd

REGIONS_CO = ["Bogotá", "Antioquia", "Valle", "Atlántico", "Santander"]
REGIONS_MX = ["CDMX", "Edomex", "Jalisco", "Nuevo León", "Puebla"]

CIE10 = ["I10", "E11", "N18", "I21", "E78"]  # HTA, DM2, ERC, IAM, Dislipidemia
ATC = ["C09", "A10", "B01", "C10", "N05"]    # ARA-II/IECA, antidiabéticos, antiagregantes, estatinas, psi

def generate_dummy_population(n=2000, country="Colombia - EPS", seed=42):
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "patient_id": [f"P{100000+i}" for i in range(n)],
        "age": rng.integers(18, 90, size=n),
        "sex": rng.choice(["F","M"], size=n, p=[0.55, 0.45]),
        "region": rng.choice(REGIONS_CO if "Colombia" in country else REGIONS_MX, size=n),
        "bmi": rng.normal(28, 4.5, size=n).clip(16, 48),
        "smoker": rng.choice([0,1], size=n, p=[0.7, 0.3]),
        "hba1c": rng.normal(6.8, 1.6, size=n).clip(4.8, 12.5),
        "egfr": rng.normal(78, 25, size=n).clip(10, 120),
        "hta": rng.choice([0,1], size=n, p=[0.5, 0.5]),
        "dm": rng.choice([0,1], size=n, p=[0.7, 0.3]),
        "ckd": rng.choice([0,1], size=n, p=[0.85, 0.15]),
        "prev_event": rng.choice([0,1], size=n, p=[0.9, 0.1]),
        "lab_recency_m": rng.integers(1, 24, size=n),
        "utilizations_12m": rng.integers(0, 15, size=n),
        "cost_12m": rng.gamma(2.0, 450_000, size=n).clip(0, 15_000_000).round(0),
        "hta_control": rng.choice([0,1], size=n, p=[0.45, 0.55]),
        "cost_event": rng.normal(5_500_000, 1_500_000, size=n).clip(1_500_000, 15_000_000).round(0)
    })
    # diagnosticos y fármacos sintéticos (listas como strings)
    df["dx_cie10"] = df.apply(lambda r: ",".join(sorted(set(np.random.choice(CIE10, size=np.random.randint(1,4)) ))), axis=1)
    df["meds_atc"] = df.apply(lambda r: ",".join(sorted(set(np.random.choice(ATC, size=np.random.randint(1,3)) ))), axis=1)
    return df
