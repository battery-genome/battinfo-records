#!/usr/bin/env python3
"""Derive OCP claim batches from the Flores half-cell p-OCV datasets.

Input is the published Flores half-cell OCV corpus in
``batches/flores-ocv-halfcells/records`` (its datasets, tests, cells, electrodes,
electrode specs, cell specs and test specs) and the BDF parquet files the dataset
records point at on Zenodo. Output is one claim-batch parameter set per electrode
spec, staged at ``records/parameter-set/<slug>/record.json``.

Which datasets are used:

- p-OCV only (the test runs the ``flores-ocv/p-ocv-test-spec`` protocol): not the
  p-OCV hold and not the GITT runs;
- single-phase working electrodes only (graphite, silicon, LFP, LNMO, NMC111,
  NMC532); a silicon-graphite blend's curve is not the OCP of one material, so the
  blend electrode specs are skipped;
- every such dataset whose cell is built with the electrode spec, except where the
  test carries a non-conformant conformance note.

What is computed for each dataset:

- The current sign is read from the data, not assumed. A half-cell's voltage is its
  working electrode's potential vs Li/Li+ (the counter electrode is lithium metal),
  and every half-cycle used must move that voltage in the direction its current
  sign gives: positive current raises it (delithiation), negative current lowers it
  (lithiation). A file that breaks this stops the run.
- The first full cycle: the first two consecutive half-cycles that each start at
  the voltage cut-off where the previous half-cycle ended and run to the other
  cut-off (the cut-offs are the cell spec's). The initial half-cycle from the
  as-assembled open-circuit voltage never counts; for the negative electrode
  materials it carries SEI formation.
- Each branch on x, the lithium fraction normalised to that branch's measured
  capacity window (0 at the delithiated end, 1 at the lithiated end), from the
  file's cumulative capacity. This is not absolute stoichiometry.

Each batch then holds three ``ocp`` claims on a common grid of GRID_POINTS values of
x: the lithiation and delithiation branches averaged across the cells, and the mean
of those two branches. Every claim names the datasets it was computed from in
``is_based_on``. Re-running gives byte-identical records: the inputs are pinned by
md5, the arithmetic is deterministic, and ``retrieved_at`` is fixed.

The batch IRI derives from (target, scope, name), so names are part of the
identity: change one and the batch gets a new IRI.

Run from the repo root with numpy, pyarrow and a BattINFO whose parameter-set schema takes
``is_based_on`` (the first one after 0.8.1) installed:

    python scripts/ingest-flores-ocp-claims.py --cache <download-dir> [--dry-run]
        [--plots <png-dir>] [--check-live]

``--check-live`` fetches every IRI a record cites from w3id.org and stops on one that
is missing or superseded.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq

REPO = Path(__file__).resolve().parent.parent
BATCH_DIR = REPO / "batches" / "flores-ocv-halfcells"
CORPUS = BATCH_DIR / "records"
OUT_DIR = REPO / "records" / "parameter-set"
SCRIPT = "scripts/ingest-flores-ocp-claims.py"

# The download, md5 check and column names of the corpus's own profile extraction.
_spec = importlib.util.spec_from_file_location("flores_extract_profiles", BATCH_DIR / "extract_profiles.py")
xp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(xp)

SINGLE_PHASE = ("graphite", "silicon", "lfp", "lnmo", "nmc111", "nmc532")
P_OCV_PROTOCOL_HANDLE = "flores-ocv/p-ocv-test-spec"
GRID_POINTS = 201
VOLTAGE_DIGITS = 5
# A half-cycle ends at a cut-off when its last voltage is this close to it.
CUTOFF_TOLERANCE_V = 0.005
# Shorter runs of nonzero current are not half-cycles.
MIN_HALF_CYCLE_ROWS = 100
RETRIEVED_AT = int(datetime(2026, 11, 26, tzinfo=timezone.utc).timestamp())
LICENSE = "cc-by-4.0"
CREDIT = "Flores et al. 2026"
USER_AGENT = "battinfo-records/flores-ocp-claims"

KIND_LABELS = {
    "graphite": "graphite", "silicon": "silicon", "lfp": "LFP",
    "lnmo": "LNMO", "nmc111": "NMC111", "nmc532": "NMC532",
}
BRANCHES = ("lithiation", "delithiation")
X_SENTENCE = "x is the lithium fraction normalised to each branch's measured capacity window, not absolute stoichiometry."


# ----------------------------------------------------------------------- corpus


def load_corpus() -> dict[str, dict[str, dict]]:
    """Every corpus record by type and IRI."""
    types = {
        "dataset": "dataset", "test": "test", "cell-instance": "cell_instance", "electrode": "electrode",
        "electrode-spec": "electrode_spec", "material-spec": "material_spec", "cell-spec": "cell_spec",
        "test-protocol": "test_spec",
    }
    corpus: dict[str, dict[str, dict]] = {}
    for folder, key in types.items():
        corpus[key] = {}
        for path in sorted((CORPUS / folder).glob("*.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            corpus[key][record[key]["id"]] = record
    return corpus


def select_datasets(corpus: dict) -> tuple[dict[str, list[dict]], list[tuple[str, str]], list[tuple[str, str]]]:
    """p-OCV datasets grouped by electrode spec, plus the skipped groups and excluded datasets."""
    p_ocv = [iri for iri, rec in corpus["test_spec"].items() if rec["test_spec"].get("handle") == P_OCV_PROTOCOL_HANDLE]
    if len(p_ocv) != 1:
        raise SystemExit(f"expected one p-OCV test spec in the corpus, found {len(p_ocv)}")
    groups: dict[str, list[dict]] = defaultdict(list)
    skipped: dict[str, str] = {}
    excluded: list[tuple[str, str]] = []
    for iri, record in sorted(corpus["dataset"].items()):
        body = record["dataset"]
        tests = [a for a in body.get("about", []) if a in corpus["test"]]
        if len(tests) != 1:
            continue  # the collection record, which describes no single test
        test = corpus["test"][tests[0]]["test"]
        if test.get("protocol_id") != p_ocv[0]:
            continue
        cell = corpus["cell_instance"][test["cell_id"]]["cell_instance"]
        if cell["id"] not in body["about"]:
            raise SystemExit(f"{iri}: the dataset and its test name different cells")
        electrode = corpus["electrode"][cell["working_electrode_id"]]["electrode"]
        spec = corpus["electrode_spec"][electrode["electrode_spec_id"]]["electrode_spec"]
        kind = spec.get("active_material_kind")
        if kind not in SINGLE_PHASE:
            skipped[spec["id"]] = f"{spec['name']}: {kind} is not a single-phase material"
            continue
        conformance = test.get("conformance") or {}
        if conformance.get("status") == "non-conformant":
            excluded.append((iri, f"{test['name']}: {conformance.get('note', 'non-conformant')}"))
            continue
        distribution = body["distributions"][0]
        groups[spec["id"]].append({
            "iri": iri, "name": body["name"], "file": distribution["name"],
            "md5": distribution["checksum"]["value"], "test": test, "cell": cell, "electrode": electrode,
            "cell_spec": corpus["cell_spec"][cell["cell_spec_id"]], "citations": body.get("citations", []),
        })
    return dict(groups), sorted(skipped.items()), excluded


# ------------------------------------------------------------------- extraction


def read_columns(path: Path) -> tuple[np.ndarray, ...]:
    """Current, voltage and cumulative capacity, read row group by row group."""
    handle = pq.ParquetFile(path)
    parts: list[list[np.ndarray]] = [[], [], []]
    for group in range(handle.num_row_groups):
        table = handle.read_row_group(group, columns=[xp.C_CURR, xp.C_VOLT, xp.C_CAP])
        for k in range(3):
            parts[k].append(table.column(k).to_numpy())
    return tuple(np.concatenate(p) for p in parts)


def half_cycles(current: np.ndarray, voltage: np.ndarray, lower: float, upper: float) -> list[dict]:
    """Runs of nonzero current, with their direction and whether they end at their cut-off."""
    sign = np.where(np.abs(current) < xp.REST_CURRENT_A, 0, np.sign(current)).astype(int)
    change = np.flatnonzero(np.diff(sign)) + 1
    starts = np.concatenate(([0], change))
    ends = np.concatenate((change, [sign.size]))
    out = []
    for start, end in zip(starts, ends):
        if sign[start] == 0 or end - start < MIN_HALF_CYCLE_ROWS:
            continue
        rising = voltage[end - 1] > voltage[start]
        # Positive current must raise the working electrode's potential, negative lower it.
        if rising != (sign[start] > 0):
            raise ValueError(
                f"rows {start}-{end}: current sign {sign[start]:+d} but voltage went "
                f"{voltage[start]:.4f} -> {voltage[end - 1]:.4f} V"
            )
        branch = "delithiation" if sign[start] > 0 else "lithiation"
        cutoff = upper if branch == "delithiation" else lower
        out.append({"branch": branch, "start": int(start), "end": int(end),
                    "at_cutoff": abs(float(voltage[end - 1]) - cutoff) <= CUTOFF_TOLERANCE_V})
    return out


def first_full_cycle(runs: list[dict]) -> tuple[dict, dict]:
    """The first two consecutive full half-cycles; a full one starts where the one before ended at a cut-off."""
    full = [k > 0 and runs[k]["at_cutoff"] and runs[k - 1]["at_cutoff"] and runs[k - 1]["branch"] != runs[k]["branch"]
            for k in range(len(runs))]
    for k in range(1, len(runs)):
        if full[k - 1] and full[k]:
            return runs[k - 1], runs[k]
    raise ValueError("no full cycle: no two consecutive half-cycles run between the cut-offs")


def branch_on_grid(capacity: np.ndarray, voltage: np.ndarray, branch: str, grid: np.ndarray) -> tuple[np.ndarray, float]:
    """Voltage on the x grid, and the branch's capacity in Ah."""
    q = np.abs(capacity - capacity[0])
    if np.any(np.diff(q) < 0):
        raise ValueError(f"{branch}: cumulative capacity is not monotonic within the half-cycle")
    window = float(q[-1])
    if window <= 0:
        raise ValueError(f"{branch}: no capacity passed")
    x = q / window if branch == "lithiation" else 1.0 - q / window
    order = np.argsort(x, kind="stable")
    x, v = x[order], voltage[order]
    unique, inverse = np.unique(x, return_inverse=True)
    v_mean = np.bincount(inverse, weights=v) / np.bincount(inverse)
    return np.interp(grid, unique, v_mean), window


