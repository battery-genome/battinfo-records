#!/usr/bin/env python3
"""Precompute PyBaMM simulations for every parameter-set record with a runnable BPX file.

For each record under ``records/parameter-set/`` whose BPX file passed its
``simulation_smoke`` check (the ``runnable`` conversion when there is one,
otherwise the ``source``), the script downloads the file, checks its sha256,
and runs the DFN model:

- at each measured discharge in the file's ``Validation`` section, so the page
  can show the fit;
- on a grid of C-rates, up to the highest measured rate, and ambient
  temperatures: 10, 25 and 40 degC when the file carries activation energies,
  the file's own ambient temperature otherwise.

A thermal model runs only when the file carries the thermal properties it
needs. Nothing is assumed: otherwise the runs are isothermal and the summary
says why.

Output is one run set per file, in a write-once layout:

    simulations/runs/<parameters_sha256>/pybamm-<version>/g<generator>/
        summary.json            voltage curves, measured curves, fit
        <run>/manifest.json     variable names, units, shapes, coordinates
        <run>/profiles.f32      through-cell profiles and scalars
        <run>/particles.f32     concentration inside the particles
    simulations/indexes/<stamp>.json    every current run set, with sha256
    simulations/latest.json             points at the newest index

Arrays are little-endian float32, row-major, time first, so a browser reads
them with ``new Float32Array(buffer, offset, length)`` and numpy with
``np.frombuffer(..., "<f4")``. Run-set files carry no timestamps or timings,
so the same input gives the same summary.

``--out`` writes the tree locally. ``--upload`` also copies it to the bucket
named by R2_BUCKET (credentials R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY,
R2_ENDPOINT): run-set files are never overwritten (existing keys are skipped),
nothing outside ``simulations/`` is ever written, and a new index plus
``latest.json`` are written only when the set of run sets changed.

    uv run --no-project --with "pybamm[bpx]==26.10.1.1" --with boto3 \\
        python scripts/simulate-parameter-sets.py --out ../sim-out [--upload]
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np
import pybamm

REPO = Path(__file__).resolve().parent.parent
PARAMETER_SET_DIR = REPO / "records" / "parameter-set"
PREFIX = "simulations"
GENERATOR_VERSION = 1
USER_AGENT = "battinfo-records-simulations/1.0"  # the artifact host refuses Python's default
MODEL = "DFN"
CURVE_POINTS = 200
GRID_C_RATES = (0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 3.0, 5.0)
GRID_TEMPERATURES_C = (10.0, 25.0, 40.0)
MAX_C_RATE_WITHOUT_MEASUREMENTS = 1.0
CONSTANT_CURRENT_TOLERANCE = 0.02  # relative spread below which a measured current counts as constant
SAME_CURRENT_TOLERANCE = 0.005  # a measured discharge this close to a grid current reuses the grid run

# Through-cell profiles and scalars, (PyBaMM variable, coordinate). Temperature only for thermal runs.
PROFILE_VARIABLES = (
    ("Electrolyte concentration [mol.m-3]", "x"),
    ("Electrolyte potential [V]", "x"),
    ("Negative electrode potential [V]", "x_n"),
    ("Positive electrode potential [V]", "x_p"),
    ("Negative particle surface concentration [mol.m-3]", "x_n"),
    ("Positive particle surface concentration [mol.m-3]", "x_p"),
    ("Cell temperature [K]", "x"),
    ("Voltage [V]", None),
    ("Current [A]", None),
    ("Volume-averaged cell temperature [K]", None),
)
THERMAL_ONLY = {"Cell temperature [K]", "Volume-averaged cell temperature [K]"}
# Concentration inside the particles, (PyBaMM variable, radial coordinate, through-cell coordinate).
PARTICLE_VARIABLES = (
    ("Negative particle concentration [mol.m-3]", "r_n", "x_n"),
    ("Positive particle concentration [mol.m-3]", "r_p", "x_p"),
)
COORDINATES = {"x": "x [m]", "x_n": "x_n [m]", "x_p": "x_p [m]", "r_n": "r_n [m]", "r_p": "r_p [m]"}


def rounded(values, digits: int) -> list[float]:
    return [round(float(v), digits) for v in np.asarray(values).ravel()]


def sample(n: int, points: int = CURVE_POINTS) -> np.ndarray:
    """Indices of at most ``points`` samples, first and last included."""
    return np.unique(np.linspace(0, n - 1, min(points, n)).round().astype(int))


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dumps(obj) -> bytes:
    return (json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def split_unit(name: str) -> tuple[str, str]:
    match = re.match(r"^(.*?)\s*\[(.*)\]$", name)
    return (match.group(1), match.group(2)) if match else (name, "")


# ---- selecting and fetching files --------------------------------------------------------------


def runnable_distribution(body: dict) -> dict | None:
    """The file to simulate: the runnable conversion if present, else the source, with a passing smoke run."""
    for role in ("runnable", "source"):
        for dist in body.get("distributions") or []:
            if dist.get("role") != role:
                continue
            checks = [c for c in dist.get("checks") or [] if c.get("check") == "simulation_smoke"]
            if any(c.get("passed") for c in checks):
                return dist
    return None


def find_records(only: str | None) -> list[tuple[str, dict, dict]]:
    found = []
    for path in sorted(PARAMETER_SET_DIR.glob("*/record.json")):
        if only and not fnmatch.fnmatch(path.parent.name, only):
            continue
        body = json.loads(path.read_text(encoding="utf-8")).get("parameter_set") or {}
        if not body.get("distributions"):
            continue  # claim batches carry no file
        dist = runnable_distribution(body)
        if dist is None:
            print(f"skip {path.parent.name}: no file with a passing simulation_smoke check")
            continue
        found.append((path.parent.name, body, dist))
    return found


def fetch(dist: dict, cache_dir: Path) -> bytes:
    checksum = dist.get("checksum") or {}
    if checksum.get("algorithm") != "sha256" or not checksum.get("value"):
        raise ValueError(f"{dist.get('name')}: no sha256 checksum on the distribution")
    expected = checksum["value"]
    cached = cache_dir / f"{expected}.json"
    if cached.exists() and sha256(cached.read_bytes()) == expected:
        return cached.read_bytes()
    with urlopen(Request(dist["content_url"], headers={"User-Agent": USER_AGENT}), timeout=300) as response:
        data = response.read()
    if sha256(data) != expected:
        raise ValueError(f"{dist['content_url']}: sha256 {sha256(data)} does not match the record's {expected}")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(data)
    return data


# ---- reading the file ----------------------------------------------------------------------------


def model_options(bpx: dict) -> dict:
    """Particle phases from the file, as in ingest-bpx-file.py's smoke run."""
    params = bpx.get("Parameterisation", {})
    phases = tuple(
        str(len(params.get(block, {}).get("Particle") or {}) or 1)
        for block in ("Negative electrode", "Positive electrode")
    )
    return {"particle phases": phases} if phases != ("1", "1") else {}


