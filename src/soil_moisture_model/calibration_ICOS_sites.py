#!/usr/bin/env python3
"""
ICOS Ecosystem Stations Soil Water Model Calibration Script

Overview:
This script calibrates a simple soil water balance model for multiple ICOS (Integrated Carbon Observation System)
ecosystem flux tower sites using observed soil water content (SWC) data. The observed data can be found here: https://doi.org/10.18160/R3G6-Z8ZH.
The code processes sites filtered (ICOS_stations_processed.csv) to specific vegetation types (croplands, grasslands, forests, shrublands, savannas).

Key Functionality:
1. Loads ICOS stations metadata from CSV and filters by vegetation type.
2. For each site (skipping previously calibrated ones):
   - Loads weekly environmental data (NetCDF: temp, precip, LAI) and hourly FLUXNET CSV for SWC.
   - Aggregates SWC to weekly means.
   - Defines 11 soil model parameters + plant-type-specific LAI-to-biomass multiplier with bounds.
   - Uses SciPy's dual_annealing global optimization to minimize RMSE between simulated and observed SWC.
   - Saves best parameters per site (Parquet) and simulation results (Parquet).
3. Handles failures (missing data, optimization errors) and reports summary.

Dependencies:
- External: simple_soil_moisture_model (custom module with SoilWaterParams dataclass, simulate_soil_water_balance, params_as_dict)
- Data paths: Hardcoded to /mnt/shared/pyrealm2/ (NetCDF inputs, FLUXNET CSVs)
- Outputs: best_params_by_site.parquet, results_all_sites.parquet

Model: Bucket-style soil water balance (inspired by SPLASH/pyrealm), accounting for:
- Precipitation input
- PET (potential ET, temperature-based)
- Drainage, runoff, field capacity
- Clay fraction, elevation effects
- Biomass/LAI influence on transpiration

pyrealm Context: Likely part of pyrealm ecosystem modeling suite for carbon/water fluxes.[web:21][web:25]

Usage: python script.py [data_dir]  (defaults to ./)
"""

from dataclasses import (
    dataclass,
    field,
    fields,
    replace,
)  # For SoilWaterParams handling (not defined here)
from typing import Dict, List, Optional, Sequence
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib.pyplot as plt  # Imported but unused
from scipy.optimize import (
    dual_annealing,
)  # Global optimization: dual annealing for non-convex param search
from simple_soil_moisture_model import (
    SoilWaterParams,
    simulate_soil_water_balance,
    params_as_dict,
)  # Custom model
import sys
import os

# Command-line data directory (optional, defaults to current dir)
if len(sys.argv) > 1:
    data_dir = sys.argv[1]
else:
    data_dir = "./"

# Load and filter ICOS stations metadata: Keep only target vegetation types
icosStations = pd.read_csv("/mnt/shared/pyrealm2/ICOS_stations_processed.csv")
icosStations = icosStations[
    icosStations["Site type"].isin(
        [
            "croplands",
            "grasslands",
            "forest",
            "open shrublands",
            "savannas",
            "closed shrublands",
            "evergreen needleleaf forests",
            "evergreen broadleaf forests",
            "deciduous needleleaf forests",  # Note: duplicated in original
            "mixed forests",
        ]
    )
]

# Fallback to global icosSites if defined (likely from prior context), else use filtered stations
sites_df = icosSites if "icosSites" in globals() else icosStations

# Track progress: Skip sites with existing calibrations
existing_sites = set()
best_params_file = f"{data_dir}/best_params_by_site.parquet"
results_file = f"{data_dir}/results_all_sites.parquet"

if os.path.exists(best_params_file):
    existing_sites = set(pd.read_parquet(best_params_file).index)

existing_results = None
if os.path.exists(results_file):
    existing_results = pd.read_parquet(results_file)

# Accumulators for outputs and errors
all_results = []
best_params_records = []
failed_sites = []
failed_swc = []
failed_calibration = []

# Base soil params (from custom module)
base_params = SoilWaterParams()

# Parameters to calibrate (soil physics, hydrology, PET, vegetation influence)
calib_param_names = [
    "initial_soil_moisture_mm",  # Starting soil water (mm)
    "base_soil_water_capacity_mm",  # Max soil water holding capacity (mm)
    "base_drainage_coeff",  # Base rate of gravity drainage
    "base_runoff_fraction_max",  # Max fraction of excess precip as surface runoff
    "runoff_exponent",  # Nonlinear exponent for runoff
    "field_capacity_fraction",  # Fraction of capacity before drainage slows
    "reference_clay_pct",  # Baseline clay % for texture effects
    "clay_sensitivity",  # How clay affects capacity/drainage
    "pet_coeff_mm_per_degday",  # Scales temperature to PET (mm/°C-day)
    "biomass_half_sat_gC_m2",  # Half-saturation for biomass effect on transpiration
]

