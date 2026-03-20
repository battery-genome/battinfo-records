# Repo Scope

This repo exists to hold the curated shared editorial corpus for BattINFO.

## In Scope

- Canonical BattINFO JSON records that belong in the shared library.
- Lightweight source, provenance, and review state metadata.
- Contributor guidance and editorial policy.

## Out Of Scope

- BattINFO code, schemas, validators, ingestion pipelines, UI, and registry backend logic.
- Auto-generated registry indexes or published discovery snapshots.
- User-local drafts that have not been intentionally promoted into shared review.
- Large evidence payloads as a default storage strategy.

## Boundary Rules

- If it defines how records are validated or served, it belongs in the BattINFO code repo.
- If it is the maintained shared content that curators review, it belongs here.
- If it is the authoritative published catalog users discover through, it belongs in the registry.
- If it is private work-in-progress for one person, it should stay local until promoted.

## Practical Test

Commit to this repo only if all of the following are true:

- The record is intended to be shared.
- The change is meaningful to editorial history.
- Another curator should be able to review the diff and understand the provenance.

If any of those are false, the content probably does not belong here yet.
