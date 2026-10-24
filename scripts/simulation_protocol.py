"""The standard simulation protocol, shared by the record runs (simulate-parameter-sets.py) and the
PyBaMM version benchmark (benchmark_runner.py), so both apply exactly the same procedure.

Every parameter file gets the same runs, whether or not it carries measured data:

- standard runs: constant-current discharges at STANDARD_C_RATES of the file's own nominal
  capacity, from the initial state the file declares, at the file's own ambient temperature,
  to the file's own lower cut-off voltage;
- the model the file's header names (SPM, SPMe or DFN; DFN when the header names none);
- a lumped thermal model only when the file carries the thermal properties it needs.

When the file itself carries measured data (its BPX ``Validation`` section, and nothing from
elsewhere), each measured discharge is also replayed with its own current, and the two curves
are compared over the time both cover. Standard runs above the highest measured rate are marked
as beyond the measured range.
"""
from __future__ import annotations

import json
import re

import numpy as np
import pybamm

STANDARD_C_RATES = (0.05, 0.1, 0.2, 0.5, 1.0, 2.0)
DEFAULT_MODEL = "DFN"
MODELS = {"SPM": "SPM", "SPME": "SPMe", "DFN": "DFN", "P2D": "DFN"}
CONSTANT_CURRENT_TOLERANCE = 0.02  # relative spread below which a measured current counts as constant
MAX_REPLAY_POINTS = 5000  # a measured current profile is resampled to at most this many points
MESH_DOMAINS = ("x_n", "x_s", "x_p", "r_n", "r_p")


def model_choice(bpx: dict) -> tuple[str, str]:
    """The PyBaMM model the file says it was made for, and where that came from."""
    declared = str((bpx.get("Header") or {}).get("Model") or "").strip()
    model = MODELS.get(declared.upper())
    if model:
        return model, "the file's header"
    if declared:
        return DEFAULT_MODEL, f"the file names a model PyBaMM does not have ({declared}); {DEFAULT_MODEL} used"
    return DEFAULT_MODEL, f"the file names no model; {DEFAULT_MODEL} used"


def model_options(bpx: dict) -> dict:
    """Particle phases from the file, as in ingest-bpx-file.py's smoke run."""
    params = bpx.get("Parameterisation", {})
    phases = tuple(
        str(len(params.get(block, {}).get("Particle") or {}) or 1)
        for block in ("Negative electrode", "Positive electrode")
    )
    return {"particle phases": phases} if phases != ("1", "1") else {}


def declared_initial_soc(bpx: dict) -> float | None:
    """The initial state of charge the file declares (BPX 1.x State, older Cell), or None."""
    state = (bpx.get("State") or {}).get("Initial conditions") or {}
    cell = (bpx.get("Parameterisation") or {}).get("Cell") or {}
    for value in (state.get("Initial state-of-charge"), cell.get("Initial state-of-charge")):
        if isinstance(value, (int, float)):
            return float(value)
    return None


def parameter_values(raw: bytes) -> pybamm.ParameterValues:
    """The file's parameters as PyBaMM reads them, initial state and temperatures included."""
    return pybamm.ParameterValues.create_from_bpx_obj(json.loads(raw))  # it rewrites the dict it gets


def model_for(name: str, options: dict, thermal: bool):
    return getattr(pybamm.lithium_ion, name)({**options, "thermal": "lumped"} if thermal else dict(options))


def thermal_support(raw: bytes, model: str, options: dict) -> tuple[bool, str]:
    """Whether PyBaMM's lumped thermal model runs on the file's own properties."""
    try:
        sim = pybamm.Simulation(model_for(model, options, True), parameter_values=parameter_values(raw),
                                experiment=pybamm.Experiment(["Rest for 10 seconds"]))
        sim.solve()
    except KeyError as exc:
        missing = re.search(r"Parameter '([^']+)'", str(exc))
        needed = f" (PyBaMM's lumped thermal model needs '{missing.group(1)}')" if missing else ""
        return False, f"The runs are isothermal: the file carries no thermal properties{needed}."
    except Exception as exc:  # noqa: BLE001
        return False, f"The runs are isothermal: the lumped thermal model did not run on this file ({type(exc).__name__})."
    return True, "Lumped thermal model, with the thermal properties given in the file."