# Realistic bounds for optimization (prevent unphysical params)
param_bounds = {
    "initial_soil_moisture_mm": (5.0, 250.0),
    "base_soil_water_capacity_mm": (60.0, 400.0),
    "base_drainage_coeff": (0.01, 0.30),
    "base_runoff_fraction_max": (0.02, 0.95),
    "runoff_exponent": (0.5, 4.0),
    "field_capacity_fraction": (0.40, 0.95),
    "reference_clay_pct": (5.0, 60.0),
    "clay_sensitivity": (0.0, 0.10),
    "pet_coeff_mm_per_degday": (0.1, 1.5),
    "biomass_half_sat_gC_m2": (20.0, 800.0),
}

# Plant-type-specific bounds for LAI-to-biomass conversion multiplier (affects transpiration)
lai_to_biomass_bounds = {
    "tree": (300.0, 1000.0),
    "shrub": (50.0, 400.0),
    "grass": (50.0, 400.0),
    "crop": (50.0, 400.0),
    "default": (50.0, 400.0),
}


def vector_to_params_simple(x, plant_type):
    """
    Convert optimization vector x to model params + multiplier.
    x[:-1]: soil params; x[-1]: LAI-to-biomass multiplier.
    Uses dataclass replace for immutable update.
    """
    vals = {n: float(v) for n, v in zip(calib_param_names, x[:-1])}
    lai_to_biomass_multiplier = float(x[-1])
    return replace(base_params, **vals), lai_to_biomass_multiplier