def has_activation_energies(node) -> bool:
    if isinstance(node, dict):
        return any("activation energy" in str(k).lower() or has_activation_energies(v) for k, v in node.items())
    return False


def parameter_values(raw: bytes, temperature_c: float | None = None) -> pybamm.ParameterValues:
    values = pybamm.ParameterValues.create_from_bpx_obj(json.loads(raw))  # it rewrites the dict it gets
    if temperature_c is not None:
        kelvin = 273.15 + temperature_c
        values.update({"Ambient temperature [K]": kelvin, "Initial temperature [K]": kelvin})
    return values


def thermal_support(raw: bytes, options: dict) -> tuple[bool, str]:
    """Whether PyBaMM's lumped thermal model runs on the file's own properties."""
    try:
        sim = pybamm.Simulation(
            pybamm.lithium_ion.DFN({**options, "thermal": "lumped"}),
            parameter_values=parameter_values(raw),
            experiment=pybamm.Experiment(["Rest for 10 seconds"]),
        )
        sim.solve()
    except KeyError as exc:
        missing = re.search(r"Parameter '([^']+)'", str(exc))
        needed = f" (PyBaMM's lumped thermal model needs '{missing.group(1)}')" if missing else ""
        return False, f"The runs are isothermal: the file carries no thermal properties{needed}."
    except Exception as exc:  # noqa: BLE001
        return False, f"The runs are isothermal: the lumped thermal model did not run on this file ({type(exc).__name__})."
    return True, "Lumped thermal model, with the thermal properties given in the file."


