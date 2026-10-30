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
| water-stress coefficient | $K_s$ | `water_stress_coefficient` | `[FAO56]`; $0 \le K_s \le 1$; not saturated hydraulic conductivity |

$ET$ is a single two-letter symbol, not $E \cdot T$.

## Water fluxes

Weekly totals, mm wk⁻¹, shape `(time, *space)`.

| Concept | Math | Code | Note |
|---|---|---|---|
| precipitation | $P$ | `precipitation` | negative values are treated as zero |
| interception | $I = \min(P, f_B I_{\max})$ | `interception` | evaporates within the week |
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
The clay-adjusted properties are the nominal values scaled by the clay offset $\Delta$ and clipped.

| Concept | Math | Units | Code | Note |
|---|---|---|---|---|
| clay content | $C$ | percent | `clay` | $C$ is clay, never carbon; this model has no carbon symbol |
| nominal clay content | $C^{\circ}$ | percent | `nominal_clay` | |
| clay sensitivity | $\kappa$ | — | `clay_sensitivity` | |
| clay offset | $\Delta = \kappa\,(C - C^{\circ})/100$ | — | — | |
| drainage coefficient | $k_d$, nominal $k_d^{\circ}$ | — (fraction per week) | `drainage_coefficient`, `nominal_drainage_coefficient` | |
| maximum runoff fraction | $r_{\max}$, nominal $r_{\max}^{\circ}$ | — | `max_runoff_fraction`, `nominal_max_runoff_fraction` | |
| stress exponent | $\beta$, nominal $\beta^{\circ}$ | — | `stress_exponent`, `nominal_stress_exponent` | |
| runoff exponent | $\gamma$ | — | `runoff_exponent` | not clay-adjusted |
| field-capacity fraction | $\phi_{fc}$ | — | `field_capacity_fraction` | not clay-adjusted |
| clay response factors | $a_d$, $a_r$, $a_\beta$ | — | `drainage_clay_response`, `runoff_clay_response`, `stress_clay_response` | subscripts are labels |

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
| elevation multiplier | $m_z$, bounds $m_{z,\min}$, $m_{z,\max}$ | `elevation_et_multiplier`, `elevation_et_multiplier_bounds` | |
| elevation gradient | $g_z$ | `elevation_et_gradient` | per km |
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
| superscript $\circ$ | nominal value, at the nominal clay content | $S_{\max}^{\circ}$, $\beta^{\circ}$, $C^{\circ}$ |

Subscript $0$ means $t = 0$ and nothing else.
In code names the circle becomes the prefix `nominal_`, as in `nominal_soil_water_capacity`.

## Deviations

Places where this model departs from `[FAO56]`, and why.
Each is deliberate.

- **$ET_p$ is `[FAO56]`'s $ET_c$ only in an unfrozen week.**
  Potential evapotranspiration is $ET_p = K_c\,ET_o^{\mathrm{eff}}$, which equals `[FAO56]`'s crop evapotranspiration $ET_c = K_c\,ET_o$ except in a frozen week, where $ET_o^{\mathrm{eff}} < ET_o$.
  It therefore has its own symbol.
- **$K_s$ is the water-stress coefficient, not saturated hydraulic conductivity.**
  Soil physics often writes saturated hydraulic conductivity as $K_s$; this model has none and follows `[FAO56]`.
- **Field capacity is a fraction of the bucket, not a water content.**
  `[FAO56]` $\theta_{FC}$ is volumetric water content at field capacity (m³ m⁻³).
  This model has no soil depth, so it uses $\phi_{fc}$, a fraction of $S_{\max}$, and reserves $\theta$.
- **$K_s$ is a power law in the relative store after infiltration, not `[FAO56]`'s depletion function.**
  Here $K_s = (S^{+} / S_{\max})^{\beta}$; `[FAO56]` eq. (84) uses root-zone depletion against TAW and RAW.
  Same concept and range, different function.
