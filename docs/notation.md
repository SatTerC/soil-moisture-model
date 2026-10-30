---
title: Notation
icon: lucide/sigma
---

# Notation

The terms, symbols and code names used throughout this documentation and the package.

## Reference sources

| Tag | Source | Role |
|---|---|---|
| `[FAO56]` | Allen, R.G. et al. (1998) Crop evapotranspiration - Guidelines for computing crop water requirements. Rome: FAO. FAO Irrigation and Drainage Paper 56, ISBN 92-5-104219-5. <https://www.fao.org/4/X0490E/x0490e00.htm> | primary; evapotranspiration and stress notation follows this except where noted |

Equations taken from it are cited as `[FAO56] eq. (n)`.
The bucket (store, runoff, drainage) has no counterpart in `[FAO56]`; its notation is project-local.

## Conventions

- Each symbol denotes one quantity, with one set of units and one shape.
- Where the model follows `[FAO56]`, its symbols are used as written there, including the two-letter $ET$.
- The Code columns give the public names: parameter and constant fields, function arguments and output fields.

## Terms

One term per concept.
The Avoid column lists synonyms not used here, usually because they mean something else.

| Concept | Term | Avoid | Note |
|---|---|---|---|
| Temperature- and elevation-driven evaporative demand | reference evapotranspiration | PET, base PET | `[FAO56]` $ET_o$ |
| Effective reference ET times crop coefficient | potential evapotranspiration | PET | `[FAO56]` $ET_c$ in an unfrozen week |
| Water drawn from the store by evapotranspiration | actual evapotranspiration | AET, ET (unqualified) | |
| Reduction factor on evapotranspiration, 1 meaning unstressed | water-stress coefficient | water stress, stress factor | `[FAO56]` $K_s$ |
| Fraction of the water held at field capacity that can be used before stress begins | depletion fraction | | `[FAO56]` $p$ |
| Biomass-dependent multiplier on reference ET | crop coefficient | | `[FAO56]` $K_c$ |
| Value of a soil property at the nominal clay content, before clay adjustment | nominal (*nominal soil water capacity*) | base, reference, standard | "base" is the degree-day base temperature; "reference" is reference ET; "standard" is `[FAO56]`'s standard conditions |
| Clay content at which the nominal values apply | nominal clay content | reference clay, base clay | |
| Store at field capacity as a fraction of the soil water capacity | field-capacity fraction | field capacity (for the fraction) | field capacity itself is the store $S_{fc}$ |
| Fraction of water above field capacity drained per week | drainage coefficient | drainage rate | |
| Saturating function of biomass that scales every biomass effect | biomass saturation | biomass fraction | |
| Week whose mean air temperature is below the freezing temperature | frozen week | freeze–thaw | there is no frozen-soil state |
| A quantity after the frozen-week adjustment | effective | adjusted, corrected | |
| Temperature above which degree-days accumulate | base temperature | threshold temperature | |
| Water in the soil store | soil moisture | soil water content, SWC | "the store" also appears in prose; SWC refers only to FLUXNET observations |
| Maximum soil moisture | soil water capacity | maximum soil water storage, bucket size | |
| Soil moisture after infiltration, before evapotranspiration | store after infiltration | available water | `[FAO56]` "available water" (TAW, RAW) is a different quantity |
| Soil moisture as a fraction of the soil water capacity | relative soil moisture | saturation, wetness | |
| Soil moisture before the first week | initial soil moisture | | |

## Evapotranspiration

Weekly totals, mm wk⁻¹, shape `(time, *space)`, except the coefficients, which are dimensionless with the same shape.

