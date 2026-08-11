# Zenodo description addendum

Text to add to the dataset description on the next Zenodo version, under a new `<h1>Semantic layer</h1>` heading. Copy the section below the rule as-is, or edit as preferred. The identifiers it cites are live.

---

## Semantic layer

A machine-readable BattINFO semantic layer accompanies this dataset. It describes every electrode batch, cell, electrochemical protocol, test and data file using the [BattINFO](https://github.com/BIG-MAP/BattINFO) / EMMO vocabulary, and links each of the 95 BDF parquet files to the cell it was measured on, the electrode batch that cell was built from, and the protocol used. The layer references the data by URL and md5 checksum; it does not duplicate it.

It is provided as two archives:

- `battinfo-records.zip` - 319 canonical BattINFO JSON records: 9 electrode-material products, 12 electrode batches (each carrying its aqueous or NMP processing route), 9 R2032 coin half-cell specifications, 95 cell instances, 4 test protocols, 95 tests and 95 dataset descriptions;
- `battinfo-bundle.zip` - the same content as JSON-LD (one document per record, each with a full inline context), a combined deposit graph, RO-Crate metadata and the validation evidence.

The half-cells are typed as `BatteryHalfCell` / `HalfCellDevice`; the active materials resolve to EMMO classes with chemical-substance anchors and, where verified, Wikidata / PubChem / Materials Project identifiers; the four protocols emit typed process graphs (`PseudoOpenCircuitVoltageMethod`, `GalvanostaticIntermittentTitrationTechnique`) describing the five-cycle constant-current, rest, pulse and voltage-hold sequences. Each dataset record names its parquet file by download URL, byte size and md5 digest, stated as an md5 rather than relabelled.

All 319 records are also published in the Battery Genome registry (https://www.battery-genome.org), so every material, cell, protocol, test and dataset has a permanent identifier that resolves to machine-readable metadata. For example, https://w3id.org/battinfo/dataset/09vb-kh3s-aq3q-4s3e describes the GITT measurement on cell ee5c27 and points back to the parquet file in this record by URL and md5 digest; that cell is https://w3id.org/battinfo/cell/bkgc-b8j2-d27b-qkke, built to the LNMO R2032 half-cell specification https://w3id.org/battinfo/spec/kzhf-qsrt-2z76-agkp. This dataset is funded by the EU IntelLiGent project (grant 101069765) and released under CC BY 4.0.
