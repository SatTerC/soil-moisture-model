"""Run the current model on a regression scenario, returning legacy-named outputs.

This is the only place that knows the current public API. When the API changes,
update this adapter, not the fixtures.
"""

import numpy as np

from soil_moisture_model import SoilWaterParams, simulate

# legacy SoilWaterParams field -> current SoilWaterParams field
PARAM_NAMES = {
    "base_soil_water_capacity_mm": "nominal_soil_water_capacity",
    "base_drainage_coeff": "nominal_drainage_coefficient",
    "base_runoff_fraction_max": "nominal_max_runoff_fraction",
    "runoff_exponent": "runoff_exponent",
    "field_capacity_fraction": "field_capacity_fraction",
    "reference_clay_pct": "nominal_clay",
    "clay_sensitivity": "clay_sensitivity",
    "pet_coeff_mm_per_degday": "reference_et_coefficient",
    "biomass_half_sat_gC_m2": "biomass_half_saturation",
}


def run_scenario(inputs: dict) -> dict[str, np.ndarray]:
    legacy_params = dict(inputs["params"])
    initial = legacy_params.pop("initial_soil_moisture_mm", 50.0)
    params = SoilWaterParams(**{PARAM_NAMES[k]: v for k, v in legacy_params.items()})
    out = simulate(
        inputs["temp_c"],
        inputs["precip_mm"],
        inputs["biomass_gC_m2"],
        float(inputs["elevation_m"]),
        float(inputs["clay_pct"]),
        initial_soil_moisture=initial,
        params=params,
    )
    return {
        "base_pet_mm": out.reference_evapotranspiration,
        "kc": out.crop_coefficient,
        "interception_capacity_mm": out.interception_capacity,
        "intercepted_mm": out.interception,
        "throughfall_mm": out.throughfall,
        "frozen_soil": out.frozen,
        "et_potential_mm": out.potential_evapotranspiration,
        "water_stress": out.water_stress_coefficient,
        "et_actual_mm": out.actual_evapotranspiration,
        "total_evaporative_loss_mm": out.total_evaporative_loss,
        "runoff_mm": out.runoff,
        "drainage_mm": out.drainage,
        "soil_moisture_mm": out.soil_moisture,
        "relative_soil_moisture": out.relative_soil_moisture,
        "soil_water_capacity_mm": out.soil.soil_water_capacity,
        "drainage_coeff": out.soil.drainage_coefficient,
        "runoff_fraction_max": out.soil.max_runoff_fraction,
    }
