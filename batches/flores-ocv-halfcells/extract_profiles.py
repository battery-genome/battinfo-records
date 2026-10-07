"""Derive a small plot profile for every Flores half-cell OCV dataset.

The 95 datasets of this batch are BDF parquet time series hosted on Zenodo, 1.7 MB
(p-OCV) to 544 MB (GITT), about 15.6 GB in total. A dataset page cannot plot those:
the platform renders a Plotly figure JSON fetched from a URL, so each dataset needs a
small derived artifact next to it. This script produces that artifact.

For each dataset record it downloads the source file (cached, md5-verified against the
record's own checksum), streams it row group by row group, and writes

    profiles/<stem>.plot.json

a Plotly figure with two stacked panels:

  1. Voltage against test time, reduced by peak-preserving min/max decimation - each
     time bucket contributes the sample where voltage was lowest and the sample where
     it was highest, at their true timestamps, in the order they occurred. Naive
     striding would drop GITT's 30-minute pulses between samples; min/max keeps every
     excursion, so the sawtooth survives a 34-million-row file at 5000 points.
  2. The open-circuit potential curve against capacity. For GITT that is the relaxed
     endpoint of each rest - the last sample before current resumes, which is the
     quasi-equilibrium potential the technique exists to measure. For p-OCV the whole
     sweep is already near equilibrium, so the curve is the longest monotonic capacity
     segment of the sweep itself.

Summary statistics (row count, duration, voltage and capacity range, current extremes)
ride along under a ``battinfo_summary`` key. Plotly reads only ``data`` and ``layout``,
so the extra key is inert in the browser and keeps the numbers with the figure.

The companion ``profiles/index.json`` records each profile's sha256, byte size and
source md5. ``build_records.py`` reads it to attach the profile distribution, so the
records regenerate deterministically without re-reading 15.6 GB.

Usage::

    python extract_profiles.py --cache <scratch-dir>          # all 95
    python extract_profiles.py --cache <scratch-dir> --only gitt --limit 3
    python extract_profiles.py --cache <scratch-dir> --force   # ignore existing profiles

Downloads are cached in ``--cache`` and verified by md5 on every reuse. Source files
larger than ``--keep-below`` bytes are deleted after extraction so the whole corpus can
be processed without 15.6 GB of free disk; the profile itself is the durable cache, and
a re-run skips any dataset whose profile already records the same source md5.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq

BATCH_DIR = Path(__file__).resolve().parent
RECORDS_DIR = BATCH_DIR / "records" / "dataset"
PROFILES_DIR = BATCH_DIR / "profiles"
INDEX_PATH = PROFILES_DIR / "index.json"

ZENODO_RECORD = "20086298"
CHUNK = 1 << 20

# Columns the BDF parquet carries. Only these are read; Unix Time and Cycle Count are
# not needed for either panel and reading them would double the memory per row group.
C_TIME = "Test Time / s"
C_VOLT = "Voltage / V"
C_CURR = "Current / A"
C_CAP = "Cumulative Capacity / Ah"

# Current below this reads as "no current flowing". The instruments write exact zeros
# during rests and +-6.2e-5 A during pulses, so the threshold is far from both.
REST_CURRENT_A = 1e-9

# A GITT run rests after every pulse, so a genuine one yields hundreds of relaxed
# endpoints. Far fewer means the file does not carry the pulse train its record claims,
# and the continuous sweep is the better curve.
MIN_REST_ENDPOINTS = 20

# Time buckets for the min/max decimation. The GITT runs of this dataset are 2900-3200 h
# long with a ~3 h pulse period, so 2500 buckets put 2-3 buckets on each pulse cycle.
# That is coarse, and it is why the decimation is min/max rather than striding: each
# bucket keeps the extremes at their true timestamps, so every pulse excursion survives
# at full amplitude even when a cycle spans only a couple of buckets (measured: 14-180 mV
# peak-to-peak per 3 h in the emitted traces, against 8 mV for a p-OCV sweep). Raising
# the count would smooth the sawtooth's shape, not recover amplitude. p-OCV files are
# short and continuous and need far fewer.
BUCKETS_GITT = 2500
BUCKETS_POCV = 1000

# Subsample kept in memory for the p-OCV open-circuit analysis. Large enough to locate
# the longest monotonic capacity segment precisely, small enough to bound memory on a
# 170-million-row file.
ANALYSIS_POINTS = 20000

# Validated in both light and dark mode against the platform's chart surfaces
# (dataviz palette slots 1 and 2, stepped to a single pair that passes both).
COLOR_VOLTAGE = "#2a78d6"
COLOR_OCP = "#e2612d"
COLOR_GRID = "rgba(128,128,128,0.22)"
COLOR_ZERO = "rgba(128,128,128,0.45)"


# --------------------------------------------------------------------------- download


def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch(name: str, want_md5: str, cache_dir: Path, *, attempts: int = 6) -> Path:
    """Download *name* from the Zenodo record into *cache_dir*, verified by md5.

    An already-cached file whose md5 matches is returned untouched. Zenodo's content
    endpoint intermittently answers 504 while it warms a cold object, so failures are
    retried with a widening backoff rather than treated as fatal.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / name
    if dest.exists() and md5_file(dest) == want_md5:
        return dest

    url = f"https://zenodo.org/api/records/{ZENODO_RECORD}/files/{name}/content"
    last = ""
    for attempt in range(1, attempts + 1):
        tmp = dest.with_suffix(dest.suffix + ".part")
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "battinfo-records/flores-ocv"}
            )
            with urllib.request.urlopen(request, timeout=900) as response, tmp.open("wb") as out:
                while True:
                    block = response.read(CHUNK)
                    if not block:
                        break
                    out.write(block)
            got = md5_file(tmp)
            if got != want_md5:
                last = f"md5 mismatch (got {got}, want {want_md5})"
                tmp.unlink(missing_ok=True)
            else:
                tmp.replace(dest)
                return dest
        except Exception as exc:  # noqa: BLE001 - transient network and proxy errors
            last = f"{type(exc).__name__}: {exc}"
            tmp.unlink(missing_ok=True)
        if attempt < attempts:
            time.sleep(min(60, 5 * 2 ** (attempt - 1)))
    raise RuntimeError(f"download failed for {name} after {attempts} attempts: {last}")


