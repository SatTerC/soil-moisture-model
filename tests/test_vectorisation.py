"""A block of pixels must give the same answer as each pixel run on its own."""

from dataclasses import fields

import numpy as np
import pytest

from soil_moisture_model import SoilWaterOutput, SoilWaterParams, simulate

N_TIME = 156
N_PIXEL = 7


@pytest.fixture
def block():
    rng = np.random.default_rng(0)
    week = np.arange(N_TIME)[:, None]
    temperature = (
        8.0 - 10.0 * np.cos(2 * np.pi * week / 52) + rng.normal(0, 2, (N_TIME, N_PIXEL))
    )
    precipitation = rng.gamma(1.5, 15.0, (N_TIME, N_PIXEL))
    biomass = rng.uniform(0.0, 600.0, (N_TIME, N_PIXEL))
    elevation = rng.uniform(0.0, 3000.0, N_PIXEL)
    texture = (rng.uniform(0.1, 0.6, N_PIXEL), rng.uniform(0.05, 0.4, N_PIXEL))
    initial = rng.uniform(0.0, 200.0, N_PIXEL)
    params = SoilWaterParams(
        rooting_depth=rng.uniform(0.2, 3.0, N_PIXEL),
        depletion_fraction=rng.uniform(0.1, 0.8, N_PIXEL),
        runoff_exponent=rng.uniform(0.5, 4.0, N_PIXEL),
        biomass_half_saturation=rng.uniform(20.0, 800.0, N_PIXEL),
    )
    return temperature, precipitation, biomass, elevation, texture, initial, params


def _pixel(params: SoilWaterParams, i: int) -> SoilWaterParams:
    return SoilWaterParams(
        **{
            k: np.asarray(v)[..., i] if np.ndim(v) else v
            for k, v in params.as_dict().items()
        }
    )


def test_block_equals_stacked_pixels(block):
    temperature, precipitation, biomass, elevation, (sand, clay), initial, params = (
        block
    )
    together = simulate(
        temperature,
        precipitation,
        biomass,
        elevation,
        sand,
        clay,
        initial_soil_moisture=initial,
        params=params,
    )
    for i in range(N_PIXEL):
        alone = simulate(
            temperature[:, i],
            precipitation[:, i],
            biomass[:, i],
            elevation[i],
            sand[i],
            clay[i],
            initial_soil_moisture=initial[i],
            params=_pixel(params, i),
        )
        for f in fields(SoilWaterOutput):
            if f.name == "soil":
                continue
            # Not exact: numpy may round power and exp differently for a block and a
            # single pixel, depending on the CPU.
            np.testing.assert_allclose(
                getattr(together, f.name)[:, i],
                getattr(alone, f.name),
                rtol=1e-12,
                atol=0,
                err_msg=f.name,
            )
        assert together.soil.soil_water_capacity[i] == alone.soil.soil_water_capacity


def test_scalar_site_inputs_broadcast(block):
    temperature, precipitation, biomass, *_ = block
    out = simulate(temperature, precipitation, biomass, 100.0, 0.4, 0.2)
    assert out.soil_moisture.shape == (N_TIME, N_PIXEL)


def test_two_spatial_dimensions(block):
    temperature, precipitation, biomass, *_ = block
    out = simulate(
        temperature.reshape(N_TIME, 1, N_PIXEL),
        precipitation.reshape(N_TIME, 1, N_PIXEL),
        biomass.reshape(N_TIME, 1, N_PIXEL),
        elevation=np.zeros((3, 1)),
        sand=0.4,
        clay=0.2,
    )
    assert out.soil_moisture.shape == (N_TIME, 3, N_PIXEL)


def test_nan_pixel_does_not_contaminate_neighbours(block):
    temperature, precipitation, biomass, elevation, texture, *_ = block
    precipitation = precipitation.copy()
    precipitation[10, 0] = np.nan
    out = simulate(temperature, precipitation, biomass, elevation, *texture)
    assert np.isnan(out.soil_moisture[-1, 0])
    assert np.all(np.isfinite(out.soil_moisture[:, 1:]))


def test_mismatched_time_dimension_raises(block):
    temperature, precipitation, biomass, *_ = block
    with pytest.raises(ValueError, match="leading"):
        simulate(temperature, precipitation[:-1], biomass, 0.0, 0.4, 0.2)
