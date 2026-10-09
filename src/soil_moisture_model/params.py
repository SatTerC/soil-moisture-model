"""Model parameters and fixed constants.

`SoilWaterParams` holds the parameters that are calibrated against observations.
`ModelConstants` holds the remaining numbers that shape the model's response but
are not calibrated. Both are frozen dataclasses whose defaults reproduce the
original model.

Every field of `SoilWaterParams` may be a scalar or an array that broadcasts
against the spatial shape of the drivers, so parameters can vary per pixel.
"""

from dataclasses import dataclass, fields

import numpy as np
from numpy.typing import ArrayLike, NDArray

type FloatOrArray = float | NDArray[np.float64]


def _check(name: str, value: ArrayLike, lo: float, hi: float, *, open_lo: bool) -> None:
    v = np.asarray(value, dtype=float)
    below = v <= lo if open_lo else v < lo
    if np.any(below) or np.any(v > hi):
        bracket = "(" if open_lo else "["
        raise ValueError(f"{name} must lie in {bracket}{lo}, {hi}], got {value!r}")


# name -> (lower bound, upper bound, lower bound excluded?)
_PARAM_RANGES: dict[str, tuple[float, float, bool]] = {
    "nominal_soil_water_capacity": (0.0, np.inf, True),
    "nominal_drainage_coefficient": (0.0, 1.0, False),
    "nominal_max_runoff_fraction": (0.0, 1.0, False),
    "runoff_exponent": (0.0, np.inf, True),
    "field_capacity_fraction": (0.0, 1.0, False),
    "nominal_clay": (0.0, 100.0, False),
    "clay_sensitivity": (0.0, np.inf, False),
    "reference_et_coefficient": (0.0, np.inf, False),
    "biomass_half_saturation": (0.0, np.inf, True),
}


@dataclass(frozen=True)
class SoilWaterParams:
    """Calibrated parameters of the soil water balance.

    The `nominal_*` parameters are the values for a soil whose clay content equals
    `nominal_clay`; `soil_properties` adjusts them for the actual clay
    content, with a strength set by `clay_sensitivity`.

    Raises
    ------
    ValueError
        If any parameter lies outside its physically meaningful range.
    """

    nominal_soil_water_capacity: FloatOrArray = 160.0
    """Soil water holding capacity at the reference clay content (mm)."""
    nominal_drainage_coefficient: FloatOrArray = 0.10
    """Fraction of water above field capacity that drains each week, at the
    reference clay content (dimensionless)."""
    nominal_max_runoff_fraction: FloatOrArray = 0.45
    """Fraction of throughfall that runs off when the soil is saturated, at the
    reference clay content (dimensionless)."""
    runoff_exponent: FloatOrArray = 2.0
    """Exponent of relative soil moisture in the runoff fraction
    (dimensionless)."""
    field_capacity_fraction: FloatOrArray = 0.70
    """Field capacity as a fraction of the soil water capacity
    (dimensionless)."""
    nominal_clay: FloatOrArray = 25.0
    """Clay content at which the `nominal_*` parameters apply (percent)."""
    clay_sensitivity: FloatOrArray = 0.04
    """Strength of the clay-content adjustment to the soil properties (per
    percent clay, scaled by 1/100)."""
    reference_et_coefficient: FloatOrArray = 0.55
    """Reference evapotranspiration per degree-day above the base temperature
    (mm per degC per day)."""
    biomass_half_saturation: FloatOrArray = 150.0
    """Plant biomass at which the biomass effects reach half their maximum
    (grams of carbon per square metre)."""

    def __post_init__(self) -> None:
        """Validate parameter ranges."""
        for name, (lo, hi, open_lo) in _PARAM_RANGES.items():
            _check(name, getattr(self, name), lo, hi, open_lo=open_lo)

    def as_dict(self) -> dict[str, FloatOrArray]:
        """Return the parameters as a ``{name: value}`` dictionary."""
        return {f.name: getattr(self, f.name) for f in fields(self)}


@dataclass(frozen=True)
class ModelConstants:
    """Fixed, uncalibrated constants of the model.

    These are modelling choices rather than physical constants. They are exposed
    so that sensitivity studies can vary them without editing the code.
    """

    # --- Biomass effects ---
    min_crop_coefficient: float = 0.30
    """Crop coefficient with no biomass (dimensionless)."""
    max_crop_coefficient: float = 1.20
    """Crop coefficient approached as biomass becomes large (dimensionless)."""
    max_interception_capacity: float = 3.0
    """Canopy interception capacity approached as biomass becomes large (mm per
    week)."""
    max_uptake_factor: float = 1.35
    """Root-uptake multiplier on potential evapotranspiration, approached as
    biomass becomes large (dimensionless)."""

    # --- Freezing ---
    freezing_temperature: float = 0.0
    """Air temperature below which the soil is treated as frozen (degC)."""
    frozen_infiltration_fraction: float = 0.20
    """Fraction of throughfall that infiltrates frozen soil; the rest runs off
    (dimensionless)."""
    frozen_drainage_multiplier: float = 0.25
    """Multiplier on the drainage coefficient when frozen (dimensionless)."""
    frozen_uptake_multiplier: float = 0.30
    """Multiplier on the biomass-driven part of the uptake factor when frozen
    (dimensionless)."""
    frozen_reference_et_multiplier: float = 0.20
    """Multiplier on reference evapotranspiration when frozen
    (dimensionless)."""

    # --- Evapotranspiration ---
    base_temperature: float = 0.0
    """Temperature above which degree-days accumulate (degC)."""
    elevation_et_gradient: float = 0.08
    """Fractional increase in reference evapotranspiration per kilometre of
    elevation (per km)."""
    elevation_et_multiplier_bounds: tuple[float, float] = (0.75, 1.35)
    """Clip bounds of the elevation multiplier (dimensionless)."""

    # --- Clay effects ---
    clay_bounds: tuple[float, float] = (0.0, 80.0)
    """Clip bounds applied to the input clay content (percent)."""
    drainage_clay_response: float = 0.5
    """Relative strength of the clay effect on drainage, which it reduces
    (dimensionless)."""
    runoff_clay_response: float = 0.5
    """Relative strength of the clay effect on runoff, which it increases
    (dimensionless)."""
    stress_clay_response: float = 0.3
    """Relative strength of the clay effect on the stress exponent, which it
    increases (dimensionless)."""
    nominal_stress_exponent: float = 1.4
    """Water-stress exponent at the reference clay content (dimensionless)."""
    soil_water_capacity_bounds: tuple[float, float] = (60.0, 320.0)
    """Clip bounds of the clay-adjusted soil water capacity (mm)."""
    drainage_coefficient_bounds: tuple[float, float] = (0.015, 0.25)
    """Clip bounds of the clay-adjusted drainage coefficient
    (dimensionless)."""
    max_runoff_fraction_bounds: tuple[float, float] = (0.05, 0.90)
    """Clip bounds of the clay-adjusted maximum runoff fraction
    (dimensionless)."""
    stress_exponent_bounds: tuple[float, float] = (1.0, 2.2)
    """Clip bounds of the clay-adjusted stress exponent (dimensionless)."""
