#!/usr/bin/env python3
"""Benchmark PyBaMM releases on the standard simulation protocol.

For the latest patch of each PyBaMM release line published in the last ``--months`` months, plus
the version the record runs are pinned to, this installs the release in a fresh environment with
uv and runs ``benchmark_runner.py`` on every parameter file the record runs use: the same
standard discharges, and the same replays of the measured data each file carries. All releases
run back to back on the same machine, so their timings compare; a release that cannot read a
file, fails to solve a case, or does not install is recorded as such.

Output: ``simulations/benchmark/<stamp>.json`` under ``--out``. With ``--upload`` it is written to
the bucket named by R2_BUCKET (never overwritten), and a new index (the current run sets plus
this benchmark) becomes ``simulations/latest.json``.

    uv run --no-project --with boto3 python scripts/benchmark-simulators.py --out ../bench-out [--upload]
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))

from simulation_files import PREFIX, USER_AGENT, Bucket, dumps, fetch, find_records, sha256  # noqa: E402

BENCHMARK_VERSION = 1
RUNNER = Path(__file__).resolve().parent / "benchmark_runner.py"
DEFAULT_PINNED = os.environ.get("PYBAMM_VERSION", "26.10.1.1")


def release_lines(months: int, pinned: str) -> list[dict]:
    """The latest patch of each release line (year.month) uploaded within ``months``, plus the pin."""
    with urlopen(Request("https://pypi.org/pypi/pybamm/json", headers={"User-Agent": USER_AGENT}), timeout=60) as r:
        releases = json.loads(r.read())["releases"]
    since = datetime.now(timezone.utc) - timedelta(days=round(months * 30.44))
    latest: dict[tuple[int, int], tuple[tuple[int, ...], str, str]] = {}
    for version, files in releases.items():
        if not files or all(f.get("yanked") for f in files) or not re.fullmatch(r"\d+(\.\d+)+", version):
            continue
        uploaded = min(f["upload_time_iso_8601"] for f in files)
        if datetime.fromisoformat(uploaded.replace("Z", "+00:00")) < since and version != pinned:
            continue
        parts = tuple(int(p) for p in version.split("."))
        line = parts[:2]
        if line not in latest or parts > latest[line][0]:
            latest[line] = (parts, version, uploaded[:10])
    chosen = {version: released for _, version, released in latest.values()}
    if pinned in releases and pinned not in chosen:
        chosen[pinned] = min(f["upload_time_iso_8601"] for f in releases[pinned])[:10]
    return [{"version": v, "released": chosen[v]}
            for v in sorted(chosen, key=lambda v: tuple(int(p) for p in v.split(".")))]


def cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or platform.machine()


def run_release(version: str, python: str, files_json: Path, work: Path) -> dict:
    out = work / f"result-{version}.json"
    command = ["uv", "run", "--no-project", "--python", python, "--with", f"pybamm[bpx]=={version}",
               "python", str(RUNNER), "--files", str(files_json), "--out", str(out)]
    print(f"== PyBaMM {version}", flush=True)
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=3600)
    except subprocess.TimeoutExpired:
        return {"status": "timed_out", "error": "no result within an hour"}
    print("\n".join(line for line in proc.stdout.splitlines() if not line.startswith(" ")), flush=True)
    if proc.returncode != 0 or not out.exists():
        tail = [line for line in proc.stderr.splitlines() if line.strip()][-3:]
        return {"status": "not_installed" if not out.exists() else "errored", "error": " | ".join(tail)[:600]}
    return {"status": "ran", **json.loads(out.read_text(encoding="utf-8"))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, required=True, help="local folder for the output")
    parser.add_argument("--cache-dir", type=Path, default=None, help="downloaded BPX files (default <out>/_cache)")
    parser.add_argument("--only", help="glob on record folder names, e.g. 'schmitt*'")
    parser.add_argument("--stamp", default=None, help="file name, e.g. <date>-<workflow run id>")
    parser.add_argument("--pinned", default=DEFAULT_PINNED, help="the PyBaMM version the record runs use")
    parser.add_argument("--months", type=int, default=12)
    parser.add_argument("--versions", help="comma-separated releases instead of the release lines")
    parser.add_argument("--python", default="3.12")
    parser.add_argument("--upload", action="store_true")
    args = parser.parse_args()

    out_root = args.out.resolve()
    work = out_root / "_benchmark"
    work.mkdir(parents=True, exist_ok=True)
    cache_dir = (args.cache_dir or out_root / "_cache").resolve()
    stamp = args.stamp or f"{datetime.now(timezone.utc):%Y-%m-%d}-local"
    if not re.fullmatch(r"[A-Za-z0-9._-]+", stamp):
        raise SystemExit(f"--stamp may only contain letters, digits, '.', '_' and '-': {stamp}")

    files, listed = [], []
    for folder, body, dist in find_records(args.only):
        raw = fetch(dist, cache_dir)
        path = work / f"{dist['checksum']['value']}.json"
        path.write_bytes(raw)
        files.append({"iri": body["id"], "path": str(path)})
        listed.append({"iri": body["id"], "name": body.get("name"), "record": folder,
                       "parameters_sha256": body["parameters_sha256"], "file_sha256": dist["checksum"]["value"]})
    files_json = work / "files.json"
    files_json.write_text(json.dumps(files), encoding="utf-8")

    if args.versions:
        versions = [{"version": v.strip(), "released": None} for v in args.versions.split(",") if v.strip()]
    else:
        versions = release_lines(args.months, args.pinned)
    print(f"{len(files)} file(s), PyBaMM releases: {', '.join(v['version'] for v in versions)}", flush=True)

    results = [{**release, **run_release(release["version"], args.python, files_json, work)} for release in versions]
    benchmark = {
        "generated": stamp, "benchmark_version": BENCHMARK_VERSION, "pinned": args.pinned,
        "protocol": "scripts/simulation_protocol.py: standard discharges plus replays of each file's measured data",
        "runner": {"os": platform.platform(), "cpu": cpu_model(), "cpus": os.cpu_count(), "python": args.python},
        "files": listed, "versions": results,
    }
    key = f"{PREFIX}/benchmark/{stamp}.json"
    body = dumps(benchmark)
    (out_root / key).parent.mkdir(parents=True, exist_ok=True)
    (out_root / key).write_bytes(body)
    print(f"wrote {key} under {out_root}", flush=True)

    if args.upload:
        bucket = Bucket()
        if bucket.exists(key):
            raise SystemExit(f"{key} already exists; use another --stamp")
        bucket.put(key, body)
        current_key, current = bucket.current_index()
        index = {**(current or {"generated": stamp, "run_sets": []}),
                 "benchmark": {"key": key, "sha256": sha256(body), "generated": stamp}}
        bucket.publish_index(f"{PREFIX}/indexes/{stamp}-benchmark.json", index)
    return 0


if __name__ == "__main__":
    sys.exit(main())
