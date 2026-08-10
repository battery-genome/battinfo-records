#!/usr/bin/env python3
"""Build the Zenodo-facing semantic-layer bundle from the authored workspace.

Run AFTER build_records.py. Produces (all under this directory):

  records/                        tracked copy of the 319 canonical BattINFO JSON
                                  records (the workspace .battinfo/ dir is gitignored).
  bundle/jsonld/                  per-record JSON-LD for all seven record types.
  bundle/deposit.jsonld           one combined JSON-LD graph for the whole deposit.
  bundle/ro-crate-metadata.json   deposit-level RO-Crate metadata.
  bundle/validation-report.txt    per-type error/warning/SHACL counts over records/.
  bundle/emission-spot-checks.txt worked JSON-LD examples for the review trail.
  bundle/gold-standard-report.txt captured output of the RO-Crate gold-standard check.

Deterministic: re-running reproduces byte-identical output.
"""
from __future__ import annotations

import collections
import contextlib
import io
import json
import shutil
from pathlib import Path

import battinfo as B

HERE = Path(__file__).resolve().parent
WS_RECORDS = HERE / ".battinfo" / "records"
RECORDS = HERE / "records"
BUNDLE = HERE / "bundle"

DOI = "10.5281/zenodo.20086298"
CONCEPT_DOI = "10.5281/zenodo.19107294"
TITLE = ("Half-Cell Open-Circuit Voltage of Several Lithium-Ion Battery Active Materials "
         "- BattINFO semantic layer")
DESCRIPTION = (
    "Machine-readable BattINFO semantic layer describing the electrode materials, cells, "
    "electrochemical protocols, tests and datasets of Zenodo record " + DOI + ". "
    "Each of the 95 BDF parquet files is described by a linked material-spec / material / "
    "cell-spec / cell-instance / test-protocol / test / dataset record chain; datasets "
    "reference the Zenodo files by URL and md5 checksum."
)
KEYWORDS = ["open circuit voltage", "OCV", "GITT", "quasi-OCV", "half-cell", "BattINFO",
            "battery data format", "LFP", "NMC", "LNMO", "graphite", "silicon"]

CREATORS = [
    {"name": "Flores, Eibar", "orcid": "0000-0003-2954-1233", "affiliation": "SINTEF"},
    {"name": "Krishnamurthi, Sridevi", "orcid": "0009-0006-0805-6713", "affiliation": "SINTEF"},
    {"name": "Stokes-Rodriguez, Killian", "orcid": "0000-0002-6299-1319", "affiliation": "SINTEF"},
    {"name": "Guldahl, Julie Cathrine", "orcid": "0009-0005-4059-7715", "affiliation": "SINTEF"},
    {"name": "Hakim, Charifa", "orcid": "0000-0003-0931-5466", "affiliation": "SINTEF"},
    {"name": "Clark, Simon", "orcid": "0000-0002-8758-6109", "affiliation": "SINTEF"},
    {"name": "Wagner, Nils Peter", "orcid": "0000-0002-8014-4324", "affiliation": "SINTEF"},
    {"name": "Obrador, Sergi", "orcid": "0009-0003-1413-0770",
     "affiliation": "Institut de Recerca de l'Energia de Catalunya"},
    {"name": "Bernabeu Santisteban, Andres", "orcid": "0000-0001-9591-6422",
     "affiliation": "Institut de Recerca de l'Energia de Catalunya"},
]

# Directory name -> record_to_jsonld type. ws.export() covers five of these; the two
# material types are emitted here directly (see gap G5 in READINESS-REPORT.md).
RECORD_TYPES = {
    "material-spec": "material-spec",
    "material": "material",
    "cell-spec": "cell-spec",
    "cell-instance": "cell-instance",
    "test-protocol": "test-protocol",
    "test": "test",
    "dataset": "dataset",
}


def mirror_records() -> int:
    if RECORDS.exists():
        shutil.rmtree(RECORDS)
    n = 0
    for src in sorted(WS_RECORDS.rglob("*.json")):
        dst = RECORDS / src.relative_to(WS_RECORDS)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
        n += 1
    return n


