---
title: Notation
icon: lucide/sigma
---

# Notation

<!--
Canonical terminology and notation for this project.
Agreed with the maintainer via the `notation` skill on 2026-10-09.

Rules for editing this file:
- A new quantity is added here in the same change that introduces it, never later.
- Deviations from the reference sources go in the Deviations section with a reason.
- This is a glossary. Design rationale belongs in design notes, not here.
-->

## Reference sources

| Tag | Source | Role |
|---|---|---|
| `[FAO56]` | Allen, R.G. et al. (1998) Crop evapotranspiration - Guidelines for computing crop water requirements. Rome: FAO. FAO Irrigation and Drainage Paper 56, ISBN 92-5-104219-5. <https://www.fao.org/4/X0490E/x0490e00.htm> | primary; evapotranspiration and stress notation follows this except where noted |

Cite equations as `[FAO56] eq. (81)` in docstrings and comments.
The bucket (store, runoff, drainage) has no counterpart in `[FAO56]`; its notation is project-local.

## Guiding principles

- **One symbol, one type.** A symbol denotes quantities of exactly one space and shape.
- **Follow `[FAO56]` where the model follows it.** Its symbols are adopted as written, including the two-letter $ET$.

## Terms

One canonical word per concept.
The banned column is enforceable; "be consistent" is not.

| Concept | Use | Never | Note |
|---|---|---|---|
| Temperature- and elevation-driven evaporative demand | reference evapotranspiration | PET, base PET | `[FAO56]` $ET_o$ |
| Reference ET times crop coefficient times uptake factor | potential evapotranspiration | PET (as an abbreviation anywhere, including identifiers) | |
| Water drawn from the store by evapotranspiration | actual evapotranspiration | AET, ET (unqualified) | |
| Reduction factor on evapotranspiration, 1 meaning unstressed | water-stress coefficient | water stress, stress factor | `[FAO56]` $K_s$ |
| Biomass-dependent multiplier on reference ET | crop coefficient | | `[FAO56]` $K_c$ |
| Value of a soil property at the nominal clay content, before clay adjustment | nominal (*nominal soil water capacity*) | base, reference, standard | "base" is the degree-day base temperature; "reference" is reference ET; "standard" is `[FAO56]`'s standard conditions |
| Clay content at which the nominal values apply | nominal clay content | reference clay, base clay | |
| Store at field capacity as a fraction of the soil water capacity | field-capacity fraction | field capacity (for the fraction) | field capacity itself is the store $S_{fc}$ |
| Fraction of water above field capacity drained per week | drainage coefficient | drainage rate | |
| Saturating function of biomass that scales every biomass effect | biomass saturation | biomass fraction | |
| Multiplier on potential evapotranspiration from root uptake | uptake factor | root-uptake multiplier | |
| Week whose mean air temperature is below the freezing temperature | frozen week | freeze–thaw | there is no frozen-soil state |
| A quantity after the frozen-week adjustment | effective | adjusted, corrected | |
| Temperature above which degree-days accumulate | base temperature | threshold temperature | |
| Water in the soil store | soil moisture | soil water content, SWC | "the store" is fine in prose; SWC only for FLUXNET observations |
| Maximum soil moisture | soil water capacity | maximum soil water storage, bucket size | |
| Soil moisture after infiltration, before evapotranspiration | store after infiltration | available water | `[FAO56]` "available water" (TAW, RAW) is a different quantity |
| Soil moisture as a fraction of the soil water capacity | relative soil moisture | saturation, wetness | |
| Soil moisture before the first week | initial soil moisture | initial store (in identifiers) | |

## Evapotranspiration

Weekly totals, mm wk⁻¹, shape `(time, *space)`, except the coefficients, which are dimensionless with the same shape.

| Concept | Math | Code | Note |
|---|---|---|---|
| reference evapotranspiration | $ET_o$ | `reference_evapotranspiration` | `[FAO56]`; letter o, not zero |
| potential evapotranspiration | $ET_p = u^{\mathrm{eff}} K_c\,ET_o^{\mathrm{eff}}$ | `potential_evapotranspiration`, local `potential_et` | |
| actual evapotranspiration | $ET_a$ | `actual_evapotranspiration`, local `aet` | |
| crop coefficient | $K_c$ | `crop_coefficient` | `[FAO56]` |
| water-stress coefficient | $K_s$ | `water_stress_coefficient`, local `k_s` | `[FAO56]`; $0 \le K_s \le 1$; not saturated hydraulic conductivity |

