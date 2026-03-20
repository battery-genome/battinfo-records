# battinfo-records

`battinfo-records` is the curated shared records repository for BattINFO.

This repo is the maintained editorial source for canonical BattINFO records that belong in the shared library. It is designed for reviewable content changes and clear promotion from editorial draft to reviewed corpus to registry publication.

## What This Repo Is For

- Curated shared BattINFO records that are intended to be maintained by an editorial process.
- Human-reviewable diffs for content updates at scale.

## What Does Not Belong Here

- BattINFO application code, schemas, validators, or backend logic. Those belong in the BattINFO code repo.
- Registry implementation logic or discovery-layer state. The registry is the published catalog, not this editorial source repo.
- Ad hoc user-local JSON drafts, scratch files, or private working notes unless they have been intentionally promoted into shared editorial review.
- Large evidence binaries by default. Store references, citations, and stable locators here instead.

## System Boundaries

- BattINFO repo: code, schemas, tooling, examples, validation, import/export logic.
- `battinfo-records`: curated shared editorial corpus and its governance metadata.
- Registry: authoritative published discovery layer derived from approved records.
- User-local working files: optional personal drafts that stay outside this repo unless promoted.

## Repository Layout

```text
.
|-- CONTRIBUTING.md
|-- docs/
|   |-- naming-and-layout.md
|   |-- provenance-policy.md
|   |-- record-lifecycle.md
|   |-- repo-scope.md
|   `-- versioning-and-revisions.md
|-- metadata/
|   |-- review-status/
|   |   |-- README.md
|   |   `-- cell-types/
|   |       `-- _template-cell-type.review.yaml
|   `-- sources/
|       |-- README.md
|       `-- cell-types/
|           `-- _template-cell-type.sources.yaml
`-- records/
    |-- _staging/
    |   |-- README.md
    |   `-- cell-types/
    |       `-- README.md
    `-- cell-types/
        |-- README.md
        `-- _template-cell-type/
            `-- record.json
```

## Record Convention

For a staging cell-type submission, use a single JSON file:

- `records/_staging/cell-types/<submission-name>.json`

For a curated cell-type record, use:

- `records/cell-types/<record-id>/record.json`

The `record.json` file is the canonical curated artifact. Metadata sidecars under `metadata/` are optional and should not be required for routine submission or promotion.
For record ids, prefer `manufacturer-model-year` when the year is known. If year is unavailable, use a revision or evidence-backed date before falling back to editorial sequence suffixes.
When the intended curated id is already known, use the same value for the staging filename.

## Recommended Workflow

1. Start in `records/_staging/` when a candidate record is being promoted from a local draft into shared editorial review.
2. Add a single staging JSON draft under `records/_staging/cell-types/`.
3. Use BattINFO tooling to validate the staging draft and promote it into the canonical curated `record.json`.
4. Move the promoted record into `records/cell-types/<record-id>/` when editorial review says it belongs in the curated corpus.
5. Publish to the registry through BattINFO/registry processes. Do not treat a Git merge alone as registry publication.

For convenience inside this repo, `scripts/promote-staging-cell-type.ps1` wraps the BattINFO promotion command and can derive an explicit curated id from `-Year`, `-Revision`, or `-EvidenceDate` when the staging draft is ambiguous.
For registry publication, `scripts/publish-curated-cell-type.ps1` wraps the BattINFO curated publication command and accepts either a curated record id or a path to `record.json`.

Example:

```powershell
.\scripts\promote-staging-cell-type.ps1 -Input google-g20m7-2025.json
.\scripts\publish-curated-cell-type.ps1 `
  -Input google-g20m7-2025 `
  -ProjectId battinfo-records-cell-types `
  -PublisherId demo-editorial `
  -SourceVersion demo-2026-03-20 `
  -RegistryUrl http://127.0.0.1:8000 `
  -ApiKey <publisher-api-key>
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [docs/repo-scope.md](docs/repo-scope.md), and [docs/record-lifecycle.md](docs/record-lifecycle.md) for the operating rules.
