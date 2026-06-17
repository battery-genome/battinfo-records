# Commercial Baseline Status 2026-03-23

Scope: baseline commercial cell types for BattINFO registry publication and Battery Genome page availability.

Note: the live publication artifacts captured later in this file still show the pre-migration editorial ids. The maintained repo ids now use `manufacturer--model[--disambiguator]`.

Validated with BattINFO editorial promotion dry-run:

- `a123-anr26650m1-b-2012`
- `energizer-cr2032-2024`
- `google-g20m7-2025`
- `samsung-eb-ba156aby-2025`
- `samsung-eb-bs931abe-2025`
- `sunwoda-bm68-2024`
- `a123--anr26650m1-b--2012`
- `energizer--cr2032--2024`
- `google--g20m7--2025`
- `samsung--eb-ba156aby--2025`
- `samsung--eb-bs931abe--2025`
- `sunwoda--bm68--2024`

Staging fixes applied:

- Normalized `negative_electrode_basis` from `graphite` to `Graphite` in `records/_staging/cell-type/a123--anr26650m1-b--2012.json`.

Promoted into curated records:

- `records/cell-type/a123--anr26650m1-b--2012/record.json`
- `records/cell-type/energizer--cr2032--2024/record.json`
- `records/cell-type/google--g20m7--2025/record.json`
- `records/cell-type/samsung--eb-ba156aby--2025/record.json`
- `records/cell-type/samsung--eb-bs931abe--2025/record.json`
- `records/cell-type/sunwoda--bm68--2024/record.json`

Publication handoff:

- Batch helper prepared at `demo/publish-commercial-baseline-cell-type.ps1`.
- Existing wrapper remains `scripts/publish-curated-cell-type.ps1`.

Cross-repo risk observed:

- BattINFO generated different `product.id` / `short_id` values for repeated promotion of the same source record during dry-run vs promotion.
- Treat identifier stability as a BattINFO tooling issue to confirm before relying on repeated republishes or resolver path continuity.

Identifier stability investigation:

- Cause confirmed in BattINFO: staging promotion called `_record_from_cell_type()` without a persisted `id` or `uid`, so each run minted a fresh random BattINFO cell-type UID.
- Direct repro on `google-g20m7-2025` before the fix:
  - dry-run 1 minted `https://w3id.org/battinfo/cell-type/vjxf-367v-3jpn-k1zb`
  - dry-run 2 minted `https://w3id.org/battinfo/cell-type/jkcy-0520-xsmp-my1x`
- Minimal BattINFO fix applied:
  - when `records/cell-type/<record-id>/record.json` already exists, re-promotion now preserves the existing curated `product.id` and derived `short_id`
  - verified for `google-g20m7-2025`: repeated dry-runs now preserve `https://w3id.org/battinfo/cell-type/nm6t-ceph-frax-1mk1`
- Regression coverage added in BattINFO targeted tests for repeated promotion stability.

Assessment:

- Current behavior was explainable from the implementation, but it is not acceptable for editorial re-promotion workflows because dry-run and repeat promotion could silently change canonical BattINFO identifiers for the same curated record id.
- After the BattINFO preservation fix, repeated promotion into an existing curated record is stable enough for the current cross-repo publication path.

Local registry canary:

- Published current curated `records/cell-type/google-g20m7-2025/record.json` through local `battinfo-registry` test-client flow.
- Canary output directory:
  - `demo/registry-local-2026-03-23-canary/`
- Canary result:
  - registry canonical id: `de--google-g20m7-2025--1e17b071`
  - embedded BattINFO product id preserved: `https://w3id.org/battinfo/cell-type/nm6t-ceph-frax-1mk1`
- Supporting artifacts written:
  - `demo/registry-local-2026-03-23-canary/demo-summary.json`
  - `demo/registry-local-2026-03-23-canary/page-model.json`
  - `demo/registry-local-2026-03-23-canary/resource.json`

Local baseline publication:

- Published all six curated commercial baseline cell types through the same local registry flow.
- Baseline output directory:
  - `demo/registry-local-2026-03-23-baseline/`
- Summary:
  - `published_count = 6`
  - canonical ids confirmed for:
    - `de--a123-anr26650m1-b-2012--80a20565`
    - `de--energizer-cr2032-2024--903980ad`
    - `de--google-g20m7-2025--1e17b071`
    - `de--samsung-eb-ba156aby-2025--92ccc417`
    - `de--samsung-eb-bs931abe-2025--2d045937`
    - `de--sunwoda-bm68-2024--c90e4438`
