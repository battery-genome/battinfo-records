"""Publish the derived plot profiles to the object store the platform reads.

The dataset records point their plot distribution at

    {R2_PUBLIC_BASE}/datasets/{short_id}/{stem}.plot.json

which is the key layout ``AuthoringWorkspace.upload()`` uses for every dataset file.
This script puts the files there. It exists because the corpus authors its dataset
records directly rather than through a workspace (gap G1 in READINESS-REPORT.md), so
``ws.upload()`` has no local file to walk: the parquet sources live on Zenodo and only
these profiles are ours to host.

Credentials come from the environment or from ``.battinfo/credentials``, same as
``ws.upload()``::

    R2_ENDPOINT, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET, R2_PUBLIC_BASE_URL

Usage::

    python upload_profiles.py --dry-run     # list what would be sent
    python upload_profiles.py

Idempotent: an object whose stored sha256 already matches the local file is skipped, so
re-running after a partial upload only sends what is missing.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROFILES = HERE / "profiles"
INDEX_PATH = PROFILES / "index.json"


def load_credentials() -> None:
    """Merge .battinfo/credentials into the environment without overriding it."""
    for candidate in (HERE / ".battinfo" / "credentials", Path.home() / ".battinfo" / "credentials"):
        if not candidate.is_file():
            continue
        for line in candidate.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if key.startswith(("R2_", "BATTINFO_")) and key not in os.environ:
                os.environ[key] = value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report without uploading.")
    parser.add_argument("--bucket", default=None, help="Override R2_BUCKET.")
    args = parser.parse_args()

    if not INDEX_PATH.is_file():
        print(f"No profile index at {INDEX_PATH}. Run extract_profiles.py first.")
        return 1
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    if not index:
        print("Profile index is empty.")
        return 1

    load_credentials()
    endpoint = os.environ.get("R2_ENDPOINT")
    access_key = os.environ.get("R2_ACCESS_KEY_ID")
    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY")
    bucket = args.bucket or os.environ.get("R2_BUCKET") or "battinfo-public"

    plan = [
        (PROFILES / name, f"datasets/{entry['short_id']}/{name}", entry["sha256"], entry["bytes"])
        for name, entry in sorted(index.items())
    ]
    missing = [path for path, *_ in plan if not path.is_file()]
    if missing:
        print(f"{len(missing)} profile(s) named in the index are absent from {PROFILES}:")
        for path in missing[:5]:
            print(f"  {path.name}")
        return 1

    total = sum(size for *_, size in plan)
    print(f"{len(plan)} profile(s), {total / 1024:.0f} KB total -> bucket {bucket}")
    if args.dry_run:
        for _, key, _, size in plan[:5]:
            print(f"  {key}  ({size / 1024:.1f} KB)")
        if len(plan) > 5:
            print(f"  ... and {len(plan) - 5} more")
        return 0

    if not (endpoint and access_key and secret_key):
        print(
            "R2_ENDPOINT, R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY are required.\n"
            "Set them in the environment or in .battinfo/credentials."
        )
        return 1

    try:
        import boto3
        from botocore.exceptions import ClientError
    except ImportError:
        print('boto3 is required: pip install "battinfo[upload]" or pip install boto3')
        return 1

    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=os.environ.get("R2_REGION", "auto"),
    )

    sent = skipped = 0
    for path, key, sha256, _ in plan:
        try:
            head = client.head_object(Bucket=bucket, Key=key)
            if (head.get("Metadata") or {}).get("sha256") == sha256:
                skipped += 1
                continue
        except ClientError:
            pass  # absent, or no permission to head: fall through and put
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=path.read_bytes(),
            ContentType="application/json",
            Metadata={"sha256": sha256},
        )
        sent += 1
        print(f"  put {key}")

    print(f"\n{sent} uploaded, {skipped} already current.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
