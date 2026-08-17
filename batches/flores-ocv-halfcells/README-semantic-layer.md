# BattINFO semantic layer - Half-Cell OCV dataset (Zenodo 20086298)

This directory is the machine-readable [BattINFO](https://github.com/BIG-MAP/BattINFO) semantic layer for the published dataset:

- **Title:** Half-Cell Open-Circuit Voltage of Several Lithium-Ion Battery Active Materials Measured under Various Electrochemical Protocols
- **DOI (version):** [10.5281/zenodo.20086298](https://doi.org/10.5281/zenodo.20086298)
- **DOI (concept):** 10.5281/zenodo.19107294
- **License:** CC BY 4.0

The layer does **not** copy the data. It describes the 95 BDF parquet files that already live on Zenodo and links each one, through a chain of typed records, to the cell it was measured on, the electrode disc inside that cell, the design that disc realizes, the powder that design is coated from, the electrochemical protocol used, and the test run. It is designed to be attached to a new Zenodo version as supplementary metadata, and to be imported into the Battery Genome registry.

> **Corpus v4, staged for review.** This directory holds corpus v4: the review-round-3 rulings on top of v3. A powder record for every active material rather than only where the source volunteers one; Topsoe named as the LNMO powder's manufacturer; a material lot for the one physical batch the source evidences; the electrode record redefined as the disc inside one cell, carrying that cell's as-built figures, with the batch statistics moved up to the electrode spec as structured `standard_deviation` / `sample_count`; and every cell linking its disc through `working_electrode_id`. The 319 records published on 2026-08-11 are the v1 shape and are still live and untouched; republishing is a separate, review-gated step, and `superseded/supersede-map.json` says what happens to each of the 319. Start with `REVIEW-TABLE-V4.md`.

## What is here

| Path | Contents |
|------|----------|
| `REVIEW-TABLE-V4.md` | **Start here.** The ten-record LNMO chain from organization to plotted dataset, what changed since v3, and the validation summary. |
| `build_records.py` | Reproducible authoring script. Reads `sources/`, writes `drafts/` and the workspace records. Deterministic: a re-run is a no-op. |
| `build_bundle.py` | Mirrors the workspace records to `records/`, emits JSON-LD, validation evidence and the deposit bundle. Run after `build_records.py`. |
| `sources/metadata.csv` | Verbatim snapshot of the dataset's `metadata.csv` (95 rows). |
| `sources/zenodo-record.json` | Verbatim snapshot of the Zenodo API record (metadata + file checksums, sizes and URLs). |
| `drafts/` | The 16 cell-spec and test-spec authoring drafts the script writes and then loads with `ws.load()`. These are the human-editable inputs, not outputs. |
| `extract_profiles.py`, `profiles/` | Derives one small Plotly figure per dataset from the parquet on Zenodo; the 95 figures it produced, with their sha256 index. |
| `upload_profiles.py` | Puts those figures in the object store the dataset records point at. Deliberately not run for v4: it is a production write. |
| `records/` | The 416 canonical BattINFO JSON records (source of truth; the working `.battinfo/` workspace is gitignored). |
| `superseded/v1/` | The 21 v1 material-layer records the electrode remodel retires, kept with a mapping table. |
| `superseded/supersede-map.json` | Generated: every one of the 319 published identifiers, and whether v4 keeps, replaces or splits it, plus a count of the v4 records that supersede nothing. |
| `build_supersede_map.py` | Writes that map by joining the published corpus to v4 on natural keys. |
| `preview/` | Rendered review pages for the staged batch (gitignored; regeneration command below). |
| `bundle/jsonld/` | Per-record JSON-LD for every record type present. |
| `bundle/deposit.jsonld` | One combined JSON-LD graph for the whole deposit (418 nodes). |
| `bundle/ro-crate-metadata.json` | Deposit-level RO-Crate metadata. |
| `bundle/validation-report.txt` | Per-type error / warning / SHACL counts over `records/`. |
| `bundle/deposit-coverage.txt` | Which record types reached the deposit graph, and which did not. |
| `bundle/emission-spot-checks.txt` | Worked JSON-LD examples: half-cell typing, electrode typing and route, powder anchors, typed protocol method, dataset distribution. |
| `bundle/gold-standard-report.txt` | Captured RO-Crate gold-standard check (see caveats below). |

## Record model (416 records)

```
organization (1)       Topsoe, written to the shared records/organization/ corpus
   ^ manufacturer.id
material-spec (7)      one POWDER per active-material kind: graphite, silicon,
   ^ active_material_   silicon-graphite, LNMO, LFP, NMC111, NMC532
   | spec_id     ^
   |             | material_spec_id
   |          material (1)  the one physical LOT the source evidences: the LNMO
   |                        study powder behind all four LNMO designs
electrode-spec (12)    electrode DESIGNS: active-material kind x source x
   ^ electrode_spec_id  processing route. Composition, design values, route, and
   |                    the batch statistics over the discs that realize it.
   |                    Cited by cell specs via working_electrode_spec_id.
electrode (95)         the DISC inside one cell: this cell's as-built figures,
   ^ working_electrode_ the public label as batch_id, the design as spec
   | id

cell-spec (12)         R2032 coin half-cells, cell_configuration = half_cell,
   |                   one per electrode design. Every one cites its design.
   v cell_spec_id
cell-instance (95)     one per parquet; serial = 6-char id, name + batch_id = public
   |                   label; working_electrode_id -> the disc inside it
   |
   +-- test (95)       cell x protocol; 11 known issues -> conformance annotations
   |     ^ protocol_id
   |     test-protocol (4)   p-OCV, p-OCV hold, GITT, GITT hold
   |
   +-- dataset (95)    about -> cell + test; references the Zenodo parquet by URL,
                       md5 and byte size, plus the derived plot figure
```

Each of the 95 parquet files maps to exactly one `electrode` + `cell-instance` + `test` + `dataset`.

## The material and electrode levels

The model separates what a powder is from what an electrode is, and this dataset is a good test of that separation because it has both kinds of provenance in one deposit.

**Kind** is vocabulary, not a record. The seven active materials resolve to BattINFO's curated `material_kinds` keys (`graphite`, `silicon`, `silicon_graphite`, `lnmo`, `lfp`, `nmc111`, `nmc532`). The kind carries the semantics: it types the electrode node with its EMMO class (`SiliconBasedElectrode`, `LithiumNickelManganeseOxideElectrode`, ...), and on a powder record it anchors to a chemical-substance IRI via `schema:sameAs` with `skos:exactMatch` links to Wikidata / PubChem / Materials Project where verified.

**Material spec is the powder, and there is one for every kind.** v2 and v3 authored a powder record only where the source volunteered something the kind key did not already carry, which meant eleven of the twelve electrode designs cited no material at all. v4 replaces that with a curator-complete policy: seven powders, one per active-material kind, so every design has a material to name and every material has a page.

Curator-complete does not mean filling in the gaps. Each powder states only what the source states, and its description says out loud what the source withholds - a reader should never have to work out whether a blank field means "not measured", "not disclosed" or "nobody looked".

| powder | theoretical capacity | manufacturer | what the record says is missing |
|---|---|---|---|
| LNMO | 140 mAh/g | **Topsoe** | no grade or product id; the manufacturer came from the corpus maintainer, not the source |
| Graphite | 372 mAh/g | - | no supplier, grade, particle size or surface area |
| Silicon | 3579 mAh/g | - | particle size, crystallinity and surface chemistry are "not available from the suppliers" |
| Silicon-graphite | - | - | the source states three (510 / 900 / 1150 mAh/g), one per blend, so the number is a design property and stays on the three electrode specs; the blend ratio is one of the properties the suppliers did not provide |
| LFP, NMC111, NMC532 | - | - | bought as finished electrodes; `metadata.csv` leaves the theoretical-capacity column empty and names no powder supplier or grade |

The theoretical specific capacity is stated once and never twice: on the powder where the source gives one value per kind, on the electrode spec where it gives one per design, nowhere where it gives none.

**Topsoe made the LNMO powder.** This is the one fact in the corpus that comes from outside the source - the Zenodo record names no supplier for any active material - and it is attributed as such on the material spec and in the organization record's editorial note. The organization joins the shared `records/organization/` corpus as `topsoe/`, with a deterministic IRI (`organization/vz1v-rvhz-n77h-344c`) rather than the random one `scripts/sync_battery_knowledge_graph.py` mints, so this build stays re-runnable.

> **Review item.** `records/organization/haldor-topsoe/` already holds a Battery Knowledge Graph stub for the same legal entity under its pre-2022 name (`organization/j50f-3ebx-sssw-svnm`). The two are one company and should be merged before either is published. The new record carries `Haldor Topsoe` in `alternateName` and says so in its editorial note, so the duplicate is findable rather than silent.

**Material is the lot, and exactly one is evidenced.** A material instance is a physical batch of powder that was opened and used. The source evidences one: "The LNMO material used in this study targeted high Mn/Ni disorder" is singular while describing four electrode batches across two processing routes, so one powder batch supplied all four. That is a lot, and it gets a record. No other kind gets one - for the other six the source names no supplier, no batch and no delivery, and for the three purchased electrodes it never saw the powder. A lot record per kind would assert a physical batch nobody wrote down.

The lot carries no `processing` block, because this one batch was coated by *both* routes. The route is a design decision and lives on the electrode spec, where it is also part of the identity seed.

**Electrode spec is the design**: active-material kind, coating composition, design values and the processing route. The route is part of the spec identity, so an aqueous LNMO electrode and an NMP LNMO electrode are two designs built from one powder - the distinction v1 could not express, because it treated the route as a batch property. Twelve designs, nine of them SINTEF's (carrying the registry organization IRI), three purchased.

**Electrode is the disc inside one cell**, 95 of them: the working-electrode disc punched from the batch, weighed, and built into that coin cell. It carries the public label as `batch_id`, the design as `electrode_spec_id`, and the six as-built figures `metadata.csv` publishes for that cell:

| property key | unit | EMMO class | source column |
|---|---|---|---|
| `loading` | mg/cm2 | ActiveMassLoading | Electrode Loading / g cm-2 |
| `dry_thickness` | um | DryCoatingThickness | Dry Thickness / um |
| `areal_capacity` | mAh/cm2 | AreicCapacity | Nominal Areal Capacity / mAh cm-2 |
| `diameter` | mm | Diameter | Electrode Diameter / mm |
| `mass` | mg | Mass | Electrode Coating Mass / g |
| `mass_fraction` | % | MassFraction | Weight percentage of Active Material / % |

`Mass of Active Material / mg` is deliberately not a seventh key. It is the product of the two columns above it - which is why the source publishes it to sixteen digits - and `mass` is the only key in the curated property map that means Mass, so a second mass key would either fall back to a non-canonical term or collapse onto the first one in JSON-LD. Both factors are stated exactly, the product is stated in the disc's notes for a human reader, and no number is lost. The coating mass is expressed in mg rather than the source's g for the same reason the loading is expressed in mg/cm2: it is the scale of the thing, and the validator's plausible range for a mass in grams is a whole-cell one.

An electrode record's IRI is minted from (spec IRI, batch label), a seed built for one record per coating batch. Ninety-five discs from twelve batches need a third part, so the seed's batch slot carries the disc's full context - `<public label>/<6-char cell id>` - while `batch_id` keeps the public label on its own for display and joins. The uid is computed with BattINFO's own `entities.stable_uid` and `electrode_identity_seed`, so nothing is hand-numbered and a re-run lands on the same identifiers.

**Every cell links its disc.** `cell_instance.working_electrode_id` (BIG-MAP/BattINFO#346) points at the electrode record, and emits as a linked node carrying only the working-electrode role class, so the disc's chemistry and design link stay on the disc and merge by `@id`. In v3 the only join was matching batch labels.

In this dataset every design was coated exactly once, so designs and batches run 1:1. Two of them share (kind, source, route) and are still separate designs: SiGr-AQ-2 and SiGr-AQ-3 state different theoretical specific capacities for their active material (1150 vs 900 mAh/g) and different active-material type strings, so they are built from different blends.

### Batch statistics

The batch is no longer a record, so its statistics moved up to the design. Each electrode spec carries `property.loading` (EMMO `ActiveMassLoading`), `property.dry_thickness` (`DryCoatingThickness`) and `property.areal_capacity` (`AreicCapacity`) as the mean over the 7-9 discs that realize it, with `min_value` / `max_value` where the discs differ. `Electrode Loading / g cm-2` is the active-material loading, not the coating loading: for every row it equals the active-material mass divided by the disc area.

**Gap E7 is closed.** BIG-MAP/BattINFO#346 added `standard_deviation` and `sample_count` to a `Quantity`, so the spread that v3 could only write as prose is now on the quantity itself and emits as named `schema:PropertyValue` qualifiers under `schema:valueReference`:

```json
"loading": {
  "value": 9.5173, "unit": "mg/cm2",
  "min_value": 8.9505, "max_value": 9.99,
  "standard_deviation": 0.3213, "sample_count": 8
}
```

which the registry renders as `9.5173 ± 0.3213 mg/cm2 (8.9505 to 9.99, n=8)`.

Where `metadata.csv` repeats one value on every cell row - all twelve dry thicknesses, and the loading and areal capacity of the three purchased electrodes - `standard_deviation` is 0 and the spec's notes say why. Zero is meaningful and the schema says so: it records that every disc carried the same declared number, which is not the same claim as a measured spread of zero.

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

Each test carries only what is genuinely a condition of the test: `ambient_temperature: "room temperature"` and `voltage_reference: "Li/Li+"`.

v3 also carried four as-built electrode figures here - active-material mass, coating mass, areal capacity and loading - because the model had nowhere per-cell to put them (gap G2). It does now. They were true before the test started and would still be true if the test had never run, so they are properties of the disc, one hop away through `working_electrode_id`. Gap G2 is closed.

## Numbers

Every quantity is rounded to a fixed number of decimals per unit, chosen at or above the precision the source's own rounded columns carry (`build_records.py`, `_DECIMALS_BY_UNIT`). Two kinds of noise go with it: the conversion artifacts the script used to create (0.0204 g/cm2 times 1000 read as `20.400000000000002` mg/cm2) and the full-float-precision derived columns `metadata.csv` publishes (an active-material mass of `0.9040957492000021` mg, the product of a 4-digit coating mass and an 8-digit weight percentage). Values with seven or more decimals: 205 in v2, 0 since v3, across records, JSON-LD, the deposit graph and the RO-Crate. No identity seed contains a number, so no identifier moved.

## What is deliberately absent

- **Electrolyte and separator** are not reported in the source record and are not invented.
- **Material lots for six of the seven powders.** Only the LNMO powder is evidenced as a physical batch. The rest have a spec but no lot, because the source describes no delivery, no supplier and no batch for them.
- **`counter_electrode_id` on all 95 cells.** The counter electrodes are lithium metal foil and the source tracks them not at all: no label, no batch, no thickness, nothing that distinguishes the disc in one cell from the disc in the next. Ninety-five electrode records for them would assert ninety-five individually-tracked components nobody recorded. What is known - lithium metal, and that the counter electrode is also the potential reference - is on the cell spec's counter-electrode holder, the right level for a component the study treats as interchangeable.
- **Binder and additive fractions.** Only the active-material weight percentage is published, so the coating composition states that and stops.
- **Current-collector foils.** Copper for the anodes and aluminium for the cathodes would be the obvious guess; the source does not say, so the field is empty.
- **Theoretical specific capacities** for the three commercial electrodes (LFP, NMC111, NMC532) are blank in `metadata.csv` and are omitted - from the powder and from the design alike, rather than substituted with a textbook value.
- **Product identifiers and grades.** No electrode carries a `product_id` or `grade`: the source states none for any of them, and a fabricated part number would look like provenance.
- **Derived OCP profiles** are out of scope for this layer; it describes the published measurements, not products computed from them.

## How to dereference

- **Canonical records** (`records/<type>/<type>-<id>.json`) are plain BattINFO JSON. Every record carries an `id` of the form `https://w3id.org/battinfo/<ns>/<uid>`, and cross-links use those IRIs (`manufacturer.id`, `active_material_spec_id`, `electrode_spec_id`, `working_electrode_spec_id`, `cell_spec_id`, `protocol_id`, dataset `about`).
- **JSON-LD** (`bundle/jsonld/<type>/<...>.jsonld`) carries the full inline `@context`, so every file expands offline. Every record type present is emitted.
- **Datasets** point at the real files: `distributions[].content_url` is the Zenodo download URL, with the md5 checksum and byte size taken from the Zenodo API; `access_url` is the DOI.

## Publishing caveats (see `bundle/gold-standard-report.txt`)

Per-record validation is clean: 416 records, 0 errors, 0 warnings, 0 SHACL non-conformances. The deposit-level RO-Crate gold-standard check reports two classes of issue, unchanged from v1 and neither coming from these records:

1. 95 errors, "Published dataset nodes must define non-empty schema:about references". Every dataset record does carry `about` (its cell and its test) and the per-record JSON-LD emits it as `dcterms:subject`; the deposit graph builder drops it.
2. 95 warnings, "BatteryTest should record prov:generated". The test-to-dataset back-link is not authored, because `ws.save()` rebuilds `test.dataset_ids` from the datasets the workspace engine holds and blanks it for everything else. The forward direction (dataset to cell and test) is complete.

Both are recorded in `READINESS-REPORT.md` as gaps G7 and G1.

A third class, 190 errors reading "Distribution sha256 must be a 64-character hexadecimal digest", was fixed upstream in BIG-MAP/BattINFO#339 and no longer appears. The deposit graph used to publish every checksum under a sha256 predicate whatever the record said; it now states `spdx:checksumAlgorithm_md5` with the Zenodo md5, which is the honest statement and needs no 10 GB download to produce.

A fourth was found in v2 and fixed upstream in BIG-MAP/BattINFO#344: the deposit graph hardcoded two record types, so the whole electrode layer was missing from `deposit.jsonld`. All nine types now reach it - `bundle/deposit-coverage.txt` shows 416 of 416 records in a 418-node graph.

## Reproducing

```bash
pip install "git+https://github.com/BIG-MAP/BattINFO.git" pyshacl
pip install pyarrow numpy     # only for extract_profiles.py
python extract_profiles.py --cache <scratch-dir>   # writes profiles/ (95 plot figures)
python build_records.py      # writes drafts/ and .battinfo/records/ (416 records)
python build_records.py      # again: idempotence check, and it rebuilds the workspace index
python build_bundle.py       # writes records/ and bundle/
python build_supersede_map.py  # writes superseded/supersede-map.json
```

`extract_profiles.py` is the only step that touches the 15.6 GB of parquet on Zenodo, and it is the only one that needs the network. Skipping it is safe: `build_records.py` attaches a profile distribution only for the datasets `profiles/index.json` names, so an empty `profiles/` simply reproduces the records as they were before.

## Plot profiles

A dataset page shows a curve when the record carries a distribution whose filename ends in `.plot.json`; `ws.submit()` promotes any such distribution to the page-model role `plot_data`, and the platform's data explorer renders it with Plotly. The source files here are far too large to plot directly (1.7 MB to 544 MB each, 15.6 GB in total, up to 170 million rows), so `extract_profiles.py` derives a small figure from each one and `profiles/` holds the results: about 80 KB per dataset, 7 MB for the corpus.

Each figure has two panels. The top one is voltage against test time, reduced by peak-preserving min/max decimation: time is split into equal buckets and each bucket keeps the samples where voltage was lowest and highest, at their true timestamps. Striding would step over GITT's pulses entirely, and a 100-million-row file has to lose 99.99% of its samples to fit in a browser, so the reduction has to be one that cannot skip an excursion. The bottom panel is the open-circuit curve against capacity: for GITT the relaxed endpoint of every rest, which is the quantity the technique exists to measure, and for p-OCV the longest single-direction sweep, since a low-current sweep is already near equilibrium and `Cumulative Capacity` restarts on each half cycle.

`profiles/index.json` records each figure's sha256, byte size and the md5 of the source it came from, so a re-run rebuilds only what changed, and `build_records.py` reads it rather than the parquet files.

All 95 profiles are extracted and committed. The records point at `{R2_PUBLIC_BASE}/datasets/{short_id}/{filename}`, the key layout `ws.upload()` uses for every dataset file. `python upload_profiles.py` puts the files there.

**The v4 profiles are not uploaded.** Uploading is a production write and this corpus is staged; until it runs with R2 credentials the URLs 404, which means a dataset page renders its data-explorer panel (the record carries a `plot_data` distribution and the platform detects it) but the figure itself does not load. `python upload_profiles.py --dry-run` lists the 95 objects, 7.1 MB in total, that a republish would send.

Rendered review pages for the staged batch, from a checkout of `battinfo-registry`:

```bash
cd ../battinfo-registry
uv run python scripts/preview_staged_batch.py \
    --records-dir ../battinfo-records/batches/flores-ocv-halfcells/records \
    --out ../battinfo-records/batches/flores-ocv-halfcells/preview
# then open preview/index.html
```

`preview/` is gitignored: the generated HTML is many times the size of the whole repository.

The build is reproducible on BattINFO main at commit `a7661d2` or later (BIG-MAP/BattINFO#346: the cell-to-electrode links and the quantity statistics fields). Re-running against an existing workspace rewrites nothing: every record reports `[unchanged]`, no dataset is written, and no identity is pruned. A rebuild in an empty workspace reproduces all 416 byte for byte apart from `provenance.retrieved_at`, the build timestamp.

Because D1 re-seeded six cell specs and v4 re-seeds the material and electrode layers, a rebuild leaves the identities it replaced behind in the workspace. `build_records.py` prunes them and reports the count, so `records/` and the deposit graph only ever contain records the run actually authored.

The whole corpus can be served locally, from a checkout of `battinfo-registry`:

```bash
cd ../battinfo-registry
uv run python scripts/preview_stack.py \
    --records-dir ../battinfo-records/batches/flores-ocv-halfcells/records --reset
uv run --env-file .preview/.env.preview python scripts/rerender_record_pages.py \
    --apply --persist-display   # reverse edges: the publish path does not compute them
```

## Attaching this layer to a new Zenodo version

The layer is supplementary metadata for [Zenodo 20086298](https://doi.org/10.5281/zenodo.20086298). Publishing it as a new version of that record keeps the concept DOI (10.5281/zenodo.19107294) and leaves the 95 parquet files untouched.

**These steps describe the v1 upload that has already happened.** They are kept as the recipe; the v4 corpus is not uploaded anywhere yet, and the counts below refresh at republish time along with `description-addendum.md`.

Upload two archives, built from this directory:

```bash
cd batches/flores-ocv-halfcells
zip -r battinfo-records.zip records          # v4: 416 files
zip -r battinfo-bundle.zip  bundle           # v4: 422 files
```

| archive | contents |
|---|---|
| `battinfo-records.zip` | `records/` - the canonical BattINFO JSON records. v4: `material-spec` (7), `material` (1), `electrode-spec` (12), `electrode` (95), `cell-spec` (12), `cell-instance` (95), `test-protocol` (4), `test` (95), `dataset` (95). |
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

**Corpus v4 has not been submitted.** All 319 published records are still live and stay live until the republish supersedes them. `superseded/supersede-map.json` is the complete statement of what happens to each: 154 keep their identifier, 147 are replaced by one successor, and 18 are split - the 6 cell specs that covered two designs each, and the 12 v1 "material lots" that were coated electrode batches and become the 7-9 discs cut from each. Eight records supersede nothing at all: the seven powders and the material lot, which describe a level v1 never had. The republish is the only step that touches the registry, and it happens after this branch is reviewed.

Each published record has a permanent `w3id.org` identifier. Three worth citing:

| record | identifier | v4 status |
|---|---|---|
| Silicon R2032 half-cell spec | `https://w3id.org/battinfo/spec/zqwq-ted6-cwb2-0d42` | same IRI, content updated |
| NMC532-NMP-1 electrode batch | `https://w3id.org/battinfo/material/17t8-f8vm-d6hj-gwzd` | retired; split across the 8 discs cut from that batch, with the batch itself surviving as its electrode spec |
| LNMO-NMP-1 GITT dataset | `https://w3id.org/battinfo/dataset/09vb-kh3s-aq3q-4s3e` | replaced: its cell spec was split, see the supersede map |

These content-negotiate: `Accept: application/ld+json` and `Accept: text/turtle` return the record from public storage with no credentials. Requesting HTML redirects to the platform page, which is behind the launch gate until the platform opens, so cite the identifier rather than a platform URL.

One caveat worth knowing when reading the registry copy: the registry serves its own index view of a record (the canonical record body verbatim, plus a flattened `metadata` block it can filter on). It does not re-emit the EMMO semantic document. The `BatteryHalfCell` device typing, the chemical-substance anchors and the typed protocol process graphs live in `bundle/jsonld/` and `bundle/deposit.jsonld`, which is what makes the Zenodo archive, not the registry, the source of truth for the semantics.
