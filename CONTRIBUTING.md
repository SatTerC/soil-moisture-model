# Contributing

Setup, the `just` recipes and how to regenerate the regression fixtures are in the [README](README.md#development).
This file covers the conventions for naming things.

## Notation

Notation lives in two places, split by audience:

| File | Holds | Published |
|---|---|---|
| [`docs/notation.md`](docs/notation.md) | terms, symbols, units, shapes, public code names, deviations from FAO-56 | yes, as the Notation page |
| this file | how symbols become code names, local names, reserved names, editing rules | no |

`docs/notation.md` is the authority for anything it covers.
Where older code disagrees with it, the document is right.

### Editing rules

- A new quantity is added to `docs/notation.md` in the same change that introduces it, never later.
  Its public name goes in the document's Code column; a local name, if it has one, goes in the [table below](#local-names).
- Propose a new symbol before using it widely, and say which existing convention it follows.
- A departure from FAO-56 goes in the document's Deviations section with its reason.
  Code that matches a listed deviation is correct; do not change it to match FAO-56.
- `docs/notation.md` is a glossary.
  Design rationale belongs elsewhere.
- Terms in the document's Avoid column are not used in prose, docstrings or identifiers.

### From symbols to code names

- **Public names spell out the concept.**
  Dataclass fields, function arguments and output fields use the descriptive name from `docs/notation.md`, never a terse one.
- **Locals inside function bodies may mirror the maths**, so dense expressions read like the equations:
  lowercase per PEP 8 (`s_max`, `k_d`, `k_c`, `f_b`, `s_fc`), Greek spelled out (`beta`, `gamma`, `kappa`, `phi`), subscript labels as suffixes ($K_c$ → `k_c`).
- **"min" and "max"** are prefixes in public names (`max_runoff_fraction`) and suffixes in locals (`r_max`).
- **Marks:** $\circ$ → `nominal_` prefix; $\mathrm{eff}$ → `_eff` suffix; $\mathrm{frz}$ → `frozen_` prefix; $S^{+}$ → `soil_moisture_after_infiltration`.
- **$ET$** becomes `et` inside compound names (`reference_et_coefficient`, `potential_et`); public output fields spell out `evapotranspiration`.
- **"pet"** never appears in an identifier: it was ambiguous between reference and potential evapotranspiration.
- **Shapes** are written `(time, *space)` and `space` in docstrings; counters take an `n_` prefix (`n_time`).
- **Docstring maths** is LaTeX between `$` delimiters. Equations taken from FAO-56 carry its tag, e.g. `[FAO56] eq. (81)`.

### Reserved names

- `t` is the week index, so temperature is never `t`; use `temp`.
- `s` is the soil moisture $S_{t-1}$ carried through the time loop, and nothing else.
- There is no bare `d`: the drainage coefficient is `k_d`.
- Free for local helpers: `x`, `y`, `i`, `j`, `k`, `mask`.

### Local names

Locals in `simulate` and the process functions that stand for a symbol.

| Symbol | Local | Note |
|---|---|---|
| $S_{t-1}$ | `s` | |
| $S^{+}_t$ | `soil_moisture_after_infiltration` | |
| $S_{\max}$ | `s_max` | |
| $S_{fc}$ | `s_fc` | |
| $Q_s$ | `surface_runoff` | |
| $Q_e$ | `excess` | |
| $ET_o$, $ET_o^{\mathrm{eff}}$ | `reference_et`, `reference_et_eff` | |
| $ET_p$ | `potential_et` | |
| $ET_a$ | `aet` | |
| $ET_p - I$ | `demand_on_store` | |
| $K_c$ | `k_c` | |
| $K_s$ | `k_s` | |
| $k_d$, $k_d^{\mathrm{eff}}$ | `k_d`, `k_d_eff` | |
| $r_{\max}$ | `r_max` | |
| $\beta$ | `beta` | |
| $f_B$ | `f_b` | |
| $f_B\,I_{\max}$ | `interception_cap` | avoids shadowing the `interception_capacity` function |
| — | `degree_day_reference_et` | import alias of `processes.reference_evapotranspiration`, which the `simulate` argument of that name shadows |
| $\Delta$ | `delta` | |
| $T$ | `temp` | never `t` |
| $s$ | `slope` | `s` is reserved for the store |