def extract(item: dict, cache: Path, grid: np.ndarray) -> dict:
    path = xp.fetch(item["file"], item["md5"], cache)
    current, voltage, capacity = read_columns(path)
    props = item["cell_spec"]["properties"]
    lower = float(props["discharging_cutoff_voltage"]["value"])
    upper = float(props["charging_voltage"]["value"])
    first, second = first_full_cycle(half_cycles(current, voltage, lower, upper))
    out: dict[str, Any] = {"order": f"{first['branch']} then {second['branch']}"}
    for run in (first, second):
        s, e = run["start"], run["end"]
        curve, window = branch_on_grid(capacity[s:e], voltage[s:e], run["branch"], grid)
        out[run["branch"]] = curve
        out[f"{run['branch']}_capacity_mAh"] = window * 1000.0
    return out


# ----------------------------------------------------------------------- records


def batch_slug(kind: str, label: str) -> str:
    return f"{kind}--flores2026-{label.lower()}--p-ocv"


def batch_name(kind: str, label: str) -> str:
    return f"Flores 2026 {label} (p-OCV) - {kind}"


def one(values: set, what: str) -> Any:
    if len(values) != 1:
        raise SystemExit(f"expected one {what} across the batch, found {sorted(map(str, values))}")
    return next(iter(values))


