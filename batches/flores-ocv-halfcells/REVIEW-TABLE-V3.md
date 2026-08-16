# Corpus v3 review table - Flores half-cell OCV semantic layer

Corpus v3 carries the review-round-2 rulings on top of v2's first-class electrode model. **Nothing here is published.** All 326 records are staged in this branch; the 319 published records and their live `w3id.org` identifiers are untouched. `superseded/supersede-map.json` says, for every one of those 319, whether v3 keeps its identifier, replaces it, or splits it.

There are two things to look at. The **records** are in `records/`, linked from the table below. The **rendered pages** are the same records run through the registry's own publication and display pipeline, so you can read the corpus the way the genome will serve it. They are not committed (326 pages is 1305 files and 30 MB); regenerate them from a `battinfo-registry` checkout:

```bash
uv run python scripts/preview_staged_batch.py \
    --records-dir ../battinfo-records/batches/flores-ocv-halfcells/records \
    --out ../battinfo-records/batches/flores-ocv-halfcells/preview
# then open batches/flores-ocv-halfcells/preview/index.html
```

The preview needs `battinfo-registry` at `origin/main` **plus** the pending re-vendor branch `chore/revendor-roles`, which adopts BattINFO `33615d6` (the role-based half-cell schemas) and teaches `preview_staged_batch.py` to read the role holders. Without it the vendored schemas predate `working_electrode` and every cell page loses its link to the electrode layer.

## The rulings, as built

| ruling | what v3 does | where to check it |
|---|---|---|
| **D1** one cell spec per electrode design | 9 cell specs become 12. The 6 whose `(kind, source)` already covered one design keep their published identifier; the 3 that covered two each become 2 new ones, and the 47 cells, 47 tests and 47 datasets seeded under them follow. All 12 now cite their design. | rows 5-9 below; `superseded/README.md` |
| **D2** half cells name electrodes by role | `working_electrode` / `counter_electrode` and `working_electrode_spec_id`. The polarity *bases* go too - a cell with no sides should not describe its electrodes as either. Emission: `hasWorkingElectrode` 12/12, `hasCounterElectrode` typed `["CounterElectrode","ReferenceElectrode"]` 12/12, `hasPositiveElectrode` / `hasNegativeElectrode` **0 occurrences** anywhere. `semantic.electrode_role_expected` is gone. | row 5; `bundle/emission-spot-checks.txt` spot check 1a |
| **D5** round the float artifacts | One rule in `build_records.py` (`_DECIMALS_BY_UNIT`, decimals per unit, 6 significant digits otherwise), applied to every quantity the corpus writes. Values with 7+ decimals: **205 in v2, 0 in v3** across records, JSON-LD, deposit graph and RO-Crate. `20.400000000000002` reads `20.4`; the source's own 17-digit derived columns read `5.1499 mg` and `0.4682 mAh/cm2`. | rows 4 and 8 |
| **EES-1a** per-batch avg and sd | Every electrode batch carries `loading` (EMMO `ActiveMassLoading`) and `dry_thickness` (`DryCoatingThickness`) as the mean over its cells, with `min_value` / `max_value` where the cells differ, and the standard deviation, n and range in the notes. | row 4 |
| **EES-1b** electrolyte from the Zenodo description | **Omitted, because the record does not state one.** Evidence below. | row 5 |

### EES-1b: the electrolyte

The live Zenodo API record (`https://zenodo.org/api/records/20086298`, revision 6, updated 2026-06-29T09:58:29Z) was fetched and searched in full - description, notes and every other metadata field. Occurrences of `electrolyte`: **0**. Also 0 for `LiPF`, `EC`, `DMC`, `EMC`, `separator`, `Celgard`, `glass fibre`, `coin cell`, `glovebox`, `molar`, `LP30`, `LP40`, `FEC`. The committed snapshot in `sources/zenodo-record.json` is byte-identical to the live description and lists the same 96 files, so the snapshot is current.

The cell specs therefore keep the sentence they had: *"Electrolyte and separator are not reported in the source record and are omitted."* If SINTEF can state the electrolyte, adding it is additive - `electrolyte` is a holder the cell spec already has - but it cannot be read out of the published record.

