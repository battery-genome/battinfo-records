# BattINFO semantic layer - Half-Cell OCV dataset (Zenodo 20086298)

This directory is the machine-readable [BattINFO](https://github.com/BIG-MAP/BattINFO)
semantic layer for the published dataset:

- **Title:** Half-Cell Open-Circuit Voltage of Several Lithium-Ion Battery Active Materials Measured under Various Electrochemical Protocols
- **DOI (version):** [10.5281/zenodo.20086298](https://doi.org/10.5281/zenodo.20086298)
- **DOI (concept):** 10.5281/zenodo.19107294
- **License:** CC BY 4.0

The layer does **not** copy the data. It describes the 95 BDF parquet files that
already live on Zenodo and links each one, through a chain of typed records, to the
cell it was measured on, the active material in that cell, the electrochemical
protocol used, and the test run. It is designed to be (a) attached to a new Zenodo
version as supplementary metadata and (b) imported into the Battery Genome registry.

## What is here

| Path | Contents |
|------|----------|
| `build_records.py` | Reproducible authoring script. Reads `sources/` and writes the workspace records. Deterministic: a re-run is a no-op. |
| `build_bundle.py` | Mirrors the workspace records to `records/` and emits the JSON-LD bundle. Run after `build_records.py`. |
| `sources/metadata.csv` | Verbatim snapshot of the dataset's `metadata.csv` (95 rows). |
| `sources/zenodo-record.json` | Verbatim snapshot of the Zenodo API record (metadata + file checksums/sizes/URLs). |
| `records/` | The 305 canonical BattINFO JSON records (source of truth; the working `.battinfo/` workspace is gitignored). |
| `bundle/jsonld/` | Per-record resolver JSON-LD for the four emittable types. |
| `bundle/deposit.jsonld` | One combined JSON-LD graph for the whole deposit. |
| `bundle/ro-crate-metadata.json` | Deposit-level RO-Crate metadata. |
| `bundle/gold-standard-report.txt` | Captured RO-Crate gold-standard check (see caveats below). |
| `bundle/save-panel.txt` | Captured `ws.save` panel and record counts (validation evidence). |

## Record model (305 records)

```
material-spec (7)      active materials: graphite, silicon, silicon-graphite,
                       LNMO, LFP, NMC111, NMC532
   ^ material_spec_id
cell-spec (9)          R2032 coin HALF-CELLS, one per (material, electrode source)
   |                   working electrode = the active material; counter/reference = Li metal
   v hasDescription
cell-instance (95)     one per parquet; serial = 6-char batch id; name = public label
   |
   +-- test (95)       cell x protocol; 11 known issues -> conformance annotations
   |     ^ protocol
   |     test-protocol (4)   p-OCV, p-OCV hold, GITT, GITT hold (structured methods)
   |
   +-- dataset (95)    references the Zenodo parquet by URL + md5 + byte size
```

Each of the 95 parquet files maps to exactly one `cell-instance` + `test` + `dataset`.

## How to dereference

- **Canonical records** (`records/<type>/<type>-<id>.json`) are plain BattINFO JSON.
  Every record carries an `id` of the form `https://w3id.org/battinfo/<ns>/<uid>`.
  Cross-links use those IRIs (`manufacturer.id`, `material_spec_id`,
  `cell_spec_id`, `protocol_id`, dataset `about`, etc.).
- **JSON-LD** (`bundle/jsonld/<type>/<...>.jsonld`) is the resolver view of the four
  emittable record types (cell-spec, cell-instance, test, dataset). Load any file
  into an RDF store; the `@context` resolves the BattINFO/EMMO vocabulary.
- **Datasets** point at the real files: `distributions[].content_url` is the Zenodo
  download URL, with the `md5` checksum and byte size from the Zenodo API. `access_url`
  is the DOI.

## Half-cell modelling decision

All nine cell specs are R2032 coin **half-cells**. They are expressed as:

- `positive_electrode` = the **working electrode** (the active material under study),
  with its `active_material.material_spec_id` linking to the material spec, and the
  electrode geometry (14 mm diameter; dry thickness / active-material mass fraction
  where they are consistent across the batch).
- `negative_electrode` = **lithium metal** (the counter and reference electrode).
- `positive_electrode_basis` = the material label; `negative_electrode_basis` = `Li`.
- `chemistry` = `Li half-cell`; `cell_format` = `coin`; `size_code` = `R2032`.
- The half-cell voltage window vs Li/Li+ is on `properties.charging_voltage` (upper
  cutoff) and `properties.discharging_cutoff_voltage` (lower cutoff), with the full
  explanation in `specification_comment`.

The working electrode is modelled as the **positive** electrode for both cathode and
anode materials because in a half-cell lithium metal is the most negative electrode,
so the working electrode is at the higher potential and the cell voltage reported in
the BDF (`Voltage / V`) equals the working-electrode potential vs Li/Li+. This keeps
the sign convention consistent with the data. The material spec's own
`electrode_polarity` records the material's intended *full-cell* role (negative for
graphite/silicon/silicon-graphite, positive for the oxides); the half-cell placement
is a measurement configuration, not a contradiction.

### Known limitations of the expression

- **Per-instance electrode figures** (active-material mass, coating mass, weight %,
  theoretical capacity, thickness, areal capacity, loading) have no typed slot on a
  cell instance: `measured` is a closed 67-key cell-performance vocabulary and the
  `Test` model exposes no `conditions` field. They are recorded as a clearly-labelled,
  parseable block on each instance's `comment`.
- **Electrolyte and separator** are not reported in the source record and are omitted
  (not invented).
- **Commercial-electrode theoretical capacities** (LFP, NMC111, NMC532) are blank in
  `metadata.csv` and are omitted from those material specs.
- Some cell specs group two electrode batches that differ by processing route
  (e.g. LNMO-AQ-1 and LNMO-NMP-1 both fall under `lnmo (intelligent1)`). Values that
  differ across the grouped batches are pushed down to the individual instances; the
  spec keeps only what is common. The public label and processing route are on every
  instance.

## Publishing caveats (see `bundle/gold-standard-report.txt`)

The per-record validation is clean (0 errors under `validation_policy="strict"`,
SHACL included). The deposit-level RO-Crate **gold-standard** check reports two
classes of issue that are inherent to this source and do not affect record validity:

1. The RO-Crate gold-standard requires a 64-char **sha256** per distribution, but
   Zenodo publishes only **md5**. Computing sha256 would require downloading ~10 GB of
   parquet files. The datasets therefore carry the authentic Zenodo md5; sha256 is
   absent by design.
2. Structured test-method steps emit an `ElectrochemicalProcess` `@type` that is not
   yet in the RO-Crate allowed-term set.

Both are documented for the operator and flagged in the readiness report.

## Reproducing

```bash
pip install "git+https://github.com/BIG-MAP/BattINFO.git" pyshacl
python build_records.py      # writes .battinfo/records/ (305 records), prints the save panel
python build_bundle.py       # writes records/ and bundle/
```
