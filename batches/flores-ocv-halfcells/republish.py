#!/usr/bin/env python3
"""Republish the Flores half-cell OCV corpus (v5) over the live v1 corpus.

The registry serves corpus v1 (319 records, source_version 2026-08-11). This batch
holds corpus v5: 425 records, one of them the collection record. This driver moves a
registry from the first state to the second, in eight ordered steps:

  0 preflight    read-only. Target health and auth; every record validates (battinfo
                 when importable, and the target's own served JSON schemas when
                 jsonschema is importable); the supersede map is consistent (every
                 successor is in this corpus, every superseded IRI is live on the
                 target and published); no new record collides with a live
                 (type, source_local_id); every outside reference resolves; every
                 record carries the IRI pinned in published-iris.json (renames are
                 display-only and never move an identity).
  1 organization publish the Topsoe organization (vz1v-rvhz-n77h-344c), which v5
                 cites and the registry does not have.
  2 collection   submit + approve the collection record, before any member, because
                 the 95 members carry series_id pointing at it.
  3 records      submit + approve the other 424 in dependency order (material spec,
                 material, electrode spec, electrode, cell spec, cell, test protocol,
                 test, dataset). A record whose IRI is already live (154 retained
                 identifiers) is submitted under its live source_local_id, so it
                 versions in place; everything else is a new identifier.
  4 supersede    one admin status call per replaced or split row of
                 superseded/supersede-map.json: status superseded + replaced_by_iri.
                 A spec that split into several specs lists them all in
                 replaced_by_iris (primary first); a material lot names its
                 electrode spec (superseded/split-successors.json).
  5 profiles     upload the 95 plot profiles (delegates to upload_profiles.py).
  6 rerender     re-render every record page with persisted display (delegates to
                 battinfo-registry scripts/rerender_record_pages.py).
  7 postflight   read-only sweep: every corpus IRI resolves 200 and is published,
                 every superseded IRI is a tombstone pointing at a live successor,
                 the collection has 95 members, no record references a dead or
                 tombstoned IRI.

Every step is idempotent. Each one re-reads the target before acting and skips what
is already done, so a re-run after an interruption resumes where it stopped; the
state file (--state) is the log of what was done and the submission ids, not the
source of truth.

USAGE

  # dry run (default): preflight + the plan with counts. Writes nothing.
  python republish.py --target http://127.0.0.1:8010

  # local preview stack, writes
  FLORES_REPUBLISH_PUBLISHER_KEY=... FLORES_REPUBLISH_ADMIN_TOKEN=... \\
  python republish.py --target http://127.0.0.1:8010 --apply \\
      --registry-repo ../battinfo-registry --registry-env-file ../battinfo-registry/.preview/.env.preview

  # only the read-only sweep
  python republish.py --target http://127.0.0.1:8010 --steps postflight

  # production: needs --production AND the confirmation variable set to the host
  FLORES_REPUBLISH_CONFIRM=battinfo-registry.onrender.com \\
  FLORES_REPUBLISH_PUBLISHER_KEY=... FLORES_REPUBLISH_ADMIN_TOKEN=... \\
  R2_ENDPOINT=... R2_ACCESS_KEY_ID=... R2_SECRET_ACCESS_KEY=... R2_BUCKET=... \\
  python republish.py --target https://battinfo-registry.onrender.com --production --apply \\
      --registry-repo ../battinfo-registry

  R2_BUCKET must be the bucket served at the records' profile base URL
  (https://pub-5d124607e4b748eea681efca486508ab.r2.dev): the registry's artifacts
  bucket (STORAGE_ARTIFACTS_BUCKET, battery-genome-artifacts), not its page bucket
  (STORAGE_PUBLIC_BUCKET). The 2026-10-07 run first uploaded to the page bucket; the
  postflight now fetches every profile URL, so that cannot pass unnoticed again.

  Run it with an interpreter that has battinfo (and jsonschema) installed, or the
  record validation in preflight is skipped with a warning; --production requires
  both. Keys come only from the environment: FLORES_REPUBLISH_PUBLISHER_KEY (the
  battinfo-records-bot publisher key) and FLORES_REPUBLISH_ADMIN_TOKEN (the
  registry's ADMIN_API_TOKEN). Neither is ever written to the state file.

SAFETY

  Any target whose host is not localhost / 127.0.0.1 / ::1 is refused unless
  --production is passed, and --apply against it additionally requires
  FLORES_REPUBLISH_CONFIRM=<target host> in the environment. Freeze other publishing
  on the target for the duration (the close-out plan's A4 note): step 6 re-renders
  the whole corpus and step 4 assumes nobody else edits these identifiers meanwhile.

ROLLBACK

  What can be undone:
    * Step 4 (status flags). Every tombstone is reversible with the same admin call:
      POST /admin/resources/{type}/{id}/status {"status": "published"} restores a
      superseded v1 record and clears replaced_by_iri(s). The state file lists every
      row this driver superseded ("supersedes"), so a rollback can replay it.
    * Step 3 versions of retained identifiers. The 154 retained records gain a new
      version; the v1 version stays in /versions. Re-submitting the v1 payload under
      a new source_version makes v1's content current again.
    * Step 5 objects can be deleted from the bucket; step 6 can be re-run at any time.
  What cannot be undone:
    * Newly minted identifiers. Every v5 IRI that was not live before (the Topsoe
      organization, the collection, and the 270 other new records) is registered
      permanently once published. It can be withdrawn (status withdrawn, which
      serves a tombstone), never deleted or reused.
    * Nothing about names. Titles and handles are display text: every record is
      pinned to its published IRI (published-iris.json), and preflight refuses a
      corpus whose IRIs differ from the pins, so a rename never re-seeds the
      collection or orphans the 95 members' series_id.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RECORDS = HERE / "records"
SUPERSEDE_MAP = HERE / "superseded" / "supersede-map.json"
SPLIT_OVERRIDES = HERE / "superseded" / "split-successors.json"
TOPSOE_RECORD = REPO / "records" / "organization" / "topsoe" / "record.json"
PROFILES_SCRIPT = HERE / "upload_profiles.py"
PROFILE_INDEX = HERE / "profiles" / "index.json"
DEFAULT_STATE_DIR = HERE / ".republish-state"

COLLECTION_IRI = "https://w3id.org/battinfo/dataset/60jv-8pmb-8v8t-9y4s"
TOPSOE_IRI = "https://w3id.org/battinfo/organization/vz1v-rvhz-n77h-344c"
EXPECTED_COUNTS = {
    "material-spec": 7, "material": 9, "electrode-spec": 12, "electrode": 95,
    "cell-spec": 12, "cell-instance": 95, "test-protocol": 4, "test": 95, "dataset": 96,
}
EXPECTED_MEMBERS = 95

DEFAULT_WORKSPACE = "battinfo-records"
DEFAULT_PUBLISHER = "battinfo-records-bot"
# A cell spec's source_local_id is manufacturer--model--year (battinfo.ws.submit). The
# corpus was published in 2026; a fixed year keeps the envelope deterministic.
CELL_SPEC_YEAR = 2026

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
PRODUCTION_CONFIRM_ENV = "FLORES_REPUBLISH_CONFIRM"
PUBLISHER_KEY_ENV = "FLORES_REPUBLISH_PUBLISHER_KEY"
ADMIN_TOKEN_ENV = "FLORES_REPUBLISH_ADMIN_TOKEN"
SUBMISSION_KEY_HEADER = "X-Battinfo-API-Key"
ADMIN_TOKEN_HEADER = "X-Battinfo-Admin-Token"

STEPS = ("preflight", "organization", "collection", "records", "supersede",
         "profiles", "rerender", "postflight")
WRITE_STEPS = {"organization", "collection", "records", "supersede", "profiles", "rerender"}
APPROVABLE = {"validated", "staged_unanchored"}

# Envelope provenance, as battinfo.ws.submit stamps it.
SOURCE_SYSTEM = "battinfo-authoring"
WORKFLOW_NAME = "authoring-workspace-submission"

INTERNAL_IRI_RE = re.compile(
    r"^https://w3id\.org/battinfo/(?P<segment>[a-z_-]+)/(?P<uid>[0-9a-hjkmnp-tv-z]{4}(?:-[0-9a-hjkmnp-tv-z]{4}){3})$"
)


# --------------------------------------------------------------------------
# The corpus
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class RecordType:
    directory: str
    resource_type: str   # registry resource type
    body_key: str        # object in the file that carries the record's own id
    record_key: str      # key under semantic_payload.battinfo_records
    rdf_type: str


# Dependency order: a record's references resolve before it is approved.
RECORD_TYPES: tuple[RecordType, ...] = (
    RecordType("material-spec", "material_spec", "material_spec", "material_spec", "MaterialSpec"),
    RecordType("material", "material", "material", "material", "Material"),
    RecordType("electrode-spec", "electrode_spec", "electrode_spec", "electrode_spec", "ElectrodeSpec"),
    RecordType("electrode", "electrode", "electrode", "electrode", "Electrode"),
    RecordType("cell-spec", "cell_spec", "cell_spec", "cell_spec", "CellSpecification"),
    RecordType("cell-instance", "cell", "cell_instance", "cell", "CellInstance"),
    RecordType("test-protocol", "test_spec", "test_spec", "test_spec", "TestSpec"),
    RecordType("test", "test", "test", "test", "BatteryTest"),
    RecordType("dataset", "dataset", "dataset", "dataset", "Dataset"),
)
ORGANIZATION_TYPE = RecordType("organization", "organization", "organization", "organization", "Organization")
TYPE_BY_DIRECTORY = {t.directory: t for t in RECORD_TYPES}
# supersede-map.json names the record body key; the registry names the resource type.
MAP_TYPE_TO_RESOURCE = {"cell_instance": "cell"}

# The registry's JSON schema per record body key (validation/schema_gate.py).
SCHEMA_FILE = {
    "cell_spec": "cell-spec.schema.json", "cell_instance": "cell-instance.schema.json",
    "test_spec": "test-protocol.schema.json", "test": "test.schema.json",
    "dataset": "dataset.schema.json", "organization": "organization.schema.json",
    "material_spec": "material-spec.schema.json", "material": "material.schema.json",
    "electrode_spec": "electrode-spec.schema.json", "electrode": "electrode.schema.json",
}


@dataclass
class Record:
    path: Path
    type: RecordType
    raw: dict[str, Any]
    source_local_id_hint: str | None = None   # organizations: the directory slug

    @property
    def body(self) -> dict[str, Any]:
        body = self.raw.get(self.type.body_key)
        return body if isinstance(body, dict) else {}

    @property
    def iri(self) -> str:
        return self.body["id"]

    @property
    def canonical_id(self) -> str:
        return self.iri.rstrip("/").rsplit("/", 1)[-1]

    @property
    def label(self) -> str:
        return f"{self.type.resource_type}/{self.canonical_id}"


def load_corpus(organization_path: Path) -> tuple[list[Record], Record]:
    records: list[Record] = []
    for rtype in RECORD_TYPES:
        for path in sorted((RECORDS / rtype.directory).glob("*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            record = Record(path=path, type=rtype, raw=raw)
            if not isinstance(record.body.get("id"), str):
                raise SystemExit(f"{path}: no {rtype.body_key}.id")
            records.append(record)
    org_raw = json.loads(organization_path.read_text(encoding="utf-8"))
    organization = Record(path=organization_path, type=ORGANIZATION_TYPE, raw=org_raw,
                          source_local_id_hint="topsoe")
    return records, organization


def corpus_fingerprint(records: list[Record], organization: Record) -> str:
    """Content hash of the corpus, independent of line endings and key order."""
    digest = hashlib.sha256()
    for record in [organization, *records]:
        digest.update(record.iri.encode())
        digest.update(json.dumps(record.raw, sort_keys=True, ensure_ascii=False).encode())
    return digest.hexdigest()[:10]


def iter_internal_iris(node: Any, path: str = "") -> Iterator[tuple[str, str]]:
    if isinstance(node, dict):
        for key, value in node.items():
            yield from iter_internal_iris(value, f"{path}.{key}" if path else key)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from iter_internal_iris(value, f"{path}[{index}]")
    elif isinstance(node, str) and INTERNAL_IRI_RE.match(node):
        yield path, node


# --------------------------------------------------------------------------
# Submission envelopes (mirrors battinfo-registry scripts/preview_staged_batch.py
# build_submission at c4a89f4, which mirrors battinfo.ws.submit)
# --------------------------------------------------------------------------


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else ""


def _slugify(value: str) -> str:
    lowered = "".join(char if char.isalnum() else "-" for char in value.lower())
    while "--" in lowered:
        lowered = lowered.replace("--", "-")
    return lowered.strip("-")


@dataclass
class Graph:
    cell_spec_by_iri: dict[str, dict[str, Any]] = field(default_factory=dict)
    cell_datasets: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    cell_tests: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    spec_tests: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    dataset_links: dict[str, dict[str, str | None]] = field(default_factory=dict)


def build_graph(records: list[Record]) -> Graph:
    graph = Graph()
    for record in records:
        if record.type.resource_type == "cell_spec":
            graph.cell_spec_by_iri[record.iri] = record.raw
    for record in records:
        if record.type.resource_type == "dataset":
            about = [item for item in record.body.get("about") or [] if isinstance(item, str)]
            cell = next((item for item in about if "/cell/" in item), None)
            test = next((item for item in about if "/test/" in item), None)
            graph.dataset_links[record.iri] = {"cell": cell, "test": test}
            if cell:
                graph.cell_datasets[cell].append(record.iri)
        elif record.type.resource_type == "test":
            if _text(record.body.get("cell_id")):
                graph.cell_tests[record.body["cell_id"]].append(record.iri)
            if _text(record.body.get("protocol_id")):
                graph.spec_tests[record.body["protocol_id"]].append(record.iri)
    return graph


def record_title(record: Record) -> str:
    body = record.body
    if record.type.resource_type == "cell_spec":
        # The record's own title wins; "<manufacturer> <model>" is only the fallback for a
        # cell spec without one (what battinfo.ws.submit() used to send for every cell spec).
        if _text(body.get("name")):
            return _text(body["name"])[:255]
        manufacturer = body.get("manufacturer")
        name = manufacturer.get("name") if isinstance(manufacturer, dict) else manufacturer
        title = f"{_text(name)} {_text(body.get('model'))}".strip()
        if title:
            return title[:255]
    if record.type.resource_type == "cell":
        for key in ("name", "serial_number", "short_id"):
            if _text(body.get(key)):
                return _text(body[key])[:255]
    for key in ("name", "short_id"):
        if _text(body.get(key)):
            return _text(body[key])[:255]
    return record.path.stem


def derived_source_local_id(record: Record) -> str:
    if record.source_local_id_hint:
        return record.source_local_id_hint
    body = record.body
    if record.type.resource_type == "cell_spec":
        manufacturer = body.get("manufacturer")
        name = manufacturer.get("name") if isinstance(manufacturer, dict) else manufacturer
        model = _text(body.get("model"))
        if _text(name) or model:
            return f"{_slugify(_text(name))}--{_slugify(model)}--{body.get('year') or CELL_SPEC_YEAR}"
    for key in ("short_id", "batch_id", "serial_number"):
        if _text(body.get(key)):
            return _text(body[key])
    return record.path.stem


def related_resources(record: Record, graph: Graph) -> list[dict[str, str]]:
    body = record.body
    rtype = record.type.resource_type
    relations: list[dict[str, str]] = []

    def link(relationship: str, target_type: str, value: Any) -> None:
        if _text(value):
            relations.append({"relationship": relationship, "resource_type": target_type,
                              "canonical_iri": value.strip()})

    if rtype == "cell":
        link("instanceOf", "cell_spec", body.get("cell_spec_id"))
        for iri in graph.cell_datasets.get(record.iri, []):
            link("hasDataset", "dataset", iri)
        for iri in graph.cell_tests.get(record.iri, []):
            link("hasTest", "test", iri)
    elif rtype == "test_spec":
        for iri in graph.spec_tests.get(record.iri, []):
            link("hasTest", "test", iri)
    elif rtype == "test":
        link("testsCell", "cell", body.get("cell_id"))
        link("conformsTo", "test_spec", body.get("protocol_id"))
    elif rtype == "dataset":
        links = graph.dataset_links.get(record.iri, {})
        link("aboutCell", "cell", links.get("cell"))
        link("generatedByTest", "test", links.get("test"))
    elif rtype == "cell_spec":
        for holder, relationship in (
            ("positive_electrode", "hasPositiveElectrodeSpec"),
            ("negative_electrode", "hasNegativeElectrodeSpec"),
            ("working_electrode", "hasWorkingElectrodeSpec"),
            ("counter_electrode", "hasCounterElectrodeSpec"),
        ):
            nested = record.raw.get(holder)
            link(relationship, "electrode_spec",
                 record.raw.get(f"{holder}_spec_id")
                 or (nested.get("electrode_spec_id") if isinstance(nested, dict) else None))
    elif rtype == "electrode":
        link("instanceOf", "electrode_spec", body.get("electrode_spec_id"))
    elif rtype == "electrode_spec":
        link("hasActiveMaterial", "material_spec", body.get("active_material_spec_id"))
        collector = body.get("current_collector")
        if isinstance(collector, dict):
            link("hasCurrentCollectorMaterial", "material_spec", collector.get("material_spec_id"))
    elif rtype == "material":
        link("instanceOf", "material_spec", body.get("material_spec_id"))
    return relations


def dataset_distributions(body: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split a dataset's files into (page-model refs, inner-record entries), as ws.submit does."""
    top_level: list[dict[str, Any]] = []
    inner: list[dict[str, Any]] = []
    for entry in body.get("distributions") or []:
        if not isinstance(entry, dict):
            continue
        name = _text(entry.get("name"))
        url = _text(entry.get("content_url")) or _text(body.get("access_url"))
        media_type = entry.get("encoding_format")
        if not url:
            inner.append(entry)
        elif name.endswith(".plot.json"):
            top_level.append({"title": name, "access_url": url, "role": "plot_data",
                              "media_type": media_type or "application/json"})
        elif name.endswith(".png"):
            top_level.append({"title": name, "access_url": url, "role": "plot_static",
                              "media_type": media_type or "image/png"})
        else:
            inner.append(entry)
            top_level.append({"title": name or _text(entry.get("role")) or "data", "access_url": url,
                              "role": _text(entry.get("role")) or "processed", "media_type": media_type})
    return top_level, inner


