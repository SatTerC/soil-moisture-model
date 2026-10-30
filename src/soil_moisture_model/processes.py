r"""Process functions of the soil water balance.

Each function is pure and vectorised: arguments may be scalars or arrays, and
broadcast against one another under the usual numpy rules. None of them carries
state between time steps; that happens in `soil_moisture_model.model.simulate`.
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .params import ModelConstants, SoilWaterParams

_DAYS_PER_WEEK = 7
"""Number of days in one model time step."""

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


def atmospheric_pressure(elevation: ArrayLike) -> NDArray:
    r"""Return atmospheric pressure from elevation, `[FAO56]` eq. (7).

    $$
    p_{\mathrm{atm}} = 101.3 \left(\frac{293 - 0.0065\, z}{293}\right)^{5.26}
    $$

    Parameters
    ----------
    elevation
        Site elevation, $z$ (metres).

    Returns
    -------
    NDArray
        Atmospheric pressure, $p_{\mathrm{atm}}$ (kPa).
    """
    z = np.asarray(elevation, dtype=float)
    return 101.3 * ((293.0 - 0.0065 * z) / 293.0) ** 5.26


def psychrometric_constant(elevation: ArrayLike) -> NDArray:
    r"""Return the psychrometric constant, `[FAO56]` eq. (8).

    $$
    \gamma_{\mathrm{psy}} = 0.665 \times 10^{-3}\, p_{\mathrm{atm}}
    $$

    Parameters
    ----------
    elevation
        Site elevation, $z$ (metres); see `atmospheric_pressure`.

    Returns
    -------
    NDArray
        Psychrometric constant, $\gamma_{\mathrm{psy}}$ (kPa per degC).
    """
    return 0.665e-3 * atmospheric_pressure(elevation)


def saturation_vapour_pressure_slope(temperature: ArrayLike) -> NDArray:
    r"""Return the slope of the saturation vapour pressure curve, `[FAO56]` eq. (13).

    $$
    s = \frac{4098 \times 0.6108 \exp\left(\frac{17.27\, T}{T + 237.3}\right)}
             {(T + 237.3)^2}
    $$

    Parameters
    ----------
    temperature
        Air temperature, $T$ (degC).

    Returns
    -------
    NDArray
        Slope of the saturation vapour pressure curve, $s$ (kPa per degC).
    """
    temp = np.asarray(temperature, dtype=float)
    return 4098.0 * 0.6108 * np.exp(17.27 * temp / (temp + 237.3)) / (temp + 237.3) ** 2


def elevation_et_multiplier(elevation: ArrayLike, temperature: ArrayLike) -> NDArray:
    r"""Return the multiplier on reference evapotranspiration due to elevation.

    The multiplier is the equilibrium evaporation factor $s / (s +
    \gamma_{\mathrm{psy}})$ at the site, relative to its value at sea level:

    $$
    m_z = \frac{s + \gamma_{\mathrm{psy}}(0)}{s + \gamma_{\mathrm{psy}}(z)}
    $$

    Lower pressure at altitude lowers the psychrometric constant, so at a given
    temperature $m_z \ge 1$ above sea level. At 20 degC it rises by about 4 %
    per kilometre.

    Parameters
    ----------
    elevation
        Site elevation, $z$ (metres).
    temperature
        Air temperature, $T$ (degC); see `saturation_vapour_pressure_slope`.

    Returns
    -------
    NDArray
        Elevation multiplier, $m_z$ (dimensionless).
    """
    slope = saturation_vapour_pressure_slope(temperature)
    return (slope + psychrometric_constant(0.0)) / (
        slope + psychrometric_constant(elevation)
    )


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

    This is the evaporative demand before the frozen-week adjustment and the
    crop coefficient are applied.

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
        Supplies `base_temperature`, $T_b$.

    Returns
    -------
    NDArray
        Reference evapotranspiration, $ET_o$ (mm per week).
    """
    temp = np.asarray(temperature, dtype=float)
    coefficient = np.asarray(reference_et_coefficient, dtype=float)
    degree_days = np.maximum(temp - constants.base_temperature, 0.0) * _DAYS_PER_WEEK
    return coefficient * degree_days * elevation_et_multiplier(elevation, temp)


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
    r_{\max} &= r_{\max}^{\circ}\,(1 + a_r \Delta)
    \end{aligned}
    $$

    So more clay means more storage, slower drainage and more runoff.

    Parameters
    ----------
    clay
        Soil clay content, $C$ (percent).
    params
        Supplies the `nominal_*` values $S_{\max}^{\circ}$, $k_d^{\circ}$ and
        $r_{\max}^{\circ}$, `nominal_clay` ($C^{\circ}$) and `clay_sensitivity`
        ($\kappa$).
    constants
        Supplies the clay response factors $a_d$ and $a_r$ and all clip bounds.

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
    )