def measured_cases(bpx: dict) -> list[dict]:
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
            "t": t, "current": current, "voltage": voltage, "capacity": capacity,
        })
    return cases


# ---- running -----------------------------------------------------------------------------------


def run_id(current_a: float | None, temperature_c: float, measured_key: str | None = None) -> str:
    if current_a is not None:
        return f"cc_{current_a:.6g}A_{temperature_c:g}C"
    slug = re.sub(r"[^A-Za-z0-9]+", "-", measured_key or "profile").strip("-").lower()
    return f"measured_{slug}_{temperature_c:g}C"


def simulate(raw: bytes, options: dict, thermal: bool, lower_cutoff: float, temperature_c: float,
             current_a: float | None = None, profile: tuple[np.ndarray, np.ndarray] | None = None):
    model = pybamm.lithium_ion.DFN({**options, "thermal": "lumped"} if thermal else dict(options))
    if profile is not None:
        t, current = profile
        step = pybamm.step.current(np.column_stack([t, current]), termination=f"{lower_cutoff:.6g} V")
    else:
        step = f"Discharge at {current_a:.6g} A until {lower_cutoff:.6g} V"
    sim = pybamm.Simulation(model, parameter_values=parameter_values(raw, temperature_c),
                            experiment=pybamm.Experiment([step]))
    return sim, sim.solve()


def curve(t, capacity, voltage) -> dict:
    idx = sample(len(t))
    return {
        "time_s": rounded(np.asarray(t)[idx], 1),
        "capacity_Ah": rounded(np.asarray(capacity)[idx], 6),
        "voltage_V": rounded(np.asarray(voltage)[idx], 5),
    }


def fit(case: dict, t_sim, voltage_sim, capacity_sim) -> dict:
    """Voltage error over the time both curves cover, and the capacity difference at the end."""
    t, voltage = case["t"], case["voltage"]
    covered = t <= t_sim[-1]
    if covered.sum() < 2:
        return {"compared_points": int(covered.sum())}
    error = np.interp(t[covered], t_sim, voltage_sim) - voltage[covered]
    measured_end = float(case["capacity"][-1])
    return {
        "rmse_mV": round(float(np.sqrt(np.mean(error ** 2))) * 1000, 1),
        "max_abs_error_mV": round(float(np.max(np.abs(error))) * 1000, 1),
        "capacity_error_percent": (
            round((float(capacity_sim[-1]) - measured_end) / measured_end * 100, 2) if measured_end else None
        ),
        "measured_time_covered_percent": round(min(1.0, float(t_sim[-1]) / float(t[-1])) * 100, 1),
        "compared_points": int(covered.sum()),
    }


def write_arrays(path: Path, arrays: list[tuple[str, str | tuple, np.ndarray]]) -> tuple[list[dict], str]:
    """Concatenate float32 arrays into one file; return their layout and the file's sha256."""
    layout, chunks, offset = [], [], 0
    for name, domain, array in arrays:
        data = np.ascontiguousarray(array, dtype="<f4")
        label, unit = split_unit(name)
        layout.append({
            "name": name, "label": label, "unit": unit, "domain": domain,
            "shape": list(data.shape), "offset_bytes": offset, "length": int(data.size),
        })
        chunks.append(data.tobytes())
        offset += data.nbytes
    blob = b"".join(chunks)
    path.write_bytes(blob)
    return layout, sha256(blob)


