"""Run the current model on a regression scenario.

This is the only place that knows the current public API. When the API changes
without changing the numbers, update this adapter, not the fixtures.
"""

from dataclasses import fields

import numpy as np

from soil_moisture_model import SoilProperties, SoilWaterParams, simulate


def run_scenario(inputs: dict) -> dict[str, np.ndarray]:
    """Return every output of a scenario run, soil properties as ``soil.<field>``."""
    params = dict(inputs["params"])
    initial = params.pop("initial_soil_moisture", None)
    out = simulate(
        inputs["temp_c"],
        inputs["precip_mm"],
        inputs["biomass_gC_m2"],
        float(inputs["elevation_m"]),
        float(inputs["sand"]),
        float(inputs["clay"]),
        initial_soil_moisture=initial,
        params=SoilWaterParams(**params),
    )
    result = {f.name: getattr(out, f.name) for f in fields(out) if f.name != "soil"}
    result["total_evaporative_loss"] = out.total_evaporative_loss
    result.update(
        {f"soil.{f.name}": getattr(out.soil, f.name) for f in fields(SoilProperties)}
    )
    return result
