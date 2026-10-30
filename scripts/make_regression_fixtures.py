# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "soil_moisture_model",
#     "numpy>=2.4.2",
# ]
#
# [tool.uv.sources]
# soil_moisture_model = { path = "..", editable = true }
# ///
"""Generate (or check) the regression fixtures in tests/fixtures/regression/.

The fixtures pin the numerical behaviour of the model on a handful of synthetic
scenarios, each chosen to exercise a branch of the model that the others do not.
They are generated from the working tree, recording the subject of the commit
that changed the model's behaviour.

The first fixtures came from the original model at commit ``9d5b8fe``; once the
model's inputs and parameters diverged from it, that path was removed, and
``git log`` of this directory holds the history.

Usage
-----
    uv run scripts/make_regression_fixtures.py --fixed-by "<commit subject>"
    uv run scripts/make_regression_fixtures.py --check
"""

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "regression"
N_WEEKS = 520

# Parameter-space corners, taken from the calibration bounds. The initial soil
# moisture (mm) is not a parameter, but is varied with them.
PARAMS_HIGH = {
    "initial_soil_moisture": 250.0,
    "drainage_coefficient": 0.30,
    "max_runoff_fraction": 0.95,
    "runoff_exponent": 4.0,
    "rooting_depth": 3.0,
    "depletion_fraction": 0.8,
    "reference_et_coefficient": 0.5,
    "biomass_half_saturation": 800.0,
}
PARAMS_LOW = {
    "initial_soil_moisture": 5.0,
    "drainage_coefficient": 0.01,
    "max_runoff_fraction": 0.02,
    "runoff_exponent": 0.5,
    "rooting_depth": 0.2,
    "depletion_fraction": 0.1,
    "reference_et_coefficient": 0.05,
    "biomass_half_saturation": 20.0,
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
    sand: float
    clay: float
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
            sand=0.4,
            clay=0.2,
        ),
        Scenario(
            name="cold_upland",
            description="Cold upland site with frozen winters.",
            temp_c=_seasonal(n, 3.0, 10.0) + noise(2.0),
            precip_mm=precip(2.0, 15.0),
            biomass_gC_m2=biomass_seasonal * 0.6,
            elevation_m=2500.0,
            sand=0.35,
            clay=0.25,
            requires={"frozen_weeks": lambda c: c["frozen_weeks"] > 50},
        ),
        Scenario(
            name="wet_clay",
            description="Very wet, clay-rich site whose bucket overflows.",
            temp_c=_seasonal(n, 8.0, 4.0) + noise(1.0),
            precip_mm=precip(3.0, 40.0),
            biomass_gC_m2=biomass_seasonal,
            elevation_m=50.0,
            sand=0.15,
            clay=0.5,
            requires={"saturated_weeks": lambda c: c["saturated_weeks"] > 20},
        ),
        Scenario(
            name="dry_sandy",
            description="Dry, sandy site with seasonal spells of zero biomass.",
            temp_c=_seasonal(n, 18.0, 8.0) + noise(1.5),
            precip_mm=precip(0.5, 6.0),
            biomass_gC_m2=dry_biomass,
            elevation_m=400.0,
            sand=0.9,
            clay=0.03,
            requires={
                "zero_biomass_weeks": lambda c: c["zero_biomass_weeks"] > 20,
                "near_empty_weeks": lambda c: c["near_empty_weeks"] > 20,
            },
        ),
        Scenario(
            name="upper_corner",
            description=(
                "Clay-rich, high elevation, parameters at the upper corners of "
                "the calibration bounds."
            ),
            temp_c=_seasonal(n, 12.0, 8.0) + noise(1.5),
            precip_mm=precip(1.5, 20.0),
            biomass_gC_m2=biomass_seasonal,
            elevation_m=6000.0,
            sand=0.2,
            clay=0.45,
            params=PARAMS_HIGH,
        ),
        Scenario(
            name="lower_corner",
            description=(
                "Sandy, sea level, parameters at the lower corners of the "
                "calibration bounds."
            ),
            temp_c=_seasonal(n, 12.0, 8.0) + noise(1.5),
            precip_mm=precip(1.5, 20.0),
            biomass_gC_m2=biomass_seasonal,
            elevation_m=0.0,
            sand=0.9,
            clay=0.02,
            params=PARAMS_LOW,
        ),
        Scenario(
            name="negative_inputs",
            description="Some negative precipitation and biomass, which are clamped.",
            temp_c=_seasonal(n, 10.0, 6.0) + noise(1.5),
            precip_mm=negative_precip,
            biomass_gC_m2=negative_biomass,
            elevation_m=100.0,
            sand=0.4,
            clay=0.2,
            requires={
                "negative_precip_weeks": lambda c: c["negative_precip_weeks"] > 0,
                "negative_biomass_weeks": lambda c: c["negative_biomass_weeks"] > 0,
            },
        ),
    ]


