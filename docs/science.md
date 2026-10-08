---
title: Science
icon: lucide/microscope
---

# Scientific background

The model is a single-layer "bucket": one soil water store $S$ (mm), with capacity $S_{\max}$, stepped forward one week at a time.
It aims to reproduce the main ecohydrological controls on soil moisture with as few parameters as possible, so that it can be calibrated at individual sites and run cheaply over large grids.
It is not a process-detailed hydrological model.

Three things set the store's behaviour:

- **Soil texture.** Clay content changes the capacity, drainage, runoff and the shape of the water-stress response.
- **Vegetation.** Plant biomass controls canopy interception, the crop coefficient and root uptake.
- **Climate.** Temperature drives evaporative demand and decides whether the soil is frozen; precipitation supplies water.

```mermaid
flowchart TD
    P["Precipitation P"] --> I["Interception I<br/>(evaporated)"]
    P --> PT["Throughfall P_T"]
    PT --> Q["Runoff Q<br/>(surface + saturation excess)"]
    PT --> F["Infiltration F"]
    F --> S[("Soil store S")]
    S --> E["Actual evapotranspiration E_a"]
    S --> D["Drainage D"]
```

## Weekly water balance

Each week, starting from the store $S_{t-1}$ at the end of the previous week:

$$
S_t = S_{t-1} + P - I - Q - E_a - D
$$

All terms are weekly totals in mm.
The model conserves water exactly: the test suite checks this identity every week.

### Interception and throughfall

Intercepted precipitation is limited by a canopy capacity that grows with biomass, and it evaporates within the week:

$$
I = \min(P, I_{\max}), \qquad P_T = P - I
$$

### Runoff and infiltration

Surface runoff takes a fraction of throughfall that rises with the store's relative saturation:

$$
Q_s = r_{\max} \left(\frac{S_{t-1}}{S_{\max}}\right)^{\gamma} P_T
$$

where $r_{\max}$ is the runoff fraction from a saturated soil and $\gamma$ the runoff exponent.
Water that would then overfill the store also runs off, as saturation excess:

$$
Q_e = \max(S_{t-1} + P_T - Q_s - S_{\max},\ 0), \qquad Q = Q_s + Q_e, \qquad F = P_T - Q
$$

The available water is then $A = S_{t-1} + F \le S_{\max}$.

### Evapotranspiration

Evaporative demand comes from a degree-day relation, scaled by elevation:

$$
E_0 = c_E \cdot 7 \max(T - T_b,\ 0) \cdot m_z,
\qquad
m_z = \mathrm{clip}\left(1 + g_z \frac{z}{1000},\ m_{z,\min},\ m_{z,\max}\right)
$$

where $T$ is weekly mean air temperature (°C), $T_b$ the base temperature, $c_E$ the calibrated evapotranspiration coefficient (mm °C⁻¹ day⁻¹) and $z$ the elevation (m).

Potential evapotranspiration applies the crop coefficient $k_c$ and the root-uptake factor $u$, both of which rise with biomass:

$$
E_p = E_0 \, k_c \, u
$$

Actual evapotranspiration is reduced by water stress and cannot exceed the available water:

$$
w = \left(\frac{A}{S_{\max}}\right)^{\beta},
\qquad
E_a = \min(w\, E_p,\ A)
$$

The stress exponent $\beta$ increases with clay content, so clay soils hold water more tightly.

### Drainage

A fixed fraction $d$ of the water above field capacity drains each week:

$$
D = d \max\left(A - E_a - \theta_{fc} S_{\max},\ 0\right)
$$

where $\theta_{fc}$ is field capacity as a fraction of $S_{\max}$.

## Biomass effects

All biomass effects share a single saturating function of biomass $B$ (g C m⁻²), with half-saturation constant $K_B$:

$$
f_B = \frac{B}{B + K_B}
$$

Each effect then rises linearly in $f_B$, from its bare-soil value to its maximum:

$$
k_c = k_{c,\min} + (k_{c,\max} - k_{c,\min}) f_B,
\qquad
I_{\max} = I_{\max}^{\infty} f_B,
\qquad
u = 1 + (u_{\max} - 1) f_B
$$

## Clay effects

The calibrated soil parameters are base values for a soil with the reference clay content $C_{\mathrm{ref}}$.
For clay content $C$ (percent, clipped to between 0 and 80), let

$$
\Delta = s_C \frac{C - C_{\mathrm{ref}}}{100}
$$

with clay sensitivity $s_C$.
Each property is scaled linearly in $\Delta$, then clipped to a plausible range:

$$
\begin{aligned}
S_{\max} &= S_{\max,0}\,(1 + \Delta) \\
d        &= d_0\,(1 - a_d \Delta) \\
r_{\max} &= r_{\max,0}\,(1 + a_r \Delta) \\
\beta    &= \beta_0\,(1 + a_\beta \Delta)
\end{aligned}
$$

More clay therefore means more storage, slower drainage, more runoff and a steeper stress response.
A single shared sensitivity $s_C$ keeps the parameter count down.

## Frozen soil

A week is frozen when its mean air temperature is below 0 °C.
In a frozen week:

- only a fraction $\phi_f$ of throughfall infiltrates, and the rest runs off;
- reference evapotranspiration, the biomass-driven part of root uptake, and drainage are each scaled down by a fixed multiplier.

This is a threshold on weekly air temperature, not a frozen-soil state: there is no memory of previous weeks, no lag, and no snowpack.

## Parameters and constants

The nine calibrated parameters are fields of [`SoilWaterParams`](API_Reference/params.md#soil_moisture_model.params.SoilWaterParams).
Every other number in the equations above is a field of [`ModelConstants`](API_Reference/params.md#soil_moisture_model.params.ModelConstants), with its default value, so sensitivity studies can vary them without editing the code.
The initial store $S_0$ is an argument of [`simulate`](API_Reference/model.md#soil_moisture_model.model.simulate) rather than a parameter.

| Symbol | Meaning | Where |
|---|---|---|
| $S_{\max,0}$, $d_0$, $r_{\max,0}$ | base capacity, drainage coefficient, max runoff fraction | `SoilWaterParams` |
| $\gamma$, $\theta_{fc}$ | runoff exponent, field-capacity fraction | `SoilWaterParams` |
| $C_{\mathrm{ref}}$, $s_C$ | reference clay, clay sensitivity | `SoilWaterParams` |
| $c_E$, $K_B$ | ET coefficient, biomass half-saturation | `SoilWaterParams` |
| $k_{c,\min}$, $k_{c,\max}$, $I_{\max}^{\infty}$, $u_{\max}$ | biomass-effect limits | `ModelConstants` |
| $T_b$, $g_z$, $m_{z,\min}$, $m_{z,\max}$ | base temperature, elevation gradient and bounds | `ModelConstants` |
| $\beta_0$, $a_d$, $a_r$, $a_\beta$ | base stress exponent, clay response factors | `ModelConstants` |
| $\phi_f$ and the frozen multipliers | frozen-soil behaviour | `ModelConstants` |

## Limitations

- Evaporative demand depends on temperature only: there is no radiation, humidity or wind.
- Interception evaporates in full every week, regardless of evaporative demand.
- Freezing is diagnosed from air temperature alone; there is no snowpack.
- The single store has no vertical structure, so it cannot represent a wet surface over a dry subsoil.
- The time step is fixed at one week.
