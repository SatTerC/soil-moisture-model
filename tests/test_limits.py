"""Analytic limits and input validation."""

import numpy as np
import pytest

from soil_moisture_model import SoilWaterParams, simulate

N = 104


def test_no_rain_store_never_rises():
    t = 15.0 + 10.0 * np.sin(np.arange(N) / 8.0)
    out = simulate(
        t, np.zeros(N), np.full(N, 300.0), 0.0, 25.0, initial_soil_moisture=150.0
    )
    assert np.all(np.diff(out.soil_moisture) <= 0.0)
    assert out.soil_moisture[-1] < 150.0


def test_no_rain_no_demand_below_field_capacity_store_constant():
    # Below 0 degC there are no degree-days, hence no evapotranspiration.
    out = simulate(
        np.full(N, -1.0),
        np.zeros(N),
        np.zeros(N),
        0.0,
        25.0,
        initial_soil_moisture=50.0,
    )
    np.testing.assert_array_equal(out.soil_moisture, 50.0)


def test_initial_store_clipped_to_capacity():
    out = simulate([-1.0], [0.0], [0.0], 0.0, 25.0, initial_soil_moisture=1e6)
    assert out.soil_moisture[0] <= out.soil.soil_water_capacity


@pytest.mark.parametrize(
    "bad",
    [
        {"nominal_soil_water_capacity": 0.0},
        {"nominal_drainage_coefficient": 1.5},
        {"nominal_max_runoff_fraction": -0.1},
        {"runoff_exponent": 0.0},
        {"field_capacity_fraction": 1.2},
        {"biomass_half_saturation": 0.0},
        {"biomass_half_saturation": np.array([100.0, -1.0])},
    ],
)
def test_params_validation(bad):
    with pytest.raises(ValueError, match=next(iter(bad))):
        SoilWaterParams(**bad)
