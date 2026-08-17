# Parameter sets (staging)

Parameter-set claim records generated from the curated `literature_ocv` library in HEU-IntelLiGent (`AnalysisOpenCircuitVoltages/data/literature_ocv`) by `scripts/ingest-literature-ocv-claims.py`. One record per (material kind, parameter set, source tool): the source's half-cell OCP claims about that material, with hysteresis branches as separate claims in the same record.

Record IRIs are deterministic from (target, scope, name), so re-running the ingest regenerates the same identifiers in place. Regenerate rather than hand-edit; fix upstream (the library manifest or the ingest script) and re-run. Attribution (contributor/funding/license) is stamped at publish time, not here.
