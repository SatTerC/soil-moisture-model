"""
Soil Moisture Model
================================

Overview
--------
This module simulates weekly soil moisture dynamics using a simple bucket-style
soil water balance model driven by precipitation, temperature, biomass, soil
clay content, and site elevation.

The model keeps the main ecohydrological structure of the original version:
- soil clay content modifies soil water capacity, drainage, runoff, and stress;
- plant biomass affects canopy interception;
- plant biomass affects evapotranspiration through crop coefficient and uptake;
- water stress reduces actual evapotranspiration when soil water is limiting;
- freezing and thawing are represented using a simple temperature-threshold rule.

Simplifications
---------------
This version reduces the parameter count to 10 by simplifying or fixing
secondary processes:
- freezing and thawing are handled with fixed internal rules and no added parameters;
- atmospheric pressure is not explicitly calculated;
- elevation affects PET through a fixed multiplier, not through calibratable
  elevation parameters;
- biomass uses one shared half-saturation parameter for crop coefficient,
  interception, and uptake;
- clay uses one shared sensitivity parameter across multiple soil properties.

Model inputs
------------
Required columns in `data`:
- `temp_c`         : weekly mean air temperature in degrees C
- `precip_mm`      : weekly precipitation in mm
- `biomass_gC_m2`  : plant biomass in gC m^-2

Required site inputs:
- `elevation_m`    : site elevation in meters
- `clay_pct`       : soil clay content in percent

Main outputs
------------
Returned DataFrame columns include:
- `soil_moisture_mm`
- `relative_soil_moisture`
- `et_actual_mm`
- `et_potential_mm`
- `total_evaporative_loss_mm`
- `runoff_mm`
- `drainage_mm`
- `intercepted_mm`
- `throughfall_mm`
- `water_stress`
- `frozen_soil`

Notes
-----
- Time step is weekly.
- All water stores and fluxes are in mm.
- PET is estimated from temperature and adjusted by elevation with a fixed
  multiplier.
- Frozen soil is diagnosed from weekly air temperature using a simple 0°C threshold.
- This is a reduced-complexity model intended for calibration, comparison,
  and exploratory ecohydrological analysis rather than detailed process
  representation.
"""

from dataclasses import dataclass, fields, replace
from typing import Dict, Optional, Sequence
import numpy as np
import pandas as pd


@dataclass
class SoilWaterParams:
    initial_soil_moisture_mm: float = 50.0
    base_soil_water_capacity_mm: float = 160.0
    base_drainage_coeff: float = 0.10
    base_runoff_fraction_max: float = 0.45
    runoff_exponent: float = 2.0
    field_capacity_fraction: float = 0.70
    reference_clay_pct: float = 25.0
    clay_sensitivity: float = 0.04
    pet_coeff_mm_per_degday: float = 0.55
    biomass_half_sat_gC_m2: float = 150.0


CALIBRATABLE_PARAMS = [
    "initial_soil_moisture_mm",
    "base_soil_water_capacity_mm",
    "base_drainage_coeff",
    "base_runoff_fraction_max",
    "runoff_exponent",
    "field_capacity_fraction",
    "reference_clay_pct",
    "clay_sensitivity",
    "pet_coeff_mm_per_degday",
    "biomass_half_sat_gC_m2",
]


def params_to_vector(
    params: SoilWaterParams,
    names: Sequence[str] = CALIBRATABLE_PARAMS,
) -> np.ndarray:
    return np.array([getattr(params, n) for n in names], dtype=float)


def vector_to_params(
    x: Sequence[float],
    base: SoilWaterParams,
    names: Sequence[str] = CALIBRATABLE_PARAMS,
) -> SoilWaterParams:
    updates = {n: float(v) for n, v in zip(names, x)}
    return replace(base, **updates)


def params_as_dict(params: SoilWaterParams) -> Dict[str, float]:
    return {f.name: getattr(params, f.name) for f in fields(params)}

