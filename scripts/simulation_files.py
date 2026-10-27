"""Shared by simulate-parameter-sets.py and benchmark-simulators.py: which BPX files to simulate,
fetching them with their checksum checked, and writing to the simulations bucket.

Standard library only (boto3 is imported when uploading), so the benchmark driver can use it
without PyBaMM installed.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parent.parent
PARAMETER_SET_DIR = REPO / "records" / "parameter-set"
PREFIX = "simulations"
USER_AGENT = "battinfo-records-simulations/1.0"  # the artifact host refuses Python's default
IMMUTABLE = "public, max-age=31536000, immutable"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dumps(obj) -> bytes:
    return (json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


# ---- selecting and fetching files --------------------------------------------------------------


def runnable_distribution(body: dict) -> dict | None:
    """The file to simulate: the runnable conversion if present, else the source, with a passing smoke run."""
    for role in ("runnable", "source"):
        for dist in body.get("distributions") or []:
            if dist.get("role") != role:
                continue
            checks = [c for c in dist.get("checks") or [] if c.get("check") == "simulation_smoke"]
            if any(c.get("passed") for c in checks):
                return dist
    return None


def find_records(only: str | None) -> list[tuple[str, dict, dict]]:
    found = []
    for path in sorted(PARAMETER_SET_DIR.glob("*/record.json")):
        if only and not fnmatch.fnmatch(path.parent.name, only):
            continue
        body = json.loads(path.read_text(encoding="utf-8")).get("parameter_set") or {}
        if not body.get("distributions"):
            continue  # claim batches carry no file
        dist = runnable_distribution(body)
        if dist is None:
            print(f"skip {path.parent.name}: no file with a passing simulation_smoke check")
            continue
        found.append((path.parent.name, body, dist))
    return found


def fetch(dist: dict, cache_dir: Path) -> bytes:
    checksum = dist.get("checksum") or {}
    if checksum.get("algorithm") != "sha256" or not checksum.get("value"):
        raise ValueError(f"{dist.get('name')}: no sha256 checksum on the distribution")
    expected = checksum["value"]
    cached = cache_dir / f"{expected}.json"
    if cached.exists() and sha256(cached.read_bytes()) == expected:
        return cached.read_bytes()
    with urlopen(Request(dist["content_url"], headers={"User-Agent": USER_AGENT}), timeout=300) as response:
        data = response.read()
    if sha256(data) != expected:
        raise ValueError(f"{dist['content_url']}: sha256 {sha256(data)} does not match the record's {expected}")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(data)
    return data


# ---- the bucket ---------------------------------------------------------------------------------


class Bucket:
    """The simulations bucket named by R2_BUCKET. Writes never leave simulations/."""

    def __init__(self) -> None:
        import boto3
        from botocore.exceptions import ClientError

        missing = [k for k in ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ENDPOINT", "R2_BUCKET") if not os.environ.get(k)]
        if missing:
            raise SystemExit(f"--upload needs {', '.join(missing)}")
        self.name = os.environ["R2_BUCKET"]
        self.client_error = ClientError
        self.s3 = boto3.client("s3", endpoint_url=os.environ["R2_ENDPOINT"], region_name="auto",
                               aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                               aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"])

    def _missing(self, exc) -> bool:
        return exc.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound")

    def put(self, key: str, body: bytes, cache_control: str = IMMUTABLE) -> None:
        if not key.startswith(f"{PREFIX}/"):  # this key can write the whole bucket; never leave the prefix
            raise SystemExit(f"refusing to write outside {PREFIX}/: {key}")
        content_type = "application/json" if key.endswith(".json") else "application/octet-stream"
        self.s3.put_object(Bucket=self.name, Key=key, Body=body, ContentType=content_type,
                           CacheControl=cache_control, Metadata={"sha256": sha256(body)})

    def exists(self, key: str) -> bool:
        try:
            self.s3.head_object(Bucket=self.name, Key=key)
            return True
        except self.client_error as exc:
            if self._missing(exc):
                return False
            raise

    def get_json(self, key: str):
        try:
            return json.loads(self.s3.get_object(Bucket=self.name, Key=key)["Body"].read())
        except self.client_error as exc:
            if self._missing(exc):
                return None
            raise

    def current_index(self) -> tuple[str | None, dict | None]:
        """The index simulations/latest.json points at, and its key; (None, None) before the first run."""
        latest = self.get_json(f"{PREFIX}/latest.json")
        if not latest:
            return None, None
        return latest["index"], self.get_json(latest["index"])

    def publish_index(self, index_key: str, index: dict) -> None:
        """Write a new index (write-once) and move simulations/latest.json to it."""
        body = dumps(index)
        self.put(index_key, body)
        self.put(f"{PREFIX}/latest.json", dumps({"index": index_key, "index_sha256": sha256(body)}), "no-cache")
        print(f"{PREFIX}/latest.json now points at {index_key}")
