"""Generate (or check) the regression fixtures in tests/fixtures/regression/.

The fixtures pin the numerical behaviour of the model on a handful of synthetic
scenarios, each chosen to exercise a branch of the model that the others do not.

By default the outputs come from the *legacy* model, loaded from the git commit
``LEGACY_REF`` rather than from the working tree, so the fixtures can always be
regenerated from a fixed reference. Once a deliberate change to the model's
behaviour lands, regenerate them from the working tree with ``--fixed-by``.

Usage
-----
    uv run --with pandas python scripts/make_regression_fixtures.py
    uv run --with pandas python scripts/make_regression_fixtures.py --check
    uv run python scripts/make_regression_fixtures.py --fixed-by "<commit subject>"
"""

import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "regression"
LEGACY_REF = "9d5b8fe"
LEGACY_PATH = "src/soil_moisture_model/main.py"
N_WEEKS = 520

# Legacy output columns that vary in time, plus the per-site soil properties.
TIME_SERIES_OUTPUTS = (
    "base_pet_mm",
    "kc",
    "biomass_uptake_factor",
    "interception_capacity_mm",
    "intercepted_mm",
    "throughfall_mm",
    "frozen_soil",
    "et_potential_mm",
    "water_stress",
    "et_actual_mm",
    "total_evaporative_loss_mm",
    "runoff_mm",
    "drainage_mm",
    "soil_moisture_mm",
    "relative_soil_moisture",
)
SITE_OUTPUTS = (
    "soil_water_capacity_mm",
    "drainage_coeff",
    "runoff_fraction_max",
    "stress_exponent",
)

# Parameter-space corners, taken from the calibration bounds.
PARAMS_HIGH = {
    "initial_soil_moisture_mm": 250.0,
    "base_soil_water_capacity_mm": 400.0,
    "base_drainage_coeff": 0.30,
    "base_runoff_fraction_max": 0.95,
    "runoff_exponent": 4.0,
    "field_capacity_fraction": 0.95,
    "reference_clay_pct": 5.0,
    "clay_sensitivity": 0.10,
    "pet_coeff_mm_per_degday": 1.5,
    "biomass_half_sat_gC_m2": 800.0,
}
PARAMS_LOW = {
    "initial_soil_moisture_mm": 5.0,
    "base_soil_water_capacity_mm": 60.0,
    "base_drainage_coeff": 0.01,
    "base_runoff_fraction_max": 0.02,
    "runoff_exponent": 0.5,
    "field_capacity_fraction": 0.40,
    "reference_clay_pct": 60.0,
    "clay_sensitivity": 0.10,
    "pet_coeff_mm_per_degday": 0.1,
    "biomass_half_sat_gC_m2": 20.0,
}


def _seasonal(n: int, mean: float, amplitude: float) -> np.ndarray:
    week = np.arange(n)
    return mean - amplitude * np.cos(2 * np.pi * week / 52.0)


@dataclass
class Scenario:
    """A synthetic site and the branch-coverage checks it must satisfy."""

    name: str
    description: str
    temp_c: np.ndarray
    precip_mm: np.ndarray
    biomass_gC_m2: np.ndarray
    elevation_m: float
    clay_pct: float
    params: dict[str, float] = field(default_factory=dict)
    # name -> predicate on the coverage counts; all must hold
    requires: dict[str, Callable[[dict], bool]] = field(default_factory=dict)


