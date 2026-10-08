r"""Process functions of the soil water balance.

Each function is pure and vectorised: arguments may be scalars or arrays, and
broadcast against one another under the usual numpy rules. None of them carries
state between time steps; that happens in `soil_moisture_model.model.simulate`.
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .constants import DAYS_PER_WEEK
from .params import ModelConstants, SoilWaterParams

DEFAULT_CONSTANTS = ModelConstants()


def biomass_fraction(biomass: ArrayLike, half_saturation: ArrayLike) -> NDArray:
    r"""Return the saturating biomass fraction that scales every biomass effect.

    $$
    f_B = \frac{B}{B + K_B}, \qquad B \leftarrow \max(B, 0)
    $$

    Parameters
    ----------
    biomass
        Plant biomass, $B$ (grams of carbon per square metre). Negative values
        are treated as zero.
    half_saturation
        Biomass at which $f_B = 1/2$, $K_B$ (grams of carbon per square metre).
        Must be positive.

    Returns
    -------
    NDArray
        $f_B \in [0, 1)$ (dimensionless).
    """
    b = np.maximum(np.asarray(biomass, dtype=float), 0.0)
    return b / (b + half_saturation)


def crop_coefficient(
    fraction: ArrayLike, constants: ModelConstants = DEFAULT_CONSTANTS
) -> NDArray:
    r"""Return the crop coefficient, interpolated linearly in the biomass fraction.

    $$
    k_c = k_{c,\min} + (k_{c,\max} - k_{c,\min})\, f_B
    $$

    Parameters
    ----------
    fraction
        Biomass fraction $f_B$; see `biomass_fraction`.
    constants
        Supplies `min_crop_coefficient` and `max_crop_coefficient`.

    Returns
    -------
    NDArray
        $k_c$ (dimensionless).
    """
    lo, hi = constants.min_crop_coefficient, constants.max_crop_coefficient
    return lo + (hi - lo) * np.asarray(fraction, dtype=float)


def interception_capacity(
    fraction: ArrayLike, constants: ModelConstants = DEFAULT_CONSTANTS
) -> NDArray:
    r"""Return the weekly canopy interception capacity.

    $$
    I_{\max} = I_{\max}^{\infty}\, f_B
    $$

    Parameters
    ----------
    fraction
        Biomass fraction $f_B$; see `biomass_fraction`.
    constants
        Supplies `max_interception_capacity`, $I_{\max}^{\infty}$.

    Returns
    -------
    NDArray
        $I_{\max}$ (mm per week).
    """
    return constants.max_interception_capacity * np.asarray(fraction, dtype=float)


def uptake_factor(
    fraction: ArrayLike, constants: ModelConstants = DEFAULT_CONSTANTS
) -> NDArray:
    r"""Return the root-uptake multiplier on potential evapotranspiration.

    $$
    u = 1 + (u_{\max} - 1)\, f_B
    $$

    Parameters
    ----------
    fraction
        Biomass fraction $f_B$; see `biomass_fraction`.
    constants
        Supplies `max_uptake_factor`, $u_{\max}$.

    Returns
    -------
    NDArray
        $u$ (dimensionless).
    """
    return 1.0 + (constants.max_uptake_factor - 1.0) * np.asarray(fraction, float)


def elevation_pet_multiplier(
    elevation: ArrayLike, constants: ModelConstants = DEFAULT_CONSTANTS
) -> NDArray:
    r"""Return the multiplier on reference evapotranspiration due to elevation.

    $$
    m_z = \mathrm{clip}\left(1 + g_z\, \frac{z}{1000},\; m_{z,\min},\; m_{z,\max}\right)
    $$

    Parameters
    ----------
    elevation
        Site elevation, $z$ (metres).
    constants
        Supplies `elevation_pet_gradient`, $g_z$, and
        `elevation_pet_multiplier_bounds`.

    Returns
    -------
    NDArray
        $m_z$ (dimensionless).
    """
    z_km = np.asarray(elevation, dtype=float) / 1000.0
    lo, hi = constants.elevation_pet_multiplier_bounds
    return np.clip(1.0 + constants.elevation_pet_gradient * z_km, lo, hi)


def reference_evapotranspiration(
    temperature: ArrayLike,
    elevation: ArrayLike,
    pet_coefficient: ArrayLike,
    constants: ModelConstants = DEFAULT_CONSTANTS,
) -> NDArray:
    r"""Return weekly reference evapotranspiration from a degree-day relation.

    $$
    E_0 = c_E \cdot 7 \max(T - T_b, 0) \cdot m_z
    $$

    This is the evaporative demand before the crop coefficient and uptake
    factor are applied.

    Parameters
    ----------
    temperature
        Weekly mean air temperature, $T$ (degC).
    elevation
        Site elevation (metres); see `elevation_pet_multiplier`.
    pet_coefficient
        Evapotranspiration per degree-day, $c_E$ (mm per degC per day).
    constants
        Supplies `pet_base_temperature`, $T_b$, and the elevation settings.

    Returns
    -------
    NDArray
        $E_0$ (mm per week).
    """
    t = np.asarray(temperature, dtype=float)
    coefficient = np.asarray(pet_coefficient, dtype=float)
    degree_days = np.maximum(t - constants.pet_base_temperature, 0.0) * DAYS_PER_WEEK
    return coefficient * degree_days * elevation_pet_multiplier(elevation, constants)


@dataclass(frozen=True)
class SoilProperties:
    """Soil hydraulic properties after adjustment for clay content.

    Each field has the broadcast shape of the clay content and the parameters.
    """

    soil_water_capacity: NDArray[np.float64]
    """Maximum soil water storage, $S_{\\max}$ (mm)."""
    drainage_coefficient: NDArray[np.float64]
    """Fraction of water above field capacity drained per week, $d$
    (dimensionless)."""
    max_runoff_fraction: NDArray[np.float64]
    """Fraction of throughfall that runs off a saturated soil, $r_{\\max}$
    (dimensionless)."""
    stress_exponent: NDArray[np.float64]
    """Exponent of the water-stress function, $\\beta$ (dimensionless)."""


def soil_properties(
    clay: ArrayLike,
    params: SoilWaterParams,
    constants: ModelConstants = DEFAULT_CONSTANTS,
) -> SoilProperties:
    r"""Adjust the base soil properties for clay content.

    With clay content $C$ clipped to `clay_bounds` and

    $$
    \Delta = s_C \, \frac{C - C_{\mathrm{ref}}}{100},
    $$

    each property is scaled linearly in $\Delta$ and then clipped to its bounds:

    $$
    \begin{aligned}
    S_{\max} &= S_{\max,0}\,(1 + \Delta) \\
    d        &= d_0\,(1 - a_d \Delta) \\
    r_{\max} &= r_{\max,0}\,(1 + a_r \Delta) \\
    \beta    &= \beta_0\,(1 + a_\beta \Delta)
    \end{aligned}
    $$

    So more clay means more storage, slower drainage, more runoff and a
    steeper stress response.

    Parameters
    ----------
    clay
        Soil clay content, $C$ (percent).
    params
        Supplies the `base_*` values, `reference_clay` ($C_{\mathrm{ref}}$)
        and `clay_sensitivity` ($s_C$).
    constants
        Supplies $\beta_0$, the response factors $a_d, a_r, a_\beta$ and all
        clip bounds.

    Returns
    -------
    SoilProperties
        The adjusted properties.
    """
    c = constants
    clay_clipped = np.clip(np.asarray(clay, dtype=float), *c.clay_bounds)
    delta = params.clay_sensitivity * (clay_clipped - params.reference_clay) / 100.0

    return SoilProperties(
        soil_water_capacity=np.clip(
            params.base_soil_water_capacity * (1.0 + delta),
            *c.soil_water_capacity_bounds,
        ),
        drainage_coefficient=np.clip(
            params.base_drainage_coefficient * (1.0 - c.drainage_clay_response * delta),
            *c.drainage_coefficient_bounds,
        ),
        max_runoff_fraction=np.clip(
            params.base_max_runoff_fraction * (1.0 + c.runoff_clay_response * delta),
            *c.max_runoff_fraction_bounds,
        ),
        stress_exponent=np.clip(
            c.base_stress_exponent * (1.0 + c.stress_clay_response * delta),
            *c.stress_exponent_bounds,
        ),
    )