# Fixed, non-calibrated biomass modifiers
_KC_MIN, _KC_MAX = 0.30, 1.20
_INTERCEPTION_MAX_MM = 3.0
_UPTAKE_MAX_FACTOR = 1.35

# Fixed, non-calibrated freeze-thaw modifiers
_FROZEN_INFILTRATION_FRACTION = 0.20
_FROZEN_DRAINAGE_MULTIPLIER = 0.25
_FROZEN_UPTAKE_MULTIPLIER = 0.30
_FROZEN_PET_MULTIPLIER = 0.20
_FREEZE_TEMP_C = 0.0


def _biomass_fraction(biomass_gC_m2, half_sat):
    biomass = np.maximum(np.asarray(biomass_gC_m2, dtype=float), 0.0)
    return biomass / (biomass + half_sat + 1e-12)


def biomass_to_kc(biomass_gC_m2, half_sat):
    frac = _biomass_fraction(biomass_gC_m2, half_sat)
    return _KC_MIN + (_KC_MAX - _KC_MIN) * frac


def biomass_interception_capacity_mm(biomass_gC_m2, half_sat):
    frac = _biomass_fraction(biomass_gC_m2, half_sat)
    return _INTERCEPTION_MAX_MM * frac


def biomass_uptake_factor(biomass_gC_m2, half_sat):
    frac = _biomass_fraction(biomass_gC_m2, half_sat)
    return 1.0 + (_UPTAKE_MAX_FACTOR - 1.0) * frac


def elevation_pet_multiplier(elevation_m):
    dz_km = float(elevation_m) / 1000.0
    return float(np.clip(1.0 + 0.08 * dz_km, 0.75, 1.35))


def temperature_pet_weekly(
    temp_c,
    elevation_m,
    coeff_mm_per_degday,
    temp_base_c: float = 0.0,
):
    temp = np.asarray(temp_c, dtype=float)
    degree_days = np.maximum(temp - temp_base_c, 0.0) * 7.0
    base_pet = coeff_mm_per_degday * degree_days
    return base_pet * elevation_pet_multiplier(elevation_m)


def clay_modified_properties(clay_pct: float, params: SoilWaterParams):
    clay = float(np.clip(clay_pct, 0.0, 80.0))
    dclay = clay - params.reference_clay_pct
    s = params.clay_sensitivity

    soil_water_capacity = float(np.clip(
        params.base_soil_water_capacity_mm * (1.0 + s * dclay / 100.0),
        60.0, 320.0
    ))

    drainage_coeff = float(np.clip(
        params.base_drainage_coeff * (1.0 - 0.5 * s * dclay / 100.0),
        0.015, 0.25
    ))

    runoff_fraction_max = float(np.clip(
        params.base_runoff_fraction_max * (1.0 + 0.5 * s * dclay / 100.0),
        0.05, 0.90
    ))

    stress_exponent = float(np.clip(
        1.4 * (1.0 + 0.3 * s * dclay / 100.0),
        1.0, 2.2
    ))

    return soil_water_capacity, drainage_coeff, runoff_fraction_max, stress_exponent


