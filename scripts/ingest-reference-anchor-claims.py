#!/usr/bin/env python3
"""Ingest the curated material-kind reference anchors as parameter-set records.

Source: the ``reference_properties`` blocks in BattINFO's material_kinds
vocabulary — curated, citable generic values (theoretical specific capacity,
true density) the genome compares reported distributions against. One kind's
anchors share one citation, so one kind = one record.

Key mapping is deliberate and non-negotiable:

- vocabulary ``specific_capacity`` anchors are THEORETICAL stoichiometric
  capacities (graphite 372 mAh/g = LiC6) and ingest under
  ``theoretical_specific_capacity`` — never under the practical
  ``specific_capacity`` key the design tiers require;
- ``density`` anchors are true (crystallographic) densities and ingest
  under ``density`` as-is.

Run with the BattINFO dev tree (>= the theoretical_specific_capacity key):

    uv run --project ../BattINFO python scripts/ingest-reference-anchor-claims.py \
        --vocab ../BattINFO/src/battinfo/data/vocab/material_kinds.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

KEY_MAP = {
    "specific_capacity": "theoretical_specific_capacity",
    "density": "density",
}
THEORETICAL_COMMENT = (
    "Theoretical stoichiometric value (curated Battery Genome reference anchor), "
    "not a practical reversible capacity."
)


def build_record(kind: str, anchors: dict) -> tuple[str, dict]:
    from battinfo.api import create_parameter_set

    citations = {v.get("citation") for v in anchors.values() if v.get("citation")}
    if len(citations) != 1:
        raise ValueError(
            f"{kind}: reference anchors carry {len(citations)} distinct citations; "
            "one record = one source — split the ingest if the vocabulary grows a second source."
        )
    citation = citations.pop()
    citation_doi = (
        citation.removeprefix("https://doi.org/")
        if citation.startswith("https://doi.org/")
        else None
    )

    claims = []
    for vocab_key, anchor in sorted(anchors.items()):
        parameter = KEY_MAP.get(vocab_key)
        if parameter is None:
            print(f"  note: {kind}.{vocab_key} has no ingest mapping; skipped")
            continue
        claim = {
            "parameter": parameter,
            "quantity": {"value": float(anchor["value"]), "unit": str(anchor["unit"])},
            "provenance_class": "literature",
        }
        if parameter == "theoretical_specific_capacity":
            claim["comment"] = THEORETICAL_COMMENT
        claims.append(claim)
    if not claims:
        raise ValueError(f"{kind}: no ingestable anchors")

    record = create_parameter_set(
        name=f"Curated reference anchors - {kind}",
        material_kind=kind,
        claims=claims,
        description=(
            f"Curated, citable reference values for {kind} from the Battery Genome "
            "material-kind vocabulary: the generic anchors reported distributions "
            "are compared against."
        ),
        source_type="literature",
        citation=citation,
        citation_doi=citation_doi,
        notes=[
            "Ingested from the reference_properties block of BattINFO's curated "
            "material_kinds vocabulary (governance-by-PR)."
        ],
    )
    record["license"] = "cc-by-4.0"
    from battinfo.validate.record import validate_record_report

    report = validate_record_report(record)
    if not report.ok:
        raise ValueError(f"{kind}: record failed validation: {report.errors}")
    return f"{kind}--reference-anchors", record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--vocab", required=True, help="path to material_kinds.json")
    parser.add_argument("--out", default="records/parameter-set")
    args = parser.parse_args()

    vocab = json.loads(Path(args.vocab).read_text(encoding="utf-8"))
    out_root = Path(args.out)
    written = 0
    for kind, entry in sorted(vocab.get("kinds", {}).items()):
        anchors = entry.get("reference_properties")
        if not anchors:
            continue
        slug, record = build_record(kind, anchors)
        out_dir = out_root / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "record.json").write_text(
            json.dumps(record, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        parameters = [c["parameter"] for c in record["parameter_set"]["claims"]]
        print(f"  wrote {slug}  [{', '.join(parameters)}]  {record['parameter_set']['id']}")
        written += 1
    print(f"\n{written} record(s) under {out_root}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