# Main loop: Process each unique site ID
for site_name in sites_df["Id"].dropna().unique():
    if site_name in existing_sites:
        print(f"Skipping {site_name} (already calibrated)")
        continue

    try:
        # Load site-specific weekly drivers (NetCDF from pyrealm2 processing)
        D_site = xr.open_dataset(
            f"/mnt/shared/pyrealm2/inputData/{site_name}_weekly_final_variables.nc"
        )
        site_meta = sites_df.loc[sites_df["Id"] == site_name].iloc[0]
        elevation = float(
            site_meta["Elevation above sea"]
        )  # For PET/atm pressure correction?
        plant_type = (
            site_meta["plant_type"] if "plant_type" in site_meta.index else np.nan
        )
        clay_pct = float(D_site.attrs["clay_fraction"])  # Soil texture effect

        # Load and process observed SWC from FLUXNET half-hourly CSV
        try:
            D_flux = pd.read_csv(
                f"/mnt/shared/pyrealm2/ICOS_ETC_ARCHIVE/tmp_{site_name}/ICOSETC_{site_name}_FLUXNET_HH_L2.csv"
            )
            site_csv_df = D_flux.copy()
            site_csv_df["TIMESTAMP"] = pd.to_datetime(
                site_csv_df["TIMESTAMP_START"].astype(str), format="%Y%m%d%H%M"
            )
            site_csv_df["SWC_F_MDS_1"] = site_csv_df["SWC_F_MDS_1"].replace(
                -9999, np.nan
            )

            # Aggregate to weekly (Friday-end periods, matching model?)
            swc_weekly_site = (
                site_csv_df.assign(
                    time=site_csv_df["TIMESTAMP"]
                    .dt.to_period("W-FRI")
                    .dt.end_time.dt.normalize()
                )
                .groupby("time", as_index=False)["SWC_F_MDS_1"]
                .mean()
            )
        except Exception as e:
            failed_swc.append((site_name, str(e)))
            swc_weekly_site = pd.DataFrame(columns=["time", "SWC_F_MDS_1"])

        # Optimization bounds: soil params + plant-specific biomass multiplier
        plant_type_key = str(plant_type).strip().lower()
        biomass_bounds = lai_to_biomass_bounds.get(
            plant_type_key, lai_to_biomass_bounds["default"]
        )
        bounds = [param_bounds[n] for n in calib_param_names] + [biomass_bounds]

        def objective(x):
            """
            RMSE objective: Simulate soil moisture vs observed SWC.
            Returns inf on errors/short data (<20 weeks).
            """
            try:
                p, lai_to_biomass_multiplier = vector_to_params_simple(x, plant_type)
                # Biomass from LAI * multiplier (drives transpiration)
                biomass = D_site.lai[:, 0, 0].data * lai_to_biomass_multiplier
                sim_in = pd.DataFrame(
                    {
                        "time": D_site.time.data,
                        "temp_c": D_site.temperature_celcius[:, 0, 0].data,
                        "precip_mm": D_site.precipitation_mm[:, 0, 0].data,
                        "biomass_gC_m2": biomass,
                    }
                )

                # Run model simulation
                out_tmp = simulate_soil_water_balance(
                    sim_in,
                    date_col="time",
                    elevation_m=elevation,
                    clay_pct=clay_pct,
                    params=p,
                )
                out_tmp["time"] = pd.to_datetime(out_tmp["time"])

                # Align sim/obs, drop NaNs
                merged = (
                    out_tmp[["time", "soil_moisture_mm"]]
                    .merge(swc_weekly_site, on="time", how="inner")
                    .dropna(subset=["soil_moisture_mm", "SWC_F_MDS_1"])
                )
                if len(merged) < 20:
                    return np.inf

                rmse_val = np.sqrt(
                    np.mean((merged["soil_moisture_mm"] - merged["SWC_F_MDS_1"]) ** 2)
                )
                return float(rmse_val)
            except Exception:
                return np.inf

        # Optimize: Dual annealing (global, handles multimodal cost surface)
        try:
            opt = dual_annealing(
                objective,
                bounds=bounds,
                maxiter=120,  # Iterations
                seed=42,  # Reproducibility
                no_local_search=False,  # Includes local refinement
            )
            best_x = opt.x
            best_rmse = float(opt.fun)
        except Exception as e:
            failed_calibration.append((site_name, str(e)))
            continue

        # Reconstruct best simulation for output
        best_params, lai_to_biomass_multiplier = vector_to_params_simple(
            best_x, plant_type
        )
        biomass_best = D_site.lai[:, 0, 0].data * lai_to_biomass_multiplier
        example_site = pd.DataFrame(
            {
                "time": D_site.time.data,
                "temp_c": D_site.temperature_celcius[:, 0, 0].data,
                "precip_mm": D_site.precipitation_mm[:, 0, 0].data,
                "biomass_gC_m2": biomass_best,
            }
        )

        out_site = simulate_soil_water_balance(
            example_site,
            date_col="time",
            elevation_m=elevation,
            clay_pct=clay_pct,
            params=best_params,
        )

        out_site["time"] = pd.to_datetime(out_site["time"])
        out_site = out_site.merge(swc_weekly_site, on="time", how="left")

        # Add metadata
        out_site["site_name"] = site_name
        out_site["plant_type"] = plant_type
        out_site["calib_rmse"] = best_rmse
        all_results.append(out_site)

        # Record best params
        rec = {
            "site_name": site_name,
            "plant_type": plant_type,
            "calib_rmse": best_rmse,
            "lai_to_biomass_multiplier": lai_to_biomass_multiplier,
        }
        rec.update(params_as_dict(best_params))  # Flatten dataclass to dict
        best_params_records.append(rec)
        print(f"Completed calibration for site: {site_name}")

    except Exception as e:
        failed_sites.append((site_name, str(e)))

    # Periodic save: Append to existing files (inside loop? Likely bug, should be outside)
    if all_results:
        results_all_sites = (
            pd.concat(all_results, ignore_index=True)
            .set_index(["time", "site_name", "plant_type"])
            .sort_index()
        )
        if existing_results is not None:
            results_all_sites = pd.concat([existing_results, results_all_sites])
        results_all_sites.to_parquet(f"{data_dir}/results_all_sites.parquet")
    else:
        print("Warning: No successful calibrations to save.")

    if best_params_records:
        best_params_by_site = (
            pd.DataFrame(best_params_records).set_index("site_name").sort_index()
        )
        if os.path.exists(best_params_file):
            existing_best_params = pd.read_parquet(best_params_file)
            best_params_by_site = pd.concat([existing_best_params, best_params_by_site])
        best_params_by_site.to_parquet(f"{data_dir}/best_params_by_site.parquet")
        best_params_records.clear()  # Clear after save
    else:
        print("Warning: No best parameters to save.")

# Final summary
print(
    f"Failed sites: {len(failed_sites)}, Failed SWC: {len(failed_swc)}, Failed calibration: {len(failed_calibration)}"
)
