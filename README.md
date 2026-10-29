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
|   |   `-- cell-spec/
|   |       `-- _template-cell-spec.review.yaml
|   `-- sources/
|       |-- README.md
|       `-- cell-spec/
|           `-- _template-cell-spec.sources.yaml
`-- records/
    |-- _staging/
    |   |-- README.md
    |   `-- cell-spec/
    |       `-- README.md
    `-- cell-spec/
        |-- README.md
        `-- _template-cell-spec/
            `-- record.json
```

## Record Convention

For a staging cell-spec submission, use a single JSON file:

- `records/_staging/cell-spec/<submission-name>.json`

For a curated cell-spec record, use:

- `records/cell-spec/<record-id>/record.json`

The `record.json` file is the canonical curated artifact. Metadata sidecars under `metadata/` are optional and should not be required for routine submission or promotion.
For record ids, prefer `manufacturer--model--year` when the year is known. Keep single `-` inside each slug segment and use `--` only between major segments. If year is unavailable, use a revision or evidence-backed date before falling back to editorial sequence suffixes.
When the intended curated id is already known, use the same value for the staging filename.

## Recommended Workflow

1. Start in `records/_staging/` when a candidate record is being promoted from a local draft into shared editorial review.
2. Add a single staging JSON draft under `records/_staging/cell-spec/`.
3. Use BattINFO tooling to validate the staging draft and promote it into the canonical curated `record.json`.
4. Move the promoted record into `records/cell-spec/<record-id>/` when editorial review says it belongs in the curated corpus.
5. Publish to the registry through BattINFO/registry processes. Do not treat a Git merge alone as registry publication.

For convenience inside this repo, `scripts/promote-staging-cell-spec.ps1` wraps the BattINFO promotion command and can derive an explicit curated id from `-Year`, `-Revision`, or `-EvidenceDate` when the staging draft is ambiguous.
If the staging draft has been accepted and you want the state transition to be explicit in one step, pass `-DeleteStagingOnSuccess` to remove the staging JSON after a successful non-dry-run promotion.
For registry publication, `scripts/publish-curated-cell-spec.ps1` wraps the BattINFO curated publication command and accepts either a curated record id or a path to `record.json`.

Example:

```powershell
.\scripts\promote-staging-cell-spec.ps1 -Input google--g20m7--2025.json
.\scripts\publish-curated-cell-spec.ps1 `
  -Input google--g20m7--2025 `
  -ProjectId battinfo-records-cell-spec `
  -PublisherId demo-editorial `
  -SourceVersion demo-2026-03-20 `
  -RegistryUrl http://127.0.0.1:8000 `
  -ApiKey <publisher-api-key>
```

## Precomputed simulations

Every parameter-set record whose BPX file passed its PyBaMM smoke run is simulated with one standard protocol (`scripts/simulation_protocol.py`): constant-current discharges at 0.05C, 0.1C, 0.2C, 0.5C, 1C and 2C of the file's nominal capacity, with the model, initial state, ambient temperature and cut-off voltage the file itself states. When the file carries measured data in its own `Validation` section, each measured discharge is also replayed with its own current and compared. Through-cell and particle profiles are stored for the standard runs.

- `scripts/simulate-parameter-sets.py` makes the runs. The `Simulations` workflow runs it on changes to `records/parameter-set/` or the scripts, weekly, and on demand.
- `scripts/benchmark-simulators.py` applies the same protocol under each PyBaMM release line of the last 12 months, on one machine, and records whether each release reads each file, how long each case takes, and how the replays compare with the measured data. The `Simulator benchmark` workflow runs it weekly, on demand, and when the protocol changes.

- `scripts/export-pybamm-bpx.py` exports PyBaMM's speed-benchmark parameter sets to BPX and checks each file against PyBaMM's native set; `scripts/ingest-bpx-file.py` turns those files and the BPX standard's examples into parameter-set records.

Both write to the `battery-genome-simulations` bucket under `simulations/`. Nothing is written to this repo. The platform reads `simulations/latest.json` for its simulation panels and its `/simulators` page.

To run either locally without uploading:

```bash
uv run --no-project --with "pybamm[bpx]==26.10.1.1" python scripts/simulate-parameter-sets.py --out ../sim-out
uv run --no-project python scripts/benchmark-simulators.py --out ../bench-out --versions 26.9.0.0,26.10.1.1
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [docs/repo-scope.md](docs/repo-scope.md), and [docs/record-lifecycle.md](docs/record-lifecycle.md) for the operating rules.
For the concrete shared review -> promote -> publish loop, see [docs/editorial-cell-spec-workflow.md](docs/editorial-cell-spec-workflow.md).


