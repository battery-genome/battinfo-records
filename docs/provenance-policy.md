# Provenance Policy

Curated records in this repo must be explainable.

## Minimum Expectation

Each curated record should remain explainable from the JSON record itself. At minimum, the record should make it clear:

- What sources support this record?
- Which source identifiers or locators are relevant?
- What part of the source matters?
- Where editorial judgment was applied?

Use `metadata/sources/...<record-id>.sources.yaml` only when a record needs extra editorial evidence notes beyond what fits cleanly in the BattINFO JSON.

## Preferred Evidence Form

Prefer lightweight references:

- DOI or accession identifier
- Stable URL
- Manufacturer datasheet identifier and revision/date
- Literature citation
- Repository or dataset identifier
- Short notes pointing to tables, sections, or figures

## Large Files

- Do not commit large PDFs, images, spreadsheets, or raw data by default.
- If a source is important, store a durable citation or locator first.
- Only add binaries when there is a clear approved need and the storage decision is intentional.

## Derived Assertions

If the curated record contains derived or normalized values:

- Cite the sources used.
- Note the derivation or editorial synthesis briefly.
- Keep derivation logic in BattINFO tooling when it becomes code-like.

## Provenance Quality Bar

Another curator should be able to review the record and determine why each important claim is present without needing private context.
