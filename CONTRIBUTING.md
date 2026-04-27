# Contributing

This repo is for curated shared BattINFO records. Contribute here when a record is ready for shared editorial handling, not for private experimentation.

## Before You Add Anything

- Confirm the content belongs in the shared curated corpus.
- Keep schema and validation work in the BattINFO code repo.
- Keep local-only drafts outside this repo until they are intentionally promoted into editorial review.

## Add a New Curated Cell Type

1. Choose a stable record id using the naming rules in [docs/naming-and-layout.md](docs/naming-and-layout.md). Prefer `manufacturer--model--year` when the year is known.
2. If the record is still under editorial review, start under `records/_staging/`.
3. Put a single JSON draft in `records/_staging/cell-type/<submission-name>.json`.
   When the intended curated id is already known, use it as the staging filename too.
4. Use BattINFO repo tooling to validate the staging draft and promote it to `records/cell-type/<record-id>/record.json`.
   BattINFO can auto-suggest an id from year, revision, or evidence date, but ambiguous drafts should be promoted with an explicit `--record-id`.
   The repo wrapper `scripts/promote-staging-cell-type.ps1` can derive that explicit id from `-Year`, `-Revision`, or `-EvidenceDate`.
5. Publish curated records to the registry through BattINFO. The repo wrapper `scripts/publish-curated-cell-type.ps1` accepts a curated record id or a path to `record.json` and forwards the registry settings.
5. Add optional metadata under `metadata/` only when it materially helps editorial review or provenance tracking.

## Editorial review status

Every curated `record.json` carries an `editorial` block:

```json
"editorial": {
  "review_status": "auto-promoted",
  "promoted_at": "2026-04-27",
  "note": "Auto-promoted from staging. Passed strict BattINFO validation. Not individually reviewed against primary source."
}
```

`review_status` values:

| Value | Meaning |
|---|---|
| `reviewed` | Specs and provenance verified against a primary source (datasheet, label, or paper). |
| `auto-promoted` | Passed strict BattINFO validation. Not individually checked. May need correction. |
| `needs-review` | Flagged — known issue or suspected error. Do not treat as authoritative. |

The `editorial` block is ignored by the publish pipeline — updating it does **not** require re-publication unless the underlying specs also change.

To promote a record from `auto-promoted` to `reviewed`:
1. Read the record against its primary source (check specs, units, provenance).
2. Correct any errors in `record.json`.
3. Set `review_status` to `"reviewed"` and update the `note`.
4. Re-publish to create a new registry version: `scripts/publish-curated-cell-type.ps1 -Input <record-id> ...`
5. Commit with a message describing what was verified or corrected.

## Update an Existing Curated Record

1. Edit `record.json` in place when the stable record id remains the same.
2. Update metadata under `metadata/` only if you are intentionally tracking extra provenance or editorial state there.
3. Prefer small, reviewable commits and pull requests that map to one editorial change at a time.

## Evidence and Provenance

- Keep provenance in the JSON record itself by default.
- Add `metadata/sources/` only when a record needs extra editorial evidence notes that do not fit cleanly in the BattINFO record.
- Prefer citations, DOIs, URLs, accession ids, manufacturer document identifiers, and notes pointing to the exact supporting section.
- Do not commit large binaries by default. Link to durable external sources or internal archival locations when available.
- Record derived editorial judgment explicitly when the final value is synthesized from multiple sources.

## Lifecycle

Use the following progression unless there is a documented exception:

1. Local draft outside this repo.
2. Shared editorial single-file staging in `records/_staging/`.
3. Reviewed curated record in `records/cell-type/`.
4. Published in the registry through external publication workflow.

The repository location should reflect the lifecycle. A record in the curated area should not still look like an unowned draft.
For the concrete checklist used during review and later edits, see [docs/editorial-cell-type-workflow.md](docs/editorial-cell-type-workflow.md).

## Minimal File Set Per Curated Cell Type

- `records/cell-type/<record-id>/record.json`

That is the baseline. Add more only when there is a clear editorial need.

## What Not To Commit

- Personal scratch JSON not intended for the shared corpus.
- Registry-generated views or backend state.
- Vendored BattINFO schemas or duplicated application code.
- Unreviewed evidence dumps and large binary attachments unless explicitly approved.

## Review Expectations

- Make diffs easy to inspect.
- Keep metadata concise and current when you choose to add it.
- Preserve stable ids where possible.
- Document why a record changed, not just that it changed.

