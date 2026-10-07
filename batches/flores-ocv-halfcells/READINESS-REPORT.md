# BattINFO readiness report - authoring the Flores half-cell OCV semantic layer

Findings from authoring 326 linked records (1 material spec, 12 electrode specs, 12 electrode batches, 12 half-cell specs, 95 cell instances, 4 protocols, 95 tests, 95 datasets) for Zenodo 20086298.

This is the fourth pass. Pass one (August 2026) predated the material kind/spec/instance model, `cell_configuration`, `Test.conditions` and protocol JSON-LD emission. Pass two re-authored the layer on the material model and is what is published today. Pass three was the first on the **first-class electrode model** (BIG-MAP/BattINFO#342): 9 material specs and 12 material lots that were really electrode products and coated batches became 12 electrode specs, 12 electrode batches and 1 genuine powder record. Pass four (corpus v3) is the first on the **role-based half-cell model** (BIG-MAP/BattINFO#345, commit `33615d6`) and carries the maintainer's review-round-2 rulings: one cell spec per electrode design, electrodes named by role, quantities rounded, batch statistics computed. The findings below are cumulative; pass three added the E series, and pass four closes most of it and adds E7.

## Result

| | pass 1 | pass 2 (published) | pass 3 | pass 4 (this branch) |
|---|---|---|---|---|
| records | 305 | 319 | 323 | **326** |
| strict-save errors | 0 | 0 | 0 | 0 |
| semantic warnings | 36 | 0 | 3 (one false positive, E5) | **0** |
| SHACL non-conforming | 0 | 0 | 0 | 0 |
| record types reaching JSON-LD | 4 of 6 | 7 of 7 | 8 of 8 | **8 of 8** |
| record types reaching the deposit graph | - | 7 of 7 | 6 of 8 (E2) | **8 of 8** |
| `ws._ws` engine calls | 6 | 0 | 0 | 0 |
| idempotent re-run | yes | yes | yes (byte-identical) | yes (byte-identical) |
| cell specs citing their electrode design | - | - | 6 of 9 | **12 of 12** |
| quantities with float artifacts | - | 205 | 205 | **0** |

Three of the four E-series gaps pass three opened were fixed upstream before this pass: E1 (the inline seam absent from the authoring model) and E2 (the deposit graph dropping the electrode layer) in BIG-MAP/BattINFO#344, E5 (the validator's known-key set drifting from the emitter's tables) in the same PR, at the mechanism rather than the symptom. E3 is closed by the corpus itself: ruling D1 splits the three multi-design cell specs, so no cell spec needs to cite more than one design. E4 and E6 stand, and E7 is new.

## What the electrode model made possible

Worth stating before the gaps, because these are things the previous pass could not express at all:

- **One powder, four electrode designs, two routes.** The LNMO material spec is cited by all four LNMO electrode specs. In v1 the same physical situation was two "material specs" (one per IntelLiGent batch) with the route pushed onto the lots, which said the aqueous and the NMP electrode were the same product built differently. They are not: different binder system, different drying, different performance, and the model now says so by putting the route in the spec identity seed.
- **Purchased electrodes stop pretending to be powders.** The three commercial electrodes carry `kind` and no `active_material_spec_id`, and lose nothing by it. v1 had to mint a "material spec" for a product nobody has powder data for.
- **Chemistry survives the polarity vocabulary gap.** An electrode-spec node is typed from its kind on either side (`SiliconBasedElectrode` + `NegativeElectrode`), so a half cell whose working electrode is an anode material now has its chemistry in the graph even though `positive_electrode_basis` has no term for it. That is most of G8, closed as a side effect.
- **Design values have a home.** Manufacturer-stated loading and areal capacity for the purchased electrodes sit on the design, where they belong, instead of being repeated per cell on 25 test records.

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

## Open gaps: the electrode model (new in pass 3)

### E1. The inline electrode-spec seam is not on the authoring model

The cell-spec JSON Schema gained `positive_electrode.electrode_spec_id` in #342, the JSON-LD emitter reads it and emits `schema:isVariantOf`, and the registry vendored it (battinfo-registry#45). The pydantic `Electrode` holder in `bundle.py` did not gain the field, and it is `extra="forbid"`, so the blessed authoring path cannot write it.

Repro:

```python
cs = ws.load("draft.cell-spec.json")
cs.positive_electrode = electrode(bom=bom(active_material=material("Silicon")))
cs.positive_electrode.electrode_spec_id = "https://w3id.org/battinfo/spec/rkf4-xz0y-h8kz-rmxz"
# ValueError: "Electrode" object has no field "electrode_spec_id"
```

This build therefore uses the other seam, the top-level `positive_electrode_spec_id`, which *is* on the model and which merges the electrode spec's `@id` onto the emitted electrode node. For a cell spec citing an electrode design that is arguably the better statement anyway. But the two seams are advertised as equal alternatives and only one is authorable, so a user who follows the electrodes-model doc hits a wall.

Fix shape: add `electrode_spec_id: str | None` to `bundle.Electrode` next to the `material_spec_id` that `MaterialComponent` already carries, and round-trip it in `to_record`/`from_record`.

### E2. The deposit graph drops the whole electrode layer

**Fixed upstream in BIG-MAP/BattINFO#344**, at the mechanism: the node loop is now driven by the record-type registry with a coverage guard, not by a hardcoded pair. Corpus v3 reaches 8 of 8 types and 326 of 326 records in a 328-node graph. Kept for the trail.

`_assemble_zenodo_jsonld` promotes standalone records to first-class deposit nodes for `material-spec` and `material` only. `electrode-spec` and `electrode` are read off disk by `_read_record_sets` (they are in `record_set_dirs()`), then never used. All 24 electrode records are absent from `bundle/deposit.jsonld`: 301 nodes for 323 records.

Repro: `bundle/deposit-coverage.txt` in this branch, or grep any electrode IRI in `bundle/deposit.jsonld`.

This is the same shape as the submit gap #342 closed, in the other publication path: a record that saves, validates and emits cleanly still fails to reach the artifact a reader gets. It matters more here than for materials, because the electrode specs are where the processing route, the composition and the design values live.

Fix shape: extend the material-node loop to `("material-spec", "material", "electrode-spec", "electrode")`; the emitter already produces the right node for both.

### E3. A cell spec can cite only one electrode design

**Closed by ruling D1**: the three multi-design specs are split into six, so all twelve cell specs cite exactly one design and the single-valued field is right for every one of them. The cost was 144 re-seeded published identifiers, mapped in `superseded/supersede-map.json`. Kept because the shape of the finding still holds for any corpus whose cell-spec grouping predates its electrode model.

`positive_electrode_spec_id` is single-valued, which is right for a cell spec that describes one design. Three of the nine published cell specs here cover two designs each (LNMO aqueous + NMP for two IntelLiGent batches; two Si/Gr blends coated in the same batch series), because the cell-spec grouping predates the electrode model.

The corpus names the designs in `specification_comment` rather than picking one, and the batches carry the labels, so nothing is lost - but the structural link is absent for a third of the specs. Splitting the three into six would fix it and re-mint 47 cells, 47 tests and 47 datasets, so it is left as a review decision (REVIEW-TABLE-V2.md, D1).

Fix shape: nothing needed in the model if the corpus splits. If multi-design cell specs are considered legitimate, the field would need to accept a list, which is a bigger change than it looks - the emitter merges the referenced `@id` onto one electrode node.

### E4. A cell instance cannot reference the electrode batch it was built from

The electrodes-model doc says this outright ("Cell instances do not yet reference electrode batches; there is no natural slot on `cell_instance` today"), and this dataset is a clean example of the cost. Every one of the 95 cells was built from exactly one of the 12 batches, and the corpus knows which: the public label is on both records. But the join is a string match on `batch_id`, not a reference, so a consumer cannot follow cell -> electrode -> design -> powder without knowing the labelling convention.

Fix shape: an `electrode_ids` (or `positive_electrode_id` / `negative_electrode_id`) reference on the cell instance, resolved like `cell_spec_id`. It would also give the cell-level answer to E3: even where the spec cannot say which design, the instance could.

### E5. The semantic validator warns about electrode design values the emitter maps

**Fixed upstream in BIG-MAP/BattINFO#344**, at the mechanism: the validator's known-key set is derived from `COMPONENT_PROPERTY_TERM_TABLES`, the transform's own registry of holder term tables, so it cannot drift again. Corpus v3 reports 0 warnings. Kept for the trail.

`areal_capacity` on an electrode spec emits the curated EMMO class `AreicCapacity` - it is in `_ELECTRODE_PROPERTY_TERMS`, added by #342, and the electrodes-model doc advertises it. The validator's known-key set is built by `_component_property_terms()`, which unions `_FRACTION_PROPERTY_TERMS`, `_DESCRIPTOR_PROPERTY_TERMS` and `_DESCRIPTOR_COATING_PROPERTY_TERMS` and was not extended to the electrode table. So a correct record warns:

```
semantic.property_unmapped  electrode_spec.property.areal_capacity
'areal_capacity' is schema-valid but has no curated EMMO mapping ...
```

The three purchased-electrode specs in this corpus each carry a manufacturer-stated areal capacity, so the corpus reports 3 warnings for 0 defects. The same applies to `nominal_areal_capacity` and `reversible_areal_capacity`.

The irony is that the helper's docstring states the invariant it breaks: "Imported from the transform itself ... so this set can never drift from what the JSON-LD emitters actually accept." It drifted.

Fix shape: add `_ELECTRODE_PROPERTY_TERMS` to the import and the union in `_component_property_terms()`. One line, and a test asserting the set equals the emitter's tables would keep it honest.

### E7. No structured home for a dispersion statistic

Ruling EES-1 asks each electrode batch to carry the mean *and* the standard deviation of its cells' active-mass loading and dry thickness. The mean has a home: `property.loading` maps to `ActiveMassLoading`, `property.dry_thickness` to `DryCoatingThickness`, and the observed spread fits `min_value` / `max_value` on the same quantity. The standard deviation has none.

- `Quantity` has `value`, `min_value`, `max_value`, `typical_value`, `value_text`, `unit`, `co_type` and `conditions`. Nothing means "standard deviation", and `conditions` is `hasMeasurementParameter` - a spread is not a measurement condition.
- The open property block would take a `loading_standard_deviation` key, but the curated property map has no EMMO class for it, so `semantic.property_unmapped` fires and the JSON-LD emits it under a non-canonical fallback term. Two keys that both mapped to `ActiveMassLoading` would instead trip `semantic.property_alias_collision`.

So the corpus states the standard deviation, the sample count and the observed range in the batch record's `notes`, in words, and the property block carries only what maps. That is honest but not machine-actionable, which is exactly the wrong way round for a QC number.

Fix shape: the value pattern this needs is `{value, standard_deviation, sample_count}` on `Quantity`, with `hasStandardDeviation` / `hasSampleSize` (or a `StatisticalDistribution` node) in the emission. It is worth doing generally rather than for loading alone - every "we made eight cells and measured them" number in a lab has the same shape, and the EES metadata template asks for avg +/- std as a matter of course.

### E6. Batch nodes are typed generically

An `electrode` record emits `@type: "Electrode"` because "an instance carries no chemistry of its own; its type comes from the spec it realizes, which is not resolvable here". True for a single-record emitter, but the deposit graph *does* have both records in hand, so a reader of the bundle sees twelve untyped electrode nodes next to twelve richly typed designs. Low impact while E2 stands (the batches are not in the graph at all); worth revisiting when it is fixed.

## Open gaps: carried forward

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

### G5. `ws.export()` covers five of the nine record types (wider in pass 3)

`record_to_jsonld` handles material specs, material lots, electrode specs and electrodes, but `ws.export()`'s internal `_TYPE_MAP` still lists only cell-spec, cell-instance, test, test-protocol and dataset, so an exported bundle silently omits both the material and the electrode layer. `build_bundle.py` emits every type itself to work around this.

Repro: `ws.export("json-ld", output_dir=...)` on this workspace; no `material-spec/`, `electrode-spec/` or `electrode/` directory appears.

### G6. The deposit graph relabels md5 checksums as sha256

**Closed upstream by BIG-MAP/BattINFO#339.** Every checksum node in the regenerated bundle now states `spdx:checksumAlgorithm_md5` with the md5 digest, and `schema:sha256` is gone. The gold-standard report drops from 285 errors to 95: the 190 false sha256 findings disappear and only G7 remains. The finding below is the state that prompted the fix.

This is the sharpened version of the first pass's H3. The issue is not only that the gold standard wants sha256 while Zenodo gives md5. The deposit graph builder emits every distribution checksum under `spdx:checksumAlgorithm_sha256` and `schema:sha256` regardless of the algorithm on the record, so the authentic 32-character md5 is published as a sha256 value - a wrong statement, not just a missing one - and then trips 190 "must be a 64-character hexadecimal digest" errors.

Repro: `bundle/deposit.jsonld`, any dataset node: `"spdx:checksumAlgorithm": {"@id": "spdx:checksumAlgorithm_md5"}` is what the canonical record supports, but the graph shows `..._sha256` with the md5 digest `7e779f63372291ad56b2e01de6639cc7`.

Fix shape: carry the record's algorithm through to the SPDX term, and let the gold standard accept any SPDX-listed algorithm rather than requiring sha256.

### G7. The deposit graph drops dataset `about`

Every dataset record carries `about` (its cell and its test) and the per-record JSON-LD emits it as `dcterms:subject`. The deposit graph builder does not carry it over, and the gold standard then fails all 95 datasets with "Published dataset nodes must define non-empty schema:about references". The checker and the builder disagree about a field the records already populate.

Repro: `bundle/gold-standard-report.txt` (95 errors) against any `records/dataset/*.json`, which has a two-element `about`.

### G8. No positive-electrode term for a working electrode made of an anode material

**Mostly closed by #342, for a reason worth noting.** `positive_electrode_basis` still curates only cathode materials (lfp, nmc, nca, lco, mno2, lmfp, lmo, nmc811, nmca), so four of the nine cell specs still omit the field. But the electrode emitter does exactly what the fix shape below proposed: `_electrode_kind_node_type` looks a kind up on the side its polarity implies and *then on the other side*, so `silicon` reaches `SiliconBasedElectrode` and LNMO reaches `LithiumNickelManganeseOxideElectrode` regardless of polarity. Those classes now reach the graph through the cited electrode spec, so the chemistry of an anode-material working electrode is no longer missing from the semantic view - only from the coarse cell-spec descriptor.

The original finding: in a lithium half-cell the working electrode is always the positive one, whatever the material, so graphite, silicon and silicon-graphite half-cells have no term available even though all three exist under `negative_electrode_basis`. LNMO had no term at either polarity.

Fix shape (remaining): allow the electrode classes at either polarity in the `*_electrode_basis` map too, the way the electrode emitter already does, or add an explicit working-electrode basis for half-cell configurations.

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

### G11. `ws.submit()` was blind to the equipment family (and materials)

**Materials and electrodes closed by BIG-MAP/BattINFO#342; equipment still open.** Found 2026-08-11 while publishing the first equipment records (SkyRC MC3000 bench units). `ws.submit()` swept a hardcoded subdir tuple `("cell-spec", "cell-instance", "test-protocol", "test", "dataset")`, so equipment-spec, equipment, channel, material-spec and material records saved in a workspace were never submitted, silently. #342 replaced the tuple with a nine-entry `_SUBDIRS` covering material-spec, material, electrode-spec and electrode, and gave the two electrode types their `related_resources` wiring (`electrode -> electrode_spec_id`). The equipment family is still absent from both the sweep and the `only=` alias table.

This corpus does not exercise the fix: it stages records for review and submits nothing.

Repro (still valid): fresh workspace, `ws.add("equipment", spec=..., serial_number=...)`, `ws.save()`, `ws.publish()` -> "Saved 0 record(s)", empty outcome list, nothing submitted.

Fix shape: extend the sweep and the `only=` aliases to the equipment types too, and include add-time-written records in the session set. While there, derive `related_resources` for equipment the way electrodes now get it.

## Worked well

- The powder / design / batch split matched this dataset better than the material model it replaces. One powder statement in the source, twelve electrode designs, twelve coated batches; nothing had to be bent, and the one thing v1 had to bend - the route being an instance property - is exactly what #342 moved.
- `ws.add("electrode_spec", ...)` and `ws.add("electrode", ...)` behave like every other adder: same `spec=` resolution, same attribution stamp, same content-derived IRIs, same `[unchanged]` on a re-run. The pair needed no special handling in the build script.
- Derived polarity is the right default. Nine of the twelve designs would have been mislabelled if polarity had been authored from the cell's point of view, and the validator catches exactly that mistake.
- Composition shorthand accepts a quantity, not just a bare number, so `{"active": {"fraction": {"value": 84.97, "unit": "%"}}}` keeps the source's own units and emits a real EMMO percent unit instead of a dimensionless 1.
- `cell_configuration = "half_cell"` did in one field what the first pass could only do in prose, and did it without a warning.
- The PyBaMM-style and structured method paths both produce a real EMMO process graph. Five cycles of typed charge, discharge, rest and voltage-hold steps with control and termination parameters is a far better protocol description than the first pass could emit at all.
- Material kinds carry verified external anchors, with no authoring effort.
- Content-derived IRIs across all eight types make the re-run genuinely byte-identical, checked by hashing the whole record tree before and after. Because the cell-spec identity seed did not change, 289 of the 319 published records came back byte-for-byte on a model change that rewrote the entire material layer.
- The identity seed is exactly the right size. Splitting three cell specs (D1) moved precisely the identifiers that had to move - the seed is (manufacturer, model, format, chemistry, size_code), so qualifying only the ambiguous `model` strings held 6 of 9 cell-spec IRIs and, with them, 154 of the 319 published identifiers. A seed that included a quantity would have re-minted the whole corpus on the rounding change; a seed that excluded `model` could not have expressed the split at all.
- `ws.project("101069765")` enrichment, `ws.contributor` and `ws.license` reach every record type including electrodes.
- The conformance model with typed deviation categories fits the 11 known issues cleanly.

## Should block or annotate the next release

BIG-MAP/BattINFO#339 closed G6 (md5 published as sha256), G9 (cells collapsing on their label) and G3 (dataset and material fields dropped from emission) before pass 2 was published. #342 closed most of G8 as a side effect of typing electrode nodes from either polarity. #344 closed E1, E2 and E5. #345 replaced the half-cell polarity convention with roles, which retires the remainder of G8 for this corpus: a half cell no longer needs a positive-electrode term for a working electrode made of an anode material, because it no longer names a positive electrode at all.

What is left, in priority order:

- **Fix before wide use:** G1, the missing entry point for a dataset that describes an already-published remote file, together with the `dataset_ids` blanking it causes. It is the one gap that still forces this corpus off the blessed authoring surface.
- **Model questions, not bugs:** E4 (how a cell instance reaches the electrode batch it was built from - the difference between a corpus that joins and one that string-matches) and E7 (a value pattern for mean / standard deviation / n). E7 is the one a reviewer will meet first, because every batch statistic in the corpus lands in prose.
- **One-line fix worth doing now:** G5 (`ws.export` type map).
- **Annotate:** G2 and G7 (both lose information the canonical records hold), G4, G10, E6.

One process finding, not a code one. Ruling D2 needed a matching change in the review tooling: `scripts/preview_staged_batch.py` in `battinfo-registry` read only the polarity holders when synthesizing a cell spec's electrode edge, so the moment the corpus started naming its electrodes by role, every cell page lost its link to the electrode layer and the powder became unreachable - the exact defect the preview tool had been built to detect. A model change that renames a field has to be swept through the surfaces that read it, and a grep for the old field name across the sibling repositories is the cheapest version of that sweep.
