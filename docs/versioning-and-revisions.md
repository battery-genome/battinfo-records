# Versioning And Revisions

This repo uses Git history as the editorial revision log.

## Expectations

- Keep stable record ids stable.
- Update a record in place when the identity has not changed.
- Explain substantive changes in the review metadata `change_summary`.
- Add or update provenance metadata when evidence changes.

## When To Create A New Record

Create a new record id when the underlying curated entity has changed identity, not merely when details have been corrected or expanded.

For cell types, a changed physical design behind the same marketed model name should usually get a new disambiguated id such as:

- `google-g20m7-2025`
- `google-g20m7-sd12`
- `google-g20m7-20260320`

## Revision Style

- Prefer small, reviewable changes.
- Avoid mixing unrelated records in one change set unless they share one editorial decision.
- Preserve old source references when they remain historically relevant, and note what has been superseded.

## Registry Publication

Registry publication/versioning can have its own release semantics. Do not duplicate that release machinery here unless there is a documented need.
