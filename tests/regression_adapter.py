"""Run the current model on a regression scenario, returning legacy-named outputs.

This is the only place that knows the current public API. When the API changes,
update this adapter, not the fixtures.
"""

import numpy as np
import pandas as pd

from soil_moisture_model import SoilWaterParams, simulate_soil_water_balance

SITE_OUTPUTS = (
    "soil_water_capacity_mm",
    "drainage_coeff",
    "runoff_fraction_max",
    "stress_exponent",
)


def run_scenario(inputs: dict) -> dict[str, np.ndarray]:
    df = simulate_soil_water_balance(
        pd.DataFrame(
            {
                "temp_c": inputs["temp_c"],
                "precip_mm": inputs["precip_mm"],
                "biomass_gC_m2": inputs["biomass_gC_m2"],
            }
        ),
        elevation_m=float(inputs["elevation_m"]),
        clay_pct=float(inputs["clay_pct"]),
        params=SoilWaterParams(**inputs["params"]),
    )
    out = {k: df[k].to_numpy() for k in df.columns if k not in SITE_OUTPUTS}
    out.update({k: np.asarray(df[k].iloc[0]) for k in SITE_OUTPUTS})
    return out