def build_envelope(record: Record, graph: Graph, *, workspace_id: str, publisher_id: str,
                   source_local_id: str, source_version: str) -> dict[str, Any]:
    raw = record.raw
    distributions: list[dict[str, Any]] = []
    if record.type.resource_type == "dataset" and "distributions" in record.body:
        # The collection has no distributions key at all; leave it absent rather than
        # send an empty list the schema's minItems rejects (close-out defect D2).
        distributions, inner = dataset_distributions(record.body)
        body = dict(record.body)
        if inner:
            body["distributions"] = inner
        else:
            body.pop("distributions")
        raw = {**raw, "dataset": body}
    records_block: dict[str, Any] = {record.type.record_key: raw}
    if record.type.resource_type == "cell":
        spec = graph.cell_spec_by_iri.get(_text(record.body.get("cell_spec_id")))
        if spec is not None:
            records_block["cell_spec"] = spec
    provenance: dict[str, Any] = {"source_system": SOURCE_SYSTEM, "workflow_name": WORKFLOW_NAME}
    record_provenance = raw.get("provenance")
    if isinstance(record_provenance, dict):
        citation = _text(record_provenance.get("citation"))
        if citation.startswith("https://doi.org/"):
            provenance["citation_doi"] = citation[len("https://doi.org/"):]
    return {
        "workspace_id": workspace_id,
        "publisher_id": publisher_id,
        "resource_type": record.type.resource_type,
        "source_local_id": source_local_id,
        "source_version": source_version,
        "title": record_title(record),
        "semantic_payload": {"@type": record.type.rdf_type, "battinfo_records": records_block},
        "related_resources": related_resources(record, graph),
        "distributions": distributions,
        "provenance": provenance,
        "publication_intent": {"mode": "staged-publication"},
    }


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------