def simulate_soil_water_balance(
    data: pd.DataFrame,
    elevation_m: float,
    clay_pct: float,
    params: SoilWaterParams = SoilWaterParams(),
    date_col: Optional[str] = None,
    temp_col: str = "temp_c",
    precip_col: str = "precip_mm",
    biomass_col: str = "biomass_gC_m2",
) -> pd.DataFrame:
    df = data.copy()

    T = df[temp_col].to_numpy(dtype=float)
    P = np.maximum(df[precip_col].to_numpy(dtype=float), 0.0)
    B = np.maximum(df[biomass_col].to_numpy(dtype=float), 0.0)

    base_pet = temperature_pet_weekly(
        T,
        elevation_m=elevation_m,
        coeff_mm_per_degday=params.pet_coeff_mm_per_degday,
        temp_base_c=0.0,
    )

    half_sat = params.biomass_half_sat_gC_m2
    kc = biomass_to_kc(B, half_sat)
    interception_capacity = biomass_interception_capacity_mm(B, half_sat)
    uptake_factor = biomass_uptake_factor(B, half_sat)

    Smax, drain_coeff, runoff_max, stress_exp = clay_modified_properties(clay_pct, params)

    n = len(df)
    S = np.zeros(n)
    runoff = np.zeros(n)
    drainage = np.zeros(n)
    et_actual = np.zeros(n)
    et_potential = np.zeros(n)
    stress = np.zeros(n)
    intercepted_mm = np.zeros(n)
    throughfall_mm = np.zeros(n)
    frozen_soil = np.zeros(n, dtype=bool)

    S_prev = float(np.clip(params.initial_soil_moisture_mm, 0.0, Smax))

    for i in range(n):
        is_frozen = T[i] < _FREEZE_TEMP_C
        frozen_soil[i] = is_frozen

        intercepted_mm[i] = min(P[i], interception_capacity[i])
        throughfall_mm[i] = P[i] - intercepted_mm[i]

        S_prev = float(np.clip(S_prev, 0.0, Smax))
        rel_sat = S_prev / Smax if Smax > 0 else 0.0

        if is_frozen:
            runoff[i] = (1.0 - _FROZEN_INFILTRATION_FRACTION) * throughfall_mm[i]
            infiltration = _FROZEN_INFILTRATION_FRACTION * throughfall_mm[i]
            pet_i = base_pet[i] * _FROZEN_PET_MULTIPLIER
            uptake_i = 1.0 + (uptake_factor[i] - 1.0) * _FROZEN_UPTAKE_MULTIPLIER
            drain_i = drain_coeff * _FROZEN_DRAINAGE_MULTIPLIER
        else:
            runoff_frac = runoff_max * (rel_sat ** params.runoff_exponent)
            runoff[i] = runoff_frac * throughfall_mm[i]
            infiltration = throughfall_mm[i] - runoff[i]
            pet_i = base_pet[i]
            uptake_i = uptake_factor[i]
            drain_i = drain_coeff

        available = min(Smax, S_prev + infiltration)
        stress[i] = float(np.clip((available / Smax) ** stress_exp, 0.0, 1.0))

        et_potential[i] = pet_i * kc[i] * uptake_i
        et_actual[i] = min(et_potential[i] * stress[i], available)

        after_et = available - et_actual[i]
        fc_store = params.field_capacity_fraction * Smax
        drainage[i] = drain_i * max(after_et - fc_store, 0.0)

        S_prev = float(np.clip(after_et - drainage[i], 0.0, Smax))
        S[i] = S_prev

    df["site_elevation_m"] = float(elevation_m)
    df["site_clay_pct"] = float(clay_pct)
    df["base_pet_mm"] = base_pet
    df["kc"] = kc
    df["biomass_uptake_factor"] = uptake_factor
    df["interception_capacity_mm"] = interception_capacity
    df["intercepted_mm"] = intercepted_mm
    df["throughfall_mm"] = throughfall_mm
    df["frozen_soil"] = frozen_soil
    df["et_potential_mm"] = et_potential
    df["water_stress"] = stress
    df["et_actual_mm"] = et_actual
    df["total_evaporative_loss_mm"] = et_actual + intercepted_mm
    df["runoff_mm"] = runoff
    df["drainage_mm"] = drainage
    df["soil_water_capacity_mm"] = Smax
    df["drainage_coeff"] = drain_coeff
    df["runoff_fraction_max"] = runoff_max
    df["stress_exponent"] = stress_exp
    df["soil_moisture_mm"] = S
    df["relative_soil_moisture"] = S / Smax

    if date_col is not None and date_col in df.columns:
        cols = [date_col] + [c for c in df.columns if c != date_col]
        df = df[cols]

    return df


