#!/usr/bin/env python3
"""Record the published IRI of every Flores record under a stable logical key.

Several BattINFO identity seeds include a record's display name (material spec,
electrode spec, test spec, test, and through them the material lots, electrodes
and datasets; the collection seeds from its access URL and name). Renaming the
records for the 2026-10-08 naming ruling would therefore mint new IRIs for
records that are already published. Names are display text and must never move
an identity, so the build pins every record to the IRI it was published with.

This script reads the committed records (the published v5 corpus) and writes
published-iris.json, keyed by facts that do not change with a rename:

    material_spec  kind                      e.g. "graphite"
    material       kind + lot label          e.g. "graphite|study powder batch"
    electrode_spec design label              e.g. "Gr-AQ-1"
    electrode      sample id                 e.g. "063b77"
    cell_spec      design label
    cell           sample id
    test_spec      protocol key              e.g. "gitt"
    test           sample id + protocol key  e.g. "063b77|gitt"
    dataset        sample id + protocol key, and "collection" for the collection

Run it once, from the records as published, before the first renamed build; it
refuses to run once the records carry the new titles. build_records.py reads the
file and fails if any record would be minted under a different IRI.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RECORDS = HERE / "records"
OUT = HERE / "published-iris.json"

PROTOCOL_KEY = {"p-OCV": "p-ocv", "p-OCV hold": "p-ocvhold", "GITT": "gitt", "GITT hold": "gitthold"}
# The published electrode-spec titles, by design label (the pre-2026-10-08 DESIGN_NAME).
OLD_DESIGN_NAME = {
    "Graphite electrode, aqueous processed (IntelLiGent, SINTEF)": "Gr-AQ-1",
    "Silicon electrode, aqueous processed (IntelLiGent, SINTEF)": "Si-AQ-1",
    "Silicon-graphite electrode, aqueous processed, lower Si % (IntelLiGent batch 1, SINTEF)": "SiGr-AQ-1",
    "Silicon-graphite electrode, aqueous processed, higher Si % (IntelLiGent batch 2, SINTEF)": "SiGr-AQ-2",
    "Silicon-graphite electrode, aqueous processed, higher Si %, 'B/Silicon Graphite' active material "
    "(IntelLiGent batch 2, SINTEF)": "SiGr-AQ-3",
    "LNMO electrode, aqueous processed (IntelLiGent batch 1, SINTEF)": "LNMO-AQ-1",
    "LNMO electrode, aqueous processed (IntelLiGent batch 2, SINTEF)": "LNMO-AQ-2",
    "LNMO electrode, NMP processed (IntelLiGent batch 1, SINTEF)": "LNMO-NMP-1",
    "LNMO electrode, NMP processed (IntelLiGent batch 2, SINTEF)": "LNMO-NMP-2",
    "LFP electrode, NMP processed (commercial, Gelon LIB)": "LFP-NMP-1",
    "NMC111 electrode, NMP processed (commercial, Customcells)": "NMC111-NMP-1",
    "NMC532 electrode, NMP processed (commercial, Gelon LIB)": "NMC532-NMP-1",
}


def body(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    return next(v for v in doc.values() if isinstance(v, dict) and "id" in v)


def main() -> int:
    if OUT.exists() and "--force" not in sys.argv:
        print(f"{OUT.name} exists; pins are written once. Pass --force to overwrite.")
        return 1
    pins: dict[str, dict[str, str]] = {k: {} for k in (
        "material_spec", "material", "electrode_spec", "electrode", "cell_spec", "cell",
        "test_spec", "test", "dataset")}

    spec_kind: dict[str, str] = {}
    for path in sorted((RECORDS / "material-spec").glob("*.json")):
        b = body(path)
        if b.get("name", "").endswith(" material spec"):
            raise SystemExit("records already carry the new titles; pins must come from the published ones")
        pins["material_spec"][b["kind"]] = b["id"]
        spec_kind[b["id"]] = b["kind"]
    for path in sorted((RECORDS / "material").glob("*.json")):
        b = body(path)
        pins["material"][f"{spec_kind[b['material_spec_id']]}|{b['lot_id']}"] = b["id"]
    for path in sorted((RECORDS / "electrode-spec").glob("*.json")):
        b = body(path)
        pins["electrode_spec"][OLD_DESIGN_NAME[b["name"]]] = b["id"]
    for path in sorted((RECORDS / "electrode").glob("*.json")):
        b = body(path)
        pins["electrode"][b["name"].rsplit(" ", 1)[1]] = b["id"]
    for path in sorted((RECORDS / "cell-spec").glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        # A cell spec record is flat: its id and electrode link sit at the top level.
        iri = doc.get("id") or body(path)["id"]
        design = next(k for k, v in pins["electrode_spec"].items() if v == doc["working_electrode_spec_id"])
        pins["cell_spec"][design] = iri
    for path in sorted((RECORDS / "cell-instance").glob("*.json")):
        b = body(path)
        pins["cell"][b["serial_number"]] = b["id"]
    for path in sorted((RECORDS / "test-protocol").glob("*.json")):
        b = body(path)
        pins["test_spec"][PROTOCOL_KEY[b["name"]]] = b["id"]
    test_re = re.compile(r"^\S+ cell (?P<hex>[0-9a-f]{6}) (?P<proto>.+)$")
    for path in sorted((RECORDS / "test").glob("*.json")):
        b = body(path)
        m = test_re.match(b["name"])
        pins["test"][f"{m['hex']}|{PROTOCOL_KEY[m['proto']]}"] = b["id"]
    ds_re = re.compile(r"^\S+ cell (?P<hex>[0-9a-f]{6}) (?P<proto>.+) half-cell OCV \(BDF\)$")
    for path in sorted((RECORDS / "dataset").glob("*.json")):
        b = body(path)
        if "DatasetSeries" in (b.get("additional_type") or []):
            pins["dataset"]["collection"] = b["id"]
            continue
        m = ds_re.match(b["name"])
        pins["dataset"][f"{m['hex']}|{PROTOCOL_KEY[m['proto']]}"] = b["id"]

    counts = {k: len(v) for k, v in pins.items()}
    total = sum(counts.values())
    print(f"pinned {total} IRIs: {counts}")
    if total != 425:
        raise SystemExit(f"expected 425 records, pinned {total}")
    OUT.write_text(json.dumps(pins, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