class HttpError(RuntimeError):
    def __init__(self, method: str, url: str, status: int, body: str) -> None:
        super().__init__(f"{method} {url} -> HTTP {status}: {body[:400]}")
        self.status = status
        self.body = body


@dataclass
class Response:
    status: int
    body: Any
    headers: dict[str, str]
    text: str


class Target:
    def __init__(self, base_url: str, *, publisher_key: str | None, admin_token: str | None,
                 timeout: float, allow_writes: bool) -> None:
        self.base_url = base_url.rstrip("/")
        self.publisher_key = publisher_key
        self.admin_token = admin_token
        self.timeout = timeout
        self.allow_writes = allow_writes
        self.requests = Counter()

    def request(self, method: str, path: str, *, body: Any = None, headers: dict[str, str] | None = None,
                accept: str = "application/json", retries: int = 3,
                follow_redirects: bool = True) -> Response:
        if method != "GET" and not self.allow_writes:
            raise RuntimeError(f"refusing {method} {path}: not in --apply mode")
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        merged = {"Accept": accept, "User-Agent": "flores-republish/1"}
        if data is not None:
            merged["Content-Type"] = "application/json"
        merged.update(headers or {})
        opener = urllib.request.build_opener() if follow_redirects else urllib.request.build_opener(_NoRedirect)
        last_error: Exception | None = None
        for attempt in range(retries):
            self.requests[method] += 1
            request = urllib.request.Request(url, data=data, method=method, headers=merged)
            try:
                with opener.open(request, timeout=self.timeout) as response:
                    return _response(response.status, response.read(), dict(response.headers))
            except urllib.error.HTTPError as error:
                payload = error.read()
                if error.code >= 500 and attempt + 1 < retries:
                    last_error = error
                    time.sleep(2 * (attempt + 1))
                    continue
                return _response(error.code, payload, dict(error.headers or {}))
            except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
                last_error = error
                if attempt + 1 < retries:
                    time.sleep(2 * (attempt + 1))
                    continue
        raise RuntimeError(f"{method} {url} failed after {retries} attempts: {last_error}")

    def get(self, path: str, **kwargs: Any) -> Response:
        return self.request("GET", path, **kwargs)

    def publisher_headers(self) -> dict[str, str]:
        return {SUBMISSION_KEY_HEADER: self.publisher_key or ""}

    def admin_headers(self) -> dict[str, str]:
        return {ADMIN_TOKEN_HEADER: self.admin_token or ""}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:  # noqa: D401
        return None


def _response(status: int, payload: bytes, headers: dict[str, str]) -> Response:
    text = payload.decode("utf-8", errors="replace")
    try:
        body = json.loads(text) if text else None
    except ValueError:
        body = None
    return Response(status=status, body=body, headers={k.lower(): v for k, v in headers.items()}, text=text)


def error_text(response: Response) -> str:
    detail = response.body.get("detail") if isinstance(response.body, dict) else None
    if isinstance(detail, dict):
        message = detail.get("message") or detail.get("reason") or ""
        issues = detail.get("errors") or detail.get("issues") or []
        first = f" first={json.dumps(issues[0], sort_keys=True)[:300]}" if isinstance(issues, list) and issues else ""
        return f"HTTP {response.status}: {message}{first}"
    return f"HTTP {response.status}: {str(detail if detail is not None else response.text)[:300]}"


# --------------------------------------------------------------------------
# The target's state, read in one listing
# --------------------------------------------------------------------------


@dataclass
class Index:
    by_iri: dict[str, dict[str, Any]]
    by_local_id: dict[tuple[str, str, str], str]   # (publisher, type, source_local_id) -> iri

    def status(self, iri: str) -> str | None:
        row = self.by_iri.get(iri)
        return row.get("status") if row else None


def fetch_index(target: Target) -> Index:
    rows: list[dict[str, Any]] = []
    offset, limit = 0, 1000
    while True:
        response = target.get(f"/resources?status=all&limit={limit}&offset={offset}")
        if response.status != 200 or not isinstance(response.body, list):
            raise RuntimeError(f"listing the target failed: {error_text(response)}")
        rows.extend(response.body)
        total = int(response.headers.get("x-total-count", len(rows)))
        offset += limit
        if offset >= total or not response.body:
            break
    by_iri = {row["canonical_iri"]: row for row in rows}
    by_local_id = {(row["publisher_id"], row["resource_type"], row["source_local_id"]): row["canonical_iri"]
                   for row in rows}
    return Index(by_iri=by_iri, by_local_id=by_local_id)


