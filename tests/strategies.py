"""Hypothesis strategies for model inputs, within the calibration bounds."""

import numpy as np
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from soil_moisture_model import SoilWaterParams

# Calibration bounds, from scripts/calibrate_icos.py.
PARAM_BOUNDS = {
    "nominal_soil_water_capacity": (60.0, 400.0),
    "nominal_drainage_coefficient": (0.01, 0.30),
    "nominal_max_runoff_fraction": (0.02, 0.95),
    "runoff_exponent": (0.5, 4.0),
    "field_capacity_fraction": (0.40, 0.95),
    "nominal_clay": (5.0, 60.0),
    "clay_sensitivity": (0.0, 0.10),
    "reference_et_coefficient": (0.1, 1.5),
    "biomass_half_saturation": (20.0, 800.0),
}


def _floats(lo, hi):
    return st.floats(lo, hi, allow_nan=False, allow_infinity=False)


params = st.builds(
    SoilWaterParams, **{k: _floats(lo, hi) for k, (lo, hi) in PARAM_BOUNDS.items()}
)


@st.composite
def model_inputs(draw):
    n_time = draw(st.integers(1, 60))
    n_pixel = draw(st.integers(1, 3))
    shape = (n_time, n_pixel)
    return {
        "temperature": draw(arrays(float, shape, elements=_floats(-25.0, 35.0))),
        "precipitation": draw(arrays(float, shape, elements=_floats(0.0, 300.0))),
        "biomass": draw(arrays(float, shape, elements=_floats(0.0, 2000.0))),
        "elevation": draw(arrays(float, n_pixel, elements=_floats(-400.0, 6000.0))),
        "clay": draw(arrays(float, n_pixel, elements=_floats(0.0, 100.0))),
        "initial_soil_moisture": draw(
            arrays(float, n_pixel, elements=_floats(0.0, 500.0))
        ),
        "params": draw(params),
    }


def previous_store(out, initial) -> np.ndarray:
    """Return S[t-1] for every week, starting from the clipped initial store."""
    s0 = np.clip(
        np.broadcast_to(initial, out.soil_moisture.shape[1:]),
        0.0,
        out.soil.soil_water_capacity,
    )
    return np.concatenate([s0[None], out.soil_moisture[:-1]])