def build_scenarios() -> list[Scenario]:
    """Return the scenarios, with seeded random drivers."""
    rng = np.random.default_rng(20261008)
    n = N_WEEKS

    def precip(shape: float, scale: float) -> np.ndarray:
        return rng.gamma(shape, scale, n)

    def noise(sd: float) -> np.ndarray:
        return rng.normal(0.0, sd, n)

    biomass_seasonal = np.maximum(_seasonal(n, 250.0, 200.0) + noise(20.0), 0.0)

    dry_biomass = np.maximum(_seasonal(n, 60.0, 60.0) + noise(10.0), 0.0)
    dry_biomass[(np.arange(n) % 52) < 10] = 0.0

    negative_precip = precip(1.5, 12.0)
    negative_precip[::7] *= -1.0
    negative_biomass = biomass_seasonal.copy()
    negative_biomass[::5] *= -1.0

    return [
        Scenario(
            name="temperate_default",
            description="Temperate lowland site with default parameters.",
            temp_c=_seasonal(n, 10.0, 6.0) + noise(1.5),
            precip_mm=precip(1.5, 12.0),
            biomass_gC_m2=biomass_seasonal,
            elevation_m=100.0,
            clay_pct=25.0,
        ),
        Scenario(
            name="cold_upland",
            description="Cold upland site with frozen winters.",
            temp_c=_seasonal(n, 3.0, 10.0) + noise(2.0),
            precip_mm=precip(2.0, 15.0),
            biomass_gC_m2=biomass_seasonal * 0.6,
            elevation_m=2500.0,
            clay_pct=30.0,
            requires={"frozen_weeks": lambda c: c["frozen_weeks"] > 50},
        ),
        Scenario(
            name="wet_clay",
            description="Very wet, clay-rich site whose bucket overflows.",
            temp_c=_seasonal(n, 8.0, 4.0) + noise(1.0),
            precip_mm=precip(3.0, 40.0),
            biomass_gC_m2=biomass_seasonal,
            elevation_m=50.0,
            clay_pct=70.0,
            requires={"overflow_weeks": lambda c: c["overflow_weeks"] > 20},
        ),
        Scenario(
            name="dry_sandy",
            description="Dry, sandy site with seasonal spells of zero biomass.",
            temp_c=_seasonal(n, 18.0, 8.0) + noise(1.5),
            precip_mm=precip(0.5, 6.0),
            biomass_gC_m2=dry_biomass,
            elevation_m=400.0,
            clay_pct=2.0,
            requires={
                "zero_biomass_weeks": lambda c: c["zero_biomass_weeks"] > 20,
                "near_empty_weeks": lambda c: c["near_empty_weeks"] > 20,
            },
        ),
        Scenario(
            name="clipped_high",
            description=(
                "Clay and elevation beyond their clip bounds, parameters at the "
                "upper corners of the calibration bounds."
            ),
            temp_c=_seasonal(n, 12.0, 8.0) + noise(1.5),
            precip_mm=precip(1.5, 20.0),
            biomass_gC_m2=biomass_seasonal,
            elevation_m=6000.0,
            clay_pct=95.0,
            params=PARAMS_HIGH,
            requires={
                "clay_clipped": lambda c: c["clay_clipped"],
                "elevation_multiplier_clipped": lambda c: c[
                    "elevation_multiplier_clipped"
                ],
                "capacity_clipped": lambda c: c["capacity_clipped"],
                "drainage_coeff_clipped": lambda c: c["drainage_coeff_clipped"],
                "runoff_fraction_max_clipped": lambda c: c[
                    "runoff_fraction_max_clipped"
                ],
            },
        ),
        Scenario(
            name="clipped_low",
            description=(
                "Low clay, parameters at the lower corners of the calibration bounds."
            ),
            temp_c=_seasonal(n, 12.0, 8.0) + noise(1.5),
            precip_mm=precip(1.5, 20.0),
            biomass_gC_m2=biomass_seasonal,
            elevation_m=0.0,
            clay_pct=0.0,
            params=PARAMS_LOW,
            requires={
                "capacity_clipped": lambda c: c["capacity_clipped"],
                "drainage_coeff_clipped": lambda c: c["drainage_coeff_clipped"],
                "runoff_fraction_max_clipped": lambda c: c[
                    "runoff_fraction_max_clipped"
                ],
            },
        ),
        Scenario(
            name="negative_inputs",
            description="Some negative precipitation and biomass, which are clamped.",
            temp_c=_seasonal(n, 10.0, 6.0) + noise(1.5),
            precip_mm=negative_precip,
            biomass_gC_m2=negative_biomass,
            elevation_m=100.0,
            clay_pct=25.0,
            requires={
                "negative_precip_weeks": lambda c: c["negative_precip_weeks"] > 0,
                "negative_biomass_weeks": lambda c: c["negative_biomass_weeks"] > 0,
            },
        ),
    ]