$ET$ is a single two-letter symbol, never $E \cdot T$.

## Water fluxes

Weekly totals, mm wk⁻¹, shape `(time, *space)`.

| Concept | Math | Code | Note |
|---|---|---|---|
| precipitation | $P$ | `precipitation` | negative values are treated as zero |
| interception | $I = \min(P, f_B I_{\max})$ | `interception` | evaporates within the week |
| throughfall | $P_T = P - I$ | `throughfall` | subscript $T$ is a label, not temperature |
| surface runoff | $Q_s$ | local `surface_runoff` | |
| saturation excess | $Q_e$ | local `excess` | |
| runoff | $Q = Q_s + Q_e$ | `runoff` | |
| infiltration | $F = P_T - Q$ | — | |
| drainage | $D$ | `drainage` | |

The weekly balance is $S_t = S_{t-1} + P - I - Q - ET_a - D$.

## Soil moisture

Soil moisture and its derived stores, mm, shape `(time, *space)` unless noted.

| Concept | Math | Code | Note |
|---|---|---|---|
| soil moisture at the end of week $t$ | $S_t$ | `soil_moisture` | |
| initial soil moisture | $S_0$ | `initial_soil_moisture` | shape `space` |
| store after infiltration | $S^{+}_t$ | local `soil_moisture_after_infiltration` | $S^{+}_t \le S_{\max}$ |
| soil water capacity | $S_{\max}$, nominal $S_{\max}^{\circ}$ | `soil_water_capacity`, `nominal_soil_water_capacity` | shape `space` |
| field capacity | $S_{fc} = \phi_{fc} S_{\max}$ | local `s_fc` | shape `space` |
| relative soil moisture | $S_r = S / S_{\max}$ | `relative_soil_moisture` | dimensionless |

## Soil properties and clay

Per pixel, shape `space`.
The clay-adjusted properties are the nominal values scaled by the clay offset $\Delta$ and clipped.

| Concept | Math | Units | Code | Note |
|---|---|---|---|---|
| clay content | $C$ | percent | `clay` | $C$ is clay, never carbon; this model has no carbon symbol |
| nominal clay content | $C^{\circ}$ | percent | `nominal_clay` | |
| clay sensitivity | $\kappa$ | — | `clay_sensitivity` | |
| clay offset | $\Delta = \kappa\,(C - C^{\circ})/100$ | — | local `delta` | |
| drainage coefficient | $k_d$, nominal $k_d^{\circ}$ | — (fraction per week) | `drainage_coefficient`, `nominal_drainage_coefficient` | |
| maximum runoff fraction | $r_{\max}$, nominal $r_{\max}^{\circ}$ | — | `max_runoff_fraction`, `nominal_max_runoff_fraction` | |
| stress exponent | $\beta$, nominal $\beta^{\circ}$ | — | `stress_exponent`, `nominal_stress_exponent` | |
| runoff exponent | $\gamma$ | — | `runoff_exponent` | not clay-adjusted |
| field-capacity fraction | $\phi_{fc}$ | — | `field_capacity_fraction` | not clay-adjusted |
| clay response factors | $a_d$, $a_r$, $a_\beta$ | — | `drainage_clay_response`, `runoff_clay_response`, `stress_clay_response` | subscripts are labels |

$\theta$ is reserved for volumetric water content (m³ m⁻³), as in `[FAO56]` and sgam.
This model has none; do not use $\theta$ for $\phi_{fc}$ or for relative soil moisture.

## Biomass effects

Dimensionless and shape `(time, *space)`, except where noted.
"min" and "max" are the limits of a biomass effect at $B = 0$ and as $B \to \infty$.

| Concept | Math | Code | Note |
|---|---|---|---|
| biomass | $B$ | `biomass` | g C m⁻² |
| biomass half-saturation | $K_B$ | `biomass_half_saturation` | g C m⁻², shape `space` |
| biomass saturation | $f_B = B / (B + K_B)$ | `biomass_saturation` | $0 \le f_B < 1$ |
| crop coefficient limits | $K_{c,\min}$, $K_{c,\max}$ | `min_crop_coefficient`, `max_crop_coefficient` | |
| uptake factor | $u = 1 + (u_{\max} - 1) f_B$ | `uptake_factor` | |
| interception capacity | $f_B\,I_{\max}$ | `interception_capacity` | mm wk⁻¹; deliberately no symbol of its own |
| interception capacity limit | $I_{\max}$ | `max_interception_capacity` | mm wk⁻¹ |