| Concept | Math | Code | Note |
|---|---|---|---|
| reference evapotranspiration | $ET_o$ | `reference_evapotranspiration` | `[FAO56]`; letter o, not zero; also an optional input to `simulate` |
| potential evapotranspiration | $ET_p = K_c\,ET_o^{\mathrm{eff}}$ | `potential_evapotranspiration` | |
| actual evapotranspiration | $ET_a$ | `actual_evapotranspiration` | |
| crop coefficient | $K_c$ | `crop_coefficient` | `[FAO56]` |
| water-stress coefficient | $K_s = \min(1, S^{+} / ((1 - p) S_{fc}))$ | `water_stress_coefficient` | `[FAO56]` eq. (84); $0 \le K_s \le 1$; not saturated hydraulic conductivity |
| depletion fraction | $p$ | `depletion_fraction` | `[FAO56]`; dimensionless, $0 \le p < 1$ |

$ET$ is a single two-letter symbol, not $E \cdot T$.

## Water fluxes

Weekly totals, mm wk⁻¹, shape `(time, *space)`.

| Concept | Math | Code | Note |
|---|---|---|---|
| precipitation | $P$ | `precipitation` | negative values are treated as zero |
| interception | $I = \min(P, f_B I_{\max}, ET_p)$ | `interception` | evaporates within the week |
| throughfall | $P_T = P - I$ | `throughfall` | subscript $T$ is a label, not temperature |
| surface runoff | $Q_s$ | — | |
| saturation excess | $Q_e$ | — | |
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
| store after infiltration | $S^{+}_t$ | — | $S^{+}_t \le S_{\max}$ |
| soil water capacity | $S_{\max}$, nominal $S_{\max}^{\circ}$ | `soil_water_capacity`, `nominal_soil_water_capacity` | shape `space` |
| field capacity | $S_{fc} = \phi_{fc} S_{\max}$ | — | shape `space` |
| relative soil moisture | $S_r = S / S_{\max}$ | `relative_soil_moisture` | dimensionless |

## Soil properties and clay

Per pixel, shape `space`.
The soil water capacity is the nominal value scaled by the clay offset $\Delta$ and clipped.

| Concept | Math | Units | Code | Note |
|---|---|---|---|---|
| clay content | $C$ | percent | `clay` | $C$ is clay, never carbon; this model has no carbon symbol |
| nominal clay content | $C^{\circ}$ | percent | `nominal_clay` | |
| clay sensitivity | $\kappa$ | — | `clay_sensitivity` | |
| clay offset | $\Delta = \kappa\,(C - C^{\circ})/100$ | — | — | |
| drainage coefficient | $k_d$ | — (fraction per week) | `drainage_coefficient` | not clay-adjusted |
| maximum runoff fraction | $r_{\max}$ | — | `max_runoff_fraction` | not clay-adjusted |
| runoff exponent | $\gamma$ | — | `runoff_exponent` | not clay-adjusted |
| field-capacity fraction | $\phi_{fc}$ | — | `field_capacity_fraction` | not clay-adjusted |

$\theta$ is reserved for volumetric water content (m³ m⁻³), as in `[FAO56]` and sgam.
This model has no volumetric water content, so $\theta$ does not appear; $\phi_{fc}$ and $S_r$ are fractions of the soil water capacity.

## Biomass effects

Dimensionless and shape `(time, *space)`, except where noted.
"min" and "max" are the limits of a biomass effect at $B = 0$ and as $B \to \infty$.

