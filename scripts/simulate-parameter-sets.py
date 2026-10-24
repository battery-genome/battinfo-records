#!/usr/bin/env python3
"""Precompute PyBaMM simulations for every parameter-set record with a runnable BPX file.

For each record under ``records/parameter-set/`` whose BPX file passed its
``simulation_smoke`` check (the ``runnable`` conversion when there is one,
otherwise the ``source``), the script downloads the file, checks its sha256,
and applies the standard protocol in ``simulation_protocol.py``: the same
constant-current discharges for every file, with the model, initial state,
ambient temperature and cut-off the file itself states. When the file carries
measured discharges (its own ``Validation`` section), each is also replayed
with its own current and compared.

Output is one run set per file, in a write-once layout:

    simulations/runs/<parameters_sha256>/pybamm-<version>/g<generator>/
        summary.json            voltage curves, measured curves, agreement
        <run>/manifest.json     variable names, units, shapes, coordinates
        <run>/profiles.f32      through-cell profiles and scalars
        <run>/particles.f32     concentration inside the particles
    simulations/indexes/<stamp>.json    every current run set (and the latest benchmark), with sha256
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
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import pybamm  # noqa: E402

import simulation_protocol as protocol  # noqa: E402
from simulation_files import PREFIX, Bucket, dumps, fetch, find_records, sha256  # noqa: E402

GENERATOR_VERSION = 2  # 2: one standard protocol for every file, no temperature grid, measured replays
CURVE_POINTS = 200
MAX_PROFILE_TIME_POINTS = 1000

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


def split_unit(name: str) -> tuple[str, str]:
    match = re.match(r"^(.*?)\s*\[(.*)\]$", name)
    return (match.group(1), match.group(2)) if match else (name, "")


def curve(t, capacity, voltage) -> dict:
    idx = sample(len(t))
    return {
        "time_s": rounded(np.asarray(t)[idx], 1),
        "capacity_Ah": rounded(np.asarray(capacity)[idx], 6),
        "voltage_V": rounded(np.asarray(voltage)[idx], 5),
    }


def write_arrays(path: Path, arrays: list[tuple[str, str | list, np.ndarray]]) -> tuple[list[dict], str]:
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
    time_all = np.asarray(solution["Time [s]"].entries)
    keep = sample(len(time_all), MAX_PROFILE_TIME_POINTS)
    coordinates = {"time_s": rounded(time_all[keep], 3)}
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
        profile_arrays.append((name, domain, entries[:, keep].T if domain else entries[keep]))  # (time, x) or (time,)
    for name, radial, through in PARTICLE_VARIABLES:
        try:
            entries = np.asarray(solution[name].entries)  # (r, x, time)
        except KeyError:
            unavailable.append(name)
            continue
        particle_arrays.append((name, [through, radial], entries[:, :, keep].transpose(2, 1, 0)))  # (time, x, r)

    files = {}
    for filename, arrays in (("profiles.f32", profile_arrays), ("particles.f32", particle_arrays)):
        if not arrays:
            continue
        layout, digest = write_arrays(run_dir / filename, arrays)
        files[filename] = {"sha256": digest, "variables": layout}
    manifest = {
        "dtype": "float32", "byte_order": "little", "layout": "row-major, time first",
        "time_points": int(len(keep)), "coordinates": coordinates, "files": files,
        "unavailable": unavailable,
    }
    (run_dir / "manifest.json").write_bytes(dumps(manifest))
    return manifest


def simulate_file(folder: str, body: dict, dist: dict, raw: bytes, out_root: Path) -> dict:
    bpx = json.loads(raw)
    cell = bpx.get("Parameterisation", {}).get("Cell", {})
    nominal = float(cell["Nominal cell capacity [A.h]"])
    lower, upper = float(cell["Lower voltage cut-off [V]"]), float(cell["Upper voltage cut-off [V]"])
    model, model_source = protocol.model_choice(bpx)
    options = protocol.model_options(bpx)
    thermal, thermal_note = protocol.thermal_support(raw, model, options)
    values = protocol.parameter_values(raw)
    ambient_c = round(float(values["Ambient temperature [K]"]) - 273.15, 2)
    initial_soc = protocol.declared_initial_soc(bpx)

    cases = protocol.measured_cases(bpx)
    specs = protocol.run_specs(bpx, nominal, cases)
    cases_by_key = {case["key"]: case for case in cases}
    max_measured = max((c["peak_current_A"] / nominal for c in cases), default=None)

    run_set = f"{PREFIX}/runs/{body['parameters_sha256']}/pybamm-{pybamm.__version__}/g{GENERATOR_VERSION}"
    run_set_dir = out_root / run_set
    runs, solutions, numerics = [], {}, None
    for spec in specs:
        entry = {**spec, "temperature_C": ambient_c}
        case = cases_by_key.get(spec.get("case", ""))
        try:
            sim, solution = protocol.solve(raw, spec, model, options, thermal, lower, case)
        except Exception as exc:  # noqa: BLE001 - a failed run is a result, not a crash
            entry.update(status="failed", error=f"{type(exc).__name__}: {str(exc).splitlines()[0][:300]}")
            print(f"  {spec['id']}: failed ({entry['error']})")
            runs.append(entry)
            continue
        numerics = numerics or protocol.mesh_and_solver(sim)
        t = np.asarray(solution["Time [s]"].entries)
        capacity = np.asarray(solution["Discharge capacity [A.h]"].entries)
        voltage = np.asarray(solution["Voltage [V]"].entries)
        solutions[spec["id"]] = (t, capacity, voltage)
        # PyBaMM reports discharge energy only when asked to; integrate V*I here instead.
        power = voltage * np.asarray(solution["Current [A]"].entries)
        energy = round(float(np.sum(np.diff(t) * (power[1:] + power[:-1]) / 2)) / 3600, 5)
        entry.update(
            status="ok", curve=curve(t, capacity, voltage),
            end={"capacity_Ah": round(float(capacity[-1]), 6), "energy_Wh": energy,
                 "duration_s": round(float(t[-1]), 1), "voltage_V": round(float(voltage[-1]), 5)},
        )
        if spec["kind"] == "standard":  # profiles for the standard runs only: the same for every file
            manifest = write_profiles(solution, run_set_dir / spec["id"], thermal)
            entry["profiles"] = {
                "manifest": f"{run_set}/{spec['id']}/manifest.json",
                "manifest_sha256": sha256((run_set_dir / spec["id"] / "manifest.json").read_bytes()),
                "files": {name: f"{run_set}/{spec['id']}/{name}" for name in manifest["files"]},
                "time_points": manifest["time_points"],
            }
        print(f"  {spec['id']}: {entry['end']['capacity_Ah']:.4f} Ah")
        runs.append(entry)

    measured = []
    for spec in (s for s in specs if s["kind"] == "measured_replay"):
        case = cases_by_key[spec["case"]]
        item = {"key": case["key"], "run": spec["id"], "constant_current": case["constant"],
                "current_A": round(case["current_A"], 6) if case["current_A"] else None,
                "temperature_C": ambient_c, "curve": curve(case["t"], case["capacity"], case["voltage"])}
        if spec["id"] in solutions:
            t, capacity, voltage = solutions[spec["id"]]
            item["agreement"] = protocol.agreement(case, t, voltage, capacity)
        measured.append(item)

    rates = ", ".join(f"{rate:g}C" for rate in protocol.STANDARD_C_RATES)
    summary = {
        "generator": {"name": "battinfo-records/scripts/simulate-parameter-sets.py", "version": GENERATOR_VERSION},
        "parameter_set": {
            "iri": body["id"], "name": body.get("name"), "record": folder,
            "parameters_sha256": body["parameters_sha256"],
            "file": {"name": dist.get("name"), "role": dist.get("role"), "content_url": dist["content_url"],
                     "sha256": dist["checksum"]["value"], "conforms_to": dist.get("conforms_to")},
        },
        "engine": {"name": "PyBaMM", "version": pybamm.__version__, "model": model, "model_source": model_source,
                   "options": options, **(numerics or {}),
                   "thermal": "lumped" if thermal else "isothermal", "thermal_note": thermal_note},
        "cell": {"nominal_capacity_Ah": nominal, "lower_cutoff_V": lower, "upper_cutoff_V": upper,
                 "ambient_temperature_C": ambient_c, "initial_soc": initial_soc},
        "grid": {
            "c_rates": list(protocol.STANDARD_C_RATES),
            "max_measured_c_rate": round(max_measured, 4) if max_measured is not None else None,
            "c_rate_note": (
                f"The same rates for every file ({rates}). Rates above the highest measured one "
                f"({max_measured:.3g}C) are beyond the measured range."
                if max_measured is not None else
                f"The same rates for every file ({rates}). The file carries no measured data."
            ),
        },
        "measured_source": "the file's own Validation section" if measured else None,
        "measured": measured,
        "runs": runs,
    }
    (run_set_dir / "summary.json").write_bytes(dumps(summary))
    return {"iri": body["id"], "name": body.get("name"), "record": folder,
            "parameters_sha256": body["parameters_sha256"], "pybamm": pybamm.__version__,
            "generator": GENERATOR_VERSION, "summary": f"{run_set}/summary.json",
            "summary_sha256": sha256((run_set_dir / "summary.json").read_bytes())}


def upload(out_root: Path, run_set_entries: list[dict], index_key: str, index: dict) -> None:
    bucket = Bucket()
    written = skipped = 0
    for entry in run_set_entries:
        run_set_dir = out_root / Path(entry["summary"]).parent
        for path in sorted(p for p in run_set_dir.rglob("*") if p.is_file()):
            key = path.relative_to(out_root).as_posix()
            if bucket.exists(key):
                skipped += 1
                continue
            bucket.put(key, path.read_bytes())
            written += 1
    print(f"run-set files: {written} written, {skipped} already there")

    def listing(ix: dict) -> list:
        return sorted((r["summary"], r["summary_sha256"]) for r in ix.get("run_sets", []))

    current_key, current = bucket.current_index()
    if current and listing(current) == listing(index):
        print(f"unchanged: {PREFIX}/latest.json still points at {current_key}")
        return
    # The benchmark job writes its own entry; a new run-set index keeps the latest one.
    bucket.publish_index(index_key, {**index, "benchmark": (current or {}).get("benchmark")})


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
        upload(out_root, entries, index_key, index)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
