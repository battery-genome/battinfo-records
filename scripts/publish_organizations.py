"""
Publishes all curated organization records to battinfo-registry.

Builds a registry submission package for each organization record
and POSTs to the registry /publication-packages endpoint.

Usage:
    python scripts/publish_organizations.py \\
        --api-key  <key> \\
        --registry-url https://battinfo-registry.onrender.com \\
        [--workspace-id battinfo-records] \\
        [--publisher-id battinfo-records-bot] \\
        [--source-version 2026-04-29] \\
        [--dry-run]
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ORG_DIR = Path(__file__).parent.parent / "records" / "organization"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def build_package(
    record: dict,
    *,
    workspace_id: str,
    publisher_id: str,
    source_version: str,
    source_local_id: str,
) -> dict:
    org = record.get("organization", {})
    title = org.get("name") or source_local_id
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
            "workflow_name": "curated-organization-publication",
            "generated_at": generated_at,
        },
        "release": {"version": source_version},
        "workspace": {
            "editorial": {
                "record_id": source_local_id,
            }
        },
        "resource": {
            "resource_type": "organization",
            "source_local_id": source_local_id,
            "title": title,
            "semantic_payload": {
                "@type": "Organization",
                "battinfo_records": {"organization": record},
            },
            "related_resources": [],
            "distributions": [],
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
    timeout: float = 30.0,
) -> dict:
    url = registry_url.rstrip("/") + "/publication-packages"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(url, data=body, headers={"Content-Type": "application/json", api_key_header: api_key}, method="POST")
    try:
        with urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8")
            return {"status": "ok", "status_code": resp.getcode(), "response": json.loads(text) if text else None}
    except HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return {"status": "error", "status_code": exc.code, "error": body_text}
    except URLError as exc:
        return {"status": "error", "status_code": None, "error": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key", default="battinfo-records-bot-live-2026")
    parser.add_argument("--registry-url", default="https://battinfo-registry.onrender.com")
    parser.add_argument("--workspace-id", default="battinfo-records")
    parser.add_argument("--publisher-id", default="battinfo-records-bot")
    parser.add_argument("--source-version", default="2026-04-29-organizations")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    records = sorted(ORG_DIR.glob("*/record.json"))
    if not records:
        print("No organization records found.")
        sys.exit(1)

    ok = fail = 0
    for record_path in records:
        slug = record_path.parent.name
        record = json.loads(record_path.read_text(encoding="utf-8"))
        package = build_package(
            record,
            workspace_id=args.workspace_id,
            publisher_id=args.publisher_id,
            source_version=args.source_version,
            source_local_id=slug,
        )
        if args.dry_run:
            print(f"  dry-run  {slug}")
            ok += 1
            continue

        print(f"  publishing {slug} ... ", end="", flush=True)
        result = post_package(package, registry_url=args.registry_url, api_key=args.api_key)
        if result["status"] == "ok":
            print(f"ok ({result['status_code']})")
            ok += 1
        else:
            print(f"FAILED ({result['status_code']}): {result.get('error', '')[:120]}")
            fail += 1
        time.sleep(0.1)

    print(f"\nDone. ok: {ok}  failed: {fail}")


if __name__ == "__main__":
    main()
