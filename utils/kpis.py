# utils/kpis.py
import numpy as np
import pandas as pd

def pct(x):
    return f"{100*x:.1f}%"

def compute_core_kpis(df, country="Colombia - EPS"):
    n = len(df)
    high_risk = (df["risk_factor"] >= 0.3).mean() if n else 0
    pmpm = float(df["cost_12m"].sum() / max(1, n) / 12)
    upc = 30.0  # dummy: UPC mensual promedio
    loss_ratio = float(df["cost_12m"].sum() / (n * 12 * upc)) if n else 0.0
    controlled_htn = (df["hta_control"] == 1).mean() if "hta_control" in df else 0.0
    event_rate_12m = df["risk_factor"].mean() if "risk_factor" in df else 0.0

    if "México" in country:
        return {
            "Población": n,
            "% Alto riesgo": pct(high_risk),
            "Loss ratio (sim.)": pct(loss_ratio),
            "Severidad prom. siniestro": f"${df['cost_event'].mean():,.0f}",
            "Eventos esperados 12m": f"{event_rate_12m*n:,.0f}",
        }
    else:
        return {
            "Población": n,
            "% Alto riesgo": pct(high_risk),
            "PMPM": f"${pmpm:,.0f}",
            "Siniestralidad UPC (sim.)": pct(loss_ratio),
            "% HTA control": pct(controlled_htn),
        }

def quick_roi(events_avoided, cost_event=2_000_000, program_cost=50_000_000):
    ahorro_bruto = events_avoided * cost_event
    roi = (ahorro_bruto - program_cost) / max(1, program_cost)
    return ahorro_bruto, roi
