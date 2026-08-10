# BattINFO semantic layer - Half-Cell OCV dataset (Zenodo 20086298)

This directory is the machine-readable [BattINFO](https://github.com/BIG-MAP/BattINFO) semantic layer for the published dataset:

- **Title:** Half-Cell Open-Circuit Voltage of Several Lithium-Ion Battery Active Materials Measured under Various Electrochemical Protocols
- **DOI (version):** [10.5281/zenodo.20086298](https://doi.org/10.5281/zenodo.20086298)
- **DOI (concept):** 10.5281/zenodo.19107294
- **License:** CC BY 4.0

The layer does **not** copy the data. It describes the 95 BDF parquet files that already live on Zenodo and links each one, through a chain of typed records, to the cell it was measured on, the electrode batch that cell was built from, the material product that batch came from, the electrochemical protocol used, and the test run. It is designed to be attached to a new Zenodo version as supplementary metadata, and to be imported into the Battery Genome registry.

## What is here

| Path | Contents |
|------|----------|
| `build_records.py` | Reproducible authoring script. Reads `sources/`, writes `drafts/` and the workspace records. Deterministic: a re-run is a no-op. |
| `build_bundle.py` | Mirrors the workspace records to `records/`, emits JSON-LD, validation evidence and the deposit bundle. Run after `build_records.py`. |
| `sources/metadata.csv` | Verbatim snapshot of the dataset's `metadata.csv` (95 rows). |
| `sources/zenodo-record.json` | Verbatim snapshot of the Zenodo API record (metadata + file checksums, sizes and URLs). |
| `drafts/` | The 13 cell-spec and test-spec authoring drafts the script writes and then loads with `ws.load()`. These are the human-editable inputs, not outputs. |
| `records/` | The 319 canonical BattINFO JSON records (source of truth; the working `.battinfo/` workspace is gitignored). |
| `bundle/jsonld/` | Per-record JSON-LD for all seven record types. |
| `bundle/deposit.jsonld` | One combined JSON-LD graph for the whole deposit (321 nodes). |
| `bundle/ro-crate-metadata.json` | Deposit-level RO-Crate metadata. |
| `bundle/validation-report.txt` | Per-type error / warning / SHACL counts over `records/`. |
| `bundle/emission-spot-checks.txt` | Worked JSON-LD examples: half-cell typing, material anchors, typed protocol method, dataset distribution. |
| `bundle/gold-standard-report.txt` | Captured RO-Crate gold-standard check (see caveats below). |

## Record model (319 records)

```
material-spec (9)      electrode products: active-material KIND x electrode source
   ^ material_spec_id   (graphite/intelligent, lfp/gelon, lnmo/intelligent1, ...)
   |
material (12)          the published electrode BATCHES, one per public label
                       (Gr-AQ-1, Si-AQ-1, SiGr-AQ-1..3, LNMO-AQ-1/2, LNMO-NMP-1/2,
                       LFP-NMP-1, NMC111-NMP-1, NMC532-NMP-1). Carries the
                       processing route (aqueous vs NMP) and the batch figures.

cell-spec (9)          R2032 coin half-cells, cell_configuration = half_cell.
   |                   Working electrode links to its material spec.
   v cell_spec_id
cell-instance (95)     one per parquet; serial = 6-char id, name + batch_id = public label
   |
   +-- test (95)       cell x protocol; 11 known issues -> conformance annotations
   |     ^ protocol_id
   |     test-protocol (4)   p-OCV, p-OCV hold, GITT, GITT hold
   |
   +-- dataset (95)    about -> cell + test; references the Zenodo parquet by URL,
                       md5 and byte size
```

Each of the 95 parquet files maps to exactly one `cell-instance` + `test` + `dataset`.

## The three material levels

Materials are modelled at the three levels the data actually distinguishes:

**Kind** is vocabulary, not a record. The seven active materials resolve to BattINFO's curated `material_kinds` keys (`graphite`, `silicon`, `silicon_graphite`, `lnmo`, `lfp`, `nmc111`, `nmc532`). The kind is what carries the semantics: it types the JSON-LD node with its EMMO class (`Silicon`, `LithiumNickelManganeseOxide`, ...), anchors it to a chemical-substance IRI via `schema:sameAs`, and adds `skos:exactMatch` links to Wikidata / PubChem / Materials Project where those are verified.

**Spec** is the electrode product: a kind from a particular source. SINTEF made the IntelLiGent batches (`intelligent`, `intelligent1`, `intelligent2`); Gelon LIB and Customcells supplied the commercial electrodes. Nine products, each with the manufacturer or supplier recorded, the SINTEF ones carrying the registry organization IRI.

**Instance** is the physical electrode batch, one per public label. This is where the processing route lives, exactly as the schema intends: aqueous versus NMP is a property of how a lot was built, not a distinct product. The route is read from the public label, which the dataset's own metadata schema defines as encoding "chemical composition and manufacturing route". Batch-constant figures (active-material mass fraction, dry thickness, theoretical specific capacity) sit on the lot too, since they vary between batches of the same product.

Two products cover two batches each (LNMO/intelligent1 spans LNMO-AQ-1 and LNMO-NMP-1; silicon-graphite/intelligent2 spans SiGr-AQ-2 and SiGr-AQ-3), which is precisely why the route and the batch figures belong on the lot rather than the spec.

## Half-cell modelling

All nine cell specs are R2032 coin half-cells, stated structurally:

- `cell_configuration = "half_cell"` types the device node `BatteryHalfCell` + `HalfCellDevice` in JSON-LD. This replaces the old convention of encoding it in a free-text chemistry string.
- `reference_electrode = "lithium"` records the counter/reference electrode.
- `chemistry = "li-metal"` and `negative_electrode_basis = "lithium-metal"` are the controlled terms for a cell whose negative electrode is lithium metal; together they add `LithiumMetalBattery` to the device typing.
- `positive_electrode` is the **working electrode**, with its active material linked to the material spec by `material_spec_id`, plus the electrode geometry (14 mm diameter, and the dry thickness / mass fraction where every batch under the spec agrees).
- `negative_electrode` is lithium metal foil, the counter and reference electrode.
- The voltage window vs Li/Li+ is on `properties.charging_voltage` (upper cutoff) and `properties.discharging_cutoff_voltage` (lower cutoff).

The working electrode is the **positive** electrode for both cathode and anode materials, because lithium metal is the lowest-potential electrode in the cell: the working electrode always sits at the higher potential, and the voltage in the BDF files (0.01-1.00 V for graphite and silicon, 3.50-4.80 V for LNMO) is the working-electrode potential vs Li/Li+. Modelling it any other way would invert the sign convention of the published data.

`positive_electrode_basis` is set only where domain-battery curates a positive-electrode class: `lfp` for LFP, `nmc` for NMC111 and NMC532. Graphite, silicon, silicon-graphite and LNMO have no positive-electrode term in the vocabulary (the first three are normally anode materials; LNMO has no term at either polarity), so the field is omitted rather than filled with a value that maps to nothing. Nothing is lost: the electrode's bill of materials names the active material and links it to the material spec, which carries the kind, the EMMO class and the substance anchor.

## Test protocols

The four protocols are authored as structured methods and emit typed EMMO process graphs: p-OCV and p-OCV hold as `PseudoOpenCircuitVoltageMethod`, GITT and GITT hold as `GalvanostaticIntermittentTitrationTechnique`, each with an `IterativeWorkflow` of five cycles containing `ConstantCurrentDischarging` / `ConstantCurrentCharging` steps with a `CRate` control parameter, and `OpenCircuitHold` or `VoltageHold` steps with a `Duration` termination parameter.

The methods are material-agnostic, which is what lets one protocol record serve all nine cell specs: the steps say "to the lower voltage cutoff", and the numeric cutoffs live on the cell spec where they belong.

## Test conditions

Each test carries the ambient conditions the record states (`ambient_temperature: "room temperature"`, `voltage_reference: "Li/Li+"`) and the four as-built electrode figures that vary from cell to cell: active-material mass, electrode coating mass, nominal areal capacity and electrode loading. These are the values that normalise the measurement, and `Test.conditions` is the only structured, per-run home the model offers for them - the cell-instance `measured` block is a closed cell-performance vocabulary with no electrode-build slots. See gap G2 in `READINESS-REPORT.md`.

## What is deliberately absent

- **Electrolyte and separator** are not reported in the source record and are not invented.
- **Theoretical specific capacities** for the three commercial electrodes (LFP, NMC111, NMC532) are blank in `metadata.csv` and are omitted.
- **The silicon-graphite composition** is not reported by the suppliers, as the Zenodo record itself notes, so no formula is stated for that kind.
- **Derived OCP profiles** are out of scope for this layer; it describes the published measurements, not products computed from them.

## How to dereference

- **Canonical records** (`records/<type>/<type>-<id>.json`) are plain BattINFO JSON. Every record carries an `id` of the form `https://w3id.org/battinfo/<ns>/<uid>`, and cross-links use those IRIs (`manufacturer.id`, `material_spec_id`, `cell_spec_id`, `protocol_id`, dataset `about`).
- **JSON-LD** (`bundle/jsonld/<type>/<...>.jsonld`) carries the full inline `@context`, so every file expands offline. All seven record types are emitted.
- **Datasets** point at the real files: `distributions[].content_url` is the Zenodo download URL, with the md5 checksum and byte size taken from the Zenodo API; `access_url` is the DOI.

## Publishing caveats (see `bundle/gold-standard-report.txt`)

Per-record validation is clean: 319 records, 0 errors, 0 warnings, SHACL conforming. The deposit-level RO-Crate gold-standard check still reports three classes of issue, none of which come from these records:

1. 190 errors, "Distribution sha256 must be a 64-character hexadecimal digest". The deposit graph builder labels every distribution checksum `sha256` regardless of the algorithm on the record, so the authentic 32-character Zenodo md5 is emitted under a sha256 predicate and then fails the length check. The canonical records state `algorithm: "md5"` correctly. Computing real sha256 digests would mean downloading roughly 10 GB of parquet.
2. 95 errors, "Published dataset nodes must define non-empty schema:about references". Every dataset record does carry `about` (its cell and its test) and the per-record JSON-LD emits it as `dcterms:subject`; the deposit graph builder drops it.
3. 95 warnings, "BatteryTest should record prov:generated". The test-to-dataset back-link is not authored, because `ws.save()` rebuilds `test.dataset_ids` from the datasets the workspace engine holds and blanks it for everything else. The forward direction (dataset to cell and test) is complete.

All three are recorded in `READINESS-REPORT.md` as gaps G6, G7 and G1.

## Reproducing

```bash
pip install "git+https://github.com/BIG-MAP/BattINFO.git" pyshacl
python build_records.py      # writes drafts/ and .battinfo/records/ (319 records)
python build_bundle.py       # writes records/ and bundle/
```
