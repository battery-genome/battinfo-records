# Parameter sets (staging)

Parameter-set claim records generated from the curated `literature_ocv` library in HEU-IntelLiGent (`AnalysisOpenCircuitVoltages/data/literature_ocv`) by `scripts/ingest-literature-ocv-claims.py`. One record per (material kind, parameter set, source tool): the source's half-cell OCP claims about that material, with hysteresis branches as separate claims in the same record.

Record IRIs are deterministic from (target, scope, name), so re-running the ingest regenerates the same identifiers in place. Regenerate rather than hand-edit; fix upstream (the library manifest or the ingest script) and re-run. Attribution (contributor/funding/license) is stamped at publish time, not here.

## BPX parameter files

Each published BPX file is one record, `<source>--bpx`, written by `scripts/ingest-bpx-file.py`. It holds every value in the file as a claim, grouped by part (cell, each electrode's material and build, separator, electrolyte, initial state), the User-defined block verbatim, and the file itself under `distributions`: the source as published, a runnable conversion only when the official parser rejects the source, and a mirror at the source repository's pinned commit, each with its sha256 and the parser and PyBaMM checks run at ingest. The record is addressed by the file's parameters, so its IRI always resolves to the same values. Which cell the file describes is stated per source: an existing cell spec (link only), a new real cell (identity-only cell spec and, if missing, the maker's organization, after a duplicate search), or a virtual cell (no cell record). The files are uploaded to the registry's artifact store, not committed here; the publish script fetches each one and checks its sha256 before posting the record.

## Namespace

Parameter sets are datasets (IDENTIFIER_POLICY 6.1 and 6.3, ruled 2026-10-11) and mint under `https://w3id.org/battinfo/dataset/{uid}`. The records here were first published under `spec/`; `scripts/migrate-parameter-sets-to-dataset.py` gave each its `dataset/` IRI and a `supersedes` link to the old `spec/` one, so republishing them marks the old records superseded while their IRIs keep resolving. The publish script keys each record by its uid (`parameter-set:<uid>`), because the registry refuses a new record under a key that already holds a `spec/` parameter set.