def run_current(scenario: Scenario) -> dict[str, np.ndarray]:
    """Run the working-tree model and return its outputs."""
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
        "sand": scenario.sand,
        "clay": scenario.clay,
        "params": dict(scenario.params),
    }


def coverage_counts(scenario: Scenario, out: dict[str, np.ndarray]) -> dict:
    """Count how often each branch of the model was exercised."""
    capacity = float(out["soil.soil_water_capacity"])
    initial = scenario.params.get(
        "initial_soil_moisture", float(out["soil.field_capacity"])
    )
    s_prev = np.concatenate(
        [[np.clip(initial, 0.0, capacity)], out["soil_moisture"][:-1]]
    )
    infiltration = out["throughfall"] - out["runoff"]
    return {
        "frozen_weeks": int(np.sum(out["frozen"])),
        "saturated_weeks": int(np.sum(s_prev + infiltration >= capacity - 1e-9)),
        "zero_biomass_weeks": int(np.sum(scenario.biomass_gC_m2 <= 0.0)),
        "near_empty_weeks": int(np.sum(out["relative_soil_moisture"] < 0.05)),
        "negative_precip_weeks": int(np.sum(scenario.precip_mm < 0.0)),
        "negative_biomass_weeks": int(np.sum(scenario.biomass_gC_m2 < 0.0)),
    }


def save_fixture(path: Path, scenario: Scenario, out: dict, meta: dict) -> None:
    """Write one scenario's inputs, outputs and metadata to an ``.npz`` file."""
    arrays = {
        "input__temp_c": scenario.temp_c,
        "input__precip_mm": scenario.precip_mm,
        "input__biomass_gC_m2": scenario.biomass_gC_m2,
        "input__elevation_m": np.asarray(scenario.elevation_m),
        "input__sand": np.asarray(scenario.sand),
        "input__clay": np.asarray(scenario.clay),
        "meta": np.asarray(json.dumps(meta, indent=2, sort_keys=True)),
    }
    arrays.update({f"param__{k}": np.asarray(v) for k, v in scenario.params.items()})
    arrays.update({f"output__{k}": np.asarray(v) for k, v in out.items()})
    np.savez(path, **arrays)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check",
        action="store_true",
        help="Compare freshly generated outputs with the stored fixtures.",
    )
    mode.add_argument(
        "--fixed-by",
        metavar="REASON",
        help="Regenerate the fixtures, recording REASON (the commit subject).",
    )
    args = parser.parse_args()

    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    scenarios = build_scenarios()
    failures = []
    for scenario in scenarios:
        path = FIXTURE_DIR / f"{scenario.name}.npz"
        out = run_current(scenario)
        counts = coverage_counts(scenario, out)
        unmet = [k for k, ok in scenario.requires.items() if not ok(counts)]
        if unmet:
            failures.append(f"{scenario.name}: branch not exercised: {unmet}")

        if args.check:
            with np.load(path) as stored:
                stored_keys = {k for k in stored.files if k.startswith("output__")}
                if stored_keys != {f"output__{k}" for k in out}:
                    failures.append(f"{scenario.name}: outputs differ from fixture")
                for k, v in out.items():
                    key = f"output__{k}"
                    if key in stored and not np.array_equal(
                        stored[key], v, equal_nan=True
                    ):
                        failures.append(f"{scenario.name}: {k} differs from fixture")
            continue

        meta = {
            "scenario": scenario.name,
            "description": scenario.description,
            "source": f"working tree ({args.fixed_by})",
            "coverage": counts,
        }
        save_fixture(path, scenario, out, meta)
        print(f"wrote {path.relative_to(REPO_ROOT)}  {counts}")

    names = {f"{s.name}.npz" for s in scenarios}
    stale = sorted(p.name for p in FIXTURE_DIR.glob("*.npz") if p.name not in names)
    if stale:
        failures.append(f"fixtures with no scenario: {stale}")

    if failures:
        sys.exit("\n".join(failures))
    if args.check:
        print("all fixtures match")


if __name__ == "__main__":
    main()
