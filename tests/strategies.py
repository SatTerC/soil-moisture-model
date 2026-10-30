"""Hypothesis strategies for model inputs, within the calibration bounds."""

import numpy as np
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from soil_moisture_model import SoilWaterParams

# Calibration bounds, from scripts/calibrate_icos.py.
PARAM_BOUNDS = {
    "drainage_coefficient": (0.01, 0.30),
    "max_runoff_fraction": (0.02, 0.95),
    "runoff_exponent": (0.5, 4.0),
    "rooting_depth": (0.2, 3.0),
    "depletion_fraction": (0.1, 0.8),
    "reference_et_coefficient": (0.05, 0.5),
    "biomass_half_saturation": (20.0, 800.0),
}


def _floats(lo, hi):
    return st.floats(lo, hi, allow_nan=False, allow_infinity=False)


params = st.builds(
    SoilWaterParams, **{k: _floats(lo, hi) for k, (lo, hi) in PARAM_BOUNDS.items()}
)


@st.composite
def texture(draw, n_pixel):
    """Sand, clay and organic matter fractions where `[SR06]` gives ordered values."""
    sand = draw(arrays(float, n_pixel, elements=_floats(0.05, 0.9)))
    clay_share = draw(arrays(float, n_pixel, elements=_floats(0.0, 1.0)))
    clay = 0.02 + clay_share * (np.minimum(0.55, 1.0 - sand) - 0.02)
    om = draw(arrays(float, n_pixel, elements=_floats(0.0, 0.08)))
    return {"sand": sand, "clay": clay, "organic_matter": om}


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
        **draw(texture(n_pixel)),
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
