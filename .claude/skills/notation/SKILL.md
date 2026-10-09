---
name: notation
description: >-
  This project's terminology, mathematical notation, and the code identifiers that
  represent it, recorded in docs/notation.md. Read that file before writing or editing
  any equation, docstring containing maths, or numerical code, and before naming any
  variable that stands for a mathematical quantity. Triggers include "soil moisture",
  "evapotranspiration", "reference ET", "crop coefficient", "water-stress
  coefficient", "runoff", "drainage", "field capacity", "clay", "nominal",
  "frozen", work in src/soil_moisture_model/ (model.py, processes.py, params.py),
  docs/science.md and scripts/calibrate_icos.py, and any request to rename, refactor,
  or document the numerical parts of this codebase.
---

# Notation

`docs/notation.md` is authoritative for terminology, symbols, and code names in this project.

**Read it before writing maths or naming a mathematical quantity.**
Do not reconstruct a symbol from FAO-56, from memory, or from surrounding code.
Surrounding code may predate the agreement; the Migration section lists renames not yet applied.

Two rules that are easy to get wrong:

- The **Deviations** section lists deliberate departures from FAO-56.
  Code matching those entries is correct.
  Do not change it to match the reference.
- A quantity not in the document gets added to it in the same change that introduces it.
  Propose the symbol, say which existing convention it follows, and get agreement before using it widely.
