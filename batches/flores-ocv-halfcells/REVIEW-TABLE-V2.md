# Corpus v2 review table - Flores half-cell OCV semantic layer

Corpus v2 re-authors this layer on the first-class electrode model (BIG-MAP/BattINFO#342, commit `63da080b`), under the ratified principle: **the material spec describes the powder, the electrode spec describes the electrode**.

**Nothing here is published.** All 323 records are staged in this branch only. The 319 published records and their live `w3id.org` identifiers are untouched; the republish is a separate, review-gated step. Every link below is a repository path, not a resolvable IRI.

## What changed at a glance

| record type | v1 | v2 | note |
|---|---|---|---|
| material-spec | 9 | **1** | v1's nine were electrode products wearing a powder's clothes. v2 authors the one powder the source actually identifies. |
| material | 12 | **0** | v1's twelve "lots" were coated electrode batches. They are now `electrode` records. |
| electrode-spec | - | **12** | new: one per electrode design (kind x source x processing route). |
| electrode | - | **12** | new: the twelve published electrode batches, one per public label. |
| cell-spec | 9 | 9 | same nine IRIs, updated content: electrode reference added, retired material link removed. |
| cell-instance | 95 | 95 | byte-identical. |
| test-protocol | 4 | 4 | byte-identical. |
| test | 95 | 95 | byte-identical. |
| dataset | 95 | 95 | byte-identical. |
| **total** | **319** | **323** | 289 records byte-identical, 9 changed, 25 new, 21 retired. |

Identifier stability was a design constraint, not a coincidence: the cell-spec identity seed is (manufacturer, model, format, chemistry, size_code) and all five are unchanged, so the nine cell-spec IRIs hold, and with them every cell, test and dataset IRI derived from them.

## Chain 1 - the LNMO-AQ-1 thread (the only chain with all nine links)

This is the aqueous chain that exercises every record type, including the powder. Read it top to bottom: organization, powder, electrode design, coated batch, cell design, physical cell, protocol, test run, published file.

| # | record type | title | staged record | bundle JSON-LD | what to check |
|---|---|---|---|---|---|
| 1 | organization | SINTEF | [`records/organization/sintef/record.json`](../../records/organization/sintef/record.json) (repo root, unchanged) | - | - Cited by `cell_spec.manufacturer.id` and by the manufacturer block of all nine SINTEF electrode specs.<br>- IRI `https://w3id.org/battinfo/organization/b4qq-aawd-zesa-kh4q`, already live in the registry.<br>- IREC still has no attachment point: its two people appear only as contributors, and contributor affiliations take a plain name (gap G10). |
| 2 | material-spec | LNMO (LiNi0.5Mn1.5O4), high Mn/Ni disorder spinel | [`records/material-spec/material-spec-epzg-hf4v-k5bk-nqxe.json`](records/material-spec/material-spec-epzg-hf4v-k5bk-nqxe.json) | [`bundle/jsonld/material-spec/…epzg-hf4v-k5bk-nqxe.jsonld`](bundle/jsonld/material-spec/material-spec-epzg-hf4v-k5bk-nqxe.jsonld) | - **Is this the right call?** It is the only powder record in the corpus. Evidence: "The LNMO material used in this study targeted high Mn/Ni disorder, therefore the OCVs is a highly disordered spinel", quoted verbatim in `notes`.<br>- No manufacturer, supplier, grade or product id: the source names none, and none is invented.<br>- Theoretical capacity (140 mAh/g) lives here because a powder record exists to hold it; the four LNMO electrode specs do not restate it. |
| 3 | electrode-spec | LNMO electrode, aqueous processed (IntelLiGent batch 1, SINTEF) | [`records/electrode-spec/electrode-spec-tcqb-q91a-gg35-n0sk.json`](records/electrode-spec/electrode-spec-tcqb-q91a-gg35-n0sk.json) | [`bundle/jsonld/electrode-spec/…tcqb-q91a-gg35-n0sk.jsonld`](bundle/jsonld/electrode-spec/electrode-spec-tcqb-q91a-gg35-n0sk.jsonld) | - `active_material_spec_id` points at row 2; the JSON-LD carries it as `hasActiveMaterial`.<br>- `@type` is `["LithiumNickelManganeseOxideElectrode", "PositiveElectrode"]` - chemistry class plus derived polarity; polarity is never authored.<br>- The aqueous route is in the identity seed, so the NMP sibling (`…f2sb-n513-x4x6-hzev`) is a different IRI for the same powder. Compare the two in `bundle/emission-spot-checks.txt`, spot checks 2b-2d. |
| 4 | electrode | LNMO-AQ-1 (batch) | [`records/electrode/electrode-620q-vkks-p6x7-8ejm.json`](records/electrode/electrode-620q-vkks-p6x7-8ejm.json) | [`bundle/jsonld/electrode/…620q-vkks-p6x7-8ejm.jsonld`](bundle/jsonld/electrode/electrode-620q-vkks-p6x7-8ejm.jsonld) | - `batch_id` is the dataset's own public label, which is the join every other record uses.<br>- The only as-built figure is the dry thickness (40 um); everything else in metadata.csv varies per cell and stays on the tests.<br>- The batch node is typed plain `Electrode`: an instance carries no chemistry of its own and the emitter will not resolve it through the spec. Acceptable, or should the spec's chemistry be inherited? |
| 5 | cell-spec | LNMO (LiNi0.5Mn1.5O4) R2032 half-cell (intelligent1) | [`records/cell-spec/cell-spec-kzhf-qsrt-2z76-agkp.json`](records/cell-spec/cell-spec-kzhf-qsrt-2z76-agkp.json) | [`bundle/jsonld/cell-spec/…kzhf-qsrt-2z76-agkp.jsonld`](bundle/jsonld/cell-spec/cell-spec-kzhf-qsrt-2z76-agkp.jsonld) | - **The one broken link in this chain**: `positive_electrode_spec_id` is absent, because this published cell spec covers both LNMO-AQ-1 and LNMO-NMP-1, and the seam is single-valued. The two designs are named in `specification_comment` instead. See decision D1 below.<br>- The inline working electrode still links the powder (`material_spec_id` -> row 2), which is why the LNMO chain is not fully severed.<br>- Everything reviewed in round 1 is unchanged: `cell_configuration: half_cell`, `reference_electrode: lithium`, lithium-metal negative, R2032, the 3.50-4.80 V window. |
| 6 | cell-instance | LNMO-AQ-1, serial 21a280 | [`records/cell-instance/cell-t66p-bb2k-fdh8-a8pz.json`](records/cell-instance/cell-t66p-bb2k-fdh8-a8pz.json) | [`bundle/jsonld/cell-instance/…t66p-bb2k-fdh8-a8pz.jsonld`](bundle/jsonld/cell-instance/cell-t66p-bb2k-fdh8-a8pz.jsonld) | - Byte-identical to the published record; the IRI is live today.<br>- `batch_id` = `LNMO-AQ-1` is the only thing tying this cell to the electrode batch in row 4 - there is no `electrode_id` field on a cell instance (gap E4).<br>- `name` is the public label, `serial_number` the 6-character id from the file name. |
| 7 | test-protocol | p-OCV | [`records/test-protocol/test-protocol-1pvg-sjjy-kn8j-jhxh.json`](records/test-protocol/test-protocol-1pvg-sjjy-kn8j-jhxh.json) | [`bundle/jsonld/test-protocol/…1pvg-sjjy-kn8j-jhxh.jsonld`](bundle/jsonld/test-protocol/test-protocol-1pvg-sjjy-kn8j-jhxh.jsonld) | - Record byte-identical to v1; only the inline `@context` grew (two electrode class terms #342 added).<br>- Emits `PseudoOpenCircuitVoltageMethod` over a five-cycle `IterativeWorkflow`.<br>- Material-agnostic by design: the numeric cutoffs live on the cell spec, so one protocol serves all nine specs. |
| 8 | test | LNMO-AQ-1 cell 21a280 p-OCV | [`records/test/test-egcb-kkka-m5fr-jtfz.json`](records/test/test-egcb-kkka-m5fr-jtfz.json) | [`bundle/jsonld/test/…egcb-kkka-m5fr-jtfz.jsonld`](bundle/jsonld/test/test-egcb-kkka-m5fr-jtfz.jsonld) | - Byte-identical to the published record.<br>- `conditions` still carries the four per-cell electrode figures (active-material mass, coating mass, areal capacity, loading). The electrode model does not change this: a batch record describes the batch, not the disc punched for one cell (gap G2 stands).<br>- Room temperature and the Li/Li+ voltage reference are stated as plain strings. |
| 9 | dataset | LNMO-AQ-1 cell 21a280 p-OCV half-cell OCV (BDF) | [`records/dataset/dataset-d0ht-kf1r-4tvr-gehm.json`](records/dataset/dataset-d0ht-kf1r-4tvr-gehm.json) | [`bundle/jsonld/dataset/…d0ht-kf1r-4tvr-gehm.jsonld`](bundle/jsonld/dataset/dataset-d0ht-kf1r-4tvr-gehm.jsonld) | - Points at `sintef__sintef-lnmo-R2032-intelligent1-21a280__20250424__p-ocv__RT.bdf.parquet`, md5 `e26d80e600269804b8b10e0f9072f5b2`, 2 668 120 bytes, all read from the Zenodo API snapshot. No parquet was downloaded.<br>- `about` names the cell and the test; the reverse link is still unauthorable (gap G1).<br>- The checksum is stated as md5 and typed as md5 in the deposit graph - no sha256 relabelling anywhere (0 occurrences). |

## Chain 2 - the aqueous silicon thread (the seam working, with no powder behind it)

Same nine steps for `Si-AQ-1`, which is the thread the brief asked for. It has no powder record by design, and it is the chain where the cell-spec to electrode-spec link is present.

| record type | title | staged record | bundle JSON-LD | what to check |
|---|---|---|---|---|
| material-spec | *(none, deliberately)* | - | - | - The description names "percentage of silicon in Si-Graphite blends" among the properties that are **not** available, so a silicon powder record would state more than the source does.<br>- The chemistry is not lost: `kind: silicon` types the electrode node `SiliconBasedElectrode` and anchors it to the EMMO class.<br>- If SINTEF knows the powder supplier and grade, adding the record later is additive: the electrode spec already has the field. |
| electrode-spec | Silicon electrode, aqueous processed (IntelLiGent, SINTEF) | [`records/electrode-spec/electrode-spec-rkf4-xz0y-h8kz-rmxz.json`](records/electrode-spec/electrode-spec-rkf4-xz0y-h8kz-rmxz.json) | [`bundle/jsonld/electrode-spec/…rkf4-xz0y-h8kz-rmxz.jsonld`](bundle/jsonld/electrode-spec/electrode-spec-rkf4-xz0y-h8kz-rmxz.jsonld) | - `active_material_spec_id` absent, `kind` present: the tolerance the optional field exists for.<br>- Theoretical capacity (3579 mAh/g) rides the design property block **because** no powder record holds it.<br>- Only the active-material weight percentage (84.97 %) is stated; binder and additive are not reported and are not invented. |
| electrode | Si-AQ-1 (batch) | [`records/electrode/electrode-69qq-5qve-qmg6-929g.json`](records/electrode/electrode-69qq-5qve-qmg6-929g.json) | [`bundle/jsonld/electrode/…69qq-5qve-qmg6-929g.jsonld`](bundle/jsonld/electrode/electrode-69qq-5qve-qmg6-929g.jsonld) | - `schema:isVariantOf` the design; the public label emitted as a `schema:PropertyValue`.<br>- Dry thickness 44 um.<br>- Eight of the 95 published measurements were made on cells from this batch (stated in the notes). |
| cell-spec | Silicon R2032 half-cell (intelligent1) | [`records/cell-spec/cell-spec-zqwq-ted6-cwb2-0d42.json`](records/cell-spec/cell-spec-zqwq-ted6-cwb2-0d42.json) | [`bundle/jsonld/cell-spec/…zqwq-ted6-cwb2-0d42.jsonld`](bundle/jsonld/cell-spec/cell-spec-zqwq-ted6-cwb2-0d42.jsonld) | - **The seam in action**: `positive_electrode_spec_id` merges the electrode spec's `@id` onto the emitted `hasPositiveElectrode` node. Compare with v1, where the same node linked a retired "material spec".<br>- Same IRI as the published record (`zqwq-ted6-cwb2-0d42`); the diff is three lines.<br>- The design polarity of the referenced spec is `negative` (silicon is an anode material) while the holder is the cell's positive electrode. That is not a contradiction - it is what a half cell against lithium metal *is* - but it is the sharpest thing in the corpus to sanity-check. See D2. |
| cell-instance | Si-AQ-1, serial 931301 | [`records/cell-instance/cell-xv8x-qmx5-vzvr-0vr4.json`](records/cell-instance/cell-xv8x-qmx5-vzvr-0vr4.json) | [`bundle/jsonld/cell-instance/…xv8x-qmx5-vzvr-0vr4.jsonld`](bundle/jsonld/cell-instance/cell-xv8x-qmx5-vzvr-0vr4.jsonld) | - Byte-identical to the published record.<br>- Production date 2025-04-05, from the test start date in the file name.<br>- Same `batch_id`-only join to the electrode batch as chain 1. |
| test-protocol | p-OCV | see chain 1 | see chain 1 | - One protocol record serves both chains, which is the point of keeping the method material-agnostic. |
| test | Si-AQ-1 cell 931301 p-OCV | [`records/test/test-0s90-29rs-22bw-x5e3.json`](records/test/test-0s90-29rs-22bw-x5e3.json) | [`bundle/jsonld/test/…0s90-29rs-22bw-x5e3.jsonld`](bundle/jsonld/test/test-0s90-29rs-22bw-x5e3.jsonld) | - Byte-identical to the published record.<br>- No conformance block: this run has no known issue. Eleven of the 95 do, all typed as deviations.<br>- Per-cell loading 0.587 mg/cm2, active-material mass 0.904 mg: the numbers that normalise this measurement. |
| dataset | Si-AQ-1 cell 931301 p-OCV half-cell OCV (BDF) | [`records/dataset/dataset-t9k1-m53j-9473-kndk.json`](records/dataset/dataset-t9k1-m53j-9473-kndk.json) | [`bundle/jsonld/dataset/…t9k1-m53j-9473-kndk.jsonld`](bundle/jsonld/dataset/dataset-t9k1-m53j-9473-kndk.jsonld) | - md5 `00a49bd5bb388ea046924071ec2f86b5`, 2 030 427 bytes.<br>- Seven BDF columns described as `variable_measured` with units.<br>- CC BY 4.0 and all nine contributors stamped, same as every other record. |

## Decisions for the maintainer

**D1. Three of the nine cell specs cannot cite an electrode design.** `lnmo/intelligent1` (LNMO-AQ-1 + LNMO-NMP-1), `lnmo/intelligent2` (LNMO-AQ-2 + LNMO-NMP-2) and `silicon_graphite/intelligent2` (SiGr-AQ-2 + SiGr-AQ-3) each span two designs, and a cell spec can cite one. Six of nine are linked; three are not.

The clean fix is to split those three into six, one per design, giving twelve cell specs each citing exactly one electrode. It was **not** done here because the cell-spec IRI is the root of the cell, test and dataset identity chain: splitting re-mints 47 cells, 47 tests, 47 datasets and 3 cell specs, superseding 144 live identifiers to express something the corpus already states in prose and through the batches. If you want the split anyway, it is a change to the grouping key in section 4 of `build_records.py` and a regeneration - but it should be a deliberate identifier decision, not a side effect.

**D2. Polarity in a half cell.** Electrode-spec polarity is derived from the kind, so the silicon, graphite and Si/Gr designs are `negative` - they are anode designs. In these cells they are the working electrode, which sits above lithium metal and is therefore the cell's *positive* electrode; that is how the published voltages read. The corpus states both facts in their proper places (design polarity on the electrode spec, cell role by which holder it sits in) and neither is authored twice. Authoring `polarity: positive` to match the cell role would trip `semantic.electrode_polarity_conflict`, so it was not done.

**D3. Twelve designs for twelve batches.** Every design in this dataset was coated exactly once, so the spec/batch pair is 1:1 throughout. That is honest rather than redundant - the specs carry design facts (composition, route, diameter, manufacturer-stated loading and areal capacity), the batches carry as-built facts (dry thickness) and the public label. It also means SiGr-AQ-2 and SiGr-AQ-3, which share (kind, source, route), are still two designs, because their active materials have different theoretical specific capacities (1150 vs 900 mAh/g) and different active-material type strings.

**D4. Supplier names for the purchased electrodes.** "Gelon LIB" and "Customcells" are read from the batch-id token of the dataset's own file-name convention, supported by the batch table calling those electrodes commercial. They are recorded as the electrode-spec manufacturer and the batch supplier. If either name is wrong, it is a one-line fix in `SOURCE_ORG`.

**D5. One cosmetic nit.** The manufacturer-stated loadings are converted from g/cm2 to mg/cm2 (only mg/cm2 resolves to an EMMO unit), so NMC532 reads `20.400000000000002 mg/cm2`. It is the same float arithmetic the published test records already use for the per-cell values, so it was left consistent rather than rounded on one side only.

## Validation

| check | result |
|---|---|
| strict save | 323 records, 0 errors |
| SHACL | 0 non-conforming |
| semantic warnings | 3, all one false positive - see below |
| idempotent re-run | yes: 228 records `[unchanged]`, 0 datasets rewritten |
| record types reaching JSON-LD | 8 of 8 |
| deposit gold standard | 95 errors + 95 warnings, unchanged from v1 (gaps G7 and G1, both pre-existing) |
| deposit graph coverage | 299 of 323 records - the 24 electrode records are missing (gap E2) |
| checksums | 95 md5 digests, typed md5; zero sha256 anywhere |

The three warnings are all `semantic.property_unmapped` on `electrode_spec.property.areal_capacity`, on the three purchased-electrode specs. The emitter maps that key to the curated EMMO class `AreicCapacity` and does so correctly in the bundle; the validator's known-key set is built from the descriptor and coating term tables and was not extended to the electrode table #342 added, so it reports a mapping that exists as missing. Details and the one-line fix are in `READINESS-REPORT.md` gap E5. The value is real, manufacturer-stated data and was kept.

## Retired records

The 21 v1 records the remodel replaces are in [`superseded/v1/`](superseded/v1/) with a mapping table, not deleted. Their published copies stay live until the republish supersedes them; see `superseded/README.md`.