# --------------------------------------------------------------------------
# State / log
# --------------------------------------------------------------------------


class State:
    def __init__(self, path: Path, *, enabled: bool) -> None:
        self.path = path
        self.enabled = enabled
        self.data: dict[str, Any] = {"steps": {}, "submissions": {}, "supersedes": {}, "log": []}
        if path.is_file():
            self.data = json.loads(path.read_text(encoding="utf-8"))

    def log(self, event: str, **fields: Any) -> None:
        self.data["log"].append({"at": _now(), "event": event, **fields})
        self.save()

    def step_done(self, step: str, summary: dict[str, Any]) -> None:
        self.data["steps"][step] = {"done": True, "at": _now(), "summary": summary}
        self.save()

    def step_incomplete(self, step: str, summary: dict[str, Any]) -> None:
        self.data["steps"][step] = {"done": False, "at": _now(), "summary": summary}
        self.save()

    def save(self) -> None:
        if not self.enabled:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        # On Windows a virus scanner or the search indexer can hold a just-written file
        # for a moment, and os.replace then fails with "Access is denied". A state file
        # that cannot be saved must not abort a half-applied run, so retry briefly.
        for attempt in range(40):
            try:
                os.replace(tmp, self.path)
                return
            except PermissionError:
                if attempt == 39:
                    raise
                time.sleep(0.25)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------
# The supersede plan
# --------------------------------------------------------------------------


@dataclass
class SupersedeRow:
    published_id: str
    resource_type: str
    status: str            # replaced | split | extra
    successor: str
    rule: str
    # Every successor, the primary first, when a record split into several that are
    # all its successors (a spec that covered two designs). Empty for a single
    # successor, including a material lot, whose one successor is its electrode spec.
    successors: tuple[str, ...] = ()

    @property
    def status_body(self) -> dict[str, Any]:
        body: dict[str, Any] = {"status": "superseded", "replaced_by_iri": self.successor}
        if self.successors:
            body["replaced_by_iris"] = list(self.successors)
        return body

    def matches(self, current: dict[str, Any]) -> bool:
        """True when the target already holds this row's tombstone."""
        return (current.get("status") == "superseded"
                and current.get("replaced_by_iri") == self.successor
                and list(current.get("replaced_by_iris") or []) == list(self.successors))

    @property
    def canonical_id(self) -> str:
        return self.published_id.rstrip("/").rsplit("/", 1)[-1]


def _natural_key(text: str) -> list[Any]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", text)]


def build_supersede_plan(records: list[Record], overrides_path: Path) -> tuple[list[SupersedeRow], dict[str, Any], list[str]]:
    """One primary successor per replaced/split row, plus the full list for a split spec.

    Returns (rows, map document, errors)."""
    document = json.loads(SUPERSEDE_MAP.read_text(encoding="utf-8"))
    overrides_doc = json.loads(overrides_path.read_text(encoding="utf-8")) if overrides_path.is_file() else {}
    overrides: dict[str, str] = overrides_doc.get("overrides") or {}
    errors: list[str] = []
    by_iri = {record.iri: record for record in records}

    # batch label of an electrode spec = the batch_id its discs carry
    spec_label: dict[str, str] = {}
    disc_spec: dict[str, str] = {}
    for record in records:
        if record.type.resource_type == "electrode":
            spec_label.setdefault(record.body["electrode_spec_id"], record.body.get("batch_id") or "")
            disc_spec[record.iri] = record.body["electrode_spec_id"]

    def label_of(iri: str) -> str:
        record = by_iri[iri]
        if record.type.resource_type == "electrode_spec":
            return spec_label.get(iri, "")
        if record.type.resource_type == "cell_spec":
            return spec_label.get(record.raw.get("working_electrode_spec_id") or "", "")
        return iri

    rows: list[SupersedeRow] = []
    used_overrides: set[str] = set()
    for entry in document["entries"]:
        if entry["status"] == "retained":
            continue
        published = entry["published_id"]
        resource_type = MAP_TYPE_TO_RESOURCE.get(entry["published_type"], entry["published_type"])
        successors = entry["successors"]
        missing = [iri for iri in successors if iri not in by_iri]
        if missing:
            errors.append(f"supersede map: {published} names successors not in this corpus: {missing}")
            continue
        allowed = set(successors)
        listed = False
        if entry["status"] == "replaced":
            choice, rule = successors[0], "replaced"
        elif entry["published_type"] == "material":
            specs = sorted({disc_spec[iri] for iri in successors})
            if len(specs) != 1:
                errors.append(f"supersede map: material lot {published} has discs of {len(specs)} electrode specs")
                continue
            choice, rule = specs[0], "material lot -> electrode spec of its discs"
            allowed |= set(specs)
        else:
            # A spec that covered two designs: both are its successors, so the
            # tombstone lists both (owner ruling 2026-10-07, option 3). The primary is
            # only an ordering for clients that read one successor.
            choice = sorted(successors, key=lambda iri: (_natural_key(label_of(iri)), iri))[0]
            rule = f"split -> all {len(successors)} successors, primary sorts first ({label_of(choice)})"
            listed = True
        if published in overrides:
            used_overrides.add(published)
            wanted = overrides[published]
            if wanted not in allowed:
                errors.append(f"override for {published} names {wanted}, which is not one of its successors")
                continue
            choice, rule = wanted, "override (split-successors.json)" + (" as primary" if listed else "")
        ordered = tuple([choice, *[iri for iri in successors if iri != choice]]) if listed else ()
        rows.append(SupersedeRow(published, resource_type, entry["status"], choice, rule, ordered))
    for published in set(overrides) - used_overrides:
        errors.append(f"override for {published} matches no replaced or split row")
    for extra in overrides_doc.get("extra_supersedes") or []:
        try:
            rows.append(SupersedeRow(extra["published_id"], extra["resource_type"], "extra",
                                     extra["successor"], "extra_supersedes (split-successors.json)"))
        except KeyError as error:
            errors.append(f"extra_supersedes entry lacks {error}")
    return rows, document, errors


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------


def validate_with_battinfo(records: list[Record]) -> tuple[bool, list[str]]:
    try:
        import battinfo as B  # noqa: N812
    except ImportError:
        return False, ["battinfo is not importable: record validation skipped"]
    errors: list[str] = []
    for record in records:
        source_root = RECORDS if record.type is not ORGANIZATION_TYPE else None
        report = B.validate_record_report(record.raw, source_root=source_root)
        for issue in report.issues:
            if issue.severity == "error":
                errors.append(f"{record.label}: {issue.message}")
    return True, errors


def validate_with_target_schemas(target: Target, records: list[Record]) -> tuple[bool, list[str]]:
    """Validate each record against the JSON schema the target itself serves at /schema/."""
    try:
        from jsonschema import Draft202012Validator
        from referencing import Registry, Resource
    except ImportError:
        return False, ["jsonschema/referencing not importable: target-schema validation skipped"]
    prefix = "https://w3id.org/battinfo/schema/"
    cache: dict[str, Any] = {}

    def fetch(uri: str) -> Resource:
        if uri not in cache:
            if not uri.startswith(prefix):
                raise LookupError(uri)
            response = target.get(f"/schema/{uri[len(prefix):]}")
            if response.status != 200 or not isinstance(response.body, dict):
                raise LookupError(f"{uri}: HTTP {response.status}")
            cache[uri] = Resource.from_contents(response.body)
        return cache[uri]

    registry = Registry(retrieve=fetch)
    errors: list[str] = []
    validators: dict[str, Any] = {}
    for record in records:
        schema_file = SCHEMA_FILE[record.type.body_key]
        if schema_file not in validators:
            validators[schema_file] = Draft202012Validator(fetch(prefix + schema_file).contents, registry=registry)
        for error in sorted(validators[schema_file].iter_errors(record.raw), key=lambda e: list(e.path))[:5]:
            location = ".".join(str(part) for part in error.path) or "<root>"
            errors.append(f"{record.label}: {location}: {error.message}")
    return True, errors


# --------------------------------------------------------------------------
# The driver
# --------------------------------------------------------------------------