### The batch statistics convention

`Electrode Loading / g cm-2` in `metadata.csv` is the **active-material** loading, not the coating loading: for every row it equals the active-material mass divided by the disc area. That is why it lands on `loading`, which the emitter maps to `ActiveMassLoading`.

Nine of the twelve batches have a genuinely per-cell loading; their notes give mean, sample (n-1) standard deviation, n and range. For the three purchased electrodes, and for **all twelve** dry thicknesses, `metadata.csv` repeats one value on every cell row - so the mean is that stated value and the standard deviation is 0 by construction. The notes say exactly that, rather than letting a repeated declaration read as a measured spread.

The standard deviation is in the notes and not in the property block because there is nowhere structured to put it: `Quantity` has no `standard_deviation` field, and the curated property map has no EMMO class that means one, so a structured key would be dropped from the JSON-LD and warned about. This is the one new model gap, **E7** in `READINESS-REPORT.md`, and it is the thing most worth ruling on next.

## What changed at a glance

| record type | v1 (published) | v2 | v3 | note |
|---|---|---|---|---|
| material-spec | 9 | 1 | 1 | unchanged since v2 (the LNMO powder). |
| material | 12 | 0 | 0 | retired by v2; now `electrode` records. |
| electrode-spec | - | 12 | 12 | same identifiers; content rounded. |
| electrode | - | 12 | 12 | same identifiers; **now carry batch loading and thickness statistics**. |
| cell-spec | 9 | 9 | **12** | D1 split. 6 identifiers held, 3 retired, 6 new. Roles, not polarity. |
| cell-instance | 95 | 95 | 95 | 48 identifiers held, 47 re-seeded. Content byte-identical either way. |
| test-protocol | 4 | 4 | 4 | identifiers held; content rounded (C-rate, step durations). |
| test | 95 | 95 | 95 | 48 identifiers held, 47 re-seeded; all 95 rounded. |
| dataset | 95 | 95 | 95 | 48 identifiers held, 47 re-seeded; content otherwise unchanged. |
| **total** | **319** | **323** | **326** | |

## The chain - LNMO-AQ-1, cell 21a280, p-OCV

The LNMO thread is the one that exercises every link, including the powder. Read it top to bottom: the organization, the powder, the electrode design, the coated batch, the cell design, the physical cell, the protocol, the test run and the published file. Preview paths are relative to `preview/`.

