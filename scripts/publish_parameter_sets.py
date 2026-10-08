"""Publish the curated parameter-set records to battinfo-registry.

Builds a registry submission package for each record under
``records/parameter-set/`` and POSTs it to ``/publication-packages``,
stamping attribution the way every corpus publication does:

- ``contributor``: the curator (name + ORCID, required flags) — added only
  when the record carries none;
- ``funding``: the grant the curation was performed under (defaults to
  IntelLiGent, HORIZON 101069765) — added only when absent;
- ``license``: NEVER touched. It was set at ingest as a condition of the
  source (four About:Energy-derived records are cc-by-sa-4.0, the rest
  cc-by-4.0); a record without a license refuses to publish rather than
  getting one silently.

A record that carries its file (a BPX parameter set, under
``parameter_set.distributions``) also sends those files as the submission's
distributions, which is what ``<IRI>?format=bpx`` resolves through. Before
posting, every file URL is fetched and checked against the record's sha256,
so a record never goes out pointing at a file that was not uploaded.

The API key comes from ``--api-key`` or the BATTINFO_REGISTRY_API_KEY
environment variable — deliberately no committed default.

Usage:
    python scripts/publish_parameter_sets.py \
        --contributor-name "..." --contributor-orcid 0000-0000-0000-0000 \
        --registry-url https://battinfo-registry.onrender.com \
        [--source-version 2026-08-17-literature-ocv] [--dry-run] [--limit N] \
        [--match '*--schmitt2026-hydra--bpx']
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

RECORD_DIR = Path(__file__).parent.parent / "records" / "parameter-set"
ORCID_URL_PREFIX = "https://orcid.org/"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def stamp_attribution(
    record: dict,
    *,
    contributor_name: str,
    contributor_orcid: str,
    grant_identifier: str,
    grant_acronym: str,
    slug: str,
) -> dict:
    if not isinstance(record.get("license"), str) or not record["license"].strip():
        raise ValueError(
            f"{slug}: record carries no license. Licenses are set at ingest as a "
            "condition of the source; refusing to publish rather than stamping one."
        )
    if not record.get("contributor"):
        record["contributor"] = [{
            "type": "Person",
            "name": contributor_name,
            "same_as": ORCID_URL_PREFIX + contributor_orcid,
        }]
    if not record.get("funding"):
        record["funding"] = {
            "type": "Grant",
            "identifier": grant_identifier,
            "acronym": grant_acronym,
            "program": "HORIZON",
            "funder": {"type": "Organization", "name": "European Union"},
        }
    return record


def envelope_distributions(record: dict) -> list[dict]:
    """The record's own files as submission distributions (registry field names)."""
    out = []
    for item in record.get("parameter_set", {}).get("distributions") or []:
        entry = {
            "title": item.get("name"),
            "access_url": item["content_url"],
            "role": item.get("role"),
            "media_type": item.get("encoding_format"),
            "conforms_to": item.get("conforms_to"),
            "checksum_sha256": (item.get("checksum") or {}).get("value"),
            "byte_size": item.get("byte_size"),
            "immutable": True,
        }
        out.append({key: value for key, value in entry.items() if value is not None})
    return out


def verify_files(distributions: list[dict], *, timeout: float = 120.0) -> list[str]:
    """Fetch each file and compare its sha256; returns the problems found."""
    problems = []
    for entry in distributions:
        url = entry["access_url"]
        try:
            with urlopen(Request(url, method="GET"), timeout=timeout) as resp:
                digest = hashlib.sha256(resp.read()).hexdigest()
        except (HTTPError, URLError) as exc:
            problems.append(f"{url}: not fetchable ({exc})")
            continue
        expected = (entry.get("checksum_sha256") or "").lower()
        if expected and digest != expected:
            problems.append(f"{url}: sha256 {digest} does not match the record's {expected}")
    return problems


def build_package(
    record: dict,
    *,
    workspace_id: str,
    publisher_id: str,
    source_version: str,
    source_local_id: str,
    workflow_name: str = "literature-ocv-parameter-publication",
) -> dict:
    body = record.get("parameter_set", {})
    title = body.get("name") or source_local_id
    generated_at = now_iso()
    return {
        "schema_version": "0.1.0",
        "kind": "BattinfoSubmission",
        "submission_mode": "resource",
        "generated_at": generated_at,
        "workspace_id": workspace_id,
        "publisher_id": publisher_id,
        "source_version": source_version,
        "title": title,
        "publication_intent": {"mode": "canonical-publication"},
        "provenance": {
            "source_system": "battinfo-records",
            "workflow_name": workflow_name,
            "generated_at": generated_at,
        },
        "release": {"version": source_version},
        "workspace": {"editorial": {"record_id": source_local_id}},
        "resource": {
            "resource_type": "parameter_set",
            "source_local_id": source_local_id,
            "title": title,
            "semantic_payload": {
                "@type": "ParameterSet",
                "battinfo_records": {"parameter_set": record},
            },
            "related_resources": [],
            "distributions": envelope_distributions(record),
        },
        "artifacts": [],
        "validation": {"ok": True, "errors": [], "policy": "default"},
    }


