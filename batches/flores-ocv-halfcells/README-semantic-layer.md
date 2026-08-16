# BattINFO semantic layer - Half-Cell OCV dataset (Zenodo 20086298)

This directory is the machine-readable [BattINFO](https://github.com/BIG-MAP/BattINFO) semantic layer for the published dataset:

- **Title:** Half-Cell Open-Circuit Voltage of Several Lithium-Ion Battery Active Materials Measured under Various Electrochemical Protocols
- **DOI (version):** [10.5281/zenodo.20086298](https://doi.org/10.5281/zenodo.20086298)
- **DOI (concept):** 10.5281/zenodo.19107294
- **License:** CC BY 4.0

The layer does **not** copy the data. It describes the 95 BDF parquet files that already live on Zenodo and links each one, through a chain of typed records, to the cell it was measured on, the electrode batch that cell was built from, the electrode design that batch realizes, the electrochemical protocol used, and the test run. It is designed to be attached to a new Zenodo version as supplementary metadata, and to be imported into the Battery Genome registry.

> **Corpus v3, staged for review.** This directory holds corpus v3: the first-class electrode model of v2 (BIG-MAP/BattINFO#342) plus the maintainer's review-round-2 rulings - one cell spec per electrode design, half-cell electrodes named by role (BIG-MAP/BattINFO#345), rounded quantities, and per-batch electrode statistics. The 319 records published on 2026-08-11 are the v1 shape and are still live and untouched; republishing is a separate, review-gated step, and `superseded/supersede-map.json` says what happens to each of the 319. Start with `REVIEW-TABLE-V3.md`.

## What is here

| Path | Contents |
|------|----------|
| `REVIEW-TABLE-V3.md` | **Start here.** The worked LNMO record chain, what changed since v2, and the validation summary. |
| `build_records.py` | Reproducible authoring script. Reads `sources/`, writes `drafts/` and the workspace records. Deterministic: a re-run is a no-op. |
| `build_bundle.py` | Mirrors the workspace records to `records/`, emits JSON-LD, validation evidence and the deposit bundle. Run after `build_records.py`. |
| `sources/metadata.csv` | Verbatim snapshot of the dataset's `metadata.csv` (95 rows). |
| `sources/zenodo-record.json` | Verbatim snapshot of the Zenodo API record (metadata + file checksums, sizes and URLs). |
| `drafts/` | The 16 cell-spec and test-spec authoring drafts the script writes and then loads with `ws.load()`. These are the human-editable inputs, not outputs. |
| `records/` | The 326 canonical BattINFO JSON records (source of truth; the working `.battinfo/` workspace is gitignored). |
| `superseded/v1/` | The 21 v1 material-layer records the electrode remodel retires, kept with a mapping table. |
| `superseded/supersede-map.json` | Generated: every one of the 319 published identifiers, and whether v3 keeps, replaces or splits it. |
| `build_supersede_map.py` | Writes that map by joining the published corpus to v3 on natural keys. |
| `preview/` | Rendered review pages for the staged batch (gitignored; regeneration command below). |
| `bundle/jsonld/` | Per-record JSON-LD for every record type present. |
| `bundle/deposit.jsonld` | One combined JSON-LD graph for the whole deposit (328 nodes). |
| `bundle/ro-crate-metadata.json` | Deposit-level RO-Crate metadata. |
| `bundle/validation-report.txt` | Per-type error / warning / SHACL counts over `records/`. |
| `bundle/deposit-coverage.txt` | Which record types reached the deposit graph, and which did not. |
| `bundle/emission-spot-checks.txt` | Worked JSON-LD examples: half-cell typing, electrode typing and route, powder anchors, typed protocol method, dataset distribution. |
| `bundle/gold-standard-report.txt` | Captured RO-Crate gold-standard check (see caveats below). |

## Record model (326 records)

```
material-spec (1)      the one POWDER the source identifies: the high Mn/Ni
   ^ active_material_   disorder LNMO used in every LNMO electrode
   | spec_id
electrode-spec (12)    electrode DESIGNS: active-material kind x source x
   ^ electrode_spec_id  processing route. Composition, design values, route.
   |                    Cited by cell specs via working_electrode_spec_id.
electrode (12)         the published electrode BATCHES, one per public label
                       (Gr-AQ-1, Si-AQ-1, SiGr-AQ-1..3, LNMO-AQ-1/2, LNMO-NMP-1/2,
                       LFP-NMP-1, NMC111-NMP-1, NMC532-NMP-1), with as-built figures.

cell-spec (12)         R2032 coin half-cells, cell_configuration = half_cell,
   |                   one per electrode design. Every one cites its design.
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

## The material and electrode levels

The model separates what a powder is from what an electrode is, and this dataset is a good test of that separation because it has both kinds of provenance in one deposit.

**Kind** is vocabulary, not a record. The seven active materials resolve to BattINFO's curated `material_kinds` keys (`graphite`, `silicon`, `silicon_graphite`, `lnmo`, `lfp`, `nmc111`, `nmc532`). The kind carries the semantics: it types the electrode node with its EMMO class (`SiliconBasedElectrode`, `LithiumNickelManganeseOxideElectrode`, ...), and on a powder record it anchors to a chemical-substance IRI via `schema:sameAs` with `skos:exactMatch` links to Wikidata / PubChem / Materials Project where verified.

**Material spec is the powder, and only one is authored.** The Zenodo description states exactly one powder-level fact: "The LNMO material used in this study targeted high Mn/Ni disorder, therefore the OCVs is a highly disordered spinel." That is a property of the material itself, it covers the whole study, and metadata.csv gives one theoretical specific capacity (140 mAh/g) for all four LNMO batches. So one powder record, cited by four electrode designs across two processing routes.

Every other powder is deliberately absent. For the silicon-containing electrodes the description says the opposite of an identification: "OCVs from Si-containing electrodes might exhibit large variations depending on material properties, such as particle size, crystallinity, surface chemistry, percentage of silicon in Si-Graphite blends, etc. None of these material and electrode properties are available from the suppliers." Graphite and silicon carry only their textbook theoretical capacities, which is the kind restated. The three commercial electrodes were bought whole; their manufacturers supplied electrode figures, never a powder identity. Those eight designs carry `kind` with no `active_material_spec_id`, which is exactly what the optional field is for.

**Electrode spec is the design**: active-material kind, coating composition, design values and the processing route. The route is part of the spec identity, so an aqueous LNMO electrode and an NMP LNMO electrode are two designs built from one powder - the distinction v1 could not express, because it treated the route as a batch property. Twelve designs, nine of them SINTEF's (carrying the registry organization IRI), three purchased.

**Electrode is the coated batch**, one per public label, carrying the label as `batch_id`, the as-built dry thickness and the batch's active-mass loading averaged over its cells (see below). Per-cell figures do not live here: they vary from disc to disc and stay on the tests.

In this dataset every design was coated exactly once, so designs and batches run 1:1. Two of them share (kind, source, route) and are still separate designs: SiGr-AQ-2 and SiGr-AQ-3 state different theoretical specific capacities for their active material (1150 vs 900 mAh/g) and different active-material type strings, so they are built from different blends.

### Batch statistics

Each electrode record carries `property.loading` (EMMO `ActiveMassLoading`) and `property.dry_thickness` (`DryCoatingThickness`) as the mean over the cells of that batch in `metadata.csv`, with `min_value` / `max_value` where the cells differ. `Electrode Loading / g cm-2` is the active-material loading, not the coating loading: for every row it equals the active-material mass divided by the disc area.

For nine of the twelve batches the loading genuinely varies cell to cell, and the batch note gives the mean, the sample (n-1) standard deviation, n and the observed range. For the other three - the purchased electrodes - and for all twelve dry thicknesses, `metadata.csv` repeats one value on every cell row; the note says so, because a repeated declaration is not a measured spread and a standard deviation of 0 should not be read as one.

The standard deviation is in the note rather than in the property block on purpose: a `Quantity` has no `standard_deviation` field and the curated property map has no EMMO class that means one, so a structured key would be dropped from the JSON-LD and warned about by the validator. `READINESS-REPORT.md` records it as gap E7.

## Half-cell modelling

All twelve cell specs are R2032 coin half-cells, stated structurally:

- `cell_configuration = "half_cell"` types the device node `BatteryHalfCell` + `HalfCellDevice` in JSON-LD. This replaces the old convention of encoding it in a free-text chemistry string.
- `reference_electrode = "lithium"` records that the potential reference is lithium metal.
- `chemistry = "li-metal"` is the controlled term for a cell whose counter electrode is lithium metal; it adds `LithiumMetalBattery` to the device typing.
- `working_electrode` is the material under study, described inline (active material, mass fraction, 14 mm diameter, dry thickness) and citing the electrode design it realizes through the top-level `working_electrode_spec_id`. It emits as `hasWorkingElectrode`.
- `counter_electrode` is lithium metal foil. It emits as `hasCounterElectrode`, typed `["CounterElectrode", "ReferenceElectrode"]`: in a half cell there is no third electrode, so the counter electrode *is* the reference, and that is one node playing two roles rather than two nodes.
- The voltage window vs Li/Li+ is on `properties.charging_voltage` (upper cutoff) and `properties.discharging_cutoff_voltage` (lower cutoff).

**No polarity anywhere.** A half cell has no positive and no negative side, so v3 names its electrodes by role and nothing else: no `positive_electrode` / `negative_electrode` holders, no `positive_electrode_basis` / `negative_electrode_basis`, and no `hasPositiveElectrode` / `hasNegativeElectrode` in any emitted document (0 occurrences across the 12 cell-spec JSON-LD files and the deposit graph). Corpus v1 and v2 did use polarity, with the working electrode as the positive one; that convention is superseded by the upstream ruling in BIG-MAP/BattINFO#345 and `docs/electrodes-model.md`.

Nothing is lost by dropping the bases. The chemistry that used to ride `positive_electrode_basis` now reaches the graph through the cited electrode spec, whose own node is typed with its chemistry class (`SiliconBasedElectrode`, `LithiumIronPhosphateElectrode`, `LithiumNickelManganeseOxideElectrode`, ...); the lithium-metal counter electrode is an authored holder rather than a basis string; and the cell keeps its half-cell device typing from `cell_configuration`.

`electrode_spec.polarity` is a different statement and stays: it is the *design's* intended full-cell side, derived from the kind, so the silicon, graphite and Si/Gr designs remain negative-electrode designs. A design's polarity and the role it is given in a cell are two facts in two places, and neither is authored twice.

Every cell spec covers exactly one electrode design, which is what lets all twelve carry `working_electrode_spec_id`. In v2 three specs each covered two designs and could cite neither; splitting them is ruling D1, and it re-seeded 144 published identifiers (`superseded/supersede-map.json`).

## Test protocols

The four protocols are authored as structured methods and emit typed EMMO process graphs: p-OCV and p-OCV hold as `PseudoOpenCircuitVoltageMethod`, GITT and GITT hold as `GalvanostaticIntermittentTitrationTechnique`, each with an `IterativeWorkflow` of five cycles containing `ConstantCurrentDischarging` / `ConstantCurrentCharging` steps with a `CRate` control parameter, and `OpenCircuitHold` or `VoltageHold` steps with a `Duration` termination parameter.

The methods are material-agnostic, which is what lets one protocol record serve all twelve cell specs: the steps say "to the lower voltage cutoff", and the numeric cutoffs live on the cell spec where they belong.

## Test conditions

Each test carries the ambient conditions the record states (`ambient_temperature: "room temperature"`, `voltage_reference: "Li/Li+"`) and the four as-built electrode figures that vary from cell to cell: active-material mass, electrode coating mass, nominal areal capacity and electrode loading. These are the values that normalise the measurement, and `Test.conditions` is the only structured, per-run home the model offers for them - the cell-instance `measured` block is a closed cell-performance vocabulary with no electrode-build slots. See gap G2 in `READINESS-REPORT.md`.

## Numbers

Every quantity is rounded to a fixed number of decimals per unit, chosen at or above the precision the source's own rounded columns carry (`build_records.py`, `_DECIMALS_BY_UNIT`). Two kinds of noise go with it: the conversion artifacts the script used to create (0.0204 g/cm2 times 1000 read as `20.400000000000002` mg/cm2) and the full-float-precision derived columns `metadata.csv` publishes (an active-material mass of `0.9040957492000021` mg, the product of a 4-digit coating mass and an 8-digit weight percentage). Values with seven or more decimals: 205 in v2, 0 in v3, across records, JSON-LD, the deposit graph and the RO-Crate. No identity seed contains a number, so no identifier moved.

## What is deliberately absent

- **Electrolyte and separator** are not reported in the source record and are not invented.
- **Powder records for eight of the nine electrode designs.** The source identifies one active material as a powder; the rest are unavailable by the authors' own statement, or were bought as finished electrodes. `kind` carries the chemistry in every case.
- **Binder and additive fractions.** Only the active-material weight percentage is published, so the coating composition states that and stops.
- **Current-collector foils.** Copper for the anodes and aluminium for the cathodes would be the obvious guess; the source does not say, so the field is empty.
- **Theoretical specific capacities** for the three commercial electrodes (LFP, NMC111, NMC532) are blank in `metadata.csv` and are omitted.
- **Product identifiers and grades.** No electrode carries a `product_id` or `grade`: the source states none for any of them, and a fabricated part number would look like provenance.
- **Derived OCP profiles** are out of scope for this layer; it describes the published measurements, not products computed from them.

## How to dereference

- **Canonical records** (`records/<type>/<type>-<id>.json`) are plain BattINFO JSON. Every record carries an `id` of the form `https://w3id.org/battinfo/<ns>/<uid>`, and cross-links use those IRIs (`manufacturer.id`, `active_material_spec_id`, `electrode_spec_id`, `working_electrode_spec_id`, `cell_spec_id`, `protocol_id`, dataset `about`).
- **JSON-LD** (`bundle/jsonld/<type>/<...>.jsonld`) carries the full inline `@context`, so every file expands offline. Every record type present is emitted.
- **Datasets** point at the real files: `distributions[].content_url` is the Zenodo download URL, with the md5 checksum and byte size taken from the Zenodo API; `access_url` is the DOI.

## Publishing caveats (see `bundle/gold-standard-report.txt`)

Per-record validation is clean: 326 records, 0 errors, 0 warnings, 0 SHACL non-conformances. The deposit-level RO-Crate gold-standard check reports two classes of issue, unchanged from v1 and neither coming from these records:

1. 95 errors, "Published dataset nodes must define non-empty schema:about references". Every dataset record does carry `about` (its cell and its test) and the per-record JSON-LD emits it as `dcterms:subject`; the deposit graph builder drops it.
2. 95 warnings, "BatteryTest should record prov:generated". The test-to-dataset back-link is not authored, because `ws.save()` rebuilds `test.dataset_ids` from the datasets the workspace engine holds and blanks it for everything else. The forward direction (dataset to cell and test) is complete.

Both are recorded in `READINESS-REPORT.md` as gaps G7 and G1.

A third class, 190 errors reading "Distribution sha256 must be a 64-character hexadecimal digest", was fixed upstream in BIG-MAP/BattINFO#339 and no longer appears. The deposit graph used to publish every checksum under a sha256 predicate whatever the record said; it now states `spdx:checksumAlgorithm_md5` with the Zenodo md5, which is the honest statement and needs no 10 GB download to produce.

A fourth was found in v2 and fixed upstream in BIG-MAP/BattINFO#344: the deposit graph hardcoded two record types, so the whole electrode layer was missing from `deposit.jsonld`. All eight types now reach it - `bundle/deposit-coverage.txt` shows 326 of 326 records in a 328-node graph.

## Reproducing

```bash
pip install "git+https://github.com/BIG-MAP/BattINFO.git" pyshacl
python build_records.py      # writes drafts/ and .battinfo/records/ (326 records)
python build_records.py      # again: idempotence check, and it rebuilds the workspace index
python build_bundle.py       # writes records/ and bundle/
python build_supersede_map.py  # writes superseded/supersede-map.json
```

Rendered review pages for the staged batch, from a checkout of `battinfo-registry`:

```bash
cd ../battinfo-registry
uv run python scripts/preview_staged_batch.py \
    --records-dir ../battinfo-records/batches/flores-ocv-halfcells/records \
    --out ../battinfo-records/batches/flores-ocv-halfcells/preview
# then open preview/index.html
```

`preview/` is gitignored: 326 pages are 1305 files and 30 MB of generated HTML, more than ten times the size of the whole repository.

The build is reproducible on BattINFO main at commit `33615d6` (BIG-MAP/BattINFO#345). Re-running against an existing workspace rewrites nothing: every record reports `[unchanged]`, no dataset is written, and no identity is pruned. A rebuild in an empty workspace reproduces all 326 byte for byte apart from `provenance.retrieved_at`, the build timestamp.

Because D1 re-seeds six cell specs, a rebuild leaves the identities it replaced behind in the workspace. `build_records.py` prunes them and reports the count, so `records/` and the deposit graph only ever contain records the run actually authored.

## Attaching this layer to a new Zenodo version

The layer is supplementary metadata for [Zenodo 20086298](https://doi.org/10.5281/zenodo.20086298). Publishing it as a new version of that record keeps the concept DOI (10.5281/zenodo.19107294) and leaves the 95 parquet files untouched.

**These steps describe the v1 upload that has already happened.** They are kept as the recipe; the v3 corpus is not uploaded anywhere yet, and the counts below refresh at republish time along with `description-addendum.md`.

Upload two archives, built from this directory:

```bash
cd batches/flores-ocv-halfcells
zip -r battinfo-records.zip records          # v3: 326 files, ~2.0 MB
zip -r battinfo-bundle.zip  bundle           # v3: 332 files, ~7.0 MB
```

| archive | contents |
|---|---|
| `battinfo-records.zip` | `records/` - the canonical BattINFO JSON records. v3: `material-spec` (1), `electrode-spec` (12), `electrode` (12), `cell-spec` (12), `cell-instance` (95), `test-protocol` (4), `test` (95), `dataset` (95). |
| `battinfo-bundle.zip` | `bundle/jsonld/` (one JSON-LD document per record, each with a full inline `@context`), `bundle/deposit.jsonld` (the combined deposit graph), `bundle/ro-crate-metadata.json`, and the evidence files: `validation-report.txt`, `deposit-coverage.txt`, `emission-spot-checks.txt`, `gold-standard-report.txt`. |

Steps on Zenodo:

1. Open the record, choose **New version**. The 95 parquet files carry over; do not re-upload them.
2. Upload `battinfo-records.zip` and `battinfo-bundle.zip`.
3. Paste the text of `description-addendum.md` into the description, as a new **Semantic layer** heading at the end.
4. Keep the existing creators, license (CC BY 4.0) and the IntelLiGent grant (101069765). Add the keywords `BattINFO`, `EMMO`, `linked data`, `RO-Crate` if they are not already there.
5. Under **Related works**, add `https://github.com/battery-genome/battinfo-records` as *is supplemented by* (software/repository), and one resolvable record identifier as *is described by*.
6. Publish. The new version DOI supersedes 10.5281/zenodo.20086298; the concept DOI is unchanged.

The records reference the parquet files by their Zenodo download URL and md5 checksum, both taken verbatim from the Zenodo API snapshot in `sources/zenodo-record.json`. A new version does not change those URLs or checksums, so nothing in the layer needs regenerating after the upload.

## Registry publication

The 319 v1 records were published to the Battery Genome registry on 2026-08-11 (workspace `battinfo-records`, publisher `battinfo-records-bot`, `source_version` `2026-08-11`), in dependency order so that every internal reference resolved before the record citing it was submitted. Every record was staged and then promoted through the review gate; none failed.

**Corpus v3 has not been submitted.** All 319 published records are still live and stay live until the republish supersedes them. `superseded/supersede-map.json` is the complete statement of what happens to each: 154 keep their identifier, 159 are replaced by one successor, 6 are split across two. The republish is the only step that touches the registry, and it happens after this branch is reviewed.

Each published record has a permanent `w3id.org` identifier. Three worth citing:

| record | identifier | v3 status |
|---|---|---|
| Silicon R2032 half-cell spec | `https://w3id.org/battinfo/spec/zqwq-ted6-cwb2-0d42` | same IRI, content updated |
| NMC532-NMP-1 electrode batch | `https://w3id.org/battinfo/material/17t8-f8vm-d6hj-gwzd` | retired; replaced by `electrode/6xwk-m3e1-1c11-nr0t` |
| LNMO-NMP-1 GITT dataset | `https://w3id.org/battinfo/dataset/09vb-kh3s-aq3q-4s3e` | replaced: its cell spec was split, see the supersede map |

These content-negotiate: `Accept: application/ld+json` and `Accept: text/turtle` return the record from public storage with no credentials. Requesting HTML redirects to the platform page, which is behind the launch gate until the platform opens, so cite the identifier rather than a platform URL.

One caveat worth knowing when reading the registry copy: the registry serves its own index view of a record (the canonical record body verbatim, plus a flattened `metadata` block it can filter on). It does not re-emit the EMMO semantic document. The `BatteryHalfCell` device typing, the chemical-substance anchors and the typed protocol process graphs live in `bundle/jsonld/` and `bundle/deposit.jsonld`, which is what makes the Zenodo archive, not the registry, the source of truth for the semantics.
