#!/usr/bin/env python3
"""Build the Zenodo-facing semantic-layer bundle from the authored workspace.

Run AFTER build_records.py. Produces (all under this directory):

  records/                       tracked copy of the 305 canonical BattINFO JSON
                                 records (the workspace .battinfo/ dir is gitignored).
  bundle/jsonld/                 per-record resolver JSON-LD for the 4 emittable
                                 types (cell-spec, cell-instance, test, dataset).
  bundle/deposit.jsonld          one combined JSON-LD graph for the whole deposit.
  bundle/ro-crate-metadata.json  deposit-level RO-Crate metadata.
  bundle/gold-standard-report.txt captured output of the RO-Crate gold-standard
                                 check (documents the known md5/term caveats).

Deterministic: re-running reproduces byte-identical output.
"""
from __future__ import annotations

import contextlib
import io
import shutil
import warnings
from pathlib import Path

warnings.simplefilter("ignore")

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
    "Machine-readable BattINFO semantic layer describing the cells, active materials, "
    "electrochemical protocols, tests and datasets of Zenodo record " + DOI + ". "
    "Each of the 95 BDF parquet files is described by a linked cell-spec / cell-instance / "
    "test-protocol / test / dataset record chain; datasets reference the Zenodo files by URL "
    "and md5 checksum."
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


def mirror_records() -> int:
    if RECORDS.exists():
        shutil.rmtree(RECORDS)
    n = 0
    for src in sorted(WS_RECORDS.rglob("*.json")):
        rel = src.relative_to(WS_RECORDS)
        dst = RECORDS / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
        n += 1
    return n


def main() -> int:
    if not WS_RECORDS.exists():
        raise SystemExit("Run build_records.py first (no .battinfo/records/ found).")
    n = mirror_records()
    print(f"mirrored {n} canonical records -> records/")

    if BUNDLE.exists():
        shutil.rmtree(BUNDLE)
    BUNDLE.mkdir(parents=True)

    ws = B.workspace(root=str(HERE), registry_url=None)
    jsonld = ws.export(fmt="json-ld", output_dir=str(BUNDLE / "jsonld"))
    print(f"exported {len(jsonld)} resolver JSON-LD files -> bundle/jsonld/ "
          "(cell-spec, cell-instance, test, dataset; test-protocol and material-spec "
          "have no JSON-LD emitter and remain as canonical JSON under records/)")

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
    print("wrote bundle/deposit.jsonld, bundle/ro-crate-metadata.json, bundle/gold-standard-report.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