def post_package(
    payload: dict,
    *,
    registry_url: str,
    api_key: str,
    api_key_header: str = "X-Battinfo-API-Key",
    timeout: float = 60.0,
) -> dict:
    url = registry_url.rstrip("/") + "/publication-packages"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", api_key_header: api_key},
        method="POST",
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8")
            return {
                "status": "ok",
                "status_code": resp.getcode(),
                "response": json.loads(text) if text else None,
            }
    except HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return {"status": "error", "status_code": exc.code, "error": body_text}
    except URLError as exc:
        return {"status": "error", "status_code": None, "error": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key", default=os.environ.get("BATTINFO_REGISTRY_API_KEY"))
    parser.add_argument("--registry-url", default="https://battinfo-registry.onrender.com")
    parser.add_argument("--workspace-id", default="battinfo-records")
    parser.add_argument("--publisher-id", default="battinfo-records-bot")
    parser.add_argument("--source-version", default="2026-08-17-literature-ocv")
    parser.add_argument("--contributor-name", required=True)
    parser.add_argument("--contributor-orcid", required=True,
                        help="bare ORCID iD, e.g. 0000-0002-1825-0097")
    parser.add_argument("--grant-identifier", default="101069765")
    parser.add_argument("--grant-acronym", default="IntelLiGent")
    parser.add_argument("--dry-run", action="store_true",
                        help="build and print packages; POST nothing")
    parser.add_argument("--limit", type=int, default=None,
                        help="publish only the first N records (smoke run)")
    parser.add_argument("--match", default="*",
                        help="publish only records whose directory name matches this glob")
    parser.add_argument("--workflow-name", default="literature-ocv-parameter-publication")
    parser.add_argument("--skip-file-check", action="store_true",
                        help="do not fetch and hash the files a record carries before posting it")
    args = parser.parse_args()

    if not args.dry_run and not args.api_key:
        print("error: no API key (--api-key or BATTINFO_REGISTRY_API_KEY)", file=sys.stderr)
        return 2

    record_paths = [
        path for path in sorted(RECORD_DIR.glob("*/record.json"))
        if fnmatch.fnmatch(path.parent.name, args.match)
    ]
    # A parameterisation set lists its members, so members go first.
    record_paths.sort(key=lambda path: "members" in json.loads(path.read_text(encoding="utf-8"))["parameter_set"])
    if args.limit:
        record_paths = record_paths[: args.limit]
    if not record_paths:
        print(f"No parameter-set records found under {RECORD_DIR}.")
        return 1

    ok = fail = 0
    for record_path in record_paths:
        slug = record_path.parent.name
        record = json.loads(record_path.read_text(encoding="utf-8"))
        license_before = record.get("license")
        record = stamp_attribution(
            record,
            contributor_name=args.contributor_name,
            contributor_orcid=args.contributor_orcid,
            grant_identifier=args.grant_identifier,
            grant_acronym=args.grant_acronym,
            slug=slug,
        )
        assert record.get("license") == license_before, f"{slug}: license changed during stamping"
        package = build_package(
            record,
            workspace_id=args.workspace_id,
            publisher_id=args.publisher_id,
            source_version=args.source_version,
            source_local_id=slug,
            workflow_name=args.workflow_name,
        )
        files = package["resource"]["distributions"]
        if args.dry_run:
            body = record["parameter_set"]
            print(
                f"  dry-run  {slug}  [{record['license']}, "
                f"{len(body.get('claims', []))} claim(s), {len(files)} file(s)]  {body['id']}"
            )
            ok += 1
            continue

        if files and not args.skip_file_check:
            problems = verify_files(files)
            if problems:
                print(f"  SKIPPED {slug}: " + "; ".join(problems))
                fail += 1
                continue

        print(f"  publishing {slug} ... ", end="", flush=True)
        result = post_package(package, registry_url=args.registry_url, api_key=args.api_key)
        if result["status"] == "ok":
            print(f"ok ({result['status_code']})")
            ok += 1
        else:
            print(f"FAILED ({result['status_code']}): {result.get('error', '')[:200]}")
            fail += 1
        time.sleep(0.1)

    print(f"\nDone. ok: {ok}  failed: {fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
