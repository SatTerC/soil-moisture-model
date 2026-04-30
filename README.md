# Soil Moisture Model

This package provides a simple, reduced-complexity model for simulating weekly soil moisture dynamics using a bucket-style soil water balance approach. It is designed for ecohydrological and agricultural applications, supporting calibration, comparison, and exploratory analysis.

## Features
- Simulates soil moisture using precipitation, temperature, biomass, clay content, and elevation
- Accounts for plant water stress, canopy interception, runoff, drainage, and freezing/thawing
- Designed for weekly time steps and exploratory modeling

## Model Parameters
Parameters are set via the `SoilWaterParams` dataclass:

| Parameter                      | Description                                 | Units   | Default |
|--------------------------------|---------------------------------------------|---------|---------|
| initial_soil_moisture_mm       | Initial soil moisture                       | mm      | 50.0    |
| base_soil_water_capacity_mm    | Base soil water holding capacity            | mm      | 160.0   |
| base_drainage_coeff            | Drainage coefficient                        | frac    | 0.10    |
| base_runoff_fraction_max       | Max runoff fraction                         | frac    | 0.45    |
| runoff_exponent                | Runoff exponent                             | -       | 2.0     |
| field_capacity_fraction        | Field capacity as fraction of capacity      | frac    | 0.70    |
| reference_clay_pct             | Reference clay percentage                   | %       | 25.0    |
| clay_sensitivity               | Clay sensitivity for soil properties        | 1/%     | 0.04    |
| pet_coeff_mm_per_degday        | PET coefficient (mm/deg-day)                | mm/°C   | 0.55    |
| biomass_half_sat_gC_m2         | Biomass half-saturation (gC/m²)             | gC/m²   | 150.0   |

## Model Inputs
The main function `simulate_soil_water_balance` requires:

- `data`: pandas DataFrame with columns:
	- `temp_c`: weekly mean air temperature (°C)
	- `precip_mm`: weekly precipitation (mm)
	- `biomass_gC_m2`: plant biomass (gC/m²)
- `elevation_m`: site elevation (meters)
- `clay_pct`: soil clay content (%)
- `params`: (optional) instance of `SoilWaterParams`

## Model Outputs
The returned DataFrame includes columns:

- `soil_moisture_mm`: soil moisture (mm)
- `relative_soil_moisture`: relative soil moisture (0-1)
- `et_actual_mm`: actual evapotranspiration (mm)
- `et_potential_mm`: potential evapotranspiration (mm)
- `total_evaporative_loss_mm`: total evaporative loss (mm)
- `runoff_mm`: runoff (mm)
- `drainage_mm`: drainage (mm)
- `intercepted_mm`: canopy interception (mm)
- `throughfall_mm`: throughfall (mm)
- `water_stress`: water stress index (0-1)
- `frozen_soil`: boolean, soil frozen status
- plus diagnostic columns (e.g., PET, crop coefficient, etc.)

## Units
- All water fluxes and storages are in millimeters (mm).
- Biomass is in grams of carbon per square meter (gC/m²).
- Temperature in degrees Celsius (°C).
- Clay content in percent (%).
- Elevation in meters (m).

## Model calibration
Code for calibration of SMM parameters using observed soil water content data from selected ICOS sites. 

## Quick start

Requires Python >=3.13.

```sh
# Clone the repository
git clone https://github.com/SatTerC/soil-moisture-model.git
cd soil-moisture-model

# Install the project and dependencies with uv
uv sync
```

## Development workflow

This project uses [`uv`](https://docs.astral.sh/uv/) for package management and [`just`](https://just.systems/) as a command runner.

```sh
# See all available commands
just

# Format and lint the code
just lint

# Run the test suite
just test

# Build the documentation
just docs
```
