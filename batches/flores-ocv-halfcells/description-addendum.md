# Zenodo description addendum (draft)

Suggested text to add to the dataset description on the next Zenodo version, under a
new `<h1>Semantic layer</h1>` heading. Plain and terse; edit as preferred.

---

## Semantic layer

A machine-readable BattINFO semantic layer accompanies this dataset. It describes
every cell, active material, electrochemical protocol, test and data file using the
[BattINFO](https://github.com/BIG-MAP/BattINFO) / EMMO vocabulary, and links each of
the 95 BDF parquet files to the cell it was measured on and the protocol used. The
layer references the data by URL and md5 checksum; it does not duplicate it.

It is provided as:

- `records/` - 305 canonical BattINFO JSON records (7 active materials, 9 coin
  half-cell specifications, 95 cell instances, 4 test protocols, 95 tests, 95 dataset
  descriptions);
- `bundle/` - the same content as JSON-LD plus a combined deposit graph and RO-Crate
  metadata.

The records are also being contributed to the Battery Genome registry
(https://www.battery-genome.org), where each cell, protocol and dataset receives a
resolvable identifier. This dataset is funded by the EU IntelLiGent project (grant
101069765) and released under CC BY 4.0.