def build_record(spec: dict, items: list[dict], curves: list[dict], grid: np.ndarray) -> tuple[str, dict, dict]:
    from battinfo.api import create_parameter_set

    kind = spec["active_material_kind"]
    label = one({i["electrode"]["batch_id"] for i in items}, "electrode batch label")
    doi = one({c["doi"] for i in items for c in i["citations"] if c.get("doi")}, "dataset citation DOI")
    conditions = {key: one({json.dumps(i["test"]["conditions"][key], sort_keys=True) for i in items}, key)
                  for key in ("ambient_temperature", "voltage_reference")}
    conditions = {key: json.loads(value) for key, value in conditions.items()}
    based_on = sorted(i["iri"] for i in items)
    n = len(items)

    mean = {b: np.mean([c[b] for c in curves], axis=0) for b in BRANCHES}
    mean["average"] = (mean["lithiation"] + mean["delithiation"]) / 2.0
    x = [round(float(v), 6) for v in grid]
    cells = f"{n} cell{'s' if n > 1 else ''}"
    methods = {
        "lithiation": f"Lithiation branch of the first full p-OCV cycle, mean of {cells}, computed by {SCRIPT}.",
        "delithiation": f"Delithiation branch of the first full p-OCV cycle, mean of {cells}, computed by {SCRIPT}.",
        "average": f"Mean of the lithiation and delithiation branches of this batch, computed by {SCRIPT}.",
    }
    claims = []
    for branch in (*BRANCHES, "average"):
        claims.append({
            "parameter": "ocp",
            "curve": {
                "x_quantity": "stoichiometry", "x": x,
                "y": [round(float(v), VOLTAGE_DIGITS) for v in mean[branch]],
                "y_unit": "V", "interpolation": "linear", "branch": branch,
            },
            # The average is computed from the two measured branch curves.
            "provenance_class": "derived" if branch == "average" else "measured",
            "method": f"{methods[branch]} {X_SENTENCE}",
            "conditions": conditions,
            "is_based_on": based_on,
        })
    material = KIND_LABELS[kind]
    record = create_parameter_set(
        name=batch_name(kind, label),
        material_spec_id=spec["active_material_spec_id"],
        scope="material",
        claims=claims,
        description=(
            f"Open-circuit potential of the Flores 2026 {material} powder vs Li/Li+, from p-OCV at C/50 on "
            f"{n} coin half-cells with {label} electrodes ({spec['id']}). Each branch comes from the first full "
            "cycle (the first lithiation and delithiation that each run between the voltage cut-offs) and is "
            "averaged across the cells."
        ),
        source_type="measurement",
        citation=f"https://doi.org/{doi}",
        citation_doi=doi,
        retrieved_at=RETRIEVED_AT,
        notes=[f"Computed by {SCRIPT} from the BDF files of the datasets each claim names in is_based_on, "
               "checked against their md5 checksums."],
        license=LICENSE,
        # New records mint under BattINFO's default base, /id/1001/. The records they name (the material
        # spec, the datasets) keep the form they are published under, which is what the registry matches.
    )
    record["provenance"]["source_name"] = CREDIT
    stats = {"label": label, "kind": kind, "datasets": based_on, "mean": mean,
             "cited": [spec["active_material_spec_id"], spec["id"], *based_on]}
    return batch_slug(kind, label), record, stats


