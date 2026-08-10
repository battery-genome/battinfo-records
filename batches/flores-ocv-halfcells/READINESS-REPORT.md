# BattINFO readiness report - authoring the Flores half-cell OCV semantic layer

Findings from authoring 319 linked records (9 material specs, 12 material lots, 9 half-cell specs, 95 cell instances, 4 protocols, 95 tests, 95 datasets) for Zenodo 20086298.

This is the second pass. The first pass (August 2026) ran against BattINFO 0.7.0 before the material kind/spec/instance model, `cell_configuration`, `Test.conditions`, protocol JSON-LD emission and the completed EMMO stack landed. This version re-authors the whole layer on current `main` (BattINFO 0.7.0 at commit of PR #338, EMMO domain-battery 0.20.2 / electrochemistry 0.37.2 / chemical-substance 0.15.0). The delta section below records which of the original findings the model closed.

## Result

| | first pass | now |
|---|---|---|
| records | 305 | 319 |
| strict-save errors | 0 | 0 |
| semantic warnings | 36 | **0** |
| SHACL non-conforming | 0 | 0 |
| record types reaching JSON-LD | 4 of 6 | **7 of 7** |
| `ws._ws` engine calls | 6 | **0** |
| idempotent re-run | yes | yes (byte-identical) |

## Delta: what the model closed

**H1 (material specs mint a random id, not idempotent) - CLOSED.** `ws.add("material_spec", ...)` derives the IRI from (manufacturer, product, grade). Re-adding the same product is a no-op. The pinned-id workaround is gone.

**H2 (material specs are second-class: no save, no attribution) - CLOSED.** Materials are saved by `ws.save()` alongside every other type and receive the same funding / contributor / license stamp; both material schemas now carry `funding`, `contributor` and `license` at the envelope. The save panel reports them.

**M1 (model accepts values the save-time schema rejects) - NOT RETESTED.** This pass authors step modes through the draft loader rather than constructing `testmethod.Step` objects directly, so the divergence was never exercised. The conformance status still has to be the hyphenated `non-conformant`.

**M2 (assigning a string to a list field explodes it into characters) - NOT RETESTED.** All list-valued fields are assigned lists in this pass.

**M3 (no typed home for per-instance electrode figures) - PARTIALLY CLOSED.** `Test.conditions` now exists on the `Test` model and is an open snake_case map that accepts any value type, so the per-cell figures have a structured home and the free-text comment block is gone. The cell instance itself is still without one; see G2.

**M4 (`conditions` cannot express a non-numeric condition) - CLOSED at the test level.** `Test.conditions` takes `"room temperature"` as a plain string and emits it as a `schema:PropertyValue`. Test-*protocol* conditions are still numeric-only, which is why the ambient statement lives on the run rather than the protocol.

**M5 (JSON-LD export omits protocols and material specs) - CLOSED for `record_to_jsonld`.** All seven record types emit. Protocols emit a typed EMMO method (`PseudoOpenCircuitVoltageMethod`, `GalvanostaticIntermittentTitrationTechnique`) over an `IterativeWorkflow` of typed steps. `dry_thickness` no longer warns because `thickness` is the curated key. `ws.export()` still covers only five types; see G5.

**M6 (blessed API cannot author a realistic dataset) - MOSTLY CLOSED.** Material specs, material lots, rich half-cell electrodes and conformance are all authorable through `ws.add` / `ws.load`. Remote-URL datasets are the one survivor; see G1.

**L1 (save return dict disagrees with the panel) - CLOSED.** An unchanged re-save reports `unchanged` in both.

**L2 (half-cell chemistry and electrode bases always warn) - CLOSED.** `cell_configuration = "half_cell"` is the structural statement, so `chemistry` can take the controlled `li-metal` and `negative_electrode_basis` the controlled `lithium-metal`. All 36 warnings are gone. What remains is a vocabulary gap rather than a modelling one; see G8.

**L3 (`duplicate_policy` only accepts error/return_existing) - MOOT.** Materials go through `ws.save()`, which upserts.

**L4 (deprecation warnings during authoring) - NOT OBSERVED.** The script imports only current names.

**H3 (deposit gold standard requires sha256, Zenodo gives md5) - CLOSED after this pass.** The second pass found it was worse than first characterised: the graph builder relabelled the md5 as a sha256 rather than merely lacking one. BIG-MAP/BattINFO#339 fixed it. See G6.

## Open gaps

Ranked by impact. Each has an exact repro.

### G1. No blessed way to author a dataset for an already-published remote file

`ws.add("test", ..., data=...)` takes local paths only (`_as_data_paths` turns whatever it gets into a `Path`, and a non-existent path is recorded as a relative artifact path). It exposes no dataset-level metadata: no checksum, byte size, distribution, `variable_measured`, `citations`, `measurement_techniques`, `published_at`, description or keywords. There is no `ws.add("dataset", ...)`, and `ws.load()` has no dataset-draft branch. `ws.import_()` reads a `battinfo.json` document, not a repository record.

This build therefore writes its 95 datasets from the public `battinfo.Dataset` model through the public `battinfo.save_dataset`, re-applying the workspace stamp (rebuilt from the public `ws.project()` / `ws.contributor()` / `ws.license()` getters, which return exactly the blocks `ws.save()` stamps). No engine handle is touched, but the datasets are outside the workspace, with three consequences:

- `ws.save()` does not report them, so their counts come from the save results of `save_dataset`.
- `ws.submit()` skips them unless called with `submit_all=True`, because it filters on the paths of the last `ws.save()`.
- The test-to-dataset back-link cannot be authored at all. `Workspace.save` (`_workspace.py:1813-1825`) rebuilds `test.dataset_ids` from the datasets the *engine* holds and unconditionally blanks the field for every test whose dataset it does not know. Writing the link with `battinfo.save_test` after the fact works, but the next `ws.save()` erases it again, so a re-run rewrites 190 files instead of none. The link is left unauthored rather than fought; this is why the deposit check reports 95 `prov:generated` warnings.

Repro: `ws.add("test", cell=c, data="https://zenodo.org/api/records/20086298/files/x.parquet/content")` records the URL as a local relative path. Then set `test.dataset_ids = [...]`, call `ws.save()`, and read the record back: the field is empty.

Fix shape: a `ws.add("dataset", ...)` that accepts a remote URL with checksum, size and media type, or a `.dataset.json` draft branch in `ws.load()`. Either would also make `dataset_ids` derivable, closing the PROV gap.

### G2. Cell instances have no home for as-built figures

`cell_instance.measured` is still a closed 67-key cell-performance vocabulary (`SpecSet`: capacity, voltage, resistance, dimensions, temperatures) with no slot for active-material mass, coating mass, areal capacity or electrode loading. The `mass` key means cell mass, so it cannot be borrowed. Nothing else on the cell-instance envelope is an open property map.

The per-cell figures therefore go in `Test.conditions`, which is defensible (they are the parameters that normalise that measurement) but is not where they belong: they describe the cell as built, not the conditions the test ran under. They also do not get EMMO property typing there - `conditions` always emits as named `schema:PropertyValue` nodes, so `single_side_loading` in `conditions` is plain text where the same key on a material lot emits `MassLoading`.

Repro: put `active_material_mass` in `cell_instance.measured` and validate: `schema.additionalProperties`. Put it in `Test.conditions` and emit: `{"@type": "schema:PropertyValue", "schema:name": "active_material_mass", ...}`.

Fix shape: an open `as_built` (or `property`) quantity map on the cell instance, validated and emitted the same way the material-lot `property` block already is.

### G3. JSON-LD emission drops fields the canonical record carries

**Closed upstream by BIG-MAP/BattINFO#339.** The bundle in this branch is emitted after that fix: dataset documents now carry description, keywords, `variable_measured`, citations, measurement techniques, publication date and the distribution's name and content size, and material documents carry the processing block, `lot_id` and notes. The finding below is the state that prompted the fix.

`record_to_jsonld` is lossy for two record types:

- **dataset**: `description`, `keywords`, `variable_measured`, `citations`, `measurement_techniques`, `published_at` and the distribution's `content_size` and `name` are all absent from the emitted document. Only title, license, access URL, created/modified, subject and a bare distribution survive.
- **material**: the whole `processing` block (route, solvent, detail) is dropped, along with `lot_id` and envelope `notes`. Processing is the main reason material instances exist as a level, so losing it in the semantic view is a sharp edge.

Repro: `record_to_jsonld(dataset_record, "dataset")` and search for the description string; `record_to_jsonld(material_record, "material")` and search for `"aqueous"`. Both miss.

### G4. No spelling of micrometre both validates and resolves

The schema's unit check for `thickness` accepts `cm, m, mm, um, μm` (that last one U+03BC GREEK SMALL LETTER MU). The unit-to-IRI map keys micrometre as `µm` (U+00B5 MICRO SIGN) and knows neither `um` nor `μm`. So `µm` fails validation, and the two spellings that pass validation fall back to `schema:unitText` instead of `emmo:MicroMetre`. This build uses ASCII `um` and accepts the untyped unit.

Repro: save a material with `{"thickness": {"value": 44, "unit": "µm"}}` -> `unit 'µm' is not compatible with spec 'thickness' (valid: cm, m, mm, um, μm)`. Save with `μm` -> passes, emits `"schema:unitText": "μm"`.

Fix shape: normalise the micro sign and the Greek mu to one key on both sides, and add `um` as an ASCII alias.

### G5. `ws.export()` covers five of the seven record types

`record_to_jsonld` handles material specs and material lots, but `ws.export()`'s internal `_TYPE_MAP` lists only cell-spec, cell-instance, test, test-protocol and dataset, so an exported bundle silently omits the material layer. `build_bundle.py` emits all seven itself to work around this.

Repro: `ws.export("json-ld", output_dir=...)` on a workspace with materials; no `material/` or `material-spec/` directory appears.

### G6. The deposit graph relabels md5 checksums as sha256

**Closed upstream by BIG-MAP/BattINFO#339.** Every checksum node in the regenerated bundle now states `spdx:checksumAlgorithm_md5` with the md5 digest, and `schema:sha256` is gone. The gold-standard report drops from 285 errors to 95: the 190 false sha256 findings disappear and only G7 remains. The finding below is the state that prompted the fix.

This is the sharpened version of the first pass's H3. The issue is not only that the gold standard wants sha256 while Zenodo gives md5. The deposit graph builder emits every distribution checksum under `spdx:checksumAlgorithm_sha256` and `schema:sha256` regardless of the algorithm on the record, so the authentic 32-character md5 is published as a sha256 value - a wrong statement, not just a missing one - and then trips 190 "must be a 64-character hexadecimal digest" errors.

Repro: `bundle/deposit.jsonld`, any dataset node: `"spdx:checksumAlgorithm": {"@id": "spdx:checksumAlgorithm_md5"}` is what the canonical record supports, but the graph shows `..._sha256` with the md5 digest `7e779f63372291ad56b2e01de6639cc7`.

Fix shape: carry the record's algorithm through to the SPDX term, and let the gold standard accept any SPDX-listed algorithm rather than requiring sha256.

### G7. The deposit graph drops dataset `about`

Every dataset record carries `about` (its cell and its test) and the per-record JSON-LD emits it as `dcterms:subject`. The deposit graph builder does not carry it over, and the gold standard then fails all 95 datasets with "Published dataset nodes must define non-empty schema:about references". The checker and the builder disagree about a field the records already populate.

Repro: `bundle/gold-standard-report.txt` (95 errors) against any `records/dataset/*.json`, which has a two-element `about`.

### G8. No positive-electrode term for a working electrode made of an anode material

`positive_electrode_basis` curates only cathode materials (lfp, nmc, nca, lco, mno2, lmfp, lmo, nmc811, nmca). In a lithium half-cell the working electrode is always the positive one, whatever the material, so graphite, silicon and silicon-graphite half-cells have no term available even though all three exist under `negative_electrode_basis`. LNMO has no term at either polarity. Four of the nine specs therefore omit the field.

This is a vocabulary gap, not a data loss - the electrode's bill of materials links to the material spec and thence to the kind's EMMO class - but the coarse descriptor that drives device typing is unavailable for half-cells of anode materials.

Fix shape: allow the electrode classes at either polarity (the class names are material statements, not polarity statements), or add an explicit working-electrode basis for half-cell configurations. Adding an LNMO electrode class would close the fourth case.

### G9. `ws.add("cell", ...)` de-duplicates on the display label

**Closed upstream by BIG-MAP/BattINFO#339.** The serial is now the identity and the name is display text, so a batch of 95 cells sharing 12 labels stays 95 cells. A repeated serial raises instead of silently dropping a record, and a label that names several cells refuses to resolve. This script already passed serials only, so its output is unaffected. The finding below is the state that prompted the fix.

The cell adder keys its in-session index on `name or serial_number` and skips any cell whose label is already present. With 95 cells sharing 12 public labels, passing `names=` and `serial_numbers=` together silently produced one cell per label instead of 95. The workaround is to pass only `serial_numbers=` (unique) and set `.name` on the returned objects afterwards.

Repro: `ws.add("cell", spec=cs, names=["A", "A"], serial_numbers=["x1", "x2"])` returns one cell, with `WARNING: 1 already in workspace`.

Fix shape: de-duplicate on the serial when one is supplied, and treat the name as a label. The current behaviour is right for the single-label case and wrong for every batch that reuses a label.

### G10. Small API asymmetries

- Contributor affiliations are plain name strings. `ws.contributor(orcid, name=, affiliation=)` writes `affiliation: {"type": "Organization", "name": "..."}` with no slot for an organization IRI, so a contributor cannot be tied to the registry organization they belong to. SINTEF's IRI reaches these records through `cell_spec.manufacturer_id` and the material-spec manufacturer block; IREC's has no attachment point at all, because its two authors appear only as contributors. The bundle-level creator path does accept `affiliation_ror`, so the two layers disagree about how much an affiliation can say.
- `ws.add("material_spec", ...)` takes `description=`; `ws.add("material", ...)` rejects it and wants `notes=[...]`.
- `ws.project()`, `ws.contributor()` and `ws.license()` print their state on every call, including the no-argument getter form, so reading the current value inside a script emits a banner.
- The test-protocol record's envelope key is `test_spec` although the record lives in `test-protocol/` and its `identifier` reads `test-protocol:...`.

## Worked well

- The kind / spec / instance split matched this dataset exactly: seven kinds of vocabulary, nine electrode products, twelve physical batches. Nothing had to be bent to fit, and the schema's own note that "aqueous vs NMP is not a distinct product" is precisely the distinction the data makes.
- `cell_configuration = "half_cell"` did in one field what the previous pass could only do in prose, and did it without a warning.
- The PyBaMM-style and structured method paths both produce a real EMMO process graph. Five cycles of typed charge, discharge, rest and voltage-hold steps with control and termination parameters is a far better protocol description than the previous pass could emit at all.
- Material kinds carry verified external anchors. Silicon emits `skos:exactMatch` to Wikidata and Materials Project alongside the chemical-substance IRI, with no authoring effort.
- Content-derived IRIs across all seven types make the re-run genuinely byte-identical, checked by hashing the whole record tree before and after.
- `ws.project("101069765")` enrichment, `ws.contributor` and `ws.license` reach every record type including materials.
- The conformance model with typed deviation categories fits the 11 known issues cleanly.

## Should block or annotate the next release

Three of the findings were fixed upstream before this layer was published. BIG-MAP/BattINFO#339 closed G6 (md5 published as sha256), G9 (cells collapsing on their label) and G3 (dataset and material fields dropped from emission). The bundle in this branch was regenerated on that commit; the 319 canonical records came out byte-identical, so only the emitted documents changed.

What is left:

- **Fix before wide use:** G1, the missing entry point for a dataset that describes an already-published remote file, together with the `dataset_ids` blanking it causes.
- **Annotate:** G2 and G7 (both lose information the canonical records hold), G4, G5, G8, G10.