def measured_cases(bpx: dict) -> list[dict]:
    """The measured discharges in the file's own Validation section."""
    cases = []
    for key, data in (bpx.get("Validation") or {}).items():
        try:
            t = np.asarray(data["Time [s]"], dtype=float)
            current = np.asarray(data["Current [A]"], dtype=float)
            voltage = np.asarray(data["Voltage [V]"], dtype=float)
        except (KeyError, TypeError, ValueError):
            continue
        if len(t) < 2 or not (len(t) == len(current) == len(voltage)):
            continue
        t = t - t[0]
        mean = float(np.mean(current))
        constant = mean > 0 and float(np.ptp(current)) <= CONSTANT_CURRENT_TOLERANCE * abs(mean)
        capacity = np.concatenate([[0.0], np.cumsum(np.diff(t) * (current[1:] + current[:-1]) / 2)]) / 3600
        cases.append({
            "key": key, "constant": constant, "current_A": mean if constant else None,
            "peak_current_A": float(np.max(np.abs(current))),
            "t": t, "current": current, "voltage": voltage, "capacity": capacity,
        })
    return cases


def slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower() or "case"


def run_specs(bpx: dict, nominal: float, cases: list[dict]) -> list[dict]:
    """Standard runs for every file, then one replay per measured discharge the file carries."""
    max_measured = max((c["peak_current_A"] / nominal for c in cases), default=None)
    specs = []
    for rate in STANDARD_C_RATES:
        specs.append({
            "id": f"standard_{rate:g}C", "kind": "standard", "c_rate": rate,
            "current_A": round(rate * nominal, 6), "protocol": f"constant-current discharge at {rate:g}C",
            "beyond_measured_range": None if max_measured is None else bool(rate > max_measured * 1.001),
        })
    for case in cases:
        if case["constant"]:
            specs.append({
                "id": f"measured_{slug(case['key'])}", "kind": "measured_replay", "case": case["key"],
                "c_rate": round(case["current_A"] / nominal, 4), "current_A": round(case["current_A"], 6),
                "protocol": "constant-current discharge at the measured mean current",
            })
        else:
            points = min(len(case["t"]), MAX_REPLAY_POINTS)
            specs.append({
                "id": f"measured_{slug(case['key'])}", "kind": "measured_replay", "case": case["key"],
                "c_rate": None, "current_A": None,
                "protocol": f"the measured current profile ({points} points)",
            })
    return specs


def replay_profile(case: dict) -> np.ndarray:
    """(time, current) for a measured current profile, resampled when it has too many points."""
    t, current = case["t"], case["current"]
    if len(t) > MAX_REPLAY_POINTS:
        grid = np.linspace(t[0], t[-1], MAX_REPLAY_POINTS)
        current = np.interp(grid, t, current)
        t = grid
    return np.column_stack([t, current])


def solve(raw: bytes, spec: dict, model: str, options: dict, thermal: bool, lower_cutoff: float,
          case: dict | None = None):
    """One run of the protocol; returns (simulation, solution)."""
    if spec["current_A"] is not None:
        step = f"Discharge at {spec['current_A']:.6g} A until {lower_cutoff:.6g} V"
    else:
        # A current profile has no single direction, so the cut-off needs its operator spelled out.
        step = pybamm.step.current(replay_profile(case), termination=f"< {lower_cutoff:.6g} V")
    sim = pybamm.Simulation(model_for(model, options, thermal), parameter_values=parameter_values(raw),
                            experiment=pybamm.Experiment([step]))
    return sim, sim.solve()


def mesh_and_solver(sim) -> dict:
    points = {getattr(k, "name", str(k)): int(v) for k, v in (getattr(sim, "var_pts", None) or {}).items()}
    return {
        "mesh_points": {name: points[name] for name in MESH_DOMAINS if name in points},
        "solver": type(sim.solver).__name__,
        "solver_rtol": getattr(sim.solver, "rtol", None),
        "solver_atol": getattr(sim.solver, "atol", None),
    }


def agreement(case: dict, t_sim, voltage_sim, capacity_sim) -> dict:
    """Voltage difference over the time both curves cover, and the capacity difference at the end."""
    t, voltage = case["t"], case["voltage"]
    covered = t <= t_sim[-1]
    if covered.sum() < 2:
        return {"compared_points": int(covered.sum())}
    difference = np.interp(t[covered], t_sim, voltage_sim) - voltage[covered]
    measured_end = float(case["capacity"][-1])
    return {
        "rmse_mV": round(float(np.sqrt(np.mean(difference ** 2))) * 1000, 1),
        "max_abs_difference_mV": round(float(np.max(np.abs(difference))) * 1000, 1),
        "capacity_difference_percent": (
            round((float(capacity_sim[-1]) - measured_end) / measured_end * 100, 2) if measured_end else None
        ),
        "measured_time_covered_percent": round(min(1.0, float(t_sim[-1]) / float(t[-1])) * 100, 1),
        "compared_points": int(covered.sum()),
    }
