"""
Scans all cell-type records, extracts unique organizations (manufacturer + brand),
and writes organization record stubs under records/organization/<slug>/record.json.

Existing org records are preserved — only missing ones are created.
Run after adding new cell-type records to keep the org list up to date.

Usage:
    python scripts/extract_organizations.py [--dry-run]
"""

import argparse
import json
import secrets
import time
from pathlib import Path

RECORDS_DIR = Path(__file__).parent.parent / "records"
CELL_TYPE_DIR = RECORDS_DIR / "cell-type"
ORG_DIR = RECORDS_DIR / "organization"

IRI_BASE = "https://w3id.org/battinfo/organization/"

# Crockford base32 alphabet (unambiguous characters)
ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"


def _random_segment(length: int = 4) -> str:
    """Return `length` random Crockford base32 characters."""
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def generate_iri() -> str:
    return IRI_BASE + "-".join(_random_segment() for _ in range(4))


def slugify(name: str) -> str:
    """Convert an org name to a filesystem-safe directory slug."""
    import re
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def load_existing_orgs() -> dict[str, dict]:
    """Return {name_lower: record_dict} for all existing org records."""
    existing: dict[str, dict] = {}
    for record_path in ORG_DIR.glob("*/record.json"):
        with open(record_path, encoding="utf-8") as f:
            rec = json.load(f)
        name = rec.get("organization", {}).get("name", "")
        if name:
            existing[name.lower()] = rec
    return existing


def extract_orgs_from_cell_types() -> dict[str, dict]:
    """
    Walk all cell-type records and collect unique organizations.
    Returns {name_lower: {"name": ..., "url": ..., "source_ids": [...]}}.
    """
    orgs: dict[str, dict] = {}

    for record_path in sorted(CELL_TYPE_DIR.glob("*/record.json")):
        with open(record_path, encoding="utf-8") as f:
            rec = json.load(f)

        product = rec.get("product", {})
        record_id = record_path.parent.name

        for field in ("manufacturer", "brand"):
            org_block = product.get(field)
            if not isinstance(org_block, dict):
                continue
            name = org_block.get("name", "").strip()
            if not name:
                continue
            key = name.lower()
            if key not in orgs:
                orgs[key] = {
                    "name": name,
                    "url": org_block.get("url"),
                    "source_ids": [],
                }
            orgs[key]["source_ids"].append(record_id)

    return orgs


def write_org_stub(slug: str, name: str, url: str | None, existing_iri: str | None = None) -> Path:
    """Write a new organization record stub and return its path."""
    org_path = ORG_DIR / slug
    org_path.mkdir(parents=True, exist_ok=True)
    record_path = org_path / "record.json"

    iri = existing_iri or generate_iri()
    short_id = iri.replace(IRI_BASE, "").replace("-", "")[:8]

    record: dict = {
        "schema_version": "0.1.0",
        "organization": {
            "id": iri,
            "short_id": short_id,
            "type": "Organization",
            "name": name,
        },
        "provenance": {
            "source_type": "inferred",
            "source_url": None,
            "retrieved_at": int(time.time()),
        },
        "editorial": {
            "review_status": "stub",
            "note": "Auto-generated stub. Add legalName, sameAs (Wikidata/ROR), location, foundingDate, type.",
        },
    }

    if url:
        record["organization"]["url"] = url

    with open(record_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return record_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing files.")
    args = parser.parse_args()

    ORG_DIR.mkdir(parents=True, exist_ok=True)

    existing = load_existing_orgs()
    extracted = extract_orgs_from_cell_types()

    created = 0
    skipped = 0

    for key, info in sorted(extracted.items(), key=lambda x: x[1]["name"]):
        name = info["name"]
        url = info["url"]
        n_records = len(set(info["source_ids"]))

        if key in existing:
            print(f"  skip  {name!r}  ({n_records} cell-type records)")
            skipped += 1
            continue

        slug = slugify(name)
        # Avoid slug collisions by appending a counter suffix if needed
        base_slug = slug
        counter = 2
        while (ORG_DIR / slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        if args.dry_run:
            print(f"  would create  {slug}/record.json  ({name!r}, {n_records} cell-type records)")
        else:
            path = write_org_stub(slug, name, url)
            print(f"  created  {path.relative_to(RECORDS_DIR)}  ({name!r}, {n_records} cell-type records)")
        created += 1

    noun = "would create" if args.dry_run else "created"
    print(f"\nDone. {noun}: {created}  Already exist: {skipped}")
    if created and not args.dry_run:
        print("\nNext steps:")
        print("  1. Curate each stub: add legalName, sameAs (Wikidata IRI), location, type.")
        print("  2. Run scripts/backfill_org_ids.py to add manufacturer.id to cell-type records.")


if __name__ == "__main__":
    main()
