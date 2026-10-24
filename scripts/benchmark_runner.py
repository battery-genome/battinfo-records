#!/usr/bin/env python3
"""Run the standard simulation protocol on BPX files inside one PyBaMM installation, timing each case.

Called by benchmark-simulators.py once per PyBaMM release, in an environment that has that
release installed. It applies the same protocol as the record runs (simulation_protocol.py):
the standard discharges for every file, plus a replay of each measured discharge the file itself
carries, compared with the measurement.

Each case is solved once to warm up (discarded), then REPEATS times; the wall time includes model
building and solving, and the median is reported. Import time is reported once, separately.

    python scripts/benchmark_runner.py --files files.json --out result.json
"""
from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

REPEATS = 3


def first_line(exc: Exception) -> str:
    return f"{type(exc).__name__}: {(str(exc).splitlines() or [''])[0][:300]}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--files", type=Path, required=True, help="JSON list of {iri, path} for the BPX files")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    started = time.perf_counter()
    import numpy as np
    import pybamm

    import simulation_protocol as protocol
    import_s = round(time.perf_counter() - started, 2)

    files = json.loads(args.files.read_text(encoding="utf-8"))
    results = {}
    for item in files:
        raw = Path(item["path"]).read_bytes()
        bpx = json.loads(raw)
        try:
            protocol.parameter_values(raw)
        except Exception as exc:  # noqa: BLE001 - this release cannot read the file: a result
            results[item["iri"]] = {"read": False, "error": first_line(exc)}
            print(f"{item['iri']}: cannot read ({first_line(exc)})", flush=True)
            continue
        cell = bpx["Parameterisation"]["Cell"]
        nominal = float(cell["Nominal cell capacity [A.h]"])
        lower = float(cell["Lower voltage cut-off [V]"])
        model, _ = protocol.model_choice(bpx)
        options = protocol.model_options(bpx)
        thermal, _ = protocol.thermal_support(raw, model, options)
        cases = protocol.measured_cases(bpx)
        cases_by_key = {case["key"]: case for case in cases}
        outcome = {}
        for spec in protocol.run_specs(bpx, nominal, cases):
            case = cases_by_key.get(spec.get("case", ""))
            about = {"kind": spec["kind"], "c_rate": spec["c_rate"], "case": spec.get("case"),
                     "beyond_measured_range": spec.get("beyond_measured_range")}
            try:
                protocol.solve(raw, spec, model, options, thermal, lower, case)  # warm-up, discarded
                times = []
                for _ in range(REPEATS):
                    start = time.perf_counter()
                    _, solution = protocol.solve(raw, spec, model, options, thermal, lower, case)
                    times.append(time.perf_counter() - start)
            except Exception as exc:  # noqa: BLE001 - a case that does not solve is a result
                outcome[spec["id"]] = {**about, "status": "failed", "error": first_line(exc)}
                print(f"  {spec['id']}: failed ({first_line(exc)})", flush=True)
                continue
            t = np.asarray(solution["Time [s]"].entries)
            capacity = np.asarray(solution["Discharge capacity [A.h]"].entries)
            voltage = np.asarray(solution["Voltage [V]"].entries)
            entry = {**about, "status": "ran", "median_s": round(statistics.median(times), 4),
                     "runs_s": [round(x, 4) for x in times], "capacity_Ah": round(float(capacity[-1]), 6)}
            if case is not None:
                entry["agreement"] = protocol.agreement(case, t, voltage, capacity)
            outcome[spec["id"]] = entry
            print(f"  {spec['id']}: {entry['median_s']:.3f} s, {entry['capacity_Ah']:.4f} Ah", flush=True)
        results[item["iri"]] = {"read": True, "model": model, "cases": outcome}

    args.out.write_text(json.dumps({
        "pybamm": pybamm.__version__, "python": platform.python_version(), "import_s": import_s,
        "repeats": REPEATS, "files": results,
    }, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
