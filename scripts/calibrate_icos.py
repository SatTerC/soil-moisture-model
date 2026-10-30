# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "soil_moisture_model",
#     "netcdf4>=1.7",
#     "pandas>=2.2",
#     "pyarrow>=18.0",
#     "scipy>=1.14",
#     "xarray>=2025.1",
# ]
#
# [tool.uv.sources]
# soil_moisture_model = { path = "..", editable = true }
# ///
"""Calibrate the soil moisture model against ICOS soil water content.

For each ICOS ecosystem station of a selected vegetation type, this script
fits the model's parameters, the initial soil water store and a LAI-to-biomass
multiplier by minimising the RMSE between simulated soil moisture and weekly
mean observed soil water content (FLUXNET ``SWC_F_MDS_1``), using
`scipy.optimize.dual_annealing`.

Observed data: ICOS ETC L2 archive, https://doi.org/10.18160/R3G6-Z8ZH.

Inputs
------
- ``--stations-csv``: station metadata with columns ``Id``, ``Site type``,
  ``Elevation above sea`` and, optionally, ``plant_type``.
- ``--input-dir``: weekly drivers, one ``<site>_weekly_final_variables.nc`` per
  site, with variables ``temperature_celcius``, ``precipitation_mm`` and ``lai``
  on ``(time, lat, lon)`` and a global attribute ``clay_fraction``.
- ``--fluxnet-dir``: half-hourly FLUXNET files at
  ``tmp_<site>/ICOSETC_<site>_FLUXNET_HH_L2.csv``.

Outputs (in ``--out-dir``, updated after every site so a run can be resumed):
``best_params_by_site.parquet`` and ``results_all_sites.parquet``.

Usage
-----
    uv run scripts/calibrate_icos.py --help

TODO: the objective compares soil moisture in mm with SWC in volumetric percent.
See the science review issue before relying on calibrated values.
"""

import argparse
from collections.abc import Callable, Sequence
from dataclasses import fields
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from scipy.optimize import dual_annealing

from soil_moisture_model import SoilWaterOutput, SoilWaterParams, simulate

SITE_TYPES = (
    "croplands",
    "grasslands",
    "forest",
    "open shrublands",
    "savannas",
    "closed shrublands",
    "evergreen needleleaf forests",
    "evergreen broadleaf forests",
    "deciduous needleleaf forests",
    "mixed forests",
)

# Search bounds of the calibrated quantities. The first entry is the initial
# store; the rest are SoilWaterParams fields.
PARAM_BOUNDS: dict[str, tuple[float, float]] = {
    "initial_soil_moisture": (5.0, 250.0),
    "nominal_soil_water_capacity": (60.0, 400.0),
    "drainage_coefficient": (0.01, 0.30),
    "max_runoff_fraction": (0.02, 0.95),
    "runoff_exponent": (0.5, 4.0),
    "field_capacity_fraction": (0.40, 0.95),
    "nominal_clay": (5.0, 60.0),
    "clay_sensitivity": (0.0, 0.10),
    "reference_et_coefficient": (0.05, 0.5),
    "biomass_half_saturation": (20.0, 800.0),
}

# Bounds of the LAI-to-biomass multiplier (gC m-2 per unit LAI) by plant type.
LAI_TO_BIOMASS_BOUNDS: dict[str, tuple[float, float]] = {
    "tree": (300.0, 1000.0),
    "shrub": (50.0, 400.0),
    "grass": (50.0, 400.0),
    "crop": (50.0, 400.0),
}
DEFAULT_LAI_TO_BIOMASS_BOUNDS = (50.0, 400.0)

MIN_MATCHED_WEEKS = 20
SWC_MISSING = -9999


def unpack(x: Sequence[float]) -> tuple[SoilWaterParams, float, float]:
    """Split an optimiser vector into (params, initial store, LAI multiplier)."""
    names = list(PARAM_BOUNDS)
    values = dict(zip(names, map(float, x[: len(names)]), strict=True))
    initial = values.pop("initial_soil_moisture")
    return SoilWaterParams(**values), initial, float(x[len(names)])


def load_stations(path: Path) -> pd.DataFrame:
    """Read the station metadata, keeping only the vegetation types of interest."""
    stations = pd.read_csv(path)
    stations = stations[stations["Site type"].isin(SITE_TYPES)]
    return stations.dropna(subset=["Id"]).drop_duplicates(subset="Id")


def load_drivers(input_dir: Path, site: str) -> tuple[pd.DatetimeIndex, dict, float]:
    """Return the weekly time index, driver arrays and clay content of a site."""
    with xr.open_dataset(input_dir / f"{site}_weekly_final_variables.nc") as ds:
        time = pd.DatetimeIndex(ds["time"].values)
        drivers = {
            "temperature": ds["temperature_celcius"][:, 0, 0].values,
            "precipitation": ds["precipitation_mm"][:, 0, 0].values,
            "lai": ds["lai"][:, 0, 0].values,
        }
        clay = clay_percent(float(ds.attrs["clay_fraction"]))
    return time, drivers, clay


def clay_percent(value: float) -> float:
    """Return the ``clay_fraction`` attribute as clay percent, as the model takes it.

    Despite its name the attribute is passed through as percent. A value of 1 or
    less is far more likely a true fraction than a soil with under 1 % clay, and
    would make every site look clay-free, so it is refused rather than guessed.
    """
    if value <= 1.0:
        raise ValueError(
            f"clay_fraction = {value} looks like a fraction (0-1), but the model "
            "takes clay percent; check the input files"
        )
    return value


