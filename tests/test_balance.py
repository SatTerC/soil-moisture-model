"""Per-week water balance.

Every week, the change in the soil store must equal what went in minus what
came out:

    S[t] - S[t-1] = P - I - Q - E_a - D
"""

import numpy as np
from hypothesis import given, settings
from strategies import model_inputs, previous_store

from soil_moisture_model import simulate


@settings(max_examples=300, deadline=None)
@given(inputs=model_inputs())
def test_water_is_conserved(inputs):
    out = simulate(**inputs)
    s_prev = previous_store(out, inputs["initial_soil_moisture"])
    precipitation = np.maximum(inputs["precipitation"], 0.0)
    residual = (
        precipitation
        - out.interception
        - out.runoff
        - out.actual_evapotranspiration
        - out.drainage
        - (out.soil_moisture - s_prev)
    )
    np.testing.assert_allclose(residual, 0.0, atol=1e-10)
