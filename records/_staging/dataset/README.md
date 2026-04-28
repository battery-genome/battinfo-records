# Staging Datasets

Place shared dataset records here while they are under editorial review and not yet accepted into the curated corpus.

This mirrors the existing staging model used for `cell-type/`, but dataset-specific promotion tooling and curated layout are not yet documented in this repo.

Use one JSON file per candidate dataset record in canonical BattINFO snake_case form.
Use the source-local id as the filename when the final curated record id or directory layout is still under discussion.

Current validation expectation for BDC-style dataset drafts:
- validate under the BattINFO `ingest` policy while BattINFO `about` links to canonical `cell` or `test` records are still unresolved
- move to stricter validation only after those cross-record links are available

