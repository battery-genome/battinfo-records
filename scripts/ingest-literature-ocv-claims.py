#!/usr/bin/env python3
"""Ingest the curated literature OCV library as parameter-set claim records.

Source: the ``literature_ocv`` library in HEU-IntelLiGent
(``AnalysisOpenCircuitVoltages/data/literature_ocv``): half-cell OCP curves
extracted from PyBaMM / BPX / BattMo literature parameterizations, with a
manifest carrying per-curve provenance (source tool, parameter set, paper,
DOI). One manifest row = one source's OCP claim about one material kind =
one ``parameter-set`` record, staged under
``records/_staging/parameter-set/<kind>--<set>--<tool>/record.json``.

Rows whose ``curve_kind`` is ``phase_component_curve`` are skipped with a
printed reason: a phase-component curve is not the material's OCP, and
publishing it under the ``ocp`` parameter key would be a false claim.

Record identity is deterministic (target kind, scope, name), so re-running
the ingest regenerates the same IRIs — idempotent, never a duplicate corpus.

Requires the battinfo development tree (parameter-set support, >= the #347
merge). Run from the repo root with the BattINFO checkout's environment:

    uv run --project ../BattINFO python scripts/ingest-literature-ocv-claims.py \
        --source "../../HEU-IntelLigent/AnalysisOpenCircuitVoltages/data/literature_ocv"

Funding/contributor/license are deliberately NOT stamped here: the publish
step stamps attribution the same way every other corpus publication does.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

INGESTED_CURVE_KINDS = {"full_curve", "tabulated_curve"}


def read_curve(csv_path: Path) -> tuple[list[float], list[float]]:
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        if "stoichiometry" not in fields or "ocv_v" not in fields:
            raise ValueError(f"{csv_path.name}: expected columns stoichiometry, ocv_v; got {fields}")
        xs: list[float] = []
        ys: list[float] = []
        for row in reader:
            xs.append(float(row["stoichiometry"]))
            ys.append(float(row["ocv_v"]))
    if len(xs) < 2:
        raise ValueError(f"{csv_path.name}: fewer than 2 points")
    return xs, ys


def branch_of(row: dict[str, str]) -> str | None:
    """OCP hysteresis branch, read from the curve filename suffix."""
    stem = Path(row["file_name"]).stem.lower()
    for branch in ("lithiation", "delithiation", "average"):
        if stem.endswith(f"_{branch}"):
            return branch
    return None


def build_claim(row: dict[str, str], source_dir: Path) -> dict:
    xs, ys = read_curve(source_dir / row["file_name"])
    curve = {
        "x_quantity": "stoichiometry",
        "x": xs,
        "y": ys,
        "y_unit": "V",
        "interpolation": "linear",
    }
    branch = branch_of(row)
    if branch is not None:
        curve["branch"] = branch
    method = f"extracted from {row['source_tool']} parameter set {row['parameter_set']}"
    if row.get("function_key"):
        method += f" ({row['function_key']})"
    claim = {
        "parameter": "ocp",
        "curve": curve,
        "provenance_class": "literature",
        "method": method,
    }
    comment_parts = [p for p in (row.get("notes", "").strip(),) if p]
    if row.get("status") == "available_with_assumption":
        comment_parts.append("Carries an assumption; see the library manifest.")
    if comment_parts:
        claim["comment"] = " ".join(comment_parts)
    return claim


def build_record(rows: list[dict[str, str]], source_dir: Path):
    """One record per (kind, parameter set, tool): one claim per manifest row.

    Hysteresis branches (silicon lithiation/delithiation/average) are one
    source stating one parameter three ways — three claims with distinct
    ``branch`` values in one record, never three records fighting over one IRI.
    """
    from battinfo.api import create_parameter_set
    from battinfo.materials import material_kind_keys, resolve_material_kind

    first = rows[0]
    kind = resolve_material_kind(first["requested_material"])
    if kind is None:
        raise ValueError(
            f"manifest material {first['requested_material']!r} is not a curated kind; "
            f"valid: {', '.join(material_kind_keys())}"
        )
    claims = [build_claim(row, source_dir) for row in rows]
    notes = [
        "Ingested from the curated literature_ocv library "
        f"({', '.join(row['file_name'] for row in rows)}).",
        "Source function(s): "
        + "; ".join(
            row.get("function_reference") or row.get("function_key") or "n/a" for row in rows
        )
        + ".",
    ]
    record = create_parameter_set(
        name=f"{first['parameter_set']} ({first['source_tool']}) - {kind}",
        material_kind=kind,
        claims=claims,
        model_context={"tool": first["source_tool"], "name": first["parameter_set"]},
        description=(
            f"Half-cell open-circuit potential of {kind} from the "
            f"{first['parameter_set']} parameterization ({first['parameter_set_reference']})."
        ),
        source_type="literature",
        citation=first.get("parameter_set_doi_or_url") or None,
        notes=notes,
    )
    slug = f"{kind}--{first['parameter_set'].lower()}--{first['source_tool'].lower()}"
    return slug, record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", required=True, help="literature_ocv directory (with manifest.csv)")
    parser.add_argument(
        "--out",
        default="records/_staging/parameter-set",
        help="staging directory for the generated records",
    )
    args = parser.parse_args()

    source_dir = Path(args.source).resolve()
    manifest = source_dir / "manifest.csv"
    if not manifest.is_file():
        print(f"error: {manifest} not found", file=sys.stderr)
        return 2
    out_root = Path(args.out)

    with manifest.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    written, skipped = [], []
    groups: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in rows:
        label = f"{row['requested_material']} / {row['parameter_set']} ({row['source_tool']})"
        if row.get("curve_kind") not in INGESTED_CURVE_KINDS:
            skipped.append((label, f"curve_kind={row.get('curve_kind')} is not a material OCP"))
            continue
        key = (row["requested_material"], row["parameter_set"], row["source_tool"])
        groups.setdefault(key, []).append(row)

    for group in groups.values():
        slug, record = build_record(group, source_dir)
        out_dir = out_root / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "record.json"
        out_path.write_text(
            json.dumps(record, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        claims = record["parameter_set"]["claims"]
        branches = [c["curve"].get("branch") for c in claims]
        branch_note = (
            f", branches: {'/'.join(b for b in branches if b)}" if any(branches) else ""
        )
        written.append((slug, record["parameter_set"]["id"]))
        print(
            f"  wrote {slug}  [{len(claims)} claim(s)"
            f"{branch_note}]  {record['parameter_set']['id']}"
        )

    for label, reason in skipped:
        print(f"  skipped {label}: {reason}")
    print(f"\n{len(written)} record(s) staged under {out_root}; {len(skipped)} skipped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
