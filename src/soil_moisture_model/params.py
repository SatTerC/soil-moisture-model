"""Model parameters and fixed constants.

`SoilWaterParams` holds the parameters that are calibrated against observations.
`ModelConstants` holds the remaining numbers that shape the model's response but
are not calibrated. Both are frozen dataclasses.

Every field of `SoilWaterParams` may be a scalar or an array that broadcasts
against the spatial shape of the drivers, so parameters can vary per pixel.
"""

from dataclasses import dataclass, fields

import numpy as np
from numpy.typing import ArrayLike, NDArray

type FloatOrArray = float | NDArray[np.float64]


def _check(
    name: str, value: ArrayLike, lo: float, hi: float, *, open_lo: bool, open_hi: bool
) -> None:
    v = np.asarray(value, dtype=float)
    below = v <= lo if open_lo else v < lo
    above = v >= hi if open_hi else v > hi
    if np.any(below) or np.any(above):
        left, right = "(["[not open_lo], ")]"[not open_hi]
        raise ValueError(f"{name} must lie in {left}{lo}, {hi}{right}, got {value!r}")


# name -> (lower bound, upper bound, lower bound excluded?, upper bound excluded?)
_PARAM_RANGES: dict[str, tuple[float, float, bool, bool]] = {
    "drainage_coefficient": (0.0, 1.0, False, False),
    "max_runoff_fraction": (0.0, 1.0, False, False),
    "runoff_exponent": (0.0, np.inf, True, False),
    "rooting_depth": (0.0, np.inf, True, False),
    "depletion_fraction": (0.0, 1.0, False, True),
    "reference_et_coefficient": (0.0, np.inf, False, False),
    "biomass_half_saturation": (0.0, np.inf, True, False),
}


@dataclass(frozen=True)
class SoilWaterParams:
    r"""Calibrated parameters of the soil water balance.

    `rooting_depth` and `depletion_fraction` are properties of the vegetation,
    which `[FAO56]` Table 22 lists by crop; the caller maps plant functional type
    to values.

    Raises
    ------
    ValueError
        If any parameter lies outside its physically meaningful range.
    """

    drainage_coefficient: FloatOrArray = 0.10
    r"""Fraction of water above field capacity that drains each week, $k_d$
    (dimensionless)."""
    max_runoff_fraction: FloatOrArray = 0.45
    r"""Fraction of throughfall that runs off when the store is full,
    $r_{\max}$ (dimensionless)."""
    runoff_exponent: FloatOrArray = 2.0
    r"""Exponent of relative soil moisture in the runoff fraction, $\gamma$
    (dimensionless)."""
    rooting_depth: FloatOrArray = 1.0
    r"""Depth of soil from which roots draw water, $Z_r$ (m)."""
    depletion_fraction: FloatOrArray = 0.5
    r"""Fraction of the water held at field capacity that can be used before
    evapotranspiration is reduced, $p$ (dimensionless, $0 \le p < 1$).
    `[FAO56]` gives 0.3 to 0.7 by crop, and says 0.5 "is commonly used for many
    crops"."""
    reference_et_coefficient: FloatOrArray = 0.15
    r"""Reference evapotranspiration per degree-day above the base temperature,
    $c_{ET}$ (mm per degC per day). The default matches the temperate humid
    row of `[FAO56]` Table 2, 1-2 mm per day at 10 degC and 2-4 mm per day at
    20 degC."""
    biomass_half_saturation: FloatOrArray = 150.0
    r"""Biomass at which the biomass saturation reaches 1/2, $K_B$ (grams of
    carbon per square metre)."""

    def __post_init__(self) -> None:
        """Validate parameter ranges."""
        for name, (lo, hi, open_lo, open_hi) in _PARAM_RANGES.items():
            _check(name, getattr(self, name), lo, hi, open_lo=open_lo, open_hi=open_hi)

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
    r"""Crop coefficient with no biomass, $K_{c,\min}$ (dimensionless)."""
    max_crop_coefficient: float = 1.20
    r"""Crop coefficient approached as biomass becomes large, $K_{c,\max}$
    (dimensionless)."""
    max_interception_capacity: float = 3.0
    r"""Interception capacity approached as biomass becomes large, $I_{\max}$
    (mm per week)."""

    # --- Frozen weeks ---
    freezing_temperature: float = 0.0
    r"""Weekly mean air temperature below which a week is frozen,
    $T_{\mathrm{frz}}$ (degC)."""
    frozen_infiltration_fraction: float = 0.20
    r"""Fraction of throughfall that infiltrates in a frozen week, the rest
    running off, $\phi^{\mathrm{frz}}$ (dimensionless)."""
    frozen_drainage_multiplier: float = 0.25
    r"""Multiplier on the drainage coefficient in a frozen week,
    $m^{\mathrm{frz}}_{d}$ (dimensionless)."""
    frozen_reference_et_multiplier: float = 0.20
    r"""Multiplier on reference evapotranspiration in a frozen week,
    $m^{\mathrm{frz}}_{ET}$ (dimensionless)."""

    # --- Evapotranspiration ---
    base_temperature: float = 0.0
    r"""Temperature above which degree-days accumulate, $T_b$ (degC)."""
