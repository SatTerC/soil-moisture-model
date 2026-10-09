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


def biomass_saturation(
    biomass: ArrayLike, biomass_half_saturation: ArrayLike
) -> NDArray:
    r"""Return the biomass saturation, which scales every biomass effect.

    $$
    f_B = \frac{B}{B + K_B}, \qquad B \leftarrow \max(B, 0)
    $$

    Parameters
    ----------
    biomass
        Plant biomass, $B$ (grams of carbon per square metre). Negative values
        are treated as zero.
    biomass_half_saturation
        Biomass half-saturation, the biomass at which $f_B = 1/2$, $K_B$ (grams
        of carbon per square metre). Must be positive.

    Returns
    -------
    NDArray
        Biomass saturation, $f_B \in [0, 1)$ (dimensionless).
    """
    b = np.maximum(np.asarray(biomass, dtype=float), 0.0)
    return b / (b + biomass_half_saturation)


def crop_coefficient(
    biomass_saturation: ArrayLike, constants: ModelConstants = DEFAULT_CONSTANTS
) -> NDArray:
    r"""Return the crop coefficient, interpolated linearly in the biomass saturation.

    $$
    K_c = K_{c,\min} + (K_{c,\max} - K_{c,\min})\, f_B
    $$

    Parameters
    ----------
    biomass_saturation
        Biomass saturation, $f_B$; see `biomass_saturation`.
    constants
        Supplies `min_crop_coefficient`, $K_{c,\min}$, and
        `max_crop_coefficient`, $K_{c,\max}$.

    Returns
    -------
    NDArray
        Crop coefficient, $K_c$ (dimensionless).
    """
    lo, hi = constants.min_crop_coefficient, constants.max_crop_coefficient
    return lo + (hi - lo) * np.asarray(biomass_saturation, dtype=float)


def interception_capacity(
    biomass_saturation: ArrayLike, constants: ModelConstants = DEFAULT_CONSTANTS
) -> NDArray:
    r"""Return the weekly interception capacity, $f_B\, I_{\max}$.

    The interception capacity rises linearly from zero with no biomass to
    $I_{\max}$ as biomass becomes large. It deliberately has no symbol of its own.

    Parameters
    ----------
    biomass_saturation
        Biomass saturation, $f_B$; see `biomass_saturation`.
    constants
        Supplies `max_interception_capacity`, $I_{\max}$.

    Returns
    -------
    NDArray
        Interception capacity, $f_B\, I_{\max}$ (mm per week).
    """
    return constants.max_interception_capacity * np.asarray(
        biomass_saturation, dtype=float
    )


def uptake_factor(
    biomass_saturation: ArrayLike, constants: ModelConstants = DEFAULT_CONSTANTS
) -> NDArray:
    r"""Return the uptake factor, a multiplier on potential evapotranspiration.

    $$
    u = 1 + (u_{\max} - 1)\, f_B
    $$

    Parameters
    ----------
    biomass_saturation
        Biomass saturation, $f_B$; see `biomass_saturation`.
    constants
        Supplies `max_uptake_factor`, $u_{\max}$.

    Returns
    -------
    NDArray
        Uptake factor, $u$ (dimensionless).
    """
    return 1.0 + (constants.max_uptake_factor - 1.0) * np.asarray(
        biomass_saturation, float
    )


