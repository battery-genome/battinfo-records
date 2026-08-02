# BattINFO 0.8 readiness report - authoring the Flores half-cell OCV semantic layer

Real-work findings from authoring 305 linked records (7 materials, 9 half-cell specs,
95 instances, 4 protocols, 95 tests, 95 datasets) for Zenodo 20086298 with BattINFO
0.7.0 (installed from git main). Ranked by impact. Each item has an exact repro.

## Blockers / high

### H1. `create_material_spec` mints a random id; material specs are not idempotent
`create_material_spec(...)` returns a fresh random IRI on every call, and
`save_material_spec` does not dedupe by content. Re-running an authoring script
silently accumulates duplicate material specs (this build produced **56** material-spec
files = 8 runs x 7 before I pinned ids). Because cell specs carry `material_spec_id`,
the changing material id also made the 9 cell specs re-serialise as `[updated]` on
every run. Every other record type derives a deterministic content-based IRI and is
idempotent - materials are the sole exception, and they break the "deterministic
re-run = no-op" contract.
Repro: `[create_material_spec(name="Graphite", formula="C")["material_spec"]["id"] for _ in range(3)]` -> three different IRIs.
Workaround: pass an explicit deterministic `id=`.

### H2. Material specs are second-class in the workspace (no save, no attribution)
The authoring workspace manages cell_specs/cells/test_specs/tests/datasets but not
material specs: `ws.save()` neither writes nor stamps them (must call
`save_material_spec` separately), so the funding/contributor/license stamping never
reaches them. The material-spec schema also forbids `contributor`/`license`/`funding`
(`additionalProperties:false`), so material specs *cannot* carry the same attribution
and funding provenance as every other record even if stamped manually.
Repro: add `license`/`contributor`/`funding` to a saved material-spec dict and run
`validate_record_report` -> `schema.additionalProperties` error.
Impact: a whole record type is excluded from attribution and funding traceability.

### H3. Deposit-level gold-standard requires sha256, Zenodo gives md5
`preview_rocrate`/`preview_jsonld` run a gold-standard check that requires a 64-char
**sha256** per distribution. Zenodo (and most repositories) publish only **md5**.
This build's deposit crate reported ~190 `Distribution sha256 must be a 64-character
hexadecimal digest` errors. Satisfying it means downloading every file to compute
sha256 - here ~10 GB. Per-record dataset validation happily accepts md5, so the record
layer and the deposit layer disagree. This blocks a clean RO-Crate for anyone building
a semantic layer over an existing repository deposit.
Repro: see `bundle/gold-standard-report.txt`.

## Medium

### M1. Model accepts values the save-time schema rejects (late failures)
Pydantic models are more permissive than the JSON schema enforced at `ws.save()`, so
some errors only appear after a full authoring pass:
- `testmethod.Step(mode="discharge")` / `"charge"` construct fine; save requires
  mode in `{cc,cv,cccv,cp,cr,rest,eis,scan,group}` (use `mode="cc"` + `direction`).
- `TestConformance(status="non_conformant")` constructs fine; save requires the
  hyphenated `non-conformant`.

### M2. Assigning a string to a list field explodes it into characters
`cell_spec.specification_comment = "R2032 ..."` serialised as
`["R","2","0","3","2"," ", ...]` and *passed* strict validation. `dataset.same_as =
"https://doi.org/..."` produced 40 `not a 'uri'` errors (one per character). A
`str | list[str]` field should coerce or reject, not iterate the string.

### M3. No typed home for per-instance as-built electrode figures
Cell-instance `measured` is a closed 67-key cell-performance vocabulary
(`additionalProperties:false`) with no slot for active-material mass, coating mass,
weight %, theoretical capacity, thickness, areal capacity or loading. The documented
fallback ("attach as test conditions") is also unreachable: `test.conditions` exists in
the JSON schema (open snake_case keys) but the `Test` pydantic model has no
`conditions` field. These per-cell values ended up in free-text `comment`.

### M4. `test_spec(conditions=...)` cannot express a non-numeric condition
`conditions` values must be numeric `Quantity`; "room temperature" (exactly what this
dataset states) cannot be represented and had to go into `description`.

### M5. JSON-LD export omits test protocols and material specs
`ws.export("json-ld")` and `record_to_jsonld` handle only
cell-spec/cell-instance/test/dataset. `record_to_jsonld(record, "test-protocol")` and
`"material-spec"` raise, so 11 of 305 records travel only as canonical JSON, not
JSON-LD. `dry_thickness` also has no curated EMMO mapping and is emitted under a
non-canonical fallback term (`semantic.property_unmapped`).

### M6. Blessed API cannot author a realistic dataset
`battinfo.workspace()` exposes only `add("cell"/"test"/"equipment")` and
`load(draft)`. Material specs, rich half-cell electrodes, remote-URL datasets with
checksums, and conformance all require the deprecated engine `ws._ws`
(`.cell_spec/.cell/.test_spec/.test/.dataset`). The documented blessed surface alone is
insufficient for this dataset.

## Low / paper-cuts

- **L1.** `save()` return dict vs panel disagree: unchanged re-run prints `[unchanged]`
  but the returned dict reports `status:"updated"` for the same records.
- **L2.** Half-cell chemistry and material-name electrode bases warn
  (`semantic.controlled_value_unmapped` x26 for `Li half-cell`, `silicon`, `Li`, ...);
  there is no half-cell-aware chemistry term, so faithful values always warn.
- **L3.** `duplicate_policy` accepts only `error`/`return_existing`;
  `save_material_spec` defaults to `create_only`/`error` and so errors on any re-run.
- **L4.** Deprecation warnings fire for many still-canonical names
  (`CellSpecification`, `cell_description`, `create_material_spec`, `Workspace`, ...)
  pointing at post-0.8 relocations - fine, but noisy during authoring.

## Worked well (earned)

- Content-derived deterministic IRIs give true idempotency for
  cell-spec/instance/test-spec/test/dataset.
- `ws.project("101069765")` OpenAIRE/CORDIS enrichment resolved IntelLiGent / HE / EC
  first try and stamped funding onto every engine record.
- `ws.contributor` / `ws.license` stamped 9 ORCIDs + CC-BY onto every engine record.
- Dataset distributions (remote content_url + md5 + byte size + parquet media),
  DOI citations, `variable_measured`, and cell/test `about` links validated under strict.
- Dataset validators (`published_at >= created_at`; md5 must be 32 hex) correctly
  forced authentic values.
- The conformance model (status + note + typed deviation category) fit the 11 known
  issues cleanly.
- `battinfo validate` and `validate_record_report` give clear, actionable messages.

## Should block or annotate 0.8

- **Block:** H1 (material-spec non-determinism) - silently corrupts any repeatable
  pipeline.
- **Annotate/fix before wide use:** H2 (material attribution gap), H3 (md5/sha256
  interop), M2 (string-to-char-list), M5 (JSON-LD coverage), M6 (blessed API gaps).