def write_profiles(solution, run_dir: Path, thermal: bool) -> dict:
    run_dir.mkdir(parents=True, exist_ok=True)
    time_s = np.asarray(solution["Time [s]"].entries)
    coordinates = {"time_s": rounded(time_s, 3)}
    for key, variable in COORDINATES.items():
        entries = np.asarray(solution[variable].entries)
        first = entries[:, 0] if entries.ndim == 2 else entries[:, 0, 0]
        coordinates[f"{key}_m"] = [float(f"{v:.6g}") for v in first]

    unavailable, profile_arrays, particle_arrays = [], [], []
    for name, domain in PROFILE_VARIABLES:
        if name in THERMAL_ONLY and not thermal:
            continue
        try:
            entries = np.asarray(solution[name].entries)
        except KeyError:
            unavailable.append(name)
            continue
        profile_arrays.append((name, domain, entries.T if domain else entries))  # (time, x) or (time,)
    for name, radial, through in PARTICLE_VARIABLES:
        try:
            entries = np.asarray(solution[name].entries)  # (r, x, time)
        except KeyError:
            unavailable.append(name)
            continue
        particle_arrays.append((name, [through, radial], entries.transpose(2, 1, 0)))  # (time, x, r)

    files = {}
    for filename, arrays in (("profiles.f32", profile_arrays), ("particles.f32", particle_arrays)):
        if not arrays:
            continue
        layout, digest = write_arrays(run_dir / filename, arrays)
        files[filename] = {"sha256": digest, "variables": layout}
    manifest = {
        "dtype": "float32", "byte_order": "little", "layout": "row-major, time first",
        "time_points": int(len(time_s)), "coordinates": coordinates, "files": files,
        "unavailable": unavailable,
    }
    (run_dir / "manifest.json").write_bytes(dumps(manifest))
    return manifest


