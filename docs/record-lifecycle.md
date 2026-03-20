# Record Lifecycle

This repo separates editorial curation from registry publication.

## Lifecycle States

1. Local draft
   Personal working material outside this repo.
2. Staging
   Candidate shared record under editorial review in `records/_staging/`.
3. Reviewed curated record
   Accepted shared record in `records/cell-types/`.
4. Published
   Registry publication has occurred through an external process.

## State Tracking

The default state signal is repository location:

- `records/_staging/` means shared editorial review is still in progress.
- `records/cell-types/` means the record is accepted into the curated corpus.
- Registry publication is tracked in the registry and release process, not by default in repo sidecars.

If an editorial process needs explicit state files later, add them sparingly under `metadata/`. They are optional, not required.

## Promotion Rules

- Do not commit private scratch work directly into the curated area.
- Start shared review material in staging when it is not yet accepted into the curated corpus.
- Validate and promote staging drafts through BattINFO before moving them into `records/cell-types/`.
- Mark registry publication separately after the publication workflow completes.

## Operational Guidance

- Staging is for shared editorial handling, not for dumping arbitrary user submissions.
- A record may be reviewed in this repo before it is published in the registry.
- Registry publication should reference a reviewed repo state, not an unreviewed draft.