def elevation_et_multiplier(
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
        Supplies `elevation_et_gradient`, $g_z$, and
        `elevation_et_multiplier_bounds`, $(m_{z,\min}, m_{z,\max})$.

    Returns
    -------
    NDArray
        Elevation multiplier, $m_z$ (dimensionless).
    """
    z_km = np.asarray(elevation, dtype=float) / 1000.0
    lo, hi = constants.elevation_et_multiplier_bounds
    return np.clip(1.0 + constants.elevation_et_gradient * z_km, lo, hi)


def reference_evapotranspiration(
    temperature: ArrayLike,
    elevation: ArrayLike,
    reference_et_coefficient: ArrayLike,
    constants: ModelConstants = DEFAULT_CONSTANTS,
) -> NDArray:
    r"""Return weekly reference evapotranspiration from a degree-day relation.

    $$
    ET_o = c_{ET} \cdot 7 \max(T - T_b, 0) \cdot m_z
    $$

    This is the evaporative demand before the frozen-week adjustment, the crop
    coefficient and the uptake factor are applied.

    Parameters
    ----------
    temperature
        Weekly mean air temperature, $T$ (degC).
    elevation
        Site elevation (metres); see `elevation_et_multiplier`.
    reference_et_coefficient
        Reference ET coefficient, the reference evapotranspiration per
        degree-day, $c_{ET}$ (mm per degC per day).
    constants
        Supplies `base_temperature`, $T_b$, and the elevation settings.

    Returns
    -------
    NDArray
        Reference evapotranspiration, $ET_o$ (mm per week).
    """
    temp = np.asarray(temperature, dtype=float)
    coefficient = np.asarray(reference_et_coefficient, dtype=float)
    degree_days = np.maximum(temp - constants.base_temperature, 0.0) * DAYS_PER_WEEK
    return coefficient * degree_days * elevation_et_multiplier(elevation, constants)


@dataclass(frozen=True)
class SoilProperties:
    """Soil hydraulic properties after adjustment for clay content.

    Each field has the broadcast shape of the clay content and the parameters.
    """

    soil_water_capacity: NDArray[np.float64]
    r"""Soil water capacity, $S_{\max}$ (mm)."""
    drainage_coefficient: NDArray[np.float64]
    """Drainage coefficient, the fraction of water above field capacity drained
    per week, $k_d$ (dimensionless)."""
    max_runoff_fraction: NDArray[np.float64]
    r"""Maximum runoff fraction, the fraction of throughfall that runs off when
    the store is full, $r_{\max}$ (dimensionless)."""
    stress_exponent: NDArray[np.float64]
    r"""Stress exponent, the exponent of relative soil moisture in the
    water-stress coefficient, $\beta$ (dimensionless)."""


def soil_properties(
    clay: ArrayLike,
    params: SoilWaterParams,
    constants: ModelConstants = DEFAULT_CONSTANTS,
) -> SoilProperties:
    r"""Adjust the nominal soil properties for clay content.

    With clay content $C$ clipped to `clay_bounds` and

    $$
    \Delta = \kappa \, \frac{C - C^{\circ}}{100},
    $$

    each property is scaled linearly in $\Delta$ and then clipped to its bounds:

    $$
    \begin{aligned}
    S_{\max} &= S_{\max}^{\circ}\,(1 + \Delta) \\
    k_d      &= k_d^{\circ}\,(1 - a_d \Delta) \\
    r_{\max} &= r_{\max}^{\circ}\,(1 + a_r \Delta) \\
    \beta    &= \beta^{\circ}\,(1 + a_\beta \Delta)
    \end{aligned}
    $$

    So more clay means more storage, slower drainage, more runoff and a
    steeper stress response.

    Parameters
    ----------
    clay
        Soil clay content, $C$ (percent).
    params
        Supplies the `nominal_*` values $S_{\max}^{\circ}$, $k_d^{\circ}$ and
        $r_{\max}^{\circ}$, `nominal_clay` ($C^{\circ}$) and `clay_sensitivity`
        ($\kappa$).
    constants
        Supplies $\beta^{\circ}$, the clay response factors $a_d, a_r, a_\beta$ and all
        clip bounds.

    Returns
    -------
    SoilProperties
        The clay-adjusted properties.
    """
    c = constants
    clay_clipped = np.clip(np.asarray(clay, dtype=float), *c.clay_bounds)
    delta = params.clay_sensitivity * (clay_clipped - params.nominal_clay) / 100.0

    return SoilProperties(
        soil_water_capacity=np.clip(
            params.nominal_soil_water_capacity * (1.0 + delta),
            *c.soil_water_capacity_bounds,
        ),
        drainage_coefficient=np.clip(
            params.nominal_drainage_coefficient
            * (1.0 - c.drainage_clay_response * delta),
            *c.drainage_coefficient_bounds,
        ),
        max_runoff_fraction=np.clip(
            params.nominal_max_runoff_fraction * (1.0 + c.runoff_clay_response * delta),
            *c.max_runoff_fraction_bounds,
        ),
        stress_exponent=np.clip(
            c.nominal_stress_exponent * (1.0 + c.stress_clay_response * delta),
            *c.stress_exponent_bounds,
        ),
    )
