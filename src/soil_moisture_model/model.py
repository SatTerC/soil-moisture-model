r"""Weekly bucket model of soil moisture.

`simulate` steps a single-layer soil water store forward one week at a time.
Each week, precipitation is split into canopy interception and throughfall;
throughfall is split into runoff and infiltration; evapotranspiration is drawn
from the store, limited by water stress; and water above field capacity drains.
Frozen weeks (air temperature below `ModelConstants.freezing_temperature`)
infiltrate less and evaporate, take up and drain more slowly.

The drivers are time-leading arrays of shape ``(time, *space)``. Site inputs and
every field of `SoilWaterParams` broadcast against ``space``, so a whole block
of pixels, each with its own parameters, runs in a single call. Only the time
dimension is looped over.
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .params import ModelConstants, SoilWaterParams
from .processes import (
    SoilProperties,
    biomass_saturation,
    crop_coefficient,
    interception_capacity,
    reference_evapotranspiration,
    soil_properties,
    uptake_factor,
)


@dataclass(frozen=True)
class SoilWaterOutput:
    """Outputs of `simulate`.

    Time series have shape ``(time, *space)``; water amounts are weekly totals.
    """

    soil_moisture: NDArray[np.float64]
    """Soil water store at the end of the week (mm)."""
    relative_soil_moisture: NDArray[np.float64]
    """Soil water store as a fraction of the soil water capacity
    (dimensionless)."""
    actual_evapotranspiration: NDArray[np.float64]
    """Water drawn from the soil by evapotranspiration (mm per week)."""
    potential_evapotranspiration: NDArray[np.float64]
    """Evapotranspiration if soil water were not limiting: reference
    evapotranspiration times crop coefficient times uptake factor (mm per
    week)."""
    reference_evapotranspiration: NDArray[np.float64]
    """Temperature- and elevation-driven evaporative demand, before the frozen
    multiplier (mm per week)."""
    crop_coefficient: NDArray[np.float64]
    """Biomass-dependent crop coefficient (dimensionless)."""
    uptake_factor: NDArray[np.float64]
    """Biomass-dependent root-uptake multiplier, before the frozen multiplier
    (dimensionless)."""
    interception_capacity: NDArray[np.float64]
    """Biomass-dependent canopy interception capacity (mm per week)."""
    interception: NDArray[np.float64]
    """Precipitation intercepted by the canopy and evaporated (mm per week)."""
    throughfall: NDArray[np.float64]
    """Precipitation reaching the soil surface (mm per week)."""
    runoff: NDArray[np.float64]
    """Throughfall that runs off instead of infiltrating, including
    saturation excess (mm per week)."""
    drainage: NDArray[np.float64]
    """Water draining below the store (mm per week)."""
    water_stress_coefficient: NDArray[np.float64]
    """Water-stress factor on evapotranspiration, 1 meaning unstressed
    (dimensionless)."""
    frozen: NDArray[np.bool_]
    """Whether the soil was treated as frozen."""
    soil: SoilProperties
    """Clay-adjusted soil properties, with shape ``space``."""

    @property
    def total_evaporative_loss(self) -> NDArray[np.float64]:
        """Actual evapotranspiration plus interception (mm per week)."""
        return self.actual_evapotranspiration + self.interception


def simulate(
    temperature: ArrayLike,
    precipitation: ArrayLike,
    biomass: ArrayLike,
    elevation: ArrayLike,
    clay: ArrayLike,
    *,
    initial_soil_moisture: ArrayLike = 50.0,
    params: SoilWaterParams | None = None,
    constants: ModelConstants | None = None,
) -> SoilWaterOutput:
    r"""Run the weekly soil water balance.

    Each week $t$, starting from store $S_{t-1}$:

    1. Interception $I = \min(P, I_{\max})$, throughfall $P_T = P - I$.
    2. Surface runoff $Q_s = r_{\max} (S_{t-1}/S_{\max})^{\gamma} P_T$, or
       $(1 - \phi_f) P_T$ if frozen.
    3. Saturation excess $Q_e = \max(S_{t-1} + P_T - Q_s - S_{\max}, 0)$ also
       runs off: total runoff $Q = Q_s + Q_e$, infiltration $F = P_T - Q$.
    4. Available water $A = S_{t-1} + F \le S_{\max}$.
    5. Water stress $w = (A / S_{\max})^{\beta}$.
    6. Actual evapotranspiration $E_a = \min(w\, E_0 k_c u,\; A)$.
    7. Drainage $D = d \max(A - E_a - \theta_{fc} S_{\max}, 0)$.
    8. $S_t = A - E_a - D$.

    Parameters
    ----------
    temperature
        Weekly mean air temperature (degC), shape ``(time, *space)``.
    precipitation
        Weekly precipitation (mm), shape ``(time, *space)``. Negative values
        are treated as zero.
    biomass
        Plant biomass (grams of carbon per square metre), shape
        ``(time, *space)``. Negative values are treated as zero.
    elevation
        Site elevation (metres), broadcastable to ``space``.
    clay
        Soil clay content (percent), broadcastable to ``space``.
    initial_soil_moisture
        Soil water store before the first week (mm), broadcastable to ``space``.
        Clipped to the soil water capacity.
    params
        Calibrated parameters. Defaults to `SoilWaterParams()`.
    constants
        Fixed constants. Defaults to `ModelConstants()`.

    Returns
    -------
    SoilWaterOutput
        Weekly fluxes and states, and the clay-adjusted soil properties.

    Raises
    ------
    ValueError
        If the drivers are not at least one-dimensional, or their leading
        (time) dimensions differ.

    Notes
    -----
    NaN in any input propagates to the affected pixels' outputs rather than
    raising, so masked pixels can share a block with valid ones.
    """
    params = SoilWaterParams() if params is None else params
    c = ModelConstants() if constants is None else constants

    temp = np.asarray(temperature, dtype=float)
    precip = np.maximum(np.asarray(precipitation, dtype=float), 0.0)
    bio = np.asarray(biomass, dtype=float)
    if temp.ndim == 0 or precip.ndim == 0 or bio.ndim == 0:
        raise ValueError("drivers must have a leading time dimension")
    n_time = temp.shape[0]
    if precip.shape[0] != n_time or bio.shape[0] != n_time:
        raise ValueError(
            "drivers must share their leading (time) dimension, got "
            f"{temp.shape}, {precip.shape} and {bio.shape}"
        )

    soil = soil_properties(clay, params, c)
    space = np.broadcast_shapes(
        temp.shape[1:],
        precip.shape[1:],
        bio.shape[1:],
        np.shape(elevation),
        np.shape(initial_soil_moisture),
        np.shape(soil.soil_water_capacity),
        *(np.shape(v) for v in params.as_dict().values()),
    )
    shape = (n_time, *space)
    temp, precip, bio = (np.broadcast_to(x, shape) for x in (temp, precip, bio))

    # Everything that does not depend on the soil water store is precomputed for
    # the whole series; only the store itself is stepped through time.
    frozen = temp < c.freezing_temperature
    f_b = biomass_saturation(bio, params.biomass_half_saturation)
    k_c = crop_coefficient(f_b, c)
    u = uptake_factor(f_b, c)
    interception_cap = interception_capacity(f_b, c)
    interception = np.minimum(precip, interception_cap)
    throughfall = precip - interception

    reference_et = reference_evapotranspiration(
        temp, elevation, params.reference_et_coefficient, c
    )
    reference_et_eff = np.where(
        frozen, reference_et * c.frozen_reference_et_multiplier, reference_et
    )
    u_eff = np.where(frozen, 1.0 + (u - 1.0) * c.frozen_uptake_multiplier, u)
    potential_et = reference_et_eff * k_c * u_eff
    k_d = soil.drainage_coefficient
    k_d_eff = np.where(frozen, k_d * c.frozen_drainage_multiplier, k_d)

    s_max = np.broadcast_to(soil.soil_water_capacity, space)
    r_max = soil.max_runoff_fraction
    beta = soil.stress_exponent
    s_fc = params.field_capacity_fraction * s_max
    frozen_runoff = (1.0 - c.frozen_infiltration_fraction) * throughfall

    s = np.clip(np.broadcast_to(initial_soil_moisture, space), 0.0, s_max)
    soil_moisture = np.empty(shape)
    runoff = np.empty(shape)
    drainage = np.empty(shape)
    aet = np.empty(shape)
    k_s = np.empty(shape)

    for t in range(n_time):
        thawed_runoff = r_max * (s / s_max) ** params.runoff_exponent * throughfall[t]
        surface_runoff = np.where(frozen[t], frozen_runoff[t], thawed_runoff)
        # Infiltration that would overfill the store runs off instead.
        excess = np.maximum(s + throughfall[t] - surface_runoff - s_max, 0.0)
        runoff[t] = surface_runoff + excess
        soil_moisture_after_infiltration = np.minimum(
            s_max, s + throughfall[t] - runoff[t]
        )
        k_s[t] = np.clip((soil_moisture_after_infiltration / s_max) ** beta, 0.0, 1.0)
        aet[t] = np.minimum(potential_et[t] * k_s[t], soil_moisture_after_infiltration)
        after_et = soil_moisture_after_infiltration - aet[t]
        drainage[t] = k_d_eff[t] * np.maximum(after_et - s_fc, 0.0)
        s = np.clip(after_et - drainage[t], 0.0, s_max)
        soil_moisture[t] = s

    return SoilWaterOutput(
        soil_moisture=soil_moisture,
        relative_soil_moisture=soil_moisture / s_max,
        actual_evapotranspiration=aet,
        potential_evapotranspiration=potential_et,
        reference_evapotranspiration=reference_et,
        crop_coefficient=k_c,
        uptake_factor=u,
        interception_capacity=interception_cap,
        interception=interception,
        throughfall=throughfall,
        runoff=runoff,
        drainage=drainage,
        water_stress_coefficient=k_s,
        frozen=frozen,
        soil=soil,
    )
