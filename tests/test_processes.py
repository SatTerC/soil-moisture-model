"""Targeted checks of the process functions."""

import numpy as np
import pytest

from soil_moisture_model import ModelConstants, SoilWaterParams, simulate
from soil_moisture_model.processes import (
    biomass_saturation,
    crop_coefficient,
    elevation_et_multiplier,
    interception_capacity,
    reference_evapotranspiration,
    soil_properties,
    uptake_factor,
)

C = ModelConstants()


class TestBiomassFraction:
    def test_zero_and_half_saturation(self):
        assert biomass_saturation(0.0, 150.0) == 0.0
        assert biomass_saturation(150.0, 150.0) == pytest.approx(0.5)

    def test_negative_biomass_treated_as_zero(self):
        assert biomass_saturation(-10.0, 150.0) == 0.0

    def test_monotone_and_below_one(self):
        f = biomass_saturation(np.linspace(0, 1e5, 1000), 150.0)
        assert np.all(np.diff(f) > 0)
        assert np.all(f < 1)


def test_biomass_effects_span_their_ranges():
    f = np.array([0.0, 1.0])
    np.testing.assert_allclose(
        crop_coefficient(f), [C.min_crop_coefficient, C.max_crop_coefficient]
    )
    np.testing.assert_allclose(
        interception_capacity(f), [0.0, C.max_interception_capacity]
    )
    np.testing.assert_allclose(uptake_factor(f), [1.0, C.max_uptake_factor])


class TestElevation:
    def test_sea_level_is_neutral(self):
        assert elevation_et_multiplier(0.0) == 1.0

    @pytest.mark.parametrize(("z", "bound"), [(10_000.0, 1), (-10_000.0, 0)])
    def test_clipped(self, z, bound):
        assert elevation_et_multiplier(z) == C.elevation_et_multiplier_bounds[bound]


def test_reference_evapotranspiration_degree_days():
    # 0.5 mm/degC/day x 10 degC x 7 days at sea level
    assert reference_evapotranspiration(10.0, 0.0, 0.5) == pytest.approx(35.0)
    assert reference_evapotranspiration(-5.0, 0.0, 0.5) == 0.0


class TestSoilProperties:
    def test_nominal_clay_gives_nominal_values(self):
        p = SoilWaterParams()
        s = soil_properties(p.nominal_clay, p)
        assert s.soil_water_capacity == p.nominal_soil_water_capacity
        assert s.drainage_coefficient == p.nominal_drainage_coefficient
        assert s.max_runoff_fraction == p.nominal_max_runoff_fraction
        assert s.stress_exponent == C.nominal_stress_exponent

    def test_more_clay_means_more_storage_and_runoff_less_drainage(self):
        p = SoilWaterParams()
        lo, hi = soil_properties(10.0, p), soil_properties(60.0, p)
        assert hi.soil_water_capacity > lo.soil_water_capacity
        assert hi.max_runoff_fraction > lo.max_runoff_fraction
        assert hi.stress_exponent > lo.stress_exponent
        assert hi.drainage_coefficient < lo.drainage_coefficient

    def test_clay_clipped_to_bounds(self):
        p = SoilWaterParams()
        assert soil_properties(500.0, p) == soil_properties(C.clay_bounds[1], p)

    @pytest.mark.parametrize(
        ("params", "attr", "bound"),
        [
            ({"nominal_soil_water_capacity": 1000.0}, "soil_water_capacity", 1),
            ({"nominal_soil_water_capacity": 10.0}, "soil_water_capacity", 0),
            ({"nominal_drainage_coefficient": 1.0}, "drainage_coefficient", 1),
            ({"nominal_drainage_coefficient": 0.0}, "drainage_coefficient", 0),
            ({"nominal_max_runoff_fraction": 1.0}, "max_runoff_fraction", 1),
            ({"nominal_max_runoff_fraction": 0.0}, "max_runoff_fraction", 0),
        ],
    )
    def test_property_clipped(self, params, attr, bound):
        s = soil_properties(25.0, SoilWaterParams(**params))
        assert getattr(s, attr) == getattr(C, f"{attr}_bounds")[bound]


def test_frozen_week_routes_most_throughfall_to_runoff():
    out = simulate([-5.0], [100.0], [0.0], 0.0, 25.0, initial_soil_moisture=0.0)
    assert out.frozen[0]
    assert out.runoff[0] == pytest.approx((1 - C.frozen_infiltration_fraction) * 100.0)
