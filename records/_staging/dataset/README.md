# Staging Datasets

Place shared dataset records here while they are under editorial review and not yet accepted into the curated corpus.

This mirrors the existing staging model used for `cell-type/`.

Use one JSON file per candidate dataset record in canonical BattINFO snake_case form.
Use the source-local id as the filename when the final curated record id or directory layout is still under discussion.

Current validation expectation for BDC-style dataset drafts:
- validate under the BattINFO `ingest` policy while BattINFO `about` links to canonical `cell` or `test` records are still unresolved
- move to stricter validation only after those cross-record links are available

## Promotion

Promote a validated draft into the curated corpus at `records/dataset/<record-id>/record.json`.
The curated id is taken from the record's own `identifier` (e.g. `bdc:bdc_000001` → `bdc_000001`);
pass `-RecordId` to override.

```powershell
# Preview (validate + resolve id, no write)
scripts/promote-staging-dataset.ps1 -Input records/_staging/dataset/bdc_000001.json -DryRun

# Promote
scripts/promote-staging-dataset.ps1 -Input records/_staging/dataset/bdc_000001.json

# Batch (whole directory), or call the BattINFO CLI directly:
battinfo editorial promote-staging-dataset-batch --input-dir records/_staging/dataset --curated-root records/dataset
```

Dataset `citations` (the dataset↔publication DOI links) pass through promotion and registry
ingestion unchanged, and are re-expressed as Zenodo `related_identifiers` (`isSupplementTo`)
when the deposit is published.