def emit_jsonld() -> int:
    out_root = BUNDLE / "jsonld"
    n = 0
    for directory, record_type in RECORD_TYPES.items():
        src_dir = RECORDS / directory
        if not src_dir.is_dir():
            continue
        dst_dir = out_root / directory
        dst_dir.mkdir(parents=True, exist_ok=True)
        for src in sorted(src_dir.glob("*.json")):
            raw = json.loads(src.read_text(encoding="utf-8"))
            doc = B.record_to_jsonld(raw, record_type, context="inline")
            (dst_dir / f"{src.stem}.jsonld").write_text(
                json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            n += 1
    return n


def validation_report() -> str:
    lines = ["Validation of records/ (battinfo validate_record_report + SHACL)", ""]
    grand = collections.Counter()
    for directory, record_type in RECORD_TYPES.items():
        src_dir = RECORDS / directory
        if not src_dir.is_dir():
            continue
        n = errors = warns = shacl_bad = 0
        detail: collections.Counter = collections.Counter()
        for src in sorted(src_dir.glob("*.json")):
            n += 1
            raw = json.loads(src.read_text(encoding="utf-8"))
            report = B.validate_record_report(raw, source_root=RECORDS)
            for issue in report.issues:
                if issue.severity == "error":
                    errors += 1
                else:
                    warns += 1
                detail[(issue.severity, issue.code)] += 1
            shacl = B.validate_shacl_report(
                B.record_to_jsonld(raw, record_type, context="inline"))
            if not (shacl.conforms if hasattr(shacl, "conforms") else bool(shacl)):
                shacl_bad += 1
        grand["records"] += n
        grand["errors"] += errors
        grand["warnings"] += warns
        grand["shacl"] += shacl_bad
        lines.append(f"{record_type:15s} records={n:3d}  errors={errors}  warnings={warns}  "
                     f"shacl_non_conforming={shacl_bad}")
        for (severity, code), count in sorted(detail.items()):
            lines.append(f"                  {count:3d}x {severity} {code}")
    lines += ["", f"TOTAL records={grand['records']}  errors={grand['errors']}  "
                  f"warnings={grand['warnings']}  shacl_non_conforming={grand['shacl']}"]
    return "\n".join(lines) + "\n"


def _pick(directory: str, predicate) -> dict:
    for src in sorted((RECORDS / directory).glob("*.json")):
        raw = json.loads(src.read_text(encoding="utf-8"))
        if predicate(raw):
            return raw
    raise SystemExit(f"no {directory} record matched the spot-check predicate")


def spot_checks() -> str:
    out = io.StringIO()

    def section(title: str, doc: dict) -> None:
        out.write(f"{'=' * 78}\n{title}\n{'=' * 78}\n")
        out.write(json.dumps({k: v for k, v in doc.items() if k != "@context"},
                             indent=2, ensure_ascii=False))
        out.write("\n\n")

    # 1. Half-cell typing on a cell spec, and the material spec its working
    #    electrode links to (kind -> EMMO class + chemical-substance + exactMatch).
    spec = _pick("cell-spec", lambda r: r["cell_spec"]["cell_configuration"] == "half_cell"
                 and "Silicon R2032" in r["cell_spec"]["model"])
    spec_ld = B.record_to_jsonld(spec, "cell-spec", context="inline")
    section("SPOT CHECK 1a - cell spec: half-cell device typing + electrode -> material spec",
            spec_ld)
    material_iri = (spec["positive_electrode"]["coating"]["component"]["active_material"][0]
                    ["material_spec_id"])
    ms = _pick("material-spec", lambda r: r["material_spec"]["id"] == material_iri)
    section("SPOT CHECK 1b - the linked material spec: EMMO class, chemical-substance "
            "anchor, external exactMatch", B.record_to_jsonld(ms, "material-spec", context="inline"))
    lot = _pick("material", lambda r: r["material"]["material_spec_id"] == material_iri)
    section("SPOT CHECK 1c - a material lot of that product: processing route + as-built "
            "batch figures", B.record_to_jsonld(lot, "material", context="inline"))

    # 2. Typed method class on a protocol.
    for name in ("GITT", "p-OCV"):
        protocol = _pick("test-protocol", lambda r, n=name: r["test_spec"]["name"] == n)
        section(f"SPOT CHECK 2 - test protocol {name}: typed EMMO method + process graph",
                B.record_to_jsonld(protocol, "test-protocol", context="inline"))

    # 3. A dataset: distribution + checksum + license + nine-contributor attribution.
    dataset = _pick("dataset", lambda r: r["dataset"]["distributions"])
    section("SPOT CHECK 3a - dataset JSON-LD: dcat distribution + spdx checksum + license "
            "+ contributors", B.record_to_jsonld(dataset, "dataset", context="inline"))
    out.write(f"{'=' * 78}\nSPOT CHECK 3b - the same dataset's canonical record (the JSON-LD\n"
              f"emitter omits description/keywords/variable_measured/citations/byteSize;\n"
              f"see gap G3 in READINESS-REPORT.md)\n{'=' * 78}\n")
    out.write(json.dumps(dataset, indent=2, ensure_ascii=False))
    out.write("\n")
    return out.getvalue()


def main() -> int:
    if not WS_RECORDS.exists():
        raise SystemExit("Run build_records.py first (no .battinfo/records/ found).")
    n = mirror_records()
    print(f"mirrored {n} canonical records -> records/")

    if BUNDLE.exists():
        shutil.rmtree(BUNDLE)
    BUNDLE.mkdir(parents=True)

    n_ld = emit_jsonld()
    print(f"emitted {n_ld} JSON-LD documents -> bundle/jsonld/ (all seven record types)")

    (BUNDLE / "validation-report.txt").write_text(validation_report(), encoding="utf-8")
    (BUNDLE / "emission-spot-checks.txt").write_text(spot_checks(), encoding="utf-8")
    print("wrote bundle/validation-report.txt, bundle/emission-spot-checks.txt")

    ws = B.workspace(root=str(HERE), registry_url=None)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        ws.preview_jsonld(output=str(BUNDLE / "deposit.jsonld"),
                          title=TITLE, description=DESCRIPTION, license="cc-by-4.0",
                          creators=CREATORS, keywords=KEYWORDS,
                          is_version_of=f"https://doi.org/{CONCEPT_DOI}")
        ws.preview_rocrate(output=str(BUNDLE / "ro-crate-metadata.json"),
                           title=TITLE, description=DESCRIPTION, license="cc-by-4.0",
                           creators=CREATORS)
    (BUNDLE / "gold-standard-report.txt").write_text(buf.getvalue(), encoding="utf-8")
    print("wrote bundle/deposit.jsonld, bundle/ro-crate-metadata.json, "
          "bundle/gold-standard-report.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
