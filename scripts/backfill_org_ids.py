"""
Backfills manufacturer.id (and brand.id where applicable) in cell-type records
by matching product.manufacturer.name against organization record names and alternateName.

Run after curating organization records. Safe to re-run — only adds missing id fields,
never removes or overwrites existing ones.

Usage:
    python scripts/backfill_org_ids.py [--dry-run]
"""

import argparse
import json
from pathlib import Path

RECORDS_DIR = Path(__file__).parent.parent / "records"
CELL_TYPE_DIR = RECORDS_DIR / "cell-type"
ORG_DIR = RECORDS_DIR / "organization"


def load_org_index() -> dict[str, str]:
    """
    Build a lookup {name_lower: iri} from all organization records.
    Includes both name and any alternateName entries.
    """
    index: dict[str, str] = {}
    for record_path in ORG_DIR.glob("*/record.json"):
        with open(record_path, encoding="utf-8") as f:
            rec = json.load(f)
        org = rec.get("organization", {})
        iri = org.get("id")
        if not iri:
            continue
        # Index by canonical name
        name = org.get("name", "").strip()
        if name:
            index[name.lower()] = iri
        # Index by all alternate names
        alt = org.get("alternateName", [])
        if isinstance(alt, str):
            alt = [alt]
        for a in alt:
            if a.strip():
                index[a.strip().lower()] = iri
    return index


def backfill_record(record_path: Path, org_index: dict[str, str], dry_run: bool) -> bool:
    """
    Adds manufacturer.id / brand.id to a cell-type record where a match is found.
    Returns True if the record was modified.
    """
    with open(record_path, encoding="utf-8") as f:
        rec = json.load(f)

    product = rec.get("product", {})
    modified = False

    for field in ("manufacturer", "brand"):
        org_block = product.get(field)
        if not isinstance(org_block, dict):
            continue
        if org_block.get("id"):
            continue  # already has an id — don't overwrite
        name = org_block.get("name", "").strip()
        if not name:
            continue
        iri = org_index.get(name.lower())
        if not iri:
            continue

        if dry_run:
            print(f"    would set {field}.id = {iri}  ({name!r})")
        else:
            org_block["id"] = iri
            modified = True

    if modified and not dry_run:
        with open(record_path, "w", encoding="utf-8") as f:
            json.dump(rec, f, indent=2, ensure_ascii=False)
            f.write("\n")

    return modified


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    org_index = load_org_index()
    if not org_index:
        print("No organization records found. Run extract_organizations.py first.")
        return

    print(f"Loaded {len(org_index)} name → IRI mappings from organization records.\n")

    updated = 0
    unmatched: set[str] = set()

    for record_path in sorted(CELL_TYPE_DIR.glob("*/record.json")):
        product = json.loads(record_path.read_text(encoding="utf-8")).get("product", {})

        for field in ("manufacturer", "brand"):
            org_block = product.get(field)
            if not isinstance(org_block, dict):
                continue
            if org_block.get("id"):
                continue
            name = org_block.get("name", "").strip()
            if name and name.lower() not in org_index:
                unmatched.add(name)

        changed = backfill_record(record_path, org_index, args.dry_run)
        if changed:
            verb = "would update" if args.dry_run else "updated"
            print(f"  {verb}: {record_path.parent.name}")
            updated += 1

    verb = "would update" if args.dry_run else "updated"
    print(f"\nDone. {verb}: {updated} records.")
    if unmatched:
        print(f"\nUnmatched org names (add to alternateName in org records):")
        for name in sorted(unmatched):
            print(f"  - {name!r}")


if __name__ == "__main__":
    main()
