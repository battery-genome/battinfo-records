# Editorial Cell-Type Workflow

This document defines the concrete workflow for reviewing, curating, publishing, and later editing shared BattINFO cell-type records.

It is the working contract between:

- `battinfo-records`, the shared editorial source
- `BattINFO`, the validation, promotion, and publication tooling
- `battinfo-registry`, the publication backend and object storage writer

## Source Of Truth

Use this order:

1. Local private drafts outside this repo are personal working material.
2. `records/_staging/cell-type/*.json` is the shared editorial draft source.
3. `records/cell-type/<record-id>/record.json` is the canonical shared curated source.
4. Registry pages, database rows, and object storage artifacts are published derived state.

Do not treat the registry object store as an editable source of truth.
Do not hand-edit generated BattINFO or registry artifacts to correct editorial content.
Fix the record in this repo, then re-promote or republish.

## Lifecycle

The intended lifecycle is:

1. Local draft outside this repo
2. Shared staging draft in `records/_staging/cell-type/`
3. Reviewed curated record in `records/cell-type/<record-id>/record.json`
4. Published registry resource
5. Reuse by downstream datasets, tests, instances, and Battery Genome pages

Repository location is the default state signal.

## What Gets Edited Where

Edit staging drafts when:

- identity is still ambiguous
- provenance is incomplete
- fields still need normalization
- reviewers are still deciding whether the record belongs in the curated corpus

Edit curated `record.json` when:

- the record identity is already accepted
- you are correcting or enriching metadata for the same physical cell type
- you are updating provenance, notes, or quantitative properties without changing the underlying product identity

Create a new curated record id when:

- the marketed model name maps to a different physical design
- the year, revision, or evidence-backed variant is materially different
- reusing the old id would blur two distinct cell types

## Review Workflow

For each staging record:

1. Confirm scope
   The record belongs in the shared reusable cell-type corpus, not only in a personal draft or one-off demo.
2. Confirm identity
   Check manufacturer, model, and whether a year, revision, or evidence-date disambiguator is needed.
3. Confirm provenance
   Make sure the record itself explains the source file, source type, citation or URL, and any editorial synthesis.
4. Confirm schema shape
   Validate that the JSON is in a BattINFO-supported authoring or canonical cell-type shape.
5. Confirm domain plausibility
   Check cell format, chemistry, electrode basis, size code, and obvious quantitative fields for contradictions.
6. Confirm reviewability
   Another curator should be able to understand why the claims are present without private context.
7. Decide the outcome
   Promote, hold for later, or reject from shared curation.

## Review Checklist

Use this checklist before promotion.

### Identity

- Manufacturer is present and normalized enough for stable review.
- Model is present and precise enough for stable review.
- Record id basis is clear:
  `year`, `revision`, `evidence_date`, or explicit manual disambiguator.
- Bare `manufacturer--model` is avoided unless the product identity is truly stable.
- Known variant ambiguity is captured in the id or in notes.

### Provenance

- `provenance.source_type` is present and accurate.
- `provenance.source_file` identifies the source artifact or import source.
- `provenance.source_url` or `provenance.citation` is present when available.
- `provenance.retrieved_at` or another evidence date is present when relevant.
- Important editorial synthesis is documented in `notes`.
- Large evidence binaries are not committed by default.

### Content Quality

- `product.name`, `product.model`, and `product.manufacturer.name` are coherent.
- `cell_format` matches the evidence.
- `chemistry` is plausible and not a silent guess unless documented as such.
- `size_code` or `iec_code` is included when supported by evidence.
- Quantitative specs use normalized units and plausible values.
- Duplicate or contradictory fields have been resolved.

### Promotion Readiness

- BattINFO validation passes.
- The proposed curated record id is acceptable.
- The record is ready to live as the shared maintained version of this cell type.
- Any remaining uncertainty is minor enough to document in notes rather than block promotion.

## Promotion Workflow

Run BattINFO validation first, then promote.

Typical path:

```powershell
.\scripts\promote-staging-cell-type.ps1 -Input records/_staging/cell-type/<draft>.json
```

If promotion is the acceptance step and you do not want to keep the shared staging copy, use:

```powershell
.\scripts\promote-staging-cell-type.ps1 -Input <draft>.json -DeleteStagingOnSuccess
```

If the draft is ambiguous, provide an explicit id basis:

```powershell
.\scripts\promote-staging-cell-type.ps1 -Input <draft>.json -Year 2025
.\scripts\promote-staging-cell-type.ps1 -Input <draft>.json -Revision sd12
.\scripts\promote-staging-cell-type.ps1 -Input <draft>.json -EvidenceDate 2026-03-20
```

The promoted target is always:

```text
records/cell-type/<record-id>/record.json
```

## Publication Workflow

Only publish curated records.

Typical path:

```powershell
.\scripts\publish-curated-cell-type.ps1 `
  -Input <record-id> `
  -ProjectId <project-id> `
  -PublisherId <publisher-id> `
  -SourceVersion <source-version> `
  -RegistryUrl <registry-url> `
  -ApiKey <api-key>
```

Publication writes registry state and object storage artifacts downstream.
That publication state does not replace this repo as the editorial source.

## Editing After Publication

When a published cell type needs correction or enrichment:

1. Edit `records/cell-type/<record-id>/record.json`
2. Re-run validation
3. Re-publish the curated record
4. Treat the registry as refreshed derived state

Do not patch the registry object store directly to fix editorial mistakes.

## Definition Of Done

A cell type is in good reusable shape when all of the following are true:

- It has a stable curated record id.
- Its record is understandable from `record.json` without private context.
- Provenance and editorial synthesis are explicit enough for review.
- BattINFO validation succeeds.
- Re-promotion preserves the accepted BattINFO identifier for the curated record.
- Registry publication succeeds.
- Downstream consumers can resolve and reuse the canonical published identity.

## Boundaries

`battinfo-records` owns:

- reviewable shared cell-type content
- editorial ids and provenance
- promotion and publication decisions

`BattINFO` owns:

- schema validation
- staging validation
- promotion behavior
- submission package generation

`battinfo-registry` owns:

- published discovery state
- database records
- public and private object storage artifacts

If a change is about content, edit this repo.
If a change is about how content is validated or published, edit BattINFO.

