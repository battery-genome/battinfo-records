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

Each package also carries BattINFO's JSON-LD export of the stamped record
(``resource.record_jsonld``). The registry serves that export's statements
about the record at its IRI, which is how ``is_based_on`` reaches the RDF.
Without it the IRI serves only the registry envelope as RDF, and a new
version published without it drops what an earlier one served. Run the
script with a battinfo newer than the 0.8.1 release, which does not export
``is_based_on``; a record that states it and gets an export without it is
skipped. ``--no-record-jsonld`` leaves the export out on purpose. The
registry keeps the version it holds when a record is re-sent under the same
``--source-version``, so adding the export to a published record takes a new
source version.

The API key comes from ``--api-key`` or the BATTINFO_REGISTRY_API_KEY
environment variable — deliberately no committed default.

Usage:
    python scripts/publish_parameter_sets.py \
        --contributor-name "..." --contributor-orcid 0000-0000-0000-0000 \
        --registry-url https://battinfo-registry.onrender.com \
        [--source-version 2026-08-17-literature-ocv] [--dry-run] [--limit N] \
        [--match '*--schmitt2026-hydra--bpx'] [--no-record-jsonld]
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
from http.client import HTTPException
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
            # Cloudflare r2.dev answers 403 to the default Python-urllib user agent.
            request = Request(url, method="GET", headers={"User-Agent": "battinfo-records-publish/1.0"})
            with urlopen(request, timeout=timeout) as resp:
                digest = hashlib.sha256(resp.read()).hexdigest()
        except (OSError, HTTPException) as exc:  # HTTP errors, timeouts and dropped connections alike
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
    record_jsonld: dict | None = None,
) -> dict:
    body = record.get("parameter_set", {})
    title = body.get("name") or source_local_id
    generated_at = now_iso()
    package = {
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
    if record_jsonld is not None:
        package["resource"]["record_jsonld"] = record_jsonld
    return package


def states_based_on(record: dict) -> bool:
    """Whether the parameter set, or any of its claims, names what it is based on."""
    body = record.get("parameter_set") or {}
    claims = list(body.get("claims") or [])
    for part in body.get("parts") or []:
        claims.extend(part.get("claims") or [])
    return bool(body.get("is_based_on")) or any(claim.get("is_based_on") for claim in claims)


def exports_based_on(doc: object) -> bool:
    """Whether a JSON-LD export carries schema:isBasedOn anywhere."""
    if isinstance(doc, dict):
        return any(str(key).endswith("isBasedOn") or exports_based_on(value) for key, value in doc.items())
    if isinstance(doc, list):
        return any(exports_based_on(item) for item in doc)
    return False


def jsonld_report(response: object) -> dict | None:
    """The registry's record_jsonld_report for the one resource a package sends."""
    resources = response.get("resources") if isinstance(response, dict) else None
    if not resources or not isinstance(resources[0], dict):
        return None
    report = resources[0].get("record_jsonld_report")
    return report if isinstance(report, dict) else None


def jsonld_report_note(report: dict | None) -> str:
    """What the registry left out of the export, or ''.

    Statements about other named subjects (an ORCID, a DOI, a substance) are
    left out by design, so those show as a count; anything else by value.
    """
    if not report:
        return ""
    parts = []
    if report.get("reason"):
        parts.append(f"not served: {report['reason']}")
    for key in ("dropped_terms", "invalid_values", "unmapped_keys"):
        if report.get(key):
            parts.append(f"{key} {', '.join(map(str, report[key]))}")
    if report.get("dropped_subjects"):
        parts.append(f"{len(report['dropped_subjects'])} other subject(s) left out")
    return "; JSON-LD export: " + "; ".join(parts) if parts else ""


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
    parser.add_argument("--no-record-jsonld", action="store_true",
                        help="send no JSON-LD export; the record's IRI then serves only the registry envelope as RDF")
    args = parser.parse_args()

    if not args.dry_run and not args.api_key:
        print("error: no API key (--api-key or BATTINFO_REGISTRY_API_KEY)", file=sys.stderr)
        return 2

    record_to_jsonld = None
    if not args.no_record_jsonld:
        try:
            from battinfo.jsonld import record_to_jsonld
        except ImportError:
            print("error: battinfo is not importable, so no record can carry its JSON-LD export. "
                  "Run with an environment that has battinfo, or pass --no-record-jsonld.", file=sys.stderr)
            return 2

    record_paths = [
        path for path in sorted(RECORD_DIR.glob("*/record.json"))
        if fnmatch.fnmatch(path.parent.name, args.match)
    ]
    if args.limit:
        record_paths = record_paths[: args.limit]
    if not record_paths:
        print(f"No parameter-set records found under {RECORD_DIR}.")
        return 1

    ok = kept = fail = 0
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
        record_jsonld = None
        if record_to_jsonld is not None:
            try:
                record_jsonld = record_to_jsonld(record, "parameter-set")
            except Exception as exc:  # the emitter's own errors vary; none should stop the other records
                print(f"  SKIPPED {slug}: no JSON-LD export ({type(exc).__name__}: {exc})")
                fail += 1
                continue
            if states_based_on(record) and not exports_based_on(record_jsonld):
                print(f"  SKIPPED {slug}: the record states is_based_on and this battinfo does not export it "
                      "(the 0.8.1 release does not; a newer battinfo does)")
                fail += 1
                continue
        package = build_package(
            record,
            workspace_id=args.workspace_id,
            publisher_id=args.publisher_id,
            source_version=args.source_version,
            # The record uid, not the folder name: the registry refuses a new
            # dataset/ record under a key that already holds a spec/ one.
            source_local_id="parameter-set:" + record["parameter_set"]["id"].rsplit("/", 1)[-1],
            workflow_name=args.workflow_name,
            record_jsonld=record_jsonld,
        )
        files = package["resource"]["distributions"]
        if args.dry_run:
            body = record["parameter_set"]
            export = (
                f"JSON-LD {len(json.dumps(record_jsonld, ensure_ascii=False).encode('utf-8')) / 1024:.1f} KiB"
                if record_jsonld is not None else "no JSON-LD"
            )
            print(
                f"  dry-run  {slug}  [{record['license']}, "
                f"{len(body.get('claims', [])) + sum(len(p.get('claims', [])) for p in body.get('parts', []))} claim(s), "
                f"{len(files)} file(s), {export}]  {body['id']}"
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
        response = result.get("response")
        if result["status"] != "ok":
            print(f"FAILED ({result['status_code']}): {result.get('error', '')[:200]}")
            fail += 1
        elif isinstance(response, dict) and response.get("created_count") == 0:
            print(f"KEPT ({result['status_code']}): the registry already holds source version "
                  f"{args.source_version} of this record and stored nothing; pass a new --source-version"
                  f"{jsonld_report_note(jsonld_report(response))}")
            kept += 1
        else:
            report = jsonld_report(response)
            note = jsonld_report_note(report)
            if record_jsonld is not None and report and report.get("reason"):
                print(f"FAILED ({result['status_code']}): published without its JSON-LD statements{note}")
                fail += 1
            else:
                print(f"ok ({result['status_code']}){note}")
                ok += 1
        time.sleep(0.1)

    print(f"\nDone. ok: {ok}  kept: {kept}  failed: {fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