| Concept | Math | Code | Note |
|---|---|---|---|
| biomass | $B$ | `biomass` | g C m⁻² |
| biomass half-saturation | $K_B$ | `biomass_half_saturation` | g C m⁻², shape `space` |
| biomass saturation | $f_B = B / (B + K_B)$ | `biomass_saturation` | $0 \le f_B < 1$ |
| crop coefficient limits | $K_{c,\min}$, $K_{c,\max}$ | `min_crop_coefficient`, `max_crop_coefficient` | |
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
| elevation multiplier | $m_z = (s + \gamma_{\mathrm{psy}}(0)) / (s + \gamma_{\mathrm{psy}}(z))$ | `elevation_et_multiplier` | dimensionless |
| atmospheric pressure | $p_{\mathrm{atm}}$ | `atmospheric_pressure` | kPa; `[FAO56]` eq. (7) |
| psychrometric constant | $\gamma_{\mathrm{psy}}$ | `psychrometric_constant` | kPa °C⁻¹; `[FAO56]` eq. (8) |
| slope of the saturation vapour pressure curve | $s$ | `saturation_vapour_pressure_slope` | kPa °C⁻¹; `[FAO56]` eq. (13) |
| frozen infiltration fraction | $\phi^{\mathrm{frz}}$ | `frozen_infiltration_fraction` | |
| frozen multipliers | $m^{\mathrm{frz}}_{ET}$, $m^{\mathrm{frz}}_{d}$ | `frozen_reference_et_multiplier`, `frozen_drainage_multiplier` | scale $ET_o$ and $k_d$ |
| effective (frozen-adjusted) values | $ET_o^{\mathrm{eff}}$, $k_d^{\mathrm{eff}}$ | suffix `_eff` | equal the plain value in unfrozen weeks |

Clip bounds have no symbols; they are named only in `ModelConstants` and written $\mathrm{clip}(\cdot)$.

## Marks and indices

| Mark | Meaning | Example |
|---|---|---|
| superscript $\mathrm{frz}$ | applies in frozen weeks | $m^{\mathrm{frz}}_{ET}$, $\phi^{\mathrm{frz}}$ |
| superscript $\mathrm{eff}$ | after the frozen-week adjustment | $k_d^{\mathrm{eff}}$ |
| subscript $t$ | week index, $t = 1, \dots, n_t$ | $S_t$ |
| subscript $0$ | before the first week, $t = 0$ | $S_0$, the initial soil moisture |
| superscript $\circ$ | nominal value, at the nominal clay content | $S_{\max}^{\circ}$, $C^{\circ}$ |

Subscript $0$ means $t = 0$ and nothing else.
In code names the circle becomes the prefix `nominal_`, as in `nominal_soil_water_capacity`.

## Deviations

Places where this model departs from `[FAO56]`, and why.
Each is deliberate.

- **$ET_p$ is `[FAO56]`'s $ET_c$ only in an unfrozen week.**
  Potential evapotranspiration is $ET_p = K_c\,ET_o^{\mathrm{eff}}$, which equals `[FAO56]`'s crop evapotranspiration $ET_c = K_c\,ET_o$ except in a frozen week, where $ET_o^{\mathrm{eff}} < ET_o$.
  It therefore has its own symbol.
- **Three `[FAO56]` symbols are renamed to avoid collisions.**
  `[FAO56]` writes atmospheric pressure $P$, the psychrometric constant $\gamma$ and the slope of the saturation vapour pressure curve $\Delta$.
  Here $P$ is precipitation, $\gamma$ the runoff exponent and $\Delta$ the clay offset, so these are $p_{\mathrm{atm}}$, $\gamma_{\mathrm{psy}}$ and $s$.
- **$K_s$ is the water-stress coefficient, not saturated hydraulic conductivity.**
  Soil physics often writes saturated hydraulic conductivity as $K_s$; this model has none and follows `[FAO56]`.
- **Field capacity is a fraction of the bucket, not a water content.**
  `[FAO56]` $\theta_{FC}$ is volumetric water content at field capacity (m³ m⁻³).
  This model has no soil depth, so it uses $\phi_{fc}$, a fraction of $S_{\max}$, and reserves $\theta$.
- **$K_s$ is `[FAO56]` eq. (84) applied to the store after infiltration.**
  The store counts water above the wilting point, so `[FAO56]`'s total available water TAW is $S_{fc}$ and its root-zone depletion is $S_{fc} - S^{+}$, giving $K_s = \min(1, S^{+} / ((1 - p) S_{fc}))$.
  `[FAO56]` evaluates depletion at the start of the day; here it is after the week's infiltration, because the step is a week.
  $p$ is a constant: `[FAO56]`'s adjustment of $p$ for the rate of $ET_c$ is not applied.
