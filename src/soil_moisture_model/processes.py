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
    \Delta = \frac{4098 \times 0.6108 \exp\left(\frac{17.27\, T}{T + 237.3}\right)}
             {(T + 237.3)^2}
    $$

    Parameters
    ----------
    temperature
        Air temperature, $T$ (degC).

    Returns
    -------
    NDArray
        Slope of the saturation vapour pressure curve, $\Delta$ (kPa per degC).
    """
    temp = np.asarray(temperature, dtype=float)
    return 4098.0 * 0.6108 * np.exp(17.27 * temp / (temp + 237.3)) / (temp + 237.3) ** 2


def elevation_et_multiplier(elevation: ArrayLike, temperature: ArrayLike) -> NDArray:
    r"""Return the multiplier on reference evapotranspiration due to elevation.

    The multiplier is the equilibrium evaporation factor $\Delta / (\Delta +
    \gamma_{\mathrm{psy}})$ at the site, relative to its value at sea level:

    $$
    m_z = \frac{\Delta + \gamma_{\mathrm{psy}}(0)}{\Delta + \gamma_{\mathrm{psy}}(z)}
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


def water_content_at_wilting_point(
    sand: ArrayLike, clay: ArrayLike, organic_matter: ArrayLike
) -> NDArray:
    r"""Return the volumetric water content at 1500 kPa, `[SR06]` eq. (1).

    $$
    \begin{aligned}
    \theta_{WP}^{t} &= -0.024 f_{\mathrm{sand}} + 0.487 f_{\mathrm{clay}}
        + 0.006 M + 0.005 f_{\mathrm{sand}} M
        - 0.013 f_{\mathrm{clay}} M + 0.068 f_{\mathrm{sand}} f_{\mathrm{clay}}
        + 0.031 \\
    \theta_{WP} &= \theta_{WP}^{t} + 0.14\, \theta_{WP}^{t} - 0.02
    \end{aligned}
    $$

    with organic matter $M$ in percent by weight, as `[SR06]` fits it.

    Parameters
    ----------
    sand
        Sand fraction by weight, $f_{\mathrm{sand}}$ (dimensionless).
    clay
        Clay fraction by weight, $f_{\mathrm{clay}}$ (dimensionless).
    organic_matter
        Organic matter fraction by weight, $f_{\mathrm{om}}$ (dimensionless);
        $M = 100\, f_{\mathrm{om}}$.

    Returns
    -------
    NDArray
        Water content at wilting point, $\theta_{WP}$ (m3 per m3).
    """
    f_sand, f_clay = np.asarray(sand, dtype=float), np.asarray(clay, dtype=float)
    om = 100.0 * np.asarray(organic_matter, dtype=float)
    first = (
        -0.024 * f_sand
        + 0.487 * f_clay
        + 0.006 * om
        + 0.005 * f_sand * om
        - 0.013 * f_clay * om
        + 0.068 * f_sand * f_clay
        + 0.031
    )
    return first + 0.14 * first - 0.02


def water_content_at_field_capacity(
    sand: ArrayLike, clay: ArrayLike, organic_matter: ArrayLike
) -> NDArray:
    r"""Return the volumetric water content at 33 kPa, `[SR06]` eq. (2).

    $$
    \begin{aligned}
    \theta_{FC}^{t} &= -0.251 f_{\mathrm{sand}} + 0.195 f_{\mathrm{clay}}
        + 0.011 M + 0.006 f_{\mathrm{sand}} M
        - 0.027 f_{\mathrm{clay}} M + 0.452 f_{\mathrm{sand}} f_{\mathrm{clay}}
        + 0.299 \\
    \theta_{FC} &= \theta_{FC}^{t} + 1.283 (\theta_{FC}^{t})^2
        - 0.374\, \theta_{FC}^{t} - 0.015
    \end{aligned}
    $$

    Parameters
    ----------
    sand, clay, organic_matter
        Sand, clay and organic matter fractions by weight; see
        `water_content_at_wilting_point`.

    Returns
    -------
    NDArray
        Water content at field capacity, $\theta_{FC}$ (m3 per m3).
    """
    f_sand, f_clay = np.asarray(sand, dtype=float), np.asarray(clay, dtype=float)
    om = 100.0 * np.asarray(organic_matter, dtype=float)
    first = (
        -0.251 * f_sand
        + 0.195 * f_clay
        + 0.011 * om
        + 0.006 * f_sand * om
        - 0.027 * f_clay * om
        + 0.452 * f_sand * f_clay
        + 0.299
    )
    return first + 1.283 * first**2 - 0.374 * first - 0.015