## Temperature, elevation and frozen weeks

| Concept | Math | Code | Note |
|---|---|---|---|
| weekly mean air temperature | $T$ | `temperature` | °C, `(time, *space)` |
| base temperature | $T_b$ | `base_temperature` | °C; degree-days accumulate above it |
| freezing temperature | $T_{\mathrm{frz}}$ | `freezing_temperature` | °C; week $t$ is frozen if $T_t < T_{\mathrm{frz}}$ |
| reference ET coefficient | $c_{ET}$ | `reference_et_coefficient` | mm °C⁻¹ day⁻¹ |
| elevation | $z$ | `elevation` | m, shape `space` |
| elevation multiplier | $m_z$, bounds $m_{z,\min}$, $m_{z,\max}$ | `elevation_et_multiplier`, `elevation_et_multiplier_bounds` | |
| elevation gradient | $g_z$ | `elevation_et_gradient` | per km |
| frozen infiltration fraction | $\phi^{\mathrm{frz}}$ | `frozen_infiltration_fraction` | |
| frozen multipliers | $m^{\mathrm{frz}}_{ET}$, $m^{\mathrm{frz}}_{u}$, $m^{\mathrm{frz}}_{d}$ | `frozen_reference_et_multiplier`, `frozen_uptake_multiplier`, `frozen_drainage_multiplier` | scale $ET_o$, $u - 1$ and $k_d$ |
| effective (frozen-adjusted) values | $ET_o^{\mathrm{eff}}$, $u^{\mathrm{eff}}$, $k_d^{\mathrm{eff}}$ | suffix `_eff` | equal the plain value in unfrozen weeks |

Clip bounds have no symbols; they are named only in `ModelConstants` and written $\mathrm{clip}(\cdot)$.

## Marks and indices

| Mark | Meaning | Example |
|---|---|---|
| superscript $\mathrm{frz}$ | applies in frozen weeks | $m^{\mathrm{frz}}_{ET}$, $\phi^{\mathrm{frz}}$ |
| superscript $\mathrm{eff}$ | after the frozen-week adjustment | $u^{\mathrm{eff}}$ |
| subscript $t$ | week index, $t = 1, \dots, n_t$ | $S_t$ |
| subscript $0$ | before the first week, $t = 0$ | $S_0$, the initial soil moisture |
| superscript $\circ$ | nominal value, at the nominal clay content | $S_{\max}^{\circ}$, $\beta^{\circ}$, $C^{\circ}$ |

Subscript $0$ means $t = 0$ and nothing else.
Code spells the superscript circle as a `nominal_` prefix.

## Code transliteration

- **Public names spell out the concept.**
  Dataclass fields, function arguments and outputs use the Code column's descriptive name, never a terse one.
- **Locals inside function bodies may mirror the maths**, so dense expressions read like the equations:
  lowercase per PEP 8 (`s_max`, `k_d`, `k_c`, `f_b`, `s_fc`), Greek spelled out (`beta`, `gamma`, `kappa`, `phi`), subscript labels as suffixes ($K_c$ → `k_c`).
  The loop variable `s` is the store $S_{t-1}$; no other quantity may be called `s`.
- **"min" and "max"** are prefixes in public names (`max_runoff_fraction`) and suffixes in locals (`r_max`).
- **Marks:** $\circ$ → `nominal_` prefix; $\mathrm{eff}$ → `_eff` suffix; $\mathrm{frz}$ → `frozen_` prefix; $S^{+}$ → `soil_moisture_after_infiltration`.
- **$ET$** becomes `et` inside compound names (`reference_et_coefficient`, `potential_et`); public output fields spell out `evapotranspiration`.
- **"pet"** never appears in an identifier.
- **Reserved locals:** `t` is the week index, so temperature is never `t` (use `temp`); `s` is only the store; there is no bare `d`.
  Free for local helpers: `x`, `y`, `i`, `j`, `k`, `mask`.
- **Shapes** are written `(time, *space)` and `space` in docstrings; counters take an `n_` prefix (`n_time`).
- **Docstring maths** is LaTeX between `$` delimiters. Equations taken from a reference carry its tag, e.g. `[FAO56] eq. (81)`.

