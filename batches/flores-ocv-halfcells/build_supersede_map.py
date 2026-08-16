#!/usr/bin/env python3
"""Map every PUBLISHED identifier of this dataset onto its corpus-v3 successor.

The 319 records of corpus v1 are live in the Battery Genome registry. Corpus v2
retired 21 of them (the material layer, replaced by first-class electrodes) and
corpus v3 re-seeds 144 more (D1: three cell specs that each covered two electrode
designs become six, and the 47 cells, 47 tests and 47 datasets seeded from them
follow). A republish therefore has to state, for every live identifier, whether it
keeps its content, is replaced by one successor, or is split across several.

This writes that statement as ``superseded/supersede-map.json``. It is generated,
not hand-maintained, and every row is derived from a natural key that survives the
re-seeding:

  cell spec       model string      ("... (intelligent1)" -> "... (intelligent1, LNMO-AQ-1)")
  cell instance   serial number     (the 6-character id from the BDF file name)
  test            test name         ("LNMO-AQ-1 cell 21a280 p-OCV")
  dataset         dataset name
  test protocol   protocol name
  material (v1)   lot id            = the public electrode label -> electrode batch_id
  material spec   (kind, grade)     = (active material, electrode source) -> electrode specs

Sources. The v1 material layer is in ``superseded/v1/``. The other 298 published
identifiers are read from the v2 tree, where they are unchanged from v1 - v2 edited
cell-spec content but no identifier and no natural key. The v2 commit is pinned so
the run is reproducible after this branch moves on.

Run:  python build_supersede_map.py      (after build_records.py)
"""
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RECORDS = HERE / "records"
SUPERSEDED = HERE / "superseded"

FILENAME_RE = re.compile(
    r"sintef__sintef-(?P<mat>[a-z0-9]+)-R2032-(?P<src>[a-z0-9]+)-(?P<hex>[0-9a-f]{6})"
    r"__(?P<date>\d{8})__(?P<proto>[a-z-]+)__RT\.bdf\.parquet"
)

# The corpus-v2 tree: same identifiers as the published v1 corpus for every type
# except the material layer, which v2 retired into superseded/v1/.
V2_COMMIT = "a798b71"
V2_PREFIX = "batches/flores-ocv-halfcells/records"

# subdirectory -> (record body key, natural-key field)
PUBLISHED_TYPES = {
    "cell-spec": ("cell_spec", "model"),
    "cell-instance": ("cell_instance", "serial_number"),
    "test-protocol": ("test_spec", "name"),
    "test": ("test", "name"),
    "dataset": ("dataset", "name"),
}


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def read_v2(subdir: str) -> list[dict]:
    listing = git("ls-tree", "--name-only", V2_COMMIT, f"{V2_PREFIX}/{subdir}/").split()
    return [json.loads(git("show", f"{V2_COMMIT}:{name}")) for name in sorted(listing)]


def read_v3(subdir: str) -> list[dict]:
    return [json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((RECORDS / subdir).glob("*.json"))]


def read_local(directory: Path) -> list[dict]:
    return [json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(directory.glob("*.json"))]


def entry(published: str, published_type: str, key: str,
          successors: list[str], successor_type: str, note: str) -> dict:
    if successors == [published]:
        status = "retained"
    elif len(successors) == 1:
        status = "replaced"
    else:
        status = "split"
    return {
        "published_id": published,
        "published_type": published_type,
        "natural_key": key,
        "status": status,
        "successor_type": successor_type,
        "successors": successors,
        "note": note,
    }