- Supporting artifacts written:
  - `demo/registry-local-2026-03-23-baseline/baseline-summary.json`
  - `demo/registry-local-2026-03-23-baseline/project-resources.json`
  - `demo/registry-local-2026-03-23-baseline/page-models/*.page-model.json`

Battery Genome status:

- Battery Genome’s registry route consumes `GET /resources/{resource_type}/{id}/page-model`; the local page-model contract produced by `battinfo-registry` matches that shape for `cell_type`.
- Remaining blocker is operational, not schema-level:
  - `battery-genome/platform` still defaults to `BATTERY_GENOME_DATA_MODE=mock`
  - registry-backed pages require `BATTERY_GENOME_DATA_MODE=bff`
  - `NEXT_PUBLIC_BATTINFO_BASE_URL` must point to a running `battinfo-registry` API, not only local test-client artifacts

Live local registry publication:

- Published the six curated commercial baseline cell types against a real local `battinfo-registry` HTTP server at `http://127.0.0.1:8010`.
- Publication used existing battinfo-records workflow wrappers:
  - `demo/publish-commercial-baseline-cell-type.ps1`
  - `scripts/publish-curated-cell-type.ps1`
- Live publication evidence written under:
  - `demo/registry-live-2026-03-23/`
- Live canonical ids matched the previously verified local baseline exactly:
  - see `demo/registry-live-2026-03-23/canonical-id-comparison.json`
- Live publication request summaries written for all six records under:
  - `demo/registry-live-2026-03-23/submission-summaries/`

Battery Genome live page verification:

- Ran `battery-genome/platform` in `bff` mode against the live local registry API and verified:
  - `http://127.0.0.1:3001/registry/cell_type/de--google-g20m7-2025--1e17b071`
- Verification result:
  - HTTP 200
  - rendered page contains `Google G20M7`
  - rendered page contains canonical id `de--google-g20m7-2025--1e17b071`
  - rendered page contains `BattINFO Registry`
- Evidence written under:
  - `demo/registry-live-2026-03-23/battery-genome/google-g20m7-2025.page-check.json`
  - `demo/registry-live-2026-03-23/battery-genome/google-g20m7-2025.registry-page.html`

Residual caveat:

- In this Codex shell environment, `next dev` hit `spawn EPERM` inside the sandbox.
- The Battery Genome live page verification succeeded only after rerunning the Next.js process outside the sandbox.
- This is an execution-environment limitation for local verification here, not a BattINFO or registry data-model blocker.

Semantic IRI publication update:

- Updated `battinfo-registry` publication flow so curated BattINFO-native resources keep the BattINFO semantic IRI as the canonical public identity instead of minting a separate registry composite IRI.
- For `google-g20m7-2025`, the canonical publication identity is now:
  - `canonical_id = nm6t-ceph-frax-1mk1`
  - `canonical_iri = https://w3id.org/battinfo/cell-type/nm6t-ceph-frax-1mk1`
- Added registry resource-type alias handling so Battery Genome can resolve page-models on:
  - `/resources/cell-type/<canonical_id>/page-model`
- Verified via targeted registry tests:
  - `battinfo-registry/tests/test_registry_flow.py`
  - `battinfo-registry/tests/test_battinfo_roundtrip.py`

Live schema and semantic-IRI republish:

- The live Neon-backed registry database was not fully migrated to the current application schema even though later tables existed.
- Missing columns/constraints were repaired and Alembic was stamped to `0005_project_snapshot_roundtrip` so current publisher/submission/resource models could run against the live database.
- Re-published all six curated commercial baseline cell types through the live local registry HTTP server after the semantic-IRI change.
- Updated live submission evidence written under:
  - `demo/registry-live-2026-03-23-semantic-iri/`
  - `demo/registry-live-2026-03-23-semantic-iri/submission-summaries/`

Battery Genome semantic-IRI verification:

- Rebuilt `battery-genome/platform` after switching local env to:
  - `BATTERY_GENOME_DATA_MODE=bff`
  - `NEXT_PUBLIC_BATTINFO_BASE_URL=http://127.0.0.1:8011`
- Verified Battery Genome route using the semantic BattINFO IRI tail:
  - `http://127.0.0.1:3002/registry/cell-type/nm6t-ceph-frax-1mk1`
- Verification result:
  - HTTP 200
  - rendered page contains `Google G20M7`
  - rendered page contains canonical id `nm6t-ceph-frax-1mk1`
  - rendered page contains `BattINFO Registry`
- Evidence written under:
  - `demo/registry-live-2026-03-23-semantic-iri/battery-genome/google-g20m7-2025.semantic-iri.page-check.json`
  - `demo/registry-live-2026-03-23-semantic-iri/battery-genome/google-g20m7-2025.semantic-iri.registry-page.html`


