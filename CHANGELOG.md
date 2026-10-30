# Changelog

Changes to the model's numerical behaviour, relative to the original code at commit `9d5b8fe`.
Refactors that leave outputs unchanged are not listed.

## Unreleased

### Added

- **`simulate` accepts reference evapotranspiration as an optional input.**
  `reference_evapotranspiration`, shape `(time, *space)` in mm per week, replaces the degree-day relation, so demand can come from a method with radiation and humidity, such as `[FAO56]` Penman–Monteith, or be shared with another model, such as pyrealm's SPLASH.
  The frozen-week adjustment still applies.
  Outputs are unchanged when it is not given.

### Removed

- **The uptake factor no longer multiplies potential evapotranspiration.**
  Potential evapotranspiration is now $ET_p = K_c\,ET_o^{\mathrm{eff}}$, `[FAO56]`'s crop evapotranspiration $ET_c$ in an unfrozen week.
  The uptake factor $u$ (up to 1.35) had no `[FAO56]` counterpart and stacked on a crop coefficient that already reaches 1.2, inflating demand by up to 62 % over reference ET.
  Removed with it: `ModelConstants.max_uptake_factor`, `ModelConstants.frozen_uptake_multiplier`, `processes.uptake_factor` and `SoilWaterOutput.uptake_factor`.
  The plant effect that the factor stood for, how far roots reach into the soil, enters `[FAO56]` through rooting depth and the depletion fraction, which come in a later change.
  In `temperate_default`, annual potential evapotranspiration falls from 2166 to 1760 mm, but actual evapotranspiration only from 705 to 682 mm, because water stress was already doing most of the limiting.

### Changed

- **The water-stress coefficient is `[FAO56]` eq. (84).**
  It was a power law, $K_s = (S^{+}/S_{\max})^{\beta}$, with $\beta = 1.4$ adjusted for clay, so evapotranspiration was reduced at any store below full capacity.
  It is now $K_s = \min(1, S^{+} / ((1 - p) S_{fc}))$: `[FAO56]` eq. (84) with the field capacity $S_{fc}$ as the total available water.
  Evapotranspiration is unstressed until a fraction $p$ of that water is used, then falls linearly to zero.
  The new constant `ModelConstants.depletion_fraction`, $p = 0.5$, is the value `[FAO56]` says "is commonly used for many crops"; Table 22 gives 0.3 to 0.7.
  Removed: `ModelConstants.nominal_stress_exponent`, `stress_clay_response`, `stress_exponent_bounds` and `SoilProperties.stress_exponent`.
  The clay effect on $\beta$ goes with them; it moved $\beta$ by at most ±0.03 within the calibration bounds, so its clip never acted.
  `SoilWaterParams.field_capacity_fraction` must now be strictly positive.
  In `temperate_default`, the number of unstressed weeks rises from 90 to 517 of 520 and annual actual evapotranspiration from 323 to 392 mm, which is all the demand left after interception.
  The `dry_sandy` regression scenario empties its store with default parameters again, so the arid coefficient and small store it was given earlier are removed.
- **Interception is bounded by evaporative demand and uses part of it.**
  Intercepted water evaporated in full every week, up to 3 mm, even in frozen weeks and weeks with no demand, and transpiration then drew on the full potential evapotranspiration as well.
  Now $I = \min(P, f_B I_{\max}, ET_p)$, water the canopy holds but cannot evaporate falls through to the soil, and the store meets only the remaining demand: $ET_a = \min(K_s (ET_p - I), S^{+})$.
  So $I + ET_a \le ET_p$, which a property test checks.
  In `temperate_default`, total evaporative loss had exceeded potential evapotranspiration in 317 of 520 weeks; annual loss falls from 464 to 409 mm, with interception unchanged at 86 mm and actual evapotranspiration down from 379 to 323 mm.
  In `cold_upland`, annual interception falls from 71 to 51 mm.
- **The elevation multiplier on reference evapotranspiration now follows from atmospheric pressure.**
  It was $1 + 0.08\,z/1000$, clipped to [0.75, 1.35]: a fixed 8 % per kilometre.
  It is now the equilibrium evaporation factor $s / (s + \gamma_{\mathrm{psy}})$ relative to sea level, with pressure, psychrometric constant and vapour pressure slope from `[FAO56]` eqs. (7), (8) and (13).
  The sign is unchanged: lower pressure at altitude lowers $\gamma_{\mathrm{psy}}$, which raises demand at a given temperature.
  The size is roughly halved, to about 4 % per kilometre at 20 °C and 5 % at 10 °C, and it no longer needs a clip.
  Removed: `ModelConstants.elevation_et_gradient` and `ModelConstants.elevation_et_multiplier_bounds`; `processes.elevation_et_multiplier` now takes temperature instead of constants.
  Annual reference evapotranspiration falls by 6 % in `cold_upland` (2500 m) and by 7 % in `clipped_high` (6000 m); `temperate_default` (100 m) is unchanged to within 0.5 %.
- **The default reference ET coefficient is 0.15 mm °C⁻¹ day⁻¹, down from 0.55.**
  At 0.55 the degree-day relation gave 5.5 mm per day of reference evapotranspiration at 10 °C and 11 mm per day at 20 °C.
  `[FAO56]` Table 2 gives 1–2 and 2–4 mm per day for humid and sub-humid temperate regions, so 0.15 sits in the middle of both.
  FAO56 offers that table for orientation, not for direct use; the value is a literature default until the model is recalibrated.
  The calibration bounds narrow from (0.1, 1.5) to (0.05, 0.5), which covers every row of Table 2, so calibration cannot restore the old demand.
  In `temperate_default`, annual potential evapotranspiration falls from 1760 to 480 mm and actual evapotranspiration from 682 to 379 mm; mean soil moisture rises from 79 to 130 mm, and runoff and drainage rise to carry the extra water.
  The `dry_sandy` regression scenario now sets an arid coefficient of 0.3 and a 60 mm store, so that it still empties the store.
- **Bucket overflow is now runoff.**
  Previously, when infiltration would have filled the store beyond its capacity, the excess was silently discarded, so water was not conserved.
  It is now added to `runoff` as saturation excess.
  Soil moisture, evapotranspiration and drainage are unchanged; only `runoff` increases, by exactly the water that was previously lost.
  In the regression scenarios the largest weekly increase is 351 mm (`wet_clay`).
