"""Supersede duplicate cell-spec records in the registry (docs/duplicate-and-revised-specs.md).

Each copy gets status "superseded" with replaced_by_iri = the record kept. Its IRI keeps resolving as a
tombstone. Dry run by default: it reads both records from the target and prints the plan. --apply writes, and
needs BG_ADMIN_TOKEN (the registry's ADMIN_API_TOKEN) in the environment; a target that is not localhost also
needs BG_PUBLISH_CONFIRM=<target host>. The token is never printed.

  python scripts/supersede-cell-specs.py --target https://battinfo-registry.onrender.com
  python scripts/supersede-cell-specs.py --target https://battinfo-registry.onrender.com --apply

Afterwards, re-render the record pages so the kept records' panels drop the copies:
  cd battinfo-registry && uv run python scripts/rerender_record_pages.py --apply --persist-display
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

SPEC = "https://w3id.org/battinfo/spec/"
LOCAL = {"localhost", "127.0.0.1", "::1"}

# (copy, kept, why). Each pair is one product imported twice: once from a cell catalogue and once from a
# datasheet PDF. None of the copies names a datasheet revision, and none holds a correct value the kept
# record lacks.
PLAN = [
    ("n2vd-am8k-799a-wnjc", "9ppa-wmzq-ek22-sm6k",
     "LG INR18650-MJ1. Copy from PDF intake with extraction errors (diameter 0.3 mm, charge current 2.7 mA)."),
    ("zb7b-26kn-2exm-20w4", "2c16-qpzn-d6xc-3shs",
     "LG INR21700-M50. Copy from PDF intake with extraction errors (mass 1 g, charge current 2.8 mA)."),
    ("yqex-braj-ekys-tzf6", "kxvq-z6n3-tmjb-39mj",
     "LG INR21700-M50T. Sparse copy from PDF intake."),
    ("k4j2-6d8j-t2v2-mthz", "cmcy-cyp8-ajxx-27rg",
     "EVE LF280K. Copy from PDF intake with extraction errors (mass 0.2 kg)."),
    ("t4xh-yb6d-c663-yh8j", "cmcy-cyp8-ajxx-27rg",
     "EVE LF280K. Copy from a second PDF; no revision stated; mass 0.3 kg is an extraction error."),
    ("1gm2-anrq-5et1-958t", "cmcy-cyp8-ajxx-27rg",
     "EVE LF280K. Copy from a third PDF; no revision stated; mass 0.3 kg is an extraction error."),
    ("vx8k-bws1-wghk-m635", "tt1e-1be6-2wq9-e2ad",
     "EVE LF90K. Sparse copy from PDF intake."),
    ("bnj2-h9ht-p6hc-wk2x", "wa3w-j2fg-ewf3-1b4c",
     "Energizer CR2032. Auto-promoted copy; the kept record was reviewed against the primary source."),
]


def call(base: str, method: str, path: str, body: dict | None = None, headers: dict | None = None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(base.rstrip("/") + path, data=data, method=method,
                                 headers={"Content-Type": "application/json", "User-Agent": "supersede-cell-specs",
                                          **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as error:
        return error.code, (error.read() or b"")[:500].decode("utf-8", "replace")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    host = urllib.parse.urlparse(args.target).hostname
    if args.apply and host not in LOCAL and os.environ.get("BG_PUBLISH_CONFIRM") != host:
        sys.exit(f"set BG_PUBLISH_CONFIRM={host} to write to it")

    problems = 0
    print(f"{len(PLAN)} copies -> {args.target} ({'APPLY' if args.apply else 'dry run'})")
    for copy, kept, why in PLAN:
        st_copy, rec_copy = call(args.target, "GET", f"/resources/cell_spec/{copy}")
        st_kept, rec_kept = call(args.target, "GET", f"/resources/cell_spec/{kept}")
        copy_state = rec_copy.get("status") if st_copy == 200 else st_copy
        kept_state = rec_kept.get("status") if st_kept == 200 else st_kept
        print(f"  {copy} ({copy_state}) -> {kept} ({kept_state})  {why}")
        if kept_state != "published":
            print("    skipped: the kept record is not published")
            problems += 1
    if not args.apply or problems:
        return 1 if problems else 0

    token = os.environ.get("BG_ADMIN_TOKEN")
    if not token:
        sys.exit("BG_ADMIN_TOKEN is not set")
    admin = {"X-Battinfo-Admin-Token": token}
    for copy, kept, _ in PLAN:
        st, res = call(args.target, "POST", f"/admin/resources/cell_spec/{copy}/status",
                       {"status": "superseded", "replaced_by_iri": SPEC + kept}, admin)
        ok = st == 200 and res.get("status") == "superseded"
        problems += not ok
        print(f"  {copy}: {'superseded' if ok else f'FAILED {st} {res}'}")
    # postflight: each copy now answers with a tombstone naming its replacement
    good = 0
    for copy, kept, _ in PLAN:
        st, res = call(args.target, "GET", f"/resolve/cell_spec/{copy}", headers={"Accept": "application/ld+json"})
        replaced = (res.get("dcterms:isReplacedBy") or {}).get("@id") if isinstance(res, dict) else None
        if st == 200 and isinstance(res, dict) and res.get("owl:deprecated") and replaced == SPEC + kept:
            good += 1
        else:
            print(f"  postflight: {copy} answers {st} {str(res)[:120]}")
            problems += 1
    print(f"  postflight: {good} of {len(PLAN)} tombstones name their replacement")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