def simulate_file(folder: str, body: dict, dist: dict, raw: bytes, out_root: Path) -> dict:
    bpx = json.loads(raw)
    cell = bpx.get("Parameterisation", {}).get("Cell", {})
    nominal = float(cell["Nominal cell capacity [A.h]"])
    lower, upper = float(cell["Lower voltage cut-off [V]"]), float(cell["Upper voltage cut-off [V]"])
    options = model_options(bpx)
    thermal, thermal_note = thermal_support(raw, options)
    ambient_c = round(float(parameter_values(raw)["Ambient temperature [K]"]) - 273.15, 2)

    cases = measured_cases(bpx)
    measured_rates = [c["current_A"] / nominal for c in cases if c["constant"]]
    max_rate = max(measured_rates) if measured_rates else MAX_C_RATE_WITHOUT_MEASUREMENTS
    c_rates = [c for c in GRID_C_RATES if c <= max_rate * 1.001]
    temperature_axis = has_activation_energies(bpx.get("Parameterisation", {}))
    temperatures = list(GRID_TEMPERATURES_C) if temperature_axis else [ambient_c]

    # Every run once: a measured constant-current discharge at the grid's current and temperature is the same run.
    specs: dict[str, dict] = {}
    for temperature in temperatures:
        for c_rate in c_rates:
            current = round(c_rate * nominal, 6)
            specs.setdefault(run_id(current, temperature), {
                "current_A": current, "temperature_C": temperature, "protocol": "constant current discharge"})
    for case in cases:
        if case["constant"]:
            current = round(case["current_A"], 6)
            same = [rid for rid, spec in specs.items()
                    if spec["temperature_C"] == ambient_c and spec["current_A"] is not None
                    and abs(spec["current_A"] - current) <= SAME_CURRENT_TOLERANCE * current]
            case["run"] = same[0] if same else run_id(current, ambient_c)
            specs.setdefault(case["run"], {
                "current_A": current, "temperature_C": ambient_c, "protocol": "constant current discharge"})
        else:
            case["run"] = run_id(None, ambient_c, case["key"])
            specs[case["run"]] = {"current_A": None, "temperature_C": ambient_c,
                                  "protocol": "measured current profile", "case": case["key"]}

    run_set = f"{PREFIX}/runs/{body['parameters_sha256']}/pybamm-{pybamm.__version__}/g{GENERATOR_VERSION}"
    run_set_dir = out_root / run_set
    runs, solutions, solver = [], {}, None
    for rid in sorted(specs):
        spec = specs[rid]
        entry = {"id": rid, **spec, "c_rate": round(spec["current_A"] / nominal, 4) if spec["current_A"] else None}
        try:
            if spec["current_A"] is not None:
                sim, solution = simulate(raw, options, thermal, lower, spec["temperature_C"], current_a=spec["current_A"])
            else:
                case = next(c for c in cases if c["key"] == spec["case"])
                sim, solution = simulate(raw, options, thermal, lower, spec["temperature_C"],
                                         profile=(case["t"], case["current"]))
        except Exception as exc:  # noqa: BLE001 - a failed run is a result, not a crash
            entry.update(status="failed", error=f"{type(exc).__name__}: {str(exc).splitlines()[0][:300]}")
            print(f"  {rid}: failed ({entry['error']})")
            runs.append(entry)
            continue
        solver = solver or type(sim.solver).__name__
        t = np.asarray(solution["Time [s]"].entries)
        capacity = np.asarray(solution["Discharge capacity [A.h]"].entries)
        voltage = np.asarray(solution["Voltage [V]"].entries)
        solutions[rid] = (t, capacity, voltage)
        # PyBaMM reports discharge energy only when asked to; integrate V*I here instead.
        power = voltage * np.asarray(solution["Current [A]"].entries)
        energy = round(float(np.sum(np.diff(t) * (power[1:] + power[:-1]) / 2)) / 3600, 5)
        manifest = write_profiles(solution, run_set_dir / rid, thermal)
        entry.update(
            status="ok", curve=curve(t, capacity, voltage),
            end={"capacity_Ah": round(float(capacity[-1]), 6), "energy_Wh": energy,
                 "duration_s": round(float(t[-1]), 1), "voltage_V": round(float(voltage[-1]), 5)},
            profiles={"manifest": f"{run_set}/{rid}/manifest.json",
                      "manifest_sha256": sha256((run_set_dir / rid / "manifest.json").read_bytes()),
                      "files": {name: f"{run_set}/{rid}/{name}" for name in manifest["files"]},
                      "time_points": manifest["time_points"]},
        )
        print(f"  {rid}: {entry['end']['capacity_Ah']:.4f} Ah, {manifest['time_points']} time points")
        runs.append(entry)

    measured = []
    for case in cases:
        item = {"key": case["key"], "run": case["run"], "constant_current": case["constant"],
                "current_A": round(case["current_A"], 6) if case["current_A"] else None,
                "temperature_C": ambient_c, "curve": curve(case["t"], case["capacity"], case["voltage"])}
        if case["run"] in solutions:
            t, capacity, voltage = solutions[case["run"]]
            item["fit"] = fit(case, t, voltage, capacity)
        measured.append(item)

    summary = {
        "generator": {"name": "battinfo-records/scripts/simulate-parameter-sets.py", "version": GENERATOR_VERSION},
        "parameter_set": {
            "iri": body["id"], "name": body.get("name"), "record": folder,
            "parameters_sha256": body["parameters_sha256"],
            "file": {"name": dist.get("name"), "role": dist.get("role"), "content_url": dist["content_url"],
                     "sha256": dist["checksum"]["value"], "conforms_to": dist.get("conforms_to")},
        },
        "engine": {"name": "PyBaMM", "version": pybamm.__version__, "model": MODEL, "options": options,
                   "solver": solver, "thermal": "lumped" if thermal else "isothermal", "thermal_note": thermal_note},
        "cell": {"nominal_capacity_Ah": nominal, "lower_cutoff_V": lower, "upper_cutoff_V": upper,
                 "ambient_temperature_C": ambient_c},
        "grid": {
            "c_rates": c_rates, "temperatures_C": temperatures,
            "c_rate_note": (f"Rates go up to the highest measured one ({max_rate:.3g}C)." if measured_rates
                            else f"The file has no measured discharges, so rates stop at "
                                 f"{MAX_C_RATE_WITHOUT_MEASUREMENTS:g}C."),
            "temperature_note": ("The file carries activation energies, so ambient temperature changes the result."
                                 if temperature_axis else
                                 "The file carries no activation energies, so only its own ambient temperature "
                                 "is simulated."),
        },
        "measured": measured,
        "runs": runs,
    }
    (run_set_dir / "summary.json").write_bytes(dumps(summary))
    return {"iri": body["id"], "name": body.get("name"), "record": folder,
            "parameters_sha256": body["parameters_sha256"], "pybamm": pybamm.__version__,
            "generator": GENERATOR_VERSION, "summary": f"{run_set}/summary.json",
            "summary_sha256": sha256((run_set_dir / "summary.json").read_bytes())}


# ---- uploading ----------------------------------------------------------------------------------


def content_type(key: str) -> str:
    return "application/json" if key.endswith(".json") else "application/octet-stream"


