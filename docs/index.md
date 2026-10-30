---
title: Home
icon: lucide/house
---

# Soil Moisture Model

A reduced-complexity, weekly bucket model of soil moisture.
It needs only weekly air temperature, precipitation and plant biomass, plus a site's elevation and soil clay content.
Each week it partitions precipitation into canopy interception, runoff, evapotranspiration, drainage and storage in a single soil water store.

The model is a component of the [SatTerC](https://github.com/SatTerC/satterc) terrestrial carbon modelling framework.
There it runs downstream of [SGAM](https://github.com/SatTerC/sgam), which supplies weekly plant biomass.
It can also be used on its own.

The model is written in plain numpy and vectorised over space: a whole block of pixels, each with its own parameters, runs in one call, and only the time dimension is looped over.

- [Science](science.md): the model's processes and equations.
- [API Reference](API_Reference/model.md): every function and class.

## Installation

=== "pip"

    ``` sh
    pip install git+https://github.com/SatTerC/soil-moisture-model
    ```

=== "uv"

    ``` sh
    uv add git+https://github.com/SatTerC/soil-moisture-model
    ```

## Quickstart

Drivers are arrays whose first axis is time, in weeks.
Site inputs and parameters broadcast against the remaining (spatial) axes.

```python
import numpy as np

from soil_moisture_model import SoilWaterParams, simulate

rng = np.random.default_rng(0)
weeks = np.arange(3 * 52)

temperature = 10.0 - 8.0 * np.cos(2 * np.pi * weeks / 52)  # degC
precipitation = rng.gamma(1.5, 12.0, weeks.size)  # mm per week
biomass = 250.0 - 200.0 * np.cos(2 * np.pi * weeks / 52)  # gC m-2

out = simulate(
    temperature,
    precipitation,
    biomass,
    elevation=150.0,  # m
    clay=25.0,  # percent
    initial_soil_moisture=80.0,  # mm
)

print(out.soil_moisture.shape)  # (156,)
print(out.soil.soil_water_capacity)  # mm, after the clay adjustment
```

To run several pixels at once, add trailing axes.
Here, three pixels share the climate but differ in clay content and soil water capacity:

```python
n_pixel = 3
block = simulate(
    np.repeat(temperature[:, None], n_pixel, axis=1),
    np.repeat(precipitation[:, None], n_pixel, axis=1),
    np.repeat(biomass[:, None], n_pixel, axis=1),
    elevation=150.0,
    clay=np.array([10.0, 25.0, 50.0]),
    params=SoilWaterParams(nominal_soil_water_capacity=np.array([120.0, 160.0, 200.0])),
)

print(block.soil_moisture.shape)  # (156, 3)
print(block.relative_soil_moisture.mean(axis=0))
```

`simulate` returns a [`SoilWaterOutput`](API_Reference/model.md#soil_moisture_model.model.SoilWaterOutput) holding every weekly flux and state.
The calibrated parameters are in [`SoilWaterParams`](API_Reference/params.md#soil_moisture_model.params.SoilWaterParams).
The fixed constants are in [`ModelConstants`](API_Reference/params.md#soil_moisture_model.params.ModelConstants).