## Deviations

Places where this project departs from its reference sources, and why.

**Do not "correct" the code back toward the reference.**

- **$ET_p$ is not `[FAO56]`'s $ET_c$.**
  Potential evapotranspiration includes the uptake factor $u$, which has no `[FAO56]` counterpart, so $ET_p = u\,K_c\,ET_o$ (in an unfrozen week) differs from `[FAO56]`'s crop evapotranspiration $ET_c = K_c\,ET_o$.
  Writing $ET_c$ would claim the two are the same.
- **$K_s$ is the water-stress coefficient, not saturated hydraulic conductivity.**
  Soil physics often writes saturated hydraulic conductivity as $K_s$; this model has none and follows `[FAO56]`.
- **Field capacity is a fraction of the bucket, not a water content.**
  `[FAO56]` $\theta_{FC}$ is volumetric water content at field capacity (m³ m⁻³).
  This model has no soil depth, so it uses $\phi_{fc}$, a fraction of $S_{\max}$, and reserves $\theta$.
- **$K_s$ is a power law in the relative store after infiltration, not `[FAO56]`'s depletion function.**
  Here $K_s = (S^{+} / S_{\max})^{\beta}$; `[FAO56]` eq. (84) uses root-zone depletion against TAW and RAW.
  Same concept and range, different function.

## Migration

Renames agreed in this document but not yet applied to the code.

| Old | New | Files |
|---|---|---|
| `SoilWaterParams.pet_coefficient` | `reference_et_coefficient` | `params.py`, `processes.py`, `model.py`, `scripts/calibrate_icos.py`, `tests/` |
| `processes.elevation_pet_multiplier` | `elevation_et_multiplier` | `processes.py`, `tests/test_processes.py` |
| `ModelConstants.elevation_pet_gradient` | `elevation_et_gradient` | `params.py`, `processes.py` |
| `ModelConstants.elevation_pet_multiplier_bounds` | `elevation_et_multiplier_bounds` | `params.py`, `processes.py`, `tests/` |
| `ModelConstants.frozen_pet_multiplier` | `frozen_reference_et_multiplier` | `params.py`, `model.py` |
| `ModelConstants.pet_base_temperature` | `base_temperature` | `params.py`, `processes.py` |
| `SoilWaterParams.base_soil_water_capacity` | `nominal_soil_water_capacity` | `params.py`, `processes.py`, `scripts/`, `tests/`, `docs/index.md` |
| `SoilWaterParams.base_drainage_coefficient` | `nominal_drainage_coefficient` | `params.py`, `processes.py`, `scripts/`, `tests/` |
| `SoilWaterParams.base_max_runoff_fraction` | `nominal_max_runoff_fraction` | `params.py`, `processes.py`, `scripts/`, `tests/` |
| `SoilWaterParams.reference_clay` | `nominal_clay` | `params.py`, `processes.py`, `scripts/`, `tests/` |
| `ModelConstants.base_stress_exponent` | `nominal_stress_exponent` | `params.py`, `processes.py`, `tests/` |
| local `pet` in `simulate` | `potential_et` | `model.py` |
| `SoilWaterOutput.water_stress` | `water_stress_coefficient` | `model.py`, `tests/`, `scripts/calibrate_icos.py` |
| local `available` in `simulate` | `soil_moisture_after_infiltration` | `model.py` |
| `processes.biomass_fraction` | `biomass_saturation` | `processes.py`, `model.py`, `tests/test_processes.py` |
| locals `e0`, `e0_eff` in `simulate` | `reference_et`, `reference_et_eff` | `model.py` |
| local `d`, `d_eff` in `simulate` | `k_d`, `k_d_eff` | `model.py` |
| local `kc` in `simulate` | `k_c` | `model.py` |
| local `stress` in `simulate` | `k_s` | `model.py` |
| symbols in `docs/science.md` and in docstrings ($E_0$, $k_c$, $\theta_{fc}$, $s_C$, $d$, $A$, $\phi_f$, $I_{\max}^{\infty}$, subscript-0 nominal values, ...) | the symbols in this document | `docs/science.md`, `model.py`, `processes.py`, `params.py` |
| argument `pet_coefficient` of `processes.reference_evapotranspiration` | `reference_et_coefficient` | `processes.py`, `model.py`, `tests/test_processes.py` |