def water_content_at_saturation(
    sand: ArrayLike, clay: ArrayLike, organic_matter: ArrayLike
) -> NDArray:
    r"""Return the volumetric water content at saturation, `[SR06]` eqs. (3), (5).

    $$
    \begin{aligned}
    \theta_{S-33}^{t} &= 0.278 f_{\mathrm{sand}} + 0.034 f_{\mathrm{clay}}
        + 0.022 M - 0.018 f_{\mathrm{sand}} M
        - 0.027 f_{\mathrm{clay}} M - 0.584 f_{\mathrm{sand}} f_{\mathrm{clay}}
        + 0.078 \\
    \theta_{S-33} &= \theta_{S-33}^{t} + 0.636\, \theta_{S-33}^{t} - 0.107 \\
    \theta_{sat} &= \theta_{FC} + \theta_{S-33}
        - 0.097 f_{\mathrm{sand}} + 0.043
    \end{aligned}
    $$

    This is the normal-density value; `[SR06]`'s adjustment for bulk density is
    not applied.

    Parameters
    ----------
    sand, clay, organic_matter
        Sand, clay and organic matter fractions by weight; see
        `water_content_at_wilting_point`.

    Returns
    -------
    NDArray
        Water content at saturation, $\theta_{sat}$ (m3 per m3).
    """
    f_sand, f_clay = np.asarray(sand, dtype=float), np.asarray(clay, dtype=float)
    om = 100.0 * np.asarray(organic_matter, dtype=float)
    first = (
        0.278 * f_sand
        + 0.034 * f_clay
        + 0.022 * om
        - 0.018 * f_sand * om
        - 0.027 * f_clay * om
        - 0.584 * f_sand * f_clay
        + 0.078
    )
    above_field_capacity = first + 0.636 * first - 0.107
    theta_fc = water_content_at_field_capacity(sand, clay, organic_matter)
    return theta_fc + above_field_capacity - 0.097 * f_sand + 0.043


@dataclass(frozen=True)
class SoilProperties:
    """Soil hydraulic properties from texture and rooting depth.

    Each field has the broadcast shape of the texture and the parameters. The
    stores count water above the wilting point, over the rooting depth.
    """

    water_content_at_wilting_point: NDArray[np.float64]
    r"""Volumetric water content at wilting point, $\theta_{WP}$ (m3 per m3)."""
    water_content_at_field_capacity: NDArray[np.float64]
    r"""Volumetric water content at field capacity, $\theta_{FC}$ (m3 per m3)."""
    water_content_at_saturation: NDArray[np.float64]
    r"""Volumetric water content at saturation, $\theta_{sat}$ (m3 per m3)."""
    field_capacity: NDArray[np.float64]
    r"""Field capacity, $S_{fc} = 1000 (\theta_{FC} - \theta_{WP}) Z_r$ (mm);
    `[FAO56]`'s total available water, eq. (82)."""
    soil_water_capacity: NDArray[np.float64]
    r"""Soil water capacity, $S_{\max} = 1000 (\theta_{sat} - \theta_{WP}) Z_r$
    (mm)."""


def soil_properties(
    sand: ArrayLike,
    clay: ArrayLike,
    organic_matter: ArrayLike,
    params: SoilWaterParams,
) -> SoilProperties:
    r"""Return the soil hydraulic properties from texture and rooting depth.

    The water contents come from the `[SR06]` pedotransfer functions; the stores
    count water above the wilting point over the rooting depth $Z_r$:

    $$
    S_{fc} = 1000 (\theta_{FC} - \theta_{WP}) Z_r, \qquad
    S_{\max} = 1000 (\theta_{sat} - \theta_{WP}) Z_r
    $$

    Where the pedotransfer functions do not give $0 < \theta_{WP} < \theta_{FC} <
    \theta_{sat} \le 1$, which happens only for implausible texture, every
    property is NaN, so the pixel's outputs are NaN.

    Parameters
    ----------
    sand, clay, organic_matter
        Sand, clay and organic matter fractions by weight; see
        `water_content_at_wilting_point`.
    params
        Supplies `rooting_depth`, $Z_r$.

    Returns
    -------
    SoilProperties
        The soil hydraulic properties.
    """
    theta_wp = water_content_at_wilting_point(sand, clay, organic_matter)
    theta_fc = water_content_at_field_capacity(sand, clay, organic_matter)
    theta_sat = water_content_at_saturation(sand, clay, organic_matter)
    ordered = (theta_wp > 0.0) & (theta_wp < theta_fc) & (theta_fc < theta_sat)
    ordered &= theta_sat <= 1.0
    theta_wp, theta_fc, theta_sat = (
        np.where(ordered, x, np.nan) for x in (theta_wp, theta_fc, theta_sat)
    )
    depth_mm = 1000.0 * np.asarray(params.rooting_depth, dtype=float)
    return SoilProperties(
        water_content_at_wilting_point=theta_wp,
        water_content_at_field_capacity=theta_fc,
        water_content_at_saturation=theta_sat,
        field_capacity=(theta_fc - theta_wp) * depth_mm,
        soil_water_capacity=(theta_sat - theta_wp) * depth_mm,
    )
