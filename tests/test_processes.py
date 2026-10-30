"""Targeted checks of the process functions."""

import numpy as np
import pytest

from soil_moisture_model import ModelConstants, SoilWaterParams, simulate
from soil_moisture_model.processes import (
    atmospheric_pressure,
    biomass_saturation,
    crop_coefficient,
    elevation_et_multiplier,
    interception_capacity,
    psychrometric_constant,
    reference_evapotranspiration,
    saturation_vapour_pressure_slope,
    soil_properties,
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


class TestElevation:
    def test_fao56_annex_values(self):
        # [FAO56] Annex 2, Tables 2.1, 2.2 and 2.4
        assert atmospheric_pressure(0.0) == pytest.approx(101.3)
        assert atmospheric_pressure(1000.0) == pytest.approx(90.0, abs=0.05)
        assert psychrometric_constant(1000.0) == pytest.approx(0.060, abs=5e-4)
        assert saturation_vapour_pressure_slope(20.0) == pytest.approx(0.145, abs=5e-4)

    def test_sea_level_is_neutral(self):
        assert elevation_et_multiplier(0.0, [0.0, 10.0, 30.0]) == pytest.approx(1.0)

    def test_rises_with_elevation_and_falls_with_temperature(self):
        z = np.array([-400.0, 0.0, 1000.0, 3000.0])
        m = elevation_et_multiplier(z, 20.0)
        assert np.all(np.diff(m) > 0)
        assert elevation_et_multiplier(1000.0, 10.0) > m[2]
        assert m[2] == pytest.approx(1.037, abs=1e-3)


def test_reference_evapotranspiration_degree_days():
    # 0.5 mm/degC/day x 10 degC x 7 days at sea level
    assert reference_evapotranspiration(10.0, 0.0, 0.5) == pytest.approx(35.0)
    assert reference_evapotranspiration(-5.0, 0.0, 0.5) == 0.0


class TestSoilProperties:
    def test_nominal_clay_gives_nominal_values(self):
        p = SoilWaterParams()
        s = soil_properties(p.nominal_clay, p)
        assert s.soil_water_capacity == p.nominal_soil_water_capacity

    def test_more_clay_means_more_storage(self):
        p = SoilWaterParams()
        lo, hi = soil_properties(10.0, p), soil_properties(60.0, p)
        assert hi.soil_water_capacity > lo.soil_water_capacity

    def test_clay_clipped_to_bounds(self):
        p = SoilWaterParams()
        assert soil_properties(500.0, p) == soil_properties(C.clay_bounds[1], p)

    @pytest.mark.parametrize(
        ("params", "attr", "bound"),
        [
            ({"nominal_soil_water_capacity": 1000.0}, "soil_water_capacity", 1),
            ({"nominal_soil_water_capacity": 10.0}, "soil_water_capacity", 0),
        ],
    )
    def test_property_clipped(self, params, attr, bound):
        s = soil_properties(25.0, SoilWaterParams(**params))
        assert getattr(s, attr) == getattr(C, f"{attr}_bounds")[bound]


def test_frozen_week_routes_most_throughfall_to_runoff():
    out = simulate([-5.0], [100.0], [0.0], 0.0, 25.0, initial_soil_moisture=0.0)
    assert out.frozen[0]
    assert out.runoff[0] == pytest.approx((1 - C.frozen_infiltration_fraction) * 100.0)


class TestSuppliedReferenceEvapotranspiration:
    rng = np.random.default_rng(0)
    temp = rng.normal(8.0, 8.0, 104)
    precip = rng.gamma(1.5, 12.0, 104)
    biomass = np.full(104, 200.0)

    def test_degree_day_values_reproduce_default_run(self):
        default = simulate(self.temp, self.precip, self.biomass, 300.0, 25.0)
        supplied = simulate(
            self.temp,
            self.precip,
            self.biomass,
            300.0,
            25.0,
            reference_evapotranspiration=default.reference_evapotranspiration,
        )
        np.testing.assert_array_equal(supplied.soil_moisture, default.soil_moisture)

    def test_replaces_degree_days_and_ignores_elevation(self):
        et_o = np.full(104, 20.0)
        low, high = (
            simulate(
                self.temp,
                self.precip,
                self.biomass,
                z,
                25.0,
                reference_evapotranspiration=et_o,
            )
            for z in (0.0, 3000.0)
        )
        np.testing.assert_array_equal(low.soil_moisture, high.soil_moisture)
        thawed = ~low.frozen
        np.testing.assert_allclose(
            low.potential_evapotranspiration[thawed],
            low.crop_coefficient[thawed] * 20.0,
        )

    def test_frozen_adjustment_still_applies(self):
        out = simulate(
            [-5.0], [0.0], [200.0], 0.0, 25.0, reference_evapotranspiration=[10.0]
        )
        assert out.potential_evapotranspiration[0] == pytest.approx(
            C.frozen_reference_et_multiplier * out.crop_coefficient[0] * 10.0
        )

    def test_time_dimension_must_match(self):
        with pytest.raises(ValueError, match="leading"):
            simulate(
                self.temp,
                self.precip,
                self.biomass,
                0.0,
                25.0,
                reference_evapotranspiration=np.ones(10),
            )


class TestInterception:
    def test_no_interception_without_demand(self):
        out = simulate([-5.0], [10.0], [1e6], 0.0, 25.0)
        assert out.interception[0] == 0.0
        assert out.throughfall[0] == 10.0

    def test_limited_by_demand_and_reduces_it(self):
        # Large biomass: interception capacity near its maximum, above demand.
        out = simulate(
            [10.0],
            [50.0],
            [1e6],
            0.0,
            25.0,
            initial_soil_moisture=1000.0,
            reference_evapotranspiration=[2.0],
        )
        et_p = out.potential_evapotranspiration[0]
        assert et_p < C.max_interception_capacity
        assert out.interception[0] == pytest.approx(et_p)
        assert out.actual_evapotranspiration[0] == pytest.approx(0.0)


@pytest.mark.parametrize(
    ("store_fraction", "k_s"), [(0.0, 0.0), (0.5, 0.5), (1.0, 1.0), (1.5, 1.0)]
)
def test_water_stress_follows_fao56_eq_84(store_fraction, k_s):
    # At nominal clay, the stress onset is (1 - p) phi_fc S_max_nominal.
    p = SoilWaterParams()
    onset = (
        (1 - C.depletion_fraction)
        * p.field_capacity_fraction
        * p.nominal_soil_water_capacity
    )
    out = simulate(
        [10.0],
        [0.0],
        [0.0],
        0.0,
        p.nominal_clay,
        initial_soil_moisture=store_fraction * onset,
    )
    assert out.water_stress_coefficient[0] == pytest.approx(k_s)
