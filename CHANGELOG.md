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