def main() -> int:
    entries: list[dict] = []

    # --- the four types whose successor is found by an unchanged natural key ----
    for subdir, (body_key, key_field) in PUBLISHED_TYPES.items():
        if subdir == "cell-spec":
            continue
        v3_by_key = {r[body_key][key_field]: r[body_key]["id"] for r in read_v3(subdir)}
        for record in read_v2(subdir):
            body = record[body_key]
            key = body[key_field]
            successor = v3_by_key.get(key)
            if successor is None:
                raise SystemExit(f"no v3 successor for {subdir} {key!r}")
            entries.append(entry(
                body["id"], body_key, key, [successor], body_key,
                "identifier held" if successor == body["id"]
                else "re-seeded: its cell spec was split (D1), and the identity seed of "
                     "this record starts at the cell spec",
            ))

    # --- cell specs: a v1 model string is a prefix of its v3 successors' ---------
    v3_specs = [r["cell_spec"] for r in read_v3("cell-spec")]
    for record in read_v2("cell-spec"):
        body = record["cell_spec"]
        model = body["model"]
        successors = sorted(
            spec["id"] for spec in v3_specs
            if spec["model"] == model or spec["model"].startswith(model[:-1] + ", ")
        )
        if not successors:
            raise SystemExit(f"no v3 successor for cell spec {model!r}")
        entries.append(entry(
            body["id"], "cell_spec", model, successors, "cell_spec",
            "identifier held: this spec already covered exactly one electrode design"
            if successors == [body["id"]]
            else "split (D1): this spec covered two electrode designs, so it becomes two "
                 "specs, each citing one",
        ))

    # --- the v1 material layer, retired by the electrode remodel (v2) ------------
    v3_batches = {r["electrode"]["batch_id"]: r["electrode"]["id"]
                  for r in read_v3("electrode")}
    for record in read_local(SUPERSEDED / "v1" / "material"):
        body = record["material"]
        label = body["lot_id"]
        successor = v3_batches.get(label)
        if successor is None:
            raise SystemExit(f"no v3 electrode for batch {label!r}")
        entries.append(entry(
            body["id"], "material", label, [successor], "electrode",
            "a coated electrode batch, not a material lot: replaced by the electrode "
            "record for the same public label",
        ))

    # A v1 material-spec was an (active material, electrode source) product. Neither
    # token is a field on a v3 electrode spec - the source is part of the design's
    # name - so the join runs through the batches: metadata.csv gives public label ->
    # electrode source, the electrode record gives public label -> design.
    src_by_label: dict[str, str] = {}
    with (HERE / "sources" / "metadata.csv").open(encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            match = FILENAME_RE.match(row["BDF names"])
            if match is None:
                raise SystemExit(f"unrecognised BDF filename: {row['BDF names']}")
            src_by_label[row["Public Labels"].strip()] = match["src"]
    kind_by_spec = {r["electrode_spec"]["id"]: r["electrode_spec"]["kind"]
                    for r in read_v3("electrode-spec")}
    v3_specs_by_source: dict[tuple[str, str], list[str]] = defaultdict(list)
    for record in read_v3("electrode"):
        body = record["electrode"]
        spec_id = body["electrode_spec_id"]
        v3_specs_by_source[(kind_by_spec[spec_id], src_by_label[body["batch_id"]])].append(spec_id)
    for record in read_local(SUPERSEDED / "v1" / "material-spec"):
        body = record["material_spec"]
        key = (body["kind"], body["grade"])
        successors = sorted(v3_specs_by_source.get(key, []))
        if not successors:
            raise SystemExit(f"no v3 electrode-spec for {key}")
        entries.append(entry(
            body["id"], "material_spec", f"{key[0]} / {key[1]}", successors, "electrode_spec",
            "an electrode product, not a powder: replaced by the electrode spec(s) of the "
            "same active material and electrode source",
        ))

    entries.sort(key=lambda e: (e["published_type"], e["published_id"]))
    by_status = defaultdict(int)
    for item in entries:
        by_status[item["status"]] += 1

    document = {
        "batch": "flores-ocv-halfcells",
        "zenodo_record": "https://doi.org/10.5281/zenodo.20086298",
        "published_corpus": {
            "version": "v1",
            "records": len(entries),
            "state": "live in the Battery Genome registry",
        },
        "staged_corpus": {
            "version": "v3",
            "branch": "data/flores-ocv-halfcells",
            "records": sum(len(list((RECORDS / d).glob("*.json")))
                           for d in sorted(p.name for p in RECORDS.iterdir() if p.is_dir())),
        },
        "generated_by": "build_supersede_map.py",
        "v2_baseline_commit": V2_COMMIT,
        "status_counts": dict(sorted(by_status.items())),
        "statuses": {
            "retained": "same identifier in v3; the record content changed but the identity did not",
            "replaced": "one successor under a new identifier",
            "split": "more than one successor: one published identifier named several things",
        },
        "entries": entries,
    }
    out = SUPERSEDED / "supersede-map.json"
    out.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out.relative_to(HERE)}: {len(entries)} published identifiers")
    for status, count in sorted(by_status.items()):
        print(f"  {status:10s} {count}")
    new_ids = sum(len(e["successors"]) for e in entries if e["status"] != "retained")
    print(f"  successors under new identifiers: {new_ids}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