| # | record type | title | staged record | preview page | what to check |
|---|---|---|---|---|---|
| 1 | organization | SINTEF | [`records/organization/sintef/record.json`](../../records/organization/sintef/record.json) (repo root) | not in the batch - the live IRI is left alone | - Cited by `cell_spec.manufacturer.id` and by the manufacturer block of all nine SINTEF electrode specs.<br>- `https://w3id.org/battinfo/organization/b4qq-aawd-zesa-kh4q`, already live.<br>- Preview rule: a record outside the batch keeps its live URL rather than being rewritten to a page that does not exist. |
| 2 | material-spec | LNMO (LiNi0.5Mn1.5O4), high Mn/Ni disorder spinel | [`records/material-spec/material-spec-epzg-hf4v-k5bk-nqxe.json`](records/material-spec/material-spec-epzg-hf4v-k5bk-nqxe.json) | `material_spec/epzg-hf4v-k5bk-nqxe/index.html` | - The only powder record in the corpus, and **the acceptance criterion for this round**: it is now reachable from a cell page through the electrode chain. 4 cell-spec pages reach it in 2 hops, 32 cell-instance pages in 3.<br>- Theoretical capacity 140 mAh/g lives here, not on the four LNMO electrode specs.<br>- No supplier, grade or product id: the source names none.<br>- `kind: lnmo` links out to the chemical-substance vocabulary - an external link, so it stays live in the preview. |
| 3 | electrode-spec | LNMO electrode, aqueous processed (IntelLiGent batch 1, SINTEF) | [`records/electrode-spec/electrode-spec-tcqb-q91a-gg35-n0sk.json`](records/electrode-spec/electrode-spec-tcqb-q91a-gg35-n0sk.json) | `electrode_spec/tcqb-q91a-gg35-n0sk/index.html` | - `active_material_spec_id` -> row 2; the page carries the link, the JSON-LD carries it as `hasActiveMaterial`.<br>- `@type` is `["LithiumNickelManganeseOxideElectrode", "PositiveElectrode"]`. The polarity class is the **design's** intended full-cell side and is derived, never authored - it is not a claim about the half cell, which has no sides. See D2 below.<br>- The aqueous route is in the identity seed, so the NMP sibling (`spec/f2sb-n513-x4x6-hzev`) is a different design built from the same powder.<br>- Design values here are only what holds for the design: the 14 mm disc. Loading varies cell to cell for a SINTEF-coated electrode, so it is on the batch. |
| 4 | electrode | LNMO-AQ-1 (batch) | [`records/electrode/electrode-620q-vkks-p6x7-8ejm.json`](records/electrode/electrode-620q-vkks-p6x7-8ejm.json) | `electrode/620q-vkks-p6x7-8ejm/index.html` | - **Changed since v2 (EES-1a).** `loading` = 3.6472 mg/cm2 with `min_value` 3.2844 and `max_value` 4.0667; the note gives `3.6472 +/- 0.3017 mg/cm2 (n = 8 cells)`.<br>- `dry_thickness` 40.0 um, with the note saying the source states one value per batch, so its standard deviation is 0 by construction.<br>- Is the standard deviation acceptable in prose? That is gap E7 and the open question of this round.<br>- `batch_id` is the dataset's own public label, still the only join from a cell instance (gap E4). |
| 5 | cell-spec | LNMO (LiNi0.5Mn1.5O4) R2032 half-cell (intelligent1, LNMO-AQ-1) | [`records/cell-spec/cell-spec-tjya-8fz6-s4bp-qt2c.json`](records/cell-spec/cell-spec-tjya-8fz6-s4bp-qt2c.json) | `cell_spec/tjya-8fz6-s4bp-qt2c/index.html` | - **New identifier (D1).** Published `spec/kzhf-qsrt-2z76-agkp` covered LNMO-AQ-1 *and* LNMO-NMP-1 and could cite neither; it splits into this and `spec/6wqv-x8m4-15cx-tyqp`.<br>- **Changed since v2 (D2).** `working_electrode` + `counter_electrode`, `working_electrode_spec_id` -> row 3, and no polarity anywhere: no holders, no `positive_electrode_basis`, no `negative_electrode_basis`.<br>- The `model` string is qualified with the electrode label only because this `(kind, source)` pair is ambiguous; the six unambiguous specs keep the exact model string they were published with, which is why they keep their identifiers.<br>- Unchanged and still worth a look: `cell_configuration: half_cell`, `reference_electrode: lithium`, R2032, the 3.50-4.80 V window vs Li/Li+.<br>- The page's hero badge reads "Half-cell / working electrode measured against Li metal" - it is derived from `reference_electrode`, which is why dropping the bases did not cost it. |
| 6 | cell-instance | LNMO-AQ-1, serial 21a280 | [`records/cell-instance/cell-bnkg-n5bg-71n7-497a.json`](records/cell-instance/cell-bnkg-n5bg-71n7-497a.json) | `cell/bnkg-n5bg-71n7-497a/index.html` | - **New identifier (D1).** Published `cell/t66p-bb2k-fdh8-a8pz`; the *content* is byte-identical, only the seed moved, because a cell's identity starts at its cell spec.<br>- The page links up to row 5 and down to its test and dataset - the down-links exist only because the preview builds the reverse index across the whole batch, exactly as publication does.<br>- `name` is the public label, `serial_number` the 6-character id from the file name, `manufactured_at` 2025-04-24 from the test start date. |
| 7 | test-protocol | p-OCV | [`records/test-protocol/test-protocol-1pvg-sjjy-kn8j-jhxh.json`](records/test-protocol/test-protocol-1pvg-sjjy-kn8j-jhxh.json) | `test_spec/1pvg-sjjy-kn8j-jhxh/index.html` | - Identifier held. Content changed only by rounding: the C/50 rate reads `0.02 A/Ah`, the rests `8 h`.<br>- Emits `PseudoOpenCircuitVoltageMethod` over a five-cycle `IterativeWorkflow`.<br>- Material-agnostic by design, which is what lets one protocol record serve all twelve cell specs; the numeric cutoffs live on the cell spec. |
| 8 | test | LNMO-AQ-1 cell 21a280 p-OCV | [`records/test/test-vnxh-n79t-a5d6-m10h.json`](records/test/test-vnxh-n79t-a5d6-m10h.json) | `test/vnxh-n79t-a5d6-m10h/index.html` | - **New identifier (D1).** Published `test/egcb-kkka-m5fr-jtfz`.<br>- **Changed since v2 (D5).** `conditions` now reads `active_material_mass 5.1499 mg`, `nominal_areal_capacity 0.4682 mAh/cm2`, `electrode_loading 3.3441 mg/cm2` - the same numbers, without the 17-digit tails the source columns carry.<br>- The per-cell loading (3.3441) sits below the batch mean (3.6472) and inside its range: the two records say compatible things at two levels, which is the point of putting statistics on the batch.<br>- Room temperature and the Li/Li+ reference are still plain strings; per-cell electrode figures still have no home but `Test.conditions` (gap G2). |
| 9 | dataset | LNMO-AQ-1 cell 21a280 p-OCV half-cell OCV (BDF) | [`records/dataset/dataset-yy36-ypr6-esgw-fr4z.json`](records/dataset/dataset-yy36-ypr6-esgw-fr4z.json) | `dataset/yy36-ypr6-esgw-fr4z/index.html` | - **New identifier (D1).** Published `dataset/d0ht-kf1r-4tvr-gehm`; content otherwise unchanged.<br>- Points at `sintef__sintef-lnmo-R2032-intelligent1-21a280__20250424__p-ocv__RT.bdf.parquet`, md5 `e26d80e600269804b8b10e0f9072f5b2`, 2 668 120 bytes, all read from the Zenodo API snapshot. No parquet was downloaded.<br>- `about` names the cell and the test; the reverse link is still unauthorable (gap G1).<br>- The checksum is stated as md5 and typed as md5; zero sha256 anywhere.<br>- The page shows the Zenodo file link live and the in-batch links relative, which is the rule that keeps a staged preview honest. |