def require_is_based_on() -> None:
    """Stop unless the installed BattINFO's parameter-set schema takes is_based_on on claims."""
    from battinfo.validate.schema import schema_for_rel_path

    claim = schema_for_rel_path("parameter-set.schema.json")["$defs"]["Claim"]["properties"]
    if "is_based_on" not in claim:
        raise SystemExit("this BattINFO's parameter-set schema has no is_based_on; install a BattINFO that has it")


def validate(record: dict) -> list[str]:
    from battinfo.validate import validate_record_report

    return [str(e) for e in validate_record_report(record, policy="strict").errors]


def check_live(iris: list[str]) -> list[str]:
    """Problems with any cited IRI: unreachable, or answering as superseded."""
    problems = []
    for iri in iris:
        request = urllib.request.Request(iri, headers={"Accept": "application/ld+json", "User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                doc = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - any failure means the IRI cannot be cited
            problems.append(f"{iri}: {type(exc).__name__}: {exc}")
            continue
        if doc.get("owl:deprecated") or doc.get("dcterms:isReplacedBy"):
            problems.append(f"{iri}: superseded by {doc.get('dcterms:isReplacedBy')}")
    return problems


def write_plot(path: Path, title: str, grid: np.ndarray, curves: list[dict], items: list[dict], mean: dict) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"lithiation": ("#2a78d6", "#86b6ef"), "delithiation": ("#eb6834", "#f3a583")}
    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=150)
    for branch in BRANCHES:
        strong, light = colors[branch]
        for item, curve in zip(items, curves):
            ax.plot(grid, curve[branch], color=light, linewidth=1.0,
                    label=f"{branch}, cell {item['cell']['serial_number']}")
        ax.plot(grid, mean[branch], color=strong, linewidth=2.0, label=f"{branch}, mean")
    ax.plot(grid, mean["average"], color="#444444", linewidth=1.2, linestyle="--", label="mean of branches")
    ax.set_xlabel("Lithium fraction x / 1")
    ax.set_ylabel("Potential vs Li/Li+ / V")
    ax.set_title(title, fontsize=10)
    ax.grid(color="#dddddd", linewidth=0.6)
    ax.legend(fontsize=7, frameon=False)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)


