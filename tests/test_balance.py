"""Per-week water balance.

Every week, the change in the soil store must equal what went in minus what
came out:

    S[t] - S[t-1] = P - I - Q - E_a - D
"""

import numpy as np
import pytest
from hypothesis import given, settings
from strategies import model_inputs, previous_store

from soil_moisture_model import simulate


def residual(inputs) -> tuple[np.ndarray, np.ndarray]:
    """Return the balance residual and the water lost to bucket overflow."""
    out = simulate(**inputs)
    s_prev = previous_store(out, inputs["initial_soil_moisture"])
    precipitation = np.maximum(inputs["precipitation"], 0.0)
    infiltration = out.throughfall - out.runoff
    overflow = np.maximum(s_prev + infiltration - out.soil.soil_water_capacity, 0.0)
    res = (
        precipitation
        - out.interception
        - out.runoff
        - out.actual_evapotranspiration
        - out.drainage
        - (out.soil_moisture - s_prev)
    )
    return res, overflow


@pytest.mark.xfail(
    strict=True,
    reason="water above capacity after infiltration is discarded, not routed to runoff",
)
@settings(max_examples=200, deadline=None)
@given(inputs=model_inputs())
def test_water_is_conserved(inputs):
    res, _ = residual(inputs)
    np.testing.assert_allclose(res, 0.0, atol=1e-9)


@settings(max_examples=200, deadline=None)
@given(inputs=model_inputs())
def test_overflow_is_the_only_leak(inputs):
    res, overflow = residual(inputs)
    np.testing.assert_allclose(res, overflow, atol=1e-9)
