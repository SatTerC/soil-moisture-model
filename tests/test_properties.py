"""Invariants that must hold for any inputs within the calibration bounds."""

import numpy as np
from hypothesis import given, settings
from strategies import model_inputs, previous_store

from soil_moisture_model import simulate

SETTINGS = settings(max_examples=200, deadline=None)


@SETTINGS
@given(inputs=model_inputs())
def test_store_within_capacity(inputs):
    out = simulate(**inputs)
    assert np.all(out.soil_moisture >= 0.0)
    assert np.all(out.soil_moisture <= out.soil.soil_water_capacity)
    assert np.all((out.relative_soil_moisture >= 0) & (out.relative_soil_moisture <= 1))
    theta = out.soil_water_content
    assert np.all(theta >= out.soil.water_content_at_wilting_point - 1e-12)
    assert np.all(theta <= out.soil.water_content_at_saturation + 1e-12)


@SETTINGS
@given(inputs=model_inputs())
def test_stress_in_unit_interval(inputs):
    out = simulate(**inputs)
    assert np.all(
        (out.water_stress_coefficient >= 0.0) & (out.water_stress_coefficient <= 1.0)
    )


@SETTINGS
@given(inputs=model_inputs())
def test_fluxes_non_negative(inputs):
    out = simulate(**inputs)
    for name in (
        "actual_evapotranspiration",
        "potential_evapotranspiration",
        "interception",
        "throughfall",
        "runoff",
        "drainage",
    ):
        assert np.all(getattr(out, name) >= 0.0), name


@SETTINGS
@given(inputs=model_inputs())
def test_runoff_and_interception_bounded_by_supply(inputs):
    out = simulate(**inputs)
    assert np.all(out.interception <= out.interception_capacity)
    assert np.all(out.runoff <= out.throughfall + 1e-12)


@SETTINGS
@given(inputs=model_inputs())
def test_evapotranspiration_bounded_by_demand_and_water(inputs):
    out = simulate(**inputs)
    s_prev = previous_store(out, inputs["initial_soil_moisture"])
    supply = s_prev + out.throughfall - out.runoff
    assert np.all(
        out.actual_evapotranspiration <= out.potential_evapotranspiration + 1e-12
    )
    assert np.all(out.actual_evapotranspiration <= supply + 1e-12)


@SETTINGS
@given(inputs=model_inputs())
def test_total_evaporative_loss_bounded_by_demand(inputs):
    out = simulate(**inputs)
    assert np.all(
        out.total_evaporative_loss <= out.potential_evapotranspiration + 1e-12
    )


@SETTINGS
@given(inputs=model_inputs())
def test_outputs_finite(inputs):
    out = simulate(**inputs)
    for name in ("soil_moisture", "actual_evapotranspiration", "runoff", "drainage"):
        assert np.all(np.isfinite(getattr(out, name))), name
