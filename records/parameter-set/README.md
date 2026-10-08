# Parameter sets (staging)

Parameter-set claim records generated from the curated `literature_ocv` library in HEU-IntelLiGent (`AnalysisOpenCircuitVoltages/data/literature_ocv`) by `scripts/ingest-literature-ocv-claims.py`. One record per (material kind, parameter set, source tool): the source's half-cell OCP claims about that material, with hysteresis branches as separate claims in the same record.

Record IRIs are deterministic from (target, scope, name), so re-running the ingest regenerates the same identifiers in place. Regenerate rather than hand-edit; fix upstream (the library manifest or the ingest script) and re-run. Attribution (contributor/funding/license) is stamped at publish time, not here.

## BPX parameter files

Records named `*--<source>--bpx` come from one published BPX file each, via `scripts/ingest-bpx-file.py`. The `cell--<source>--bpx` record is the parameterisation set: it lists the member records and carries the file itself under `distributions` (role `source`, the file as published; role `runnable`, a declared conversion where current parsers reject the source), with sha256 checksums and the parser and PyBaMM checks run at ingest. These records are addressed by the file: their IRIs derive from its canonical-JSON digest, never from names or targets, so the set's IRI always resolves to the same parameters. The files are uploaded to the registry's artifact store, not committed here; the publish script fetches each one and checks its sha256 before posting the record.