# ---------------------------------------------------------------------- decimation


class MinMaxDecimator:
    """Peak-preserving reduction of a monotonically-timed signal to <= 2N points.

    Time is split into *buckets* equal fixed-width intervals. Each bucket keeps the
    sample where the signal reached its minimum and the sample where it reached its
    maximum, with the true timestamps of both, so a spike narrower than a bucket still
    appears at full amplitude and at the right moment. Samples arrive in time order and
    a bucket may straddle several row groups, so the extremes are merged incrementally.
    """

    def __init__(self, t_start: float, t_end: float, buckets: int) -> None:
        self.t_start = float(t_start)
        self.span = max(float(t_end) - float(t_start), 1e-9)
        self.buckets = int(buckets)
        self.vmin = np.full(self.buckets, np.inf)
        self.vmax = np.full(self.buckets, -np.inf)
        self.tmin = np.zeros(self.buckets)
        self.tmax = np.zeros(self.buckets)

    def add(self, t: np.ndarray, v: np.ndarray) -> None:
        if t.size == 0:
            return
        idx = ((t - self.t_start) / self.span * self.buckets).astype(np.int64)
        np.clip(idx, 0, self.buckets - 1, out=idx)
        # Time is non-decreasing, so bucket indices are too: contiguous runs of equal
        # index delimit each bucket's slice and no sorting is needed.
        change = np.flatnonzero(np.diff(idx)) + 1
        starts = np.concatenate(([0], change))
        ends = np.concatenate((change, [idx.size]))
        for start, end in zip(starts, ends):
            bucket = idx[start]
            chunk = v[start:end]
            lo = int(np.argmin(chunk))
            hi = int(np.argmax(chunk))
            if chunk[lo] < self.vmin[bucket]:
                self.vmin[bucket] = chunk[lo]
                self.tmin[bucket] = t[start + lo]
            if chunk[hi] > self.vmax[bucket]:
                self.vmax[bucket] = chunk[hi]
                self.tmax[bucket] = t[start + hi]

    def series(self) -> tuple[np.ndarray, np.ndarray]:
        """Emit the kept samples in true chronological order."""
        filled = np.flatnonzero(np.isfinite(self.vmin))
        if filled.size == 0:
            return np.empty(0), np.empty(0)
        t_lo, v_lo = self.tmin[filled], self.vmin[filled]
        t_hi, v_hi = self.tmax[filled], self.vmax[filled]
        # Within a bucket emit whichever extreme happened first.
        first_is_min = t_lo <= t_hi
        t_out = np.empty(filled.size * 2)
        v_out = np.empty(filled.size * 2)
        t_out[0::2] = np.where(first_is_min, t_lo, t_hi)
        v_out[0::2] = np.where(first_is_min, v_lo, v_hi)
        t_out[1::2] = np.where(first_is_min, t_hi, t_lo)
        v_out[1::2] = np.where(first_is_min, v_hi, v_lo)
        # A bucket holding a single sample yields that sample twice; drop the repeat.
        keep = np.ones(t_out.size, dtype=bool)
        keep[1::2] = ~((t_out[1::2] == t_out[0::2]) & (v_out[1::2] == v_out[0::2]))
        return t_out[keep], v_out[keep]