def load_weekly_swc(fluxnet_dir: Path, site: str) -> pd.Series:
    """Return weekly mean observed SWC, indexed by the Friday ending each week."""
    path = fluxnet_dir / f"tmp_{site}" / f"ICOSETC_{site}_FLUXNET_HH_L2.csv"
    hh = pd.read_csv(path, usecols=["TIMESTAMP_START", "SWC_F_MDS_1"])
    stamp = pd.to_datetime(hh["TIMESTAMP_START"].astype(str), format="%Y%m%d%H%M")
    swc = hh["SWC_F_MDS_1"].replace(SWC_MISSING, np.nan)
    week_end = stamp.dt.to_period("W-FRI").dt.end_time.dt.normalize()
    return swc.groupby(week_end.to_numpy()).mean()


def run(drivers: dict, elevation: float, clay: float, x) -> SoilWaterOutput:
    """Run the model for one site from an optimiser vector."""
    params, initial, lai_to_biomass = unpack(x)
    return simulate(
        drivers["temperature"],
        drivers["precipitation"],
        drivers["lai"] * lai_to_biomass,
        elevation,
        clay,
        initial_soil_moisture=initial,
        params=params,
    )


def make_objective(
    time: pd.DatetimeIndex,
    drivers: dict,
    swc: pd.Series,
    elevation: float,
    clay: float,
) -> Callable[[np.ndarray], float]:
    """Return the RMSE objective between simulated soil moisture and SWC.

    Weeks are matched on their timestamps once, up front. The objective is
    infinite if fewer than `MIN_MATCHED_WEEKS` weeks have both values.
    """
    obs = swc.reindex(time).to_numpy()
    matched = np.isfinite(obs)
    obs = obs[matched]

    def objective(x: np.ndarray) -> float:
        sim = run(drivers, elevation, clay, x).soil_moisture[matched]
        ok = np.isfinite(sim)
        if ok.sum() < MIN_MATCHED_WEEKS:
            return np.inf
        return float(np.sqrt(np.mean((sim[ok] - obs[ok]) ** 2)))

    return objective


def to_frame(out: SoilWaterOutput, time: pd.DatetimeIndex) -> pd.DataFrame:
    """Tabulate the time-series outputs of a run."""
    columns = {f.name: getattr(out, f.name) for f in fields(out) if f.name != "soil"}
    columns["total_evaporative_loss"] = out.total_evaporative_loss
    return pd.DataFrame(columns, index=pd.Index(time, name="time"))


def calibrate_site(
    site: str,
    meta: pd.Series,
    input_dir: Path,
    fluxnet_dir: Path,
    maxiter: int,
) -> tuple[pd.DataFrame, dict]:
    """Calibrate one site; return its best-fit simulation and parameter record."""
    time, drivers, clay = load_drivers(input_dir, site)
    swc = load_weekly_swc(fluxnet_dir, site)
    elevation = float(meta["Elevation above sea"])
    plant_type = meta.get("plant_type", np.nan)

    lai_bounds = LAI_TO_BIOMASS_BOUNDS.get(
        str(plant_type).strip().lower(), DEFAULT_LAI_TO_BIOMASS_BOUNDS
    )
    bounds = [*PARAM_BOUNDS.values(), lai_bounds]
    objective = make_objective(time, drivers, swc, elevation, clay)
    opt = dual_annealing(objective, bounds=bounds, maxiter=maxiter, seed=42)
    if not np.isfinite(opt.fun):
        raise RuntimeError(f"fewer than {MIN_MATCHED_WEEKS} weeks of matched SWC")

    params, initial, lai_to_biomass = unpack(opt.x)
    results = to_frame(run(drivers, elevation, clay, opt.x), time)
    results["SWC_F_MDS_1"] = swc.reindex(time).to_numpy()
    results["site_name"] = site
    results["plant_type"] = plant_type
    results["calib_rmse"] = float(opt.fun)

    record = {
        "site_name": site,
        "plant_type": plant_type,
        "calib_rmse": float(opt.fun),
        "lai_to_biomass_multiplier": lai_to_biomass,
        "initial_soil_moisture": initial,
        **params.as_dict(),
    }
    return results.reset_index(), record


def main(argv: Sequence[str] | None = None) -> None:
    """Calibrate every selected station not already in the output files."""
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0] if __doc__ else None
    )
    parser.add_argument("--stations-csv", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--fluxnet-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=Path())
    parser.add_argument("--maxiter", type=int, default=120)
    args = parser.parse_args(argv)

    params_file = args.out_dir / "best_params_by_site.parquet"
    results_file = args.out_dir / "results_all_sites.parquet"
    best = pd.read_parquet(params_file) if params_file.exists() else None
    results = pd.read_parquet(results_file) if results_file.exists() else None
    done = set() if best is None else set(best.index)

    failed: list[tuple[str, str]] = []
    for _, meta in load_stations(args.stations_csv).iterrows():
        site = str(meta["Id"])
        if site in done:
            print(f"Skipping {site} (already calibrated)")
            continue
        try:
            site_results, record = calibrate_site(
                site, meta, args.input_dir, args.fluxnet_dir, args.maxiter
            )
        except Exception as e:
            failed.append((site, repr(e)))
            print(f"Failed {site}: {e!r}")
            continue

        # Write after every site, so an interrupted run can be resumed.
        site_results = site_results.set_index(["time", "site_name", "plant_type"])
        record_frame = pd.DataFrame([record]).set_index("site_name")
        results = pd.concat([x for x in (results, site_results) if x is not None])
        best = pd.concat([x for x in (best, record_frame) if x is not None])
        results.sort_index().to_parquet(results_file)
        best.sort_index().to_parquet(params_file)
        print(f"Completed calibration for site: {site}")

    print(f"Failed sites: {len(failed)}")


if __name__ == "__main__":
    main()