# -------------------------------------------------------------------------- main


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--cache", required=True, type=Path, help="folder for the downloaded BDF files")
    parser.add_argument("--dry-run", action="store_true", help="build and validate; write no records")
    parser.add_argument("--plots", type=Path, help="write a quick-look PNG per batch to this folder")
    parser.add_argument("--check-live", action="store_true", help="fetch every cited IRI and stop on a superseded one")
    args = parser.parse_args()

    require_is_based_on()
    corpus = load_corpus()
    groups, skipped, excluded = select_datasets(corpus)
    grid = np.linspace(0.0, 1.0, GRID_POINTS)

    failures = 0
    for spec_iri in sorted(groups, key=lambda s: corpus["electrode_spec"][s]["electrode_spec"]["name"]):
        spec = corpus["electrode_spec"][spec_iri]["electrode_spec"]
        items = sorted(groups[spec_iri], key=lambda i: i["iri"])
        curves = [extract(item, args.cache, grid) for item in items]
        slug, record, stats = build_record(spec, items, curves, grid)
        errors = validate(record)
        body = record["parameter_set"]
        print(f"{slug}  {body['id']}")
        print(f"  {body['name']}  [{len(items)} dataset(s)]")
        for item, curve in zip(items, curves):
            print(f"    {item['iri']}  cell {item['cell']['serial_number']}  {curve['order']}  "
                  f"lith {curve['lithiation_capacity_mAh']:.3f} mAh, delith {curve['delithiation_capacity_mAh']:.3f} mAh")
        for branch in (*BRANCHES, "average"):
            y = stats["mean"][branch]
            print(f"    {branch:12s} {float(np.min(y)):.4f} - {float(np.max(y)):.4f} V")
        if errors:
            failures += 1
            print("  INVALID: " + "; ".join(errors))
        if args.check_live:
            problems = check_live(stats["cited"])
            if problems:
                failures += 1
                print("  NOT LIVE: " + "; ".join(problems))
        if args.plots:
            write_plot(args.plots / f"{slug}.png", body["name"], grid, curves, items, stats["mean"])
        if not args.dry_run and not errors:
            out = OUT_DIR / slug / "record.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(record, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                           encoding="utf-8", newline="\n")
    for spec_iri, reason in skipped:
        print(f"skipped {spec_iri}: {reason}")
    for iri, reason in excluded:
        print(f"excluded {iri}: {reason}")
    if args.dry_run:
        print("dry run: no records written")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