def run_bounds(mask: np.ndarray) -> list[tuple[int, int, bool]]:
    """Split *mask* into maximal runs, as (start, end, value) triples."""
    if mask.size == 0:
        return []
    change = np.flatnonzero(np.diff(mask)) + 1
    starts = np.concatenate(([0], change))
    ends = np.concatenate((change, [mask.size]))
    return [(int(s), int(e), bool(mask[s])) for s, e in zip(starts, ends)]


def longest_monotonic(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return the longest run over which *x* moves in a single direction.

    A p-OCV file sweeps the cell several times and ``Cumulative Capacity`` restarts on
    every half cycle, so plotting the raw pairs would overlay every sweep and retrace.
    The longest single-direction run is one complete sweep: the open-circuit curve.
    """
    if x.size < 3:
        return x, y
    step = np.diff(x)
    sign = np.sign(step)
    # Flat samples continue whichever direction is already running.
    nonzero = sign[sign != 0]
    if nonzero.size == 0:
        return x, y
    best_start = best_end = 0
    start = 0
    current = 0.0
    for k in range(sign.size):
        s = sign[k]
        if s == 0:
            continue
        if current == 0.0:
            current = s
            continue
        if s != current:
            if k - start > best_end - best_start:
                best_start, best_end = start, k
            start = k
            current = s
    if sign.size - start > best_end - best_start:
        best_start, best_end = start, sign.size
    return x[best_start : best_end + 1], y[best_start : best_end + 1]


# ------------------------------------------------------------------------ extraction


def extract(path: Path, *, technique: str) -> dict[str, Any]:
    """Stream the parquet file and build both curves plus the summary statistics."""
    handle = pq.ParquetFile(path)
    n_rows = handle.metadata.num_rows
    buckets = BUCKETS_GITT if technique == "gitt" else BUCKETS_POCV

    # First and last row group give the time span the buckets are laid out over,
    # without reading the file twice.
    first = handle.read_row_group(0, columns=[C_TIME]).column(0).to_numpy()
    last = handle.read_row_group(handle.num_row_groups - 1, columns=[C_TIME]).column(0).to_numpy()
    t_start, t_end = float(first[0]), float(last[-1])

    decimator = MinMaxDecimator(t_start, t_end, buckets)
    stride = max(1, n_rows // ANALYSIS_POINTS)

    rest_endpoints: list[tuple[float, float]] = []
    carried: tuple[float, float] | None = None
    sample_cap: list[np.ndarray] = []
    sample_volt: list[np.ndarray] = []

    v_min = np.inf
    v_max = -np.inf
    cap_min = np.inf
    cap_max = -np.inf
    i_min = np.inf
    i_max = -np.inf
    offset = 0

    for group in range(handle.num_row_groups):
        table = handle.read_row_group(group, columns=[C_TIME, C_VOLT, C_CURR, C_CAP])
        t = table.column(0).to_numpy()
        v = table.column(1).to_numpy()
        i = table.column(2).to_numpy()
        cap = table.column(3).to_numpy()

        decimator.add(t, v)

        v_min = min(v_min, float(np.nanmin(v)))
        v_max = max(v_max, float(np.nanmax(v)))
        cap_min = min(cap_min, float(np.nanmin(cap)))
        cap_max = max(cap_max, float(np.nanmax(cap)))
        i_min = min(i_min, float(np.nanmin(i)))
        i_max = max(i_max, float(np.nanmax(i)))

        # Relaxed endpoints: the final sample of every rest, flushed when current
        # resumes. Rests routinely straddle row groups, so the candidate is carried.
        resting = np.abs(i) < REST_CURRENT_A
        for start, end, is_rest in run_bounds(resting):
            if is_rest:
                carried = (float(cap[end - 1]), float(v[end - 1]))
            elif carried is not None:
                rest_endpoints.append(carried)
                carried = None

        take = np.arange((-offset) % stride, t.size, stride)
        if take.size:
            sample_cap.append(cap[take])
            sample_volt.append(v[take])
        offset += t.size

    if carried is not None:
        rest_endpoints.append(carried)

    plot_t, plot_v = decimator.series()

    # Which curve is the open-circuit one depends on the protocol, not on whether rests
    # exist: a p-OCV file also rests, but only 11 times, at the ends of its half cycles.
    # GITT interrupts a slow titration hundreds of times and the relaxed endpoint of each
    # rest is the measurement; p-OCV sweeps continuously at a current low enough that the
    # sweep itself approximates equilibrium. Falling back to the sweep when a GITT file
    # yields too few rests keeps a mislabelled or truncated file from losing its curve.
    if technique == "gitt" and len(rest_endpoints) >= MIN_REST_ENDPOINTS:
        ocp_cap = np.array([c for c, _ in rest_endpoints])
        ocp_v = np.array([v for _, v in rest_endpoints])
        ocp_source = "relaxation endpoints"
    else:
        ocp_cap = np.concatenate(sample_cap) if sample_cap else np.empty(0)
        ocp_v = np.concatenate(sample_volt) if sample_volt else np.empty(0)
        ocp_source = "sweep"
    ocp_cap, ocp_v = longest_monotonic(ocp_cap, ocp_v)

    return {
        "t_hours": plot_t / 3600.0,
        "voltage": plot_v,
        "ocp_capacity_mah": ocp_cap * 1000.0,
        "ocp_voltage": ocp_v,
        "ocp_source": ocp_source,
        "summary": {
            "n_points": int(n_rows),
            "n_plotted": int(plot_t.size),
            "t_max_s": round(t_end - t_start, 1),
            "t_max_hours": round((t_end - t_start) / 3600.0, 2),
            "voltage_min_v": round(v_min, 4),
            "voltage_max_v": round(v_max, 4),
            "capacity_min_ah": float(f"{cap_min:.6g}"),
            "capacity_max_ah": float(f"{cap_max:.6g}"),
            "current_min_a": float(f"{i_min:.4g}"),
            "current_max_a": float(f"{i_max:.4g}"),
            "n_rest_endpoints": len(rest_endpoints),
        },
    }


# --------------------------------------------------------------------------- figure


def build_figure(profile: dict[str, Any], *, title: str, technique: str) -> dict[str, Any]:
    """Assemble the two-panel Plotly figure the dataset page renders.

    Two single-measure panels rather than one dual-axis plot: voltage against time on
    top, the open-circuit curve against capacity below. Each panel carries one trace,
    so the axis titles identify the data and no legend is needed.
    """
    t = np.round(profile["t_hours"], 4)
    v = np.round(profile["voltage"], 4)
    cap = np.round(profile["ocp_capacity_mah"], 5)
    ocp = np.round(profile["ocp_voltage"], 4)

    relaxed = profile["ocp_source"] == "relaxation endpoints"
    ocp_label = "Relaxed OCP / V" if relaxed else "Quasi-OCV / V"
    ocp_name = "Relaxed OCP" if relaxed else "Quasi-OCV"

    data: list[dict[str, Any]] = [
        {
            # Plain "scatter", never "scattergl": the platform loads
            # plotly.js-basic-dist-min, whose only trace modules are bar, pie and
            # scatter. A WebGL trace would silently fail to draw there.
            "type": "scatter",
            "mode": "lines",
            "name": "Voltage",
            "x": t.tolist(),
            "y": v.tolist(),
            "line": {"color": COLOR_VOLTAGE, "width": 1.6},
            "hovertemplate": "%{x:.3f} h<br>%{y:.4f} V<extra></extra>",
            "xaxis": "x",
            "yaxis": "y",
        }
    ]
    if cap.size >= 2:
        data.append(
            {
                "type": "scatter",
                "mode": "lines+markers" if cap.size <= 400 else "lines",
                "name": ocp_name,
                "x": cap.tolist(),
                "y": ocp.tolist(),
                "line": {"color": COLOR_OCP, "width": 2},
                "marker": {"size": 5, "color": COLOR_OCP},
                "hovertemplate": "%{x:.4f} mAh<br>%{y:.4f} V<extra></extra>",
                "xaxis": "x2",
                "yaxis": "y2",
            }
        )

    axis = {
        "gridcolor": COLOR_GRID,
        "zerolinecolor": COLOR_ZERO,
        "showline": True,
        "linecolor": COLOR_GRID,
        "ticks": "outside",
        "tickcolor": COLOR_GRID,
    }
    layout: dict[str, Any] = {
        "title": {"text": title, "font": {"size": 14}},
        "showlegend": False,
        "hovermode": "closest",
        "xaxis": {**axis, "title": {"text": "Test time / h"}, "domain": [0, 1], "anchor": "y"},
        "yaxis": {**axis, "title": {"text": "Voltage / V"}, "domain": [0.60, 1.0], "anchor": "x"},
    }
    if cap.size >= 2:
        layout["xaxis2"] = {
            **axis,
            "title": {"text": "Capacity / mAh"},
            "domain": [0, 1],
            "anchor": "y2",
        }
        layout["yaxis2"] = {
            **axis,
            "title": {"text": ocp_label},
            "domain": [0.0, 0.42],
            "anchor": "x2",
        }
    else:
        layout["yaxis"]["domain"] = [0.0, 1.0]

    return {
        "data": data,
        "layout": layout,
        "battinfo_summary": {**profile["summary"], "technique": technique},
    }


# ----------------------------------------------------------------------------- main


def load_targets() -> list[dict[str, Any]]:
    targets = []
    for record_path in sorted(RECORDS_DIR.glob("*.json")):
        record = json.loads(record_path.read_text(encoding="utf-8"))["dataset"]
        dist = record["distributions"][0]
        targets.append(
            {
                "record_path": record_path,
                "short_id": record["short_id"],
                "title": record["name"],
                "file": dist["name"],
                "md5": dist["checksum"]["value"],
                "size": int(dist["content_size"]),
                "technique": record["measurement_techniques"][0],
            }
        )
    return targets


def profile_name(source_file: str) -> str:
    """``<stem>.plot.json`` for a ``<stem>.bdf.parquet`` source."""
    stem = source_file
    for suffix in (".bdf.parquet", ".parquet"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    return f"{stem}.plot.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", required=True, type=Path, help="Scratch dir for downloads.")
    parser.add_argument("--only", choices=["gitt", "quasi_ocv"], help="Restrict to one technique.")
    parser.add_argument("--limit", type=int, help="Process at most this many datasets.")
    parser.add_argument("--force", action="store_true", help="Rebuild existing profiles.")
    parser.add_argument(
        "--keep-below",
        type=int,
        default=32 * 1024 * 1024,
        help="Delete a downloaded source larger than this after extraction (bytes).",
    )
    args = parser.parse_args()

    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    index: dict[str, Any] = {}
    if INDEX_PATH.exists():
        index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))

    targets = load_targets()
    if args.only:
        targets = [t for t in targets if t["technique"] == args.only]
    if args.limit:
        targets = targets[: args.limit]

    failures: list[tuple[str, str]] = []
    done = 0
    for position, target in enumerate(targets, 1):
        out_name = profile_name(target["file"])
        out_path = PROFILES_DIR / out_name
        recorded = index.get(out_name)
        if (
            not args.force
            and out_path.exists()
            and recorded
            and recorded.get("source_md5") == target["md5"]
        ):
            print(f"[{position}/{len(targets)}] cached {out_name}", flush=True)
            done += 1
            continue

        print(
            f"[{position}/{len(targets)}] {target['technique']:9s} "
            f"{target['size'] / 1e6:7.1f} MB  {target['file']}",
            flush=True,
        )
        source: Path | None = None
        try:
            source = fetch(target["file"], target["md5"], args.cache)
            profile = extract(source, technique=target["technique"])
            figure = build_figure(profile, title=target["title"], technique=target["technique"])
            out_path.write_text(
                json.dumps(figure, separators=(",", ":"), ensure_ascii=False), encoding="utf-8"
            )
            index[out_name] = {
                "source_file": target["file"],
                "source_md5": target["md5"],
                "short_id": target["short_id"],
                "technique": target["technique"],
                "bytes": out_path.stat().st_size,
                "sha256": sha256_file(out_path),
                "summary": figure["battinfo_summary"],
            }
            done += 1
            print(
                f"    -> {out_name}  {out_path.stat().st_size / 1024:.1f} KB  "
                f"{figure['battinfo_summary']['n_plotted']} pts  "
                f"ocp {len(figure['data'][1]['x']) if len(figure['data']) > 1 else 0} pts",
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001 - one bad file must not stop the corpus
            failures.append((target["file"], f"{type(exc).__name__}: {exc}"))
            print(f"    FAILED {type(exc).__name__}: {exc}", flush=True)
        finally:
            if source is not None and source.exists() and source.stat().st_size > args.keep_below:
                source.unlink()

        INDEX_PATH.write_text(
            json.dumps(dict(sorted(index.items())), indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    INDEX_PATH.write_text(
        json.dumps(dict(sorted(index.items())), indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"\n{done}/{len(targets)} profile(s) available.")
    if failures:
        print(f"{len(failures)} failure(s):")
        for name, reason in failures:
            print(f"  {name}: {reason}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
