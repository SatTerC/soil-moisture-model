# Changelog

Changes to the model's numerical behaviour, relative to the original code at commit `9d5b8fe`.
Refactors that leave outputs unchanged are not listed.

## Unreleased

### Changed

- **Bucket overflow is now runoff.**
  Previously, when infiltration would have filled the store beyond its capacity, the excess was silently discarded, so water was not conserved.
  It is now added to `runoff` as saturation excess.
  Soil moisture, evapotranspiration and drainage are unchanged; only `runoff` increases, by exactly the water that was previously lost.
  In the regression scenarios the largest weekly increase is 351 mm (`wet_clay`).