def load_legacy_module():
    """Import the legacy model module from git commit ``LEGACY_REF``."""
    source = subprocess.run(
        ["git", "show", f"{LEGACY_REF}:{LEGACY_PATH}"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    tmp = Path(tempfile.mkdtemp()) / "legacy_soil_moisture_model.py"
    tmp.write_text(source)
    spec = importlib.util.spec_from_file_location("legacy_soil_moisture_model", tmp)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_legacy(scenario: Scenario) -> dict[str, np.ndarray]:
    """Run the legacy model and return its outputs keyed by legacy column name."""
    import pandas as pd

    legacy = load_legacy_module()
    params = legacy.SoilWaterParams(**scenario.params)
    df = legacy.simulate_soil_water_balance(
        pd.DataFrame(
            {
                "temp_c": scenario.temp_c,
                "precip_mm": scenario.precip_mm,
                "biomass_gC_m2": scenario.biomass_gC_m2,
            }
        ),
        elevation_m=scenario.elevation_m,
        clay_pct=scenario.clay_pct,
        params=params,
    )
    out = {k: df[k].to_numpy() for k in TIME_SERIES_OUTPUTS}
    out.update({k: np.asarray(df[k].iloc[0]) for k in SITE_OUTPUTS})
    return out


def run_current(scenario: Scenario) -> dict[str, np.ndarray]:
    """Run the working-tree model and return outputs keyed by legacy column name."""
    sys.path.insert(0, str(REPO_ROOT / "tests"))
    from regression_adapter import run_scenario

    return run_scenario(scenario_inputs(scenario))


def scenario_inputs(scenario: Scenario) -> dict:
    """Return the inputs of a scenario as stored in its fixture."""
    return {
        "temp_c": scenario.temp_c,
        "precip_mm": scenario.precip_mm,
        "biomass_gC_m2": scenario.biomass_gC_m2,
        "elevation_m": scenario.elevation_m,
        "clay_pct": scenario.clay_pct,
        "params": dict(scenario.params),
    }


def coverage_counts(scenario: Scenario, out: dict[str, np.ndarray]) -> dict:
    """Count how often each branch of the model was exercised."""
    capacity = float(out["soil_water_capacity_mm"])
    initial = PARAMS_DEFAULT_INITIAL
    if "initial_soil_moisture_mm" in scenario.params:
        initial = scenario.params["initial_soil_moisture_mm"]
    s_prev = np.concatenate(
        [[np.clip(initial, 0.0, capacity)], out["soil_moisture_mm"][:-1]]
    )
    infiltration = out["throughfall_mm"] - out["runoff_mm"]

    p = {**PARAMS_DEFAULT, **scenario.params}
    clay = float(np.clip(scenario.clay_pct, 0.0, 80.0))
    dclay = (clay - p["reference_clay_pct"]) * p["clay_sensitivity"] / 100.0
    raw_capacity = p["base_soil_water_capacity_mm"] * (1.0 + dclay)
    raw_drainage = p["base_drainage_coeff"] * (1.0 - 0.5 * dclay)
    raw_runoff = p["base_runoff_fraction_max"] * (1.0 + 0.5 * dclay)
    raw_elev = 1.0 + 0.08 * scenario.elevation_m / 1000.0

    return {
        "frozen_weeks": int(np.sum(out["frozen_soil"])),
        "overflow_weeks": int(np.sum(s_prev + infiltration > capacity)),
        "zero_biomass_weeks": int(np.sum(scenario.biomass_gC_m2 <= 0.0)),
        "near_empty_weeks": int(np.sum(out["relative_soil_moisture"] < 0.05)),
        "negative_precip_weeks": int(np.sum(scenario.precip_mm < 0.0)),
        "negative_biomass_weeks": int(np.sum(scenario.biomass_gC_m2 < 0.0)),
        "clay_clipped": bool(clay != scenario.clay_pct),
        "elevation_multiplier_clipped": bool(not 0.75 <= raw_elev <= 1.35),
        "capacity_clipped": bool(not np.isclose(raw_capacity, capacity)),
        "drainage_coeff_clipped": bool(
            not np.isclose(raw_drainage, float(out["drainage_coeff"]))
        ),
        "runoff_fraction_max_clipped": bool(
            not np.isclose(raw_runoff, float(out["runoff_fraction_max"]))
        ),
    }


PARAMS_DEFAULT = {
    "initial_soil_moisture_mm": 50.0,
    "base_soil_water_capacity_mm": 160.0,
    "base_drainage_coeff": 0.10,
    "base_runoff_fraction_max": 0.45,
    "runoff_exponent": 2.0,
    "field_capacity_fraction": 0.70,
    "reference_clay_pct": 25.0,
    "clay_sensitivity": 0.04,
    "pet_coeff_mm_per_degday": 0.55,
    "biomass_half_sat_gC_m2": 150.0,
}
PARAMS_DEFAULT_INITIAL = PARAMS_DEFAULT["initial_soil_moisture_mm"]


def save_fixture(path: Path, scenario: Scenario, out: dict, meta: dict) -> None:
    """Write one scenario's inputs, outputs and metadata to an ``.npz`` file."""
    arrays = {
        "input__temp_c": scenario.temp_c,
        "input__precip_mm": scenario.precip_mm,
        "input__biomass_gC_m2": scenario.biomass_gC_m2,
        "input__elevation_m": np.asarray(scenario.elevation_m),
        "input__clay_pct": np.asarray(scenario.clay_pct),
        "meta": np.asarray(json.dumps(meta, indent=2, sort_keys=True)),
    }
    arrays.update({f"param__{k}": np.asarray(v) for k, v in scenario.params.items()})
    arrays.update({f"output__{k}": np.asarray(v) for k, v in out.items()})
    np.savez(path, **arrays)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare freshly generated outputs with the stored fixtures.",
    )
    parser.add_argument(
        "--fixed-by",
        metavar="REASON",
        help=(
            "Generate outputs from the working-tree model instead of the legacy "
            "commit, recording REASON (the fixing commit's subject) in the metadata."
        ),
    )
    args = parser.parse_args()

    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    failures = []
    for scenario in build_scenarios():
        out = run_current(scenario) if args.fixed_by else run_legacy(scenario)
        counts = coverage_counts(scenario, out)
        unmet = [k for k, ok in scenario.requires.items() if not ok(counts)]
        if unmet:
            failures.append(f"{scenario.name}: branch not exercised: {unmet}")

        path = FIXTURE_DIR / f"{scenario.name}.npz"
        if args.check:
            with np.load(path) as stored:
                for k, v in out.items():
                    if not np.array_equal(stored[f"output__{k}"], v):
                        failures.append(f"{scenario.name}: {k} differs from fixture")
            continue

        meta = {
            "scenario": scenario.name,
            "description": scenario.description,
            "source": (
                f"working tree ({args.fixed_by})"
                if args.fixed_by
                else f"legacy {LEGACY_REF}:{LEGACY_PATH}"
            ),
            "coverage": counts,
        }
        save_fixture(path, scenario, out, meta)
        print(f"wrote {path.relative_to(REPO_ROOT)}  {counts}")

    if failures:
        sys.exit("\n".join(failures))
    if args.check:
        print("all fixtures match")


if __name__ == "__main__":
    main()
