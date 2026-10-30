# Soil Moisture Model

A reduced-complexity, weekly bucket model of soil moisture, driven by air temperature, precipitation and plant biomass, with site elevation and soil clay content.
It is written in plain numpy, vectorised over space, and designed as a component of the [SatTerC](https://github.com/SatTerC/satterc) framework.

Documentation, including the model's equations: https://SatTerC.github.io/soil-moisture-model

## Installation

```sh
pip install git+https://github.com/SatTerC/soil-moisture-model
```

## Usage

```python
from soil_moisture_model import simulate

out = simulate(temperature, precipitation, biomass, elevation=150.0, clay=25.0)
out.soil_moisture  # mm, shape (time, *space)
```

## Development

This project uses [`uv`](https://docs.astral.sh/uv/) for package management and [`just`](https://just.systems/) as a command runner.

```sh
uv sync                # install, including dev dependencies
uv run just lint       # format and lint
uv run just typecheck
uv run just test       # or `uv run just test-cov`
uv run just docs       # build the documentation
```

### Regression fixtures

`tests/fixtures/regression/` pins the model's outputs on synthetic scenarios.
Any change that alters the numbers must regenerate them in its own commit, with an entry in `CHANGELOG.md`:

```sh
uv run scripts/make_regression_fixtures.py --fixed-by "<commit subject>"
uv run scripts/make_regression_fixtures.py --check
```

### Calibration

`scripts/calibrate_icos.py` calibrates the model against ICOS soil water content observations.
It declares its own dependencies inline, so `uv run` installs them in an isolated environment:

```sh
uv run scripts/calibrate_icos.py --help
```
