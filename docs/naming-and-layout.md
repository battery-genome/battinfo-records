# Naming And Layout

Keep file and directory names predictable so the repo scales cleanly.

## Record Ids

- Use lowercase kebab-case ids.
- Keep ids stable once published into the curated corpus.
- Make the directory name match the record id exactly.
- Prefer a real-world disambiguator in the id when the manufacturer model name may map to multiple physical designs.

Use this precedence for curated cell-type ids:

1. `manufacturer-model-year`
2. `manufacturer-model-revision`
3. `manufacturer-model-evidence-date`
4. `manufacturer-model-vN` only as a last resort

Examples:

- `google-g20m7-2025`
- `google-g20m7-sd12`
- `google-g20m7-20260320`

Avoid using a bare `manufacturer-model` id unless you are confident it refers to one stable physical design.

## Curated Cell-Type Layout

For each staging submission:

```text
records/_staging/cell-types/<submission-name>.json
```

Use the intended curated record id as `<submission-name>` when it is already known.
If the draft is still ambiguous, a provisional descriptive filename is acceptable until promotion assigns an explicit curated id.

For each curated cell type:

```text
records/cell-types/<record-id>/record.json
```

## Directory Rules

- One directory per curated record under `records/cell-types/`.
- The main content artifact is always `record.json`.
- Single-file staging drafts live directly under `records/_staging/cell-types/`.
- Metadata files under `metadata/` are optional, not required.
- Names beginning with `_` are reserved for repo-internal examples or process folders, not real curated records.

## Reviewability

- Prefer concise filenames over deep nesting.
- Do not add extra sidecar files unless they materially help review or curation.
- Keep the layout consistent across all record types as the repo grows.