class Driver:
    def __init__(self, args: argparse.Namespace, target: Target, state: State) -> None:
        self.args = args
        self.target = target
        self.state = state
        self.records, self.organization = load_corpus(args.organization_record)
        self.collection = next(r for r in self.records if r.iri == COLLECTION_IRI)
        self.others = [r for r in self.records if r.iri != COLLECTION_IRI]
        self.graph = build_graph(self.records)
        self.source_version = args.source_version or (
            f"flores-v5-{corpus_fingerprint(self.records, self.organization)}")
        self.supersede_rows, self.supersede_doc, self.plan_errors = build_supersede_plan(
            self.records, args.overrides)
        self._index: Index | None = None

    # -- helpers -------------------------------------------------------------

    def index(self, *, refresh: bool = False) -> Index:
        if self._index is None or refresh:
            self._index = fetch_index(self.target)
        return self._index

    def say(self, message: str) -> None:
        print(message, flush=True)

    def live_local_id(self, record: Record) -> tuple[str, str | None]:
        """(source_local_id to submit under, problem). A live IRI keeps its live id."""
        row = self.index().by_iri.get(record.iri)
        if row is not None:
            if row["publisher_id"] != self.args.publisher_id:
                return "", (f"{record.label} is live under publisher {row['publisher_id']!r}, "
                            f"not {self.args.publisher_id!r}: cannot version it")
            return row["source_local_id"], None
        local_id = derived_source_local_id(record)
        holder = self.index().by_local_id.get((self.args.publisher_id, record.type.resource_type, local_id))
        if holder is not None and holder != record.iri:
            return local_id, (f"{record.label}: source_local_id {local_id!r} already belongs to {holder}; "
                              "submitting would rewrite that record's identity")
        return local_id, None

    def is_current(self, record: Record) -> bool:
        """Published under this corpus version AND under the title this driver sends.

        The title is not part of the content hash, so a record whose registry title is
        stale (a cell spec once titled "<manufacturer> <model>") is resubmitted; the
        registry updates the title of an unchanged record without minting a version."""
        row = self.index().by_iri.get(record.iri)
        return bool(row and row.get("status") == "published" and row.get("source_version") == self.source_version
                    and row.get("title") == record_title(record))

    # -- step 0 --------------------------------------------------------------

    def preflight(self) -> bool:
        errors: list[str] = []
        warnings: list[str] = []
        self.say("== 0 preflight")
        health = self.target.get("/health")
        if health.status != 200 or not isinstance(health.body, dict) or health.body.get("status") != "ok":
            errors.append(f"target health: {error_text(health)}")
        else:
            self.say(f"  health ok (corpus_revision {health.body.get('corpus_revision')})")

        # auth
        if self.target.publisher_key:
            me = self.target.get("/me", headers=self.target.publisher_headers())
            if me.status != 200:
                errors.append(f"publisher key rejected: {error_text(me)}")
            elif (me.body.get("publisher_id"), me.body.get("workspace_id")) != (self.args.publisher_id, self.args.workspace_id):
                errors.append(f"publisher key belongs to {me.body.get('publisher_id')}/{me.body.get('workspace_id')}, "
                              f"expected {self.args.publisher_id}/{self.args.workspace_id}")
            else:
                self.say(f"  publisher key ok ({self.args.publisher_id} in {self.args.workspace_id})")
        else:
            (errors if self.args.apply else warnings).append(f"{PUBLISHER_KEY_ENV} is not set")
        if self.target.admin_token:
            if self.target.allow_writes:
                # Approve a submission id that cannot exist: the admin check runs first
                # (403 on a bad token), then 404. Nothing can be written either way.
                probe = self.target.request(
                    "POST", "/submissions/00000000-0000-0000-0000-000000000000/approve",
                    headers=self.target.admin_headers(), body={"reviewed_by": "preflight-probe"})
                if probe.status == 404:
                    self.say("  admin token ok")
                else:
                    errors.append(f"admin token rejected: {error_text(probe)}")
            else:
                warnings.append("admin token present; probed only with --apply (a dry run sends no POST)")
        else:
            (errors if self.args.apply else warnings).append(f"{ADMIN_TOKEN_ENV} is not set")

        # corpus shape
        counts = Counter(r.type.directory for r in self.records)
        for directory, expected in EXPECTED_COUNTS.items():
            if counts[directory] != expected:
                errors.append(f"records/{directory}: {counts[directory]} records, expected {expected}")
        members = [r for r in self.records if r.type.resource_type == "dataset" and r.body.get("series_id") == COLLECTION_IRI]
        if len(members) != EXPECTED_MEMBERS:
            errors.append(f"{len(members)} datasets carry series_id {COLLECTION_IRI}, expected {EXPECTED_MEMBERS}")
        if self.collection.body.get("series_id"):
            errors.append("the collection itself carries series_id")
        if self.organization.iri != TOPSOE_IRI:
            errors.append(f"organization record is {self.organization.iri}, expected {TOPSOE_IRI}")
        self.say(f"  corpus: {len(self.records)} records + 1 organization, {len(members)} collection members, "
                 f"source_version {self.source_version}")

        # identity pins: names are display text, IRIs never move
        pins_path = HERE / "published-iris.json"
        if pins_path.is_file():
            pinned = {iri for table in json.loads(pins_path.read_text(encoding="utf-8")).values()
                      for iri in table.values()}
            local = {record.iri for record in self.records}
            if local != pinned:
                errors.append(f"identity pins: {len(pinned - local)} pinned IRIs missing from the corpus, "
                              f"{len(local - pinned)} unpinned IRIs in it (published-iris.json)")
            else:
                self.say(f"  identity pins ok: all {len(pinned)} records carry their published IRI")
        else:
            errors.append("identity pins: published-iris.json is missing")
        if self.collection.iri != COLLECTION_IRI:
            errors.append(f"identity pins: the collection is {self.collection.iri}, expected {COLLECTION_IRI}")

        # validation
        everything = [self.organization, *self.records]
        ran, problems = validate_with_battinfo(everything)
        if not ran:
            (errors if self.args.production else warnings).extend(problems)
        else:
            errors.extend(problems)
            self.say(f"  battinfo validation: {len(problems)} error(s) over {len(everything)} records")
        ran, problems = validate_with_target_schemas(self.target, everything)
        if not ran:
            (errors if self.args.production else warnings).extend(problems)
        else:
            errors.extend(problems)
            self.say(f"  target-schema validation: {len(problems)} error(s) over {len(everything)} records")

        # supersede map
        errors.extend(self.plan_errors)
        index = self.index()
        if self.supersede_doc.get("published_corpus", {}).get("records") != 319:
            warnings.append("supersede map does not describe 319 published identifiers")
        retained = [e["published_id"] for e in self.supersede_doc["entries"] if e["status"] == "retained"]
        corpus_iris = {r.iri for r in self.records}
        for iri in retained:
            if iri not in corpus_iris:
                errors.append(f"supersede map: retained {iri} is not in this corpus")
            if index.status(iri) != "published":
                errors.append(f"supersede map: retained {iri} is {index.status(iri) or 'absent'} on the target")
        for row in self.supersede_rows:
            status = index.status(row.published_id)
            replaced_by = (index.by_iri.get(row.published_id) or {}).get("replaced_by_iri")
            if status == "published":
                continue
            if row.matches(index.by_iri.get(row.published_id) or {}):
                continue   # step 4 already applied it
            errors.append(f"supersede map: {row.published_id} is {status or 'absent'} on the target"
                          + (f" (replaced by {replaced_by})" if replaced_by else ""))
        statuses = Counter(e["status"] for e in self.supersede_doc["entries"])
        self.say(f"  supersede map: {dict(statuses)}; {len(self.supersede_rows)} status calls planned")
        listed = [row for row in self.supersede_rows if row.successors]
        if listed:
            self.say(f"  split specs: {len(listed)} tombstones list all their successors")
            if not self.target_accepts_successor_lists():
                errors.append(f"{len(listed)} split rows need a tombstone that lists several successors, but the "
                              "target does not declare replaced_by_iris; deploy the registry change first")

        # identity collisions and outside references
        for record in [self.organization, *self.records]:
            _, problem = self.live_local_id(record)
            if problem:
                errors.append(problem)
        provided = corpus_iris | {TOPSOE_IRI}
        outside: dict[str, list[str]] = defaultdict(list)
        for record in self.records:
            for path, iri in iter_internal_iris(record.raw):
                if iri not in provided:
                    outside[iri].append(f"{record.label}:{path}")
        for iri, sites in sorted(outside.items()):
            if index.status(iri) != "published":
                errors.append(f"outside reference {iri} is {index.status(iri) or 'absent'} on the target "
                              f"(cited by {sites[0]}{' and others' if len(sites) > 1 else ''})")
        self.say(f"  outside references: {len(outside)} ({', '.join(sorted(outside)) or 'none'})")

        for warning in warnings:
            self.say(f"  WARNING {warning}")
        for error in errors[:60]:
            self.say(f"  ERROR {error}")
        if len(errors) > 60:
            self.say(f"  ... and {len(errors) - 60} more errors")
        self.say(f"  preflight: {'FAILED' if errors else 'passed'} ({len(errors)} errors, {len(warnings)} warnings)")
        self.state.log("preflight", errors=len(errors), warnings=len(warnings), first_errors=errors[:10])
        return not errors

    # -- plan ----------------------------------------------------------------

    def print_plan(self) -> None:
        index = self.index()
        self.say("\n== plan")
        org = "already published" if index.status(TOPSOE_IRI) == "published" else "publish"
        self.say(f"  1 organization  Topsoe {TOPSOE_IRI}: {org}")
        self.say(f"  2 collection    {COLLECTION_IRI}: "
                 f"{'current' if self.is_current(self.collection) else 'submit + approve'}")
        plan = Counter()
        for record in self.others:
            if self.is_current(record):
                plan[(record.type.resource_type, "current")] += 1
            elif record.iri in index.by_iri:
                plan[(record.type.resource_type, "new version of a live identifier")] += 1
            else:
                plan[(record.type.resource_type, "new identifier")] += 1
        self.say(f"  3 records       {len(self.others)} in dependency order:")
        for rtype in RECORD_TYPES:
            parts = [f"{what} {n}" for (t, what), n in sorted(plan.items()) if t == rtype.resource_type]
            if parts:
                self.say(f"      {rtype.resource_type:<15} {', '.join(parts)}")
        todo = Counter()
        for row in self.supersede_rows:
            done = index.status(row.published_id) == "superseded"
            todo[(row.status, "done" if done else "to apply")] += 1
        self.say(f"  4 supersede     {len(self.supersede_rows)} status calls: "
                 + ", ".join(f"{s} {w} {n}" for (s, w), n in sorted(todo.items())))
        for row in self.supersede_rows:
            if row.status != "replaced":
                self.say(f"      {row.status:<6} {row.published_id} -> {row.successor}  [{row.rule}]")
        profiles = json.loads(PROFILE_INDEX.read_text(encoding="utf-8")) if PROFILE_INDEX.is_file() else {}
        self.say(f"  5 profiles      {len(profiles)} plot profiles via upload_profiles.py "
                 f"({'production object storage' if self.args.production else 'skipped for a non-production target'}"
                 f"{'; mirror to ' + str(self.args.profiles_mirror) if self.args.profiles_mirror else ''})")
        self.say(f"  6 rerender      {' '.join(self.rerender_command() or ['(manual: see --registry-repo)'])}")
        self.say("  7 postflight    426 resolves, "
                 f"{len(self.supersede_rows)} tombstones, {EXPECTED_MEMBERS} members, reference sweep")

    # -- steps 1-3 -----------------------------------------------------------

    def publish(self, record: Record) -> tuple[bool, str]:
        """Submit (idempotent) and approve one record. Returns (published, note)."""
        if self.is_current(record):
            return True, "current"
        local_id, problem = self.live_local_id(record)
        if problem:
            return False, problem
        envelope = build_envelope(record, self.graph, workspace_id=self.args.workspace_id,
                                  publisher_id=self.args.publisher_id, source_local_id=local_id,
                                  source_version=self.source_version)
        response = self.target.request("POST", "/submissions", body=envelope,
                                       headers=self.target.publisher_headers())
        if response.status not in (200, 201):
            self.state.log("submit_failed", iri=record.iri, error=error_text(response))
            return False, f"submit {error_text(response)}"
        submission = response.body
        self.state.data["submissions"][record.iri] = {
            "id": submission["id"], "status": submission["status"], "created": response.status == 201}
        self.state.log("submitted", iri=record.iri, submission=submission["id"], status=submission["status"],
                       created=response.status == 201)
        status = submission["status"]
        if status in APPROVABLE:
            approve = self.target.request(
                "POST", f"/submissions/{submission['id']}/approve", headers=self.target.admin_headers(),
                body={"reviewed_by": self.args.reviewer,
                      "review_comment": f"Flores corpus v5 republish ({self.source_version})."})
            if approve.status != 200:
                self.state.log("approve_failed", iri=record.iri, submission=submission["id"], error=error_text(approve))
                return False, f"approve {error_text(approve)}"
            status = approve.body["status"]
            self.state.data["submissions"][record.iri]["status"] = status
            self.state.log("approved", iri=record.iri, submission=submission["id"], status=status)
        if status != "published":
            return False, f"submission {submission['id']} is {status}"
        row = self.index().by_iri.setdefault(record.iri, {"canonical_iri": record.iri})
        row.update({"status": "published", "source_version": self.source_version,
                    "publisher_id": self.args.publisher_id, "resource_type": record.type.resource_type,
                    "source_local_id": local_id, "title": record_title(record)})
        return True, "published"

    def publish_many(self, step: str, records: list[Record]) -> bool:
        outcome = Counter()
        pending: list[tuple[Record, str]] = []
        for number, record in enumerate(records, 1):
            ok, note = self.publish(record)
            outcome[note if ok else "failed"] += 1
            if not ok:
                pending.append((record, note))
            if number % 50 == 0:
                self.say(f"  ... {number}/{len(records)} {dict(outcome)}")
        if pending:
            # A record approved before a sibling it references can fail the link gate;
            # every sibling is published or pending by now, so one more pass settles it.
            self.say(f"  retrying {len(pending)} record(s)")
            retry, pending = pending, []
            for record, _ in retry:
                ok, note = self.publish(record)
                if ok:
                    outcome["failed"] -= 1
                    outcome[f"{note} (retry)"] += 1
                else:
                    pending.append((record, note))
        summary = {k: v for k, v in outcome.items() if v}
        for record, note in pending[:20]:
            self.say(f"  FAILED {record.label}: {note}")
        self.say(f"  {step}: {summary}")
        (self.state.step_incomplete if pending else self.state.step_done)(step, summary)
        return not pending

    def step_organization(self) -> bool:
        self.say("\n== 1 organization")
        return self.publish_many("organization", [self.organization])

    def step_collection(self) -> bool:
        self.say("\n== 2 collection")
        return self.publish_many("collection", [self.collection])

    def step_records(self) -> bool:
        self.say(f"\n== 3 records ({len(self.others)})")
        if self.index().status(COLLECTION_IRI) != "published":
            self.say("  the collection is not published yet: run step 2 first")
            return False
        return self.publish_many("records", self.others)

    # -- step 4 --------------------------------------------------------------

    def target_accepts_successor_lists(self) -> bool:
        """Whether the target's admin status payload declares replaced_by_iris.

        An older registry would ignore the field and keep only the primary successor,
        so a split row is never sent to one."""
        openapi = self.target.get("/openapi.json")
        if openapi.status != 200 or not isinstance(openapi.body, dict):
            return False
        return '"replaced_by_iris"' in json.dumps(openapi.body.get("components", {}).get("schemas", {}))

    def step_supersede(self) -> bool:
        self.say(f"\n== 4 supersede ({len(self.supersede_rows)} rows)")
        index = self.index(refresh=True)
        outcome = Counter()
        failures: list[str] = []
        for row in self.supersede_rows:
            current = index.by_iri.get(row.published_id) or {}
            if row.matches(current):
                outcome["already superseded"] += 1
                continue
            if current.get("status") != "published":
                failures.append(f"{row.published_id} is {current.get('status') or 'absent'}; not touching it")
                continue
            dead = [iri for iri in (row.successors or (row.successor,)) if index.status(iri) != "published"]
            if dead:
                failures.append(f"{row.published_id}: successor(s) not published: {dead}")
                continue
            response = self.target.request(
                "POST", f"/admin/resources/{row.resource_type}/{row.canonical_id}/status",
                headers=self.target.admin_headers(),
                body=row.status_body)
            if response.status != 200:
                failures.append(f"{row.published_id}: {error_text(response)}")
                self.state.log("supersede_failed", iri=row.published_id, error=error_text(response))
                continue
            self.state.data["supersedes"][row.published_id] = {
                "resource_type": row.resource_type, "replaced_by_iri": row.successor,
                "replaced_by_iris": list(row.successors) or None, "rule": row.rule}
            self.state.log("superseded", iri=row.published_id, replaced_by=row.successor,
                           replaced_by_all=list(row.successors) or None)
            current.update({"status": "superseded", "replaced_by_iri": row.successor,
                            "replaced_by_iris": list(row.successors) or None})
            outcome["superseded"] += 1
        for failure in failures[:20]:
            self.say(f"  FAILED {failure}")
        summary = {**{k: v for k, v in outcome.items() if v}, "failed": len(failures)}
        self.say(f"  supersede: {summary}")
        (self.state.step_incomplete if failures else self.state.step_done)("supersede", summary)
        return not failures

    # -- step 5 --------------------------------------------------------------

    def step_profiles(self) -> bool:
        self.say("\n== 5 profiles")
        index = json.loads(PROFILE_INDEX.read_text(encoding="utf-8"))
        if self.args.profiles_mirror:
            mirror: Path = self.args.profiles_mirror
            copied = current = 0
            for name, entry in sorted(index.items()):
                source = PROFILE_INDEX.parent / name
                dest = mirror / "datasets" / entry["short_id"] / name
                if dest.is_file() and hashlib.sha256(dest.read_bytes()).hexdigest() == entry["sha256"]:
                    current += 1
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(source.read_bytes())
                copied += 1
            self.say(f"  mirror {mirror}: {copied} copied, {current} already current")
        if not self.args.production:
            self.say("  object storage is production-only; not uploading for a non-production target "
                     "(upload_profiles.py --dry-run shows the plan)")
            result = subprocess.run([sys.executable, str(PROFILES_SCRIPT), "--dry-run"], cwd=HERE,
                                    capture_output=True, text=True)
            self.say("  " + (result.stdout.strip().splitlines() or ["(no output)"])[0])
            self.state.step_done("profiles", {"uploaded": 0, "reason": "non-production target",
                                              "mirrored": bool(self.args.profiles_mirror)})
            return True
        result = subprocess.run([sys.executable, str(PROFILES_SCRIPT)], cwd=HERE, text=True)
        ok = result.returncode == 0
        (self.state.step_done if ok else self.state.step_incomplete)("profiles", {"returncode": result.returncode})
        return ok

    # -- step 6 --------------------------------------------------------------

    def rerender_command(self) -> list[str] | None:
        repo: Path | None = self.args.registry_repo
        if repo is None:
            return None
        python = self.args.registry_python
        if python is None:
            for candidate in (repo / ".venv" / "Scripts" / "python.exe", repo / ".venv" / "bin" / "python"):
                if candidate.is_file():
                    python = str(candidate)
                    break
        command = [python] if python else ["uv", "run", "python"]
        command += ["scripts/rerender_record_pages.py", "--apply", "--persist-display"]
        if self.args.registry_env_file:
            command += ["--env-file", str(self.args.registry_env_file)]
        return command

    def step_rerender(self) -> bool:
        self.say("\n== 6 rerender")
        command = self.rerender_command()
        if command is None:
            self.say("  no --registry-repo: run this in the battinfo-registry checkout, against the target's "
                     "database and bucket, then re-run with --steps postflight:\n"
                     "      uv run python scripts/rerender_record_pages.py --apply --persist-display")
            self.state.step_incomplete("rerender", {"manual": True})
            return True
        self.say(f"  {' '.join(command)}  (cwd {self.args.registry_repo})")
        env = dict(os.environ)
        env.setdefault("PYTHONPATH", str(Path(self.args.registry_repo) / "src"))
        result = subprocess.run(command, cwd=self.args.registry_repo, env=env, text=True,
                                capture_output=True)
        tail = (result.stdout + result.stderr).strip().splitlines()[-12:]
        for line in tail:
            self.say(f"    {line}")
        ok = result.returncode == 0
        (self.state.step_done if ok else self.state.step_incomplete)(
            "rerender", {"returncode": result.returncode, "tail": tail[-4:]})
        return ok

    # -- step 7 --------------------------------------------------------------

    def postflight(self) -> bool:
        self.say("\n== 7 postflight")
        index = self.index(refresh=True)
        errors: list[str] = []
        fetched: dict[str, dict[str, Any]] = {}

        # every corpus IRI resolves and is published
        for record in [self.organization, *self.records]:
            response = self.target.get(f"/resources/{record.type.resource_type}/{record.canonical_id}")
            if response.status != 200:
                errors.append(f"{record.label}: GET {response.status}")
                continue
            fetched[record.iri] = response.body
            if response.body.get("status") != "published":
                errors.append(f"{record.label}: status {response.body.get('status')}")
            if response.body.get("source_version") != self.source_version:
                errors.append(f"{record.label}: source_version {response.body.get('source_version')!r}, "
                              f"expected {self.source_version!r}")
        self.say(f"  resolve: {len(fetched)}/{len(self.records) + 1} return 200")

        # tombstones
        tombstones = 0
        for row in self.supersede_rows:
            segment, uid = INTERNAL_IRI_RE.match(row.published_id).group("segment", "uid")
            response = self.target.get(f"/w3id/{segment}/{uid}", accept="application/ld+json",
                                       follow_redirects=False)
            body = response.body if isinstance(response.body, dict) else {}
            replaced_node = body.get("dcterms:isReplacedBy")
            nodes = replaced_node if isinstance(replaced_node, list) else [replaced_node or {}]
            replaced = [node.get("@id") for node in nodes if isinstance(node, dict)]
            expected = list(row.successors or (row.successor,))
            dead = [iri for iri in expected if index.status(iri) != "published"]
            if response.status != 200 or body.get("owl:deprecated") is not True:
                errors.append(f"{row.published_id}: not a tombstone (HTTP {response.status})")
            elif sorted(replaced) != sorted(expected):
                errors.append(f"{row.published_id}: tombstone points at {replaced}, expected {expected}")
            elif dead:
                errors.append(f"{row.published_id}: successor(s) not published: {dead}")
            else:
                tombstones += 1
        self.say(f"  tombstones: {tombstones}/{len(self.supersede_rows)} point at a live successor")

        # profile figures: every plot URL a dataset record names must serve the file
        plot_urls = sorted({
            dist["content_url"]
            for record in self.records if record.type.resource_type == "dataset"
            for dist in record.body.get("distributions") or []
            if str(dist.get("content_url", "")).endswith(".plot.json")
        })
        missing_plots = []
        for url in plot_urls:
            # r2.dev answers 403 to some default client user agents
            request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0 (flores-republish)"})
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    if response.status != 200:
                        missing_plots.append(f"{url} (HTTP {response.status})")
            except urllib.error.HTTPError as error:
                missing_plots.append(f"{url} (HTTP {error.code})")
            except OSError as error:
                missing_plots.append(f"{url} ({error})")
        errors.extend(f"profile figure not served: {item}" for item in missing_plots[:5])
        if len(missing_plots) > 5:
            errors.append(f"... and {len(missing_plots) - 5} more profile figures not served")
        self.say(f"  profiles: {len(plot_urls) - len(missing_plots)}/{len(plot_urls)} figure URLs serve the file")

        # collection membership
        members_expected ={r.iri for r in self.records if r.body.get("series_id") == COLLECTION_IRI}
        method, members_live = self.collection_members(fetched)
        if members_live != members_expected:
            errors.append(f"collection lists {len(members_live)} members via {method}, expected "
                          f"{len(members_expected)} (missing {len(members_expected - members_live)}, "
                          f"extra {len(members_live - members_expected)})")
        member_count = (fetched.get(COLLECTION_IRI) or {}).get("member_count")
        if member_count is not None and member_count != len(members_expected):
            errors.append(f"collection member_count is {member_count}, expected {len(members_expected)}")
        self.say(f"  collection: {len(members_live)} members via {method}; member_count "
                 f"{member_count if member_count is not None else '(not served by this registry)'}")

        # dead links
        dead = Counter()
        for record in [self.organization, *self.records]:
            payload = (fetched.get(record.iri) or {}).get("semantic_payload") or record.raw
            for path, iri in iter_internal_iris(payload):
                if iri == record.iri:
                    continue
                status = index.status(iri)
                if status != "published":
                    dead[(iri, status or "absent")] += 1
        for (iri, status), count in sorted(dead.items()):
            errors.append(f"reference to {iri} ({status}) from {count} site(s)")
        self.say(f"  references: {len(dead)} dead or tombstoned target(s)")

        # retained identifiers carry the new version
        retained = [e["published_id"] for e in self.supersede_doc["entries"] if e["status"] == "retained"]
        stale = [iri for iri in retained if (index.by_iri.get(iri) or {}).get("source_version") != self.source_version]
        if stale:
            errors.append(f"{len(stale)} retained identifiers do not carry {self.source_version} (first {stale[0]})")
        self.say(f"  retained: {len(retained) - len(stale)}/{len(retained)} carry the v5 version")

        rerender = self.state.data["steps"].get("rerender", {})
        if not rerender.get("done"):
            self.say("  NOTE step 6 (rerender) is not recorded as done in the state file; reverse-edge panels "
                     "are missing until it runs")
        for error in errors[:40]:
            self.say(f"  ERROR {error}")
        if len(errors) > 40:
            self.say(f"  ... and {len(errors) - 40} more")
        self.say(f"  postflight: {'FAILED' if errors else 'passed'} ({len(errors)} errors)")
        summary = {"resolved": len(fetched), "tombstones": tombstones, "members": len(members_live),
                   "members_method": method, "dead_references": len(dead), "errors": len(errors)}
        self.state.log("postflight", **summary, first_errors=errors[:10])
        (self.state.step_done if not errors else self.state.step_incomplete)("postflight", summary)
        return not errors

    def collection_members(self, fetched: dict[str, dict[str, Any]]) -> tuple[str, set[str]]:
        openapi = self.target.get("/openapi.json")
        params = []
        if openapi.status == 200 and isinstance(openapi.body, dict):
            params = [p.get("name") for p in
                      openapi.body.get("paths", {}).get("/resources", {}).get("get", {}).get("parameters", [])]
        if "series_id" in params:
            members: set[str] = set()
            offset = 0
            while True:
                query = urllib.parse.urlencode({"resource_type": "dataset", "series_id": COLLECTION_IRI,
                                                "limit": 1000, "offset": offset})
                response = self.target.get(f"/resources?{query}")
                if response.status != 200:
                    break
                members |= {row["canonical_iri"] for row in response.body}
                offset += 1000
                if offset >= int(response.headers.get("x-total-count", 0)):
                    break
            return "the series_id list filter", members
        members = set()
        for iri, resource in fetched.items():
            records = (resource.get("semantic_payload") or {}).get("battinfo_records") or {}
            dataset = (records.get("dataset") or {}).get("dataset") or {}
            if dataset.get("series_id") == COLLECTION_IRI:
                members.add(iri)
        return "member records' series_id (no series_id filter advertised)", members


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def parse_steps(text: str | None) -> list[str]:
    if not text:
        return list(STEPS)
    chosen: list[str] = []
    for part in text.split(","):
        part = part.strip()
        if re.fullmatch(r"\d+-\d+", part):
            low, high = (int(x) for x in part.split("-"))
            chosen.extend(STEPS[low:high + 1])
        elif part.isdigit():
            chosen.append(STEPS[int(part)])
        elif part in STEPS:
            chosen.append(part)
        else:
            raise SystemExit(f"unknown step {part!r}; steps are {', '.join(STEPS)} or 0-7")
    return [s for s in STEPS if s in chosen]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", required=True, help="Registry base URL.")
    parser.add_argument("--apply", action="store_true", help="Write. Without it nothing is written.")
    parser.add_argument("--production", action="store_true",
                        help=f"Allow a non-localhost target. --apply then also needs {PRODUCTION_CONFIRM_ENV}=<host>.")
    parser.add_argument("--steps", default=None,
                        help="Comma list of step names or numbers (e.g. 'postflight', '4-7'). Default: all. "
                             "Preflight always runs before a write step.")
    parser.add_argument("--state", type=Path, default=None,
                        help="State/log file (default: .republish-state/<host>.json beside this script, gitignored).")
    parser.add_argument("--source-version", default=None,
                        help="source_version stamped on every submission (default: flores-v5-<corpus hash>).")
    parser.add_argument("--overrides", type=Path, default=SPLIT_OVERRIDES, help="Split-successor overrides.")
    parser.add_argument("--organization-record", type=Path, default=TOPSOE_RECORD,
                        help="The Topsoe organization record (default: the repo's records/organization/topsoe).")
    parser.add_argument("--workspace-id", default=DEFAULT_WORKSPACE)
    parser.add_argument("--publisher-id", default=DEFAULT_PUBLISHER)
    parser.add_argument("--reviewer", default="flores-republish", help="reviewed_by on approvals.")
    parser.add_argument("--registry-repo", type=Path, default=None,
                        help="battinfo-registry checkout, for step 6 (rerender_record_pages.py).")
    parser.add_argument("--registry-env-file", type=Path, default=None,
                        help="Env file naming the target's database and bucket, passed to the rerender script.")
    parser.add_argument("--registry-python", default=None, help="Interpreter for the rerender script.")
    parser.add_argument("--profiles-mirror", type=Path, default=None,
                        help="Also copy the profiles under DIR/datasets/<short_id>/ (a local stand-in bucket).")
    parser.add_argument("--timeout", type=float, default=120.0, help="HTTP timeout in seconds.")
    args = parser.parse_args(argv)

    parsed = urllib.parse.urlparse(args.target)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("http", "https") or not host:
        parser.error(f"--target is not an http(s) URL: {args.target}")
    args.local = host in LOCAL_HOSTS
    if not args.local and not args.production:
        parser.error(f"{host} is not localhost. Pass --production to target it.")
    if args.local and args.production:
        parser.error("--production with a localhost target makes no sense.")
    if args.apply and args.production and os.environ.get(PRODUCTION_CONFIRM_ENV) != host:
        parser.error(f"--apply against {host} needs {PRODUCTION_CONFIRM_ENV}={host} in the environment.")

    steps = parse_steps(args.steps)
    state_path = args.state or DEFAULT_STATE_DIR / f"{host}-{parsed.port or parsed.scheme}.json"
    state = State(state_path, enabled=args.apply)
    target = Target(args.target, publisher_key=os.environ.get(PUBLISHER_KEY_ENV),
                    admin_token=os.environ.get(ADMIN_TOKEN_ENV), timeout=args.timeout,
                    allow_writes=args.apply)
    driver = Driver(args, target, state)
    state.data.setdefault("target", args.target)
    state.data["source_version"] = driver.source_version

    mode = "APPLY" if args.apply else "DRY RUN (nothing is written)"
    print(f"Flores v5 republish -> {args.target}  [{mode}]  steps: {', '.join(steps)}")
    if args.apply:
        print(f"state: {state_path}")

    writes = [s for s in steps if s in WRITE_STEPS]
    preflight_ok = driver.preflight() if ("preflight" in steps or writes) else True
    if not args.apply:
        if "preflight" in steps or writes:
            driver.print_plan()
        postflight_ok = driver.postflight() if "postflight" in steps and not writes else True
        print("\nDry run: nothing written." + (" Re-run with --apply to execute." if writes else ""))
        return 0 if preflight_ok and postflight_ok else 1
    if writes and not preflight_ok:
        print("\nPreflight failed: nothing written.")
        return 1

    runners = {
        "organization": driver.step_organization, "collection": driver.step_collection,
        "records": driver.step_records, "supersede": driver.step_supersede,
        "profiles": driver.step_profiles, "rerender": driver.step_rerender,
        "postflight": driver.postflight,
    }
    for step in steps:
        if step == "preflight":
            continue
        if not runners[step]():
            print(f"\nStopped at step {step}. Fix the cause and re-run; completed work is skipped.")
            print(f"requests: {dict(target.requests)}")
            return 1
    print(f"\nDone. requests: {dict(target.requests)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
