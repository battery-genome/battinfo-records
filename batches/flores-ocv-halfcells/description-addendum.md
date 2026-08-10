# Zenodo description addendum (draft)

Suggested text to add to the dataset description on the next Zenodo version, under a new `<h1>Semantic layer</h1>` heading. Plain and terse; edit as preferred.

---

## Semantic layer

A machine-readable BattINFO semantic layer accompanies this dataset. It describes every electrode batch, cell, electrochemical protocol, test and data file using the [BattINFO](https://github.com/BIG-MAP/BattINFO) / EMMO vocabulary, and links each of the 95 BDF parquet files to the cell it was measured on, the electrode batch that cell was built from, and the protocol used. The layer references the data by URL and md5 checksum; it does not duplicate it.

It is provided as two archives:

- `battinfo-records.zip` - 319 canonical BattINFO JSON records: 9 electrode-material products, 12 electrode batches (each carrying its aqueous or NMP processing route), 9 R2032 coin half-cell specifications, 95 cell instances, 4 test protocols, 95 tests and 95 dataset descriptions;
- `battinfo-bundle.zip` - the same content as JSON-LD (one document per record, each with a full inline context), a combined deposit graph, RO-Crate metadata and the validation evidence.

The half-cells are typed as `BatteryHalfCell` / `HalfCellDevice`; the active materials resolve to EMMO classes with chemical-substance anchors and, where verified, Wikidata / PubChem / Materials Project identifiers; the four protocols emit typed process graphs (`PseudoOpenCircuitVoltageMethod`, `GalvanostaticIntermittentTitrationTechnique`) describing the five-cycle constant-current, rest, pulse and voltage-hold sequences. Each dataset record names its parquet file by download URL, byte size and md5 digest, stated as an md5 rather than relabelled.

The records are also being contributed to the Battery Genome registry (https://www.battery-genome.org), which gives the cells, protocols, tests and datasets resolvable identifiers. This dataset is funded by the EU IntelLiGent project (grant 101069765) and released under CC BY 4.0.