def upload(out_root: Path, run_set_entries: list[dict], index_key: str) -> None:
    import boto3
    from botocore.exceptions import ClientError

    missing = [k for k in ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ENDPOINT", "R2_BUCKET") if not os.environ.get(k)]
    if missing:
        raise SystemExit(f"--upload needs {', '.join(missing)}")
    bucket = os.environ["R2_BUCKET"]
    s3 = boto3.client("s3", endpoint_url=os.environ["R2_ENDPOINT"], region_name="auto",
                      aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                      aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"])

    def put(key: str, body: bytes, cache_control: str) -> None:
        if not key.startswith(f"{PREFIX}/"):  # this key can write the whole bucket; never leave the prefix
            raise SystemExit(f"refusing to write outside {PREFIX}/: {key}")
        s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType=content_type(key),
                      CacheControl=cache_control, Metadata={"sha256": sha256(body)})

    def exists(key: str) -> bool:
        try:
            s3.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                return False
            raise

    written = skipped = 0
    for entry in run_set_entries:
        run_set_dir = out_root / Path(entry["summary"]).parent
        for path in sorted(p for p in run_set_dir.rglob("*") if p.is_file()):
            key = path.relative_to(out_root).as_posix()
            if exists(key):
                skipped += 1
                continue
            put(key, path.read_bytes(), "public, max-age=31536000, immutable")
            written += 1
    print(f"run-set files: {written} written, {skipped} already there")

    def listing(index: dict) -> list:
        return sorted((r["summary"], r["summary_sha256"]) for r in index.get("run_sets", []))

    new_index = json.loads((out_root / index_key).read_text(encoding="utf-8"))
    try:
        latest = json.loads(s3.get_object(Bucket=bucket, Key=f"{PREFIX}/latest.json")["Body"].read())
        current = json.loads(s3.get_object(Bucket=bucket, Key=latest["index"])["Body"].read())
        if listing(current) == listing(new_index):
            print(f"unchanged: {PREFIX}/latest.json still points at {latest['index']}")
            return
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in ("404", "NoSuchKey", "NotFound"):
            raise
    put(index_key, (out_root / index_key).read_bytes(), "public, max-age=31536000, immutable")
    put(f"{PREFIX}/latest.json", (out_root / PREFIX / "latest.json").read_bytes(), "no-cache")
    print(f"{PREFIX}/latest.json now points at {index_key}")


# ---- main ---------------------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, required=True, help="local folder for the output tree")
    parser.add_argument("--only", help="glob on record folder names, e.g. 'schmitt*'")
    parser.add_argument("--cache-dir", type=Path, default=None, help="downloaded BPX files (default <out>/_cache)")
    parser.add_argument("--stamp", default=None,
                        help="index name, e.g. <date>-<workflow run id> (default <UTC date>-local)")
    parser.add_argument("--upload", action="store_true", help="also copy the tree to the bucket in R2_BUCKET")
    args = parser.parse_args()

    out_root = args.out.resolve()
    cache_dir = (args.cache_dir or out_root / "_cache").resolve()
    stamp = args.stamp or f"{datetime.now(timezone.utc):%Y-%m-%d}-local"
    if not re.fullmatch(r"[A-Za-z0-9._-]+", stamp):
        raise SystemExit(f"--stamp may only contain letters, digits, '.', '_' and '-': {stamp}")

    records = find_records(args.only)
    print(f"PyBaMM {pybamm.__version__}, {len(records)} file(s) to simulate")
    entries, failures = [], 0
    for folder, body, dist in records:
        print(f"{folder}: {dist['name']} ({dist['role']})")
        try:
            raw = fetch(dist, cache_dir)
            entries.append(simulate_file(folder, body, dist, raw, out_root))
        except Exception as exc:  # noqa: BLE001 - one bad file must not stop the others
            failures += 1
            print(f"  FAILED: {type(exc).__name__}: {exc}")

    index_key = f"{PREFIX}/indexes/{stamp}.json"
    index = {"generated": stamp, "generator_version": GENERATOR_VERSION,
             "run_sets": sorted(entries, key=lambda e: e["summary"]), "benchmark": None}
    (out_root / index_key).parent.mkdir(parents=True, exist_ok=True)
    (out_root / index_key).write_bytes(dumps(index))
    (out_root / PREFIX / "latest.json").write_bytes(
        dumps({"index": index_key, "index_sha256": sha256((out_root / index_key).read_bytes())}))
    print(f"wrote {len(entries)} run set(s) and {index_key} under {out_root}")

    if args.upload:
        upload(out_root, entries, index_key)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