## Validation

| check | result |
|---|---|
| strict save | 326 records, 0 errors |
| semantic warnings | **0** (v2 had 3; `semantic.electrode_role_expected` never fires - the corpus has no polarity holders on a half cell) |
| SHACL | 0 non-conforming |
| idempotent re-run | yes: every record `[unchanged]`, 0 datasets written, 0 identities pruned |
| record types reaching JSON-LD | 8 of 8 |
| deposit graph | 8 of 8 types, 326 of 326 records, 328 nodes |
| float artifacts (7+ decimals) | 0, from 205 in v2 |
| preview | 326 pages rendered, 0 skipped, 0 broken relative links |
| acceptance criterion | met: `cell_spec/tjya-8fz6-s4bp-qt2c` -> `electrode_spec/tcqb-q91a-gg35-n0sk` -> `material_spec/epzg-hf4v-k5bk-nqxe`, and the same from 4 cell-spec and 32 cell-instance pages |
| deposit gold standard | 95 errors + 95 warnings, unchanged from v1 (gaps G7 and G1, both pre-existing and neither from these records) |
| checksums | 95 md5 digests, typed md5; zero sha256 anywhere |

## Open questions for this round

1. **E7, the standard deviation.** The corpus states it in prose because the model has no structured slot for it. A `{value, standard_deviation, sample_count}` pattern on `Quantity` would fix it for every lab number of this shape, not just loading. Worth doing before the EES crosswalk?
2. **E4, cell instance to electrode batch.** Still a string join on `batch_id`. D1 fixed the *design* link at the spec level; the *batch* link at the instance level is the remaining hop a consumer has to guess.
3. **The three purchased batches.** Their `loading` mean equals the design value on the electrode spec, because the source repeats the manufacturer's number on every cell row. Stated in both places with a note explaining why, or dropped from the batch?
4. **Registry follow-up.** `chore/revendor-roles` in `battinfo-registry` is required before any of this can be published or previewed; it now also carries the preview-tool fix for role holders. It needs a PR and a merge.
