"""End-to-end smoke test of scripts/calibrate_icos.py on synthetic data."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("scipy")
pd = pytest.importorskip("pandas")
xr = pytest.importorskip("xarray")
pytest.importorskip("pyarrow")

SCRIPT = Path(__file__).parents[1] / "scripts" / "calibrate_icos.py"
N_WEEKS = 80


@pytest.fixture(scope="module")
def calibrate():
    spec = importlib.util.spec_from_file_location("calibrate_icos", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_site(root: Path, site: str, *, with_swc: bool) -> None:
    rng = np.random.default_rng(len(site))
    # Week-ending Fridays, matching the script's W-FRI aggregation of SWC.
    time = pd.date_range("2020-01-03", periods=N_WEEKS, freq="W-FRI")
    week = np.arange(N_WEEKS)
    cube = lambda a: a[:, None, None]  # noqa: E731
    ds = xr.Dataset(
        {
            "temperature_celcius": (
                ("time", "lat", "lon"),
                cube(10 - 8 * np.cos(2 * np.pi * week / 52)),
            ),
            "precipitation_mm": (
                ("time", "lat", "lon"),
                cube(rng.gamma(1.5, 12.0, N_WEEKS)),
            ),
            "lai": (("time", "lat", "lon"), cube(2 + np.sin(2 * np.pi * week / 52))),
        },
        coords={"time": time, "lat": [50.0], "lon": [5.0]},
        attrs={"clay_fraction": 25.0},
    )
    (root / "inputs").mkdir(exist_ok=True)
    ds.to_netcdf(root / "inputs" / f"{site}_weekly_final_variables.nc")

    if with_swc:
        stamps = pd.date_range(time[0] - pd.Timedelta(days=6), time[-1], freq="30min")
        swc = (
            30
            + 5 * np.sin(np.arange(len(stamps)) / 2000)
            + rng.normal(0, 1, len(stamps))
        )
        swc[::97] = -9999
        d = root / "fluxnet" / f"tmp_{site}"
        d.mkdir(parents=True)
        pd.DataFrame(
            {
                "TIMESTAMP_START": stamps.strftime("%Y%m%d%H%M").astype(int),
                "SWC_F_MDS_1": swc,
            }
        ).to_csv(d / f"ICOSETC_{site}_FLUXNET_HH_L2.csv", index=False)


def test_calibrates_and_resumes(calibrate, tmp_path, capsys):
    write_site(tmp_path, "BE-Xxx", with_swc=True)
    write_site(tmp_path, "DE-Yyy", with_swc=False)
    (tmp_path / "fluxnet").mkdir(exist_ok=True)
    pd.DataFrame(
        {
            "Id": ["BE-Xxx", "DE-Yyy", "FR-Zzz"],
            "Site type": ["grasslands", "forest", "urban"],
            "Elevation above sea": [100.0, 400.0, 10.0],
            "plant_type": ["grass", "tree", "grass"],
        }
    ).to_csv(tmp_path / "stations.csv", index=False)
    argv = [
        "--stations-csv", str(tmp_path / "stations.csv"),
        "--input-dir", str(tmp_path / "inputs"),
        "--fluxnet-dir", str(tmp_path / "fluxnet"),
        "--out-dir", str(tmp_path),
        "--maxiter", "2",
    ]  # fmt: skip

    calibrate.main(argv)

    best = pd.read_parquet(tmp_path / "best_params_by_site.parquet")
    results = pd.read_parquet(tmp_path / "results_all_sites.parquet")
    assert list(best.index) == ["BE-Xxx"]  # DE-Yyy has no SWC, FR-Zzz is filtered out
    assert np.isfinite(best.loc["BE-Xxx", "calib_rmse"])
    assert len(results) == N_WEEKS
    assert "Failed sites: 1" in capsys.readouterr().out

    calibrate.main(argv)  # second run skips the calibrated site and adds no rows
    assert "Skipping BE-Xxx" in capsys.readouterr().out
    assert len(pd.read_parquet(tmp_path / "results_all_sites.parquet")) == N_WEEKS
