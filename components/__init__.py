# components/__init__.py
# Marca el directorio como paquete y expone submódulos útiles.
from .charts import risk_hist, region_heat, survival_deciles

__all__ = ["risk_hist", "region_heat", "survival_deciles"]
