# Corpus v4 review table - Flores half-cell OCV (Zenodo 20086298)

**Staged only. Nothing here is published.** The 319 v1 records are still live in the registry and untouched. This is the review-round-3 build: 416 records, 0 errors, 0 warnings, 0 SHACL non-conformances, byte-identical on a re-run.

Built on BattINFO main at `dc9b905` (>= `a7661d2`, BIG-MAP/BattINFO#346). Registry served locally from `battinfo-registry` at `2a88439` (PRs #49 + #50), platform at `a0a3b9b`.

## v4.1 - the review of this table

Five content fixes on the same 416 records. Nothing was re-modelled and no identifier moved.

| # | fix | what changed | records touched |
|---|---|---|---|
| B3 | No `polarity` on an electrode spec | battinfo derives it from the kind's family, so an anode design wrote `"negative"` unasked - the one piece of polarity language left in a corpus whose ruling is that a half cell has no sides, and it contradicts this batch's own convention, where a "negative" graphite design charges to 1.00 V vs Li/Li+ | 12 electrode-specs |
| B5 | Cell names carry the serial | `LNMO-NMP-2` -> `LNMO-NMP-2 cell 2f9459`, matching how the disc, the test and the dataset are already named. Ninety-five cells under twelve names made a browse listing unreadable | 95 cells |
| B1 | Known issues reach the dataset | The eleven non-conformant runs said so on the test record only. Now the dataset says it too: a `Known issue: ...` prefix on the description (which the emitter carries into `dcterms:description` / `schema:description`) and the full statement in the record's notes | 11 dataset descriptions + notes |
| S5 | No circular citation | The Zenodo DOI left `provenance.citation` - an untyped citable reference, and the field the platform feeds into "Peer-reviewed papers this dataset supports". It stays in the slots that mean self-reference: `access_url`, `same_as`, the new `is_based_on`, and the typed `kind: "dataset"` self-citation | 95 datasets |
| S11 | Profiles paragraph corrected | It quoted the count of relaxation endpoints *detected* (368-1704) as the count *plotted*. The real range is 83-1019, median 118 | this table |

**Identity note.** `entities.cell_instance_identity_seed` folds the name into the seed whenever one is set (`label = name or serial_number or batch_id`), so the B5 rename would have re-minted all 95 cell IRIs and the 95 test and 95 dataset IRIs seeded from them - 285 identifiers, 95 of them live and retained from v1, moved by a change of display text. `build_records.py` therefore pins the published identities through `iris=`, computed with battinfo's own primitives. Worth fixing upstream: the seed should prefer the serial over display text when a serial is given, which is what `ws.add("cell", ...)` already promises ("names - display text, which several cells of one batch may share"; "the serial is the cell's identity").

## What the round-3 rulings changed

| # | Ruling | v3 | v4 |
|---|---|---|---|
| R1 | A powder for every kind | 1 material spec (LNMO only); 11 of 12 designs cited no material | **7 material specs**, one per active-material kind; all 12 designs carry `active_material_spec_id` |
| R2 | Topsoe made the LNMO powder | no manufacturer on any powder | **1 organization record**; the LNMO spec's `manufacturer` carries its IRI and name |
| R3 | A lot where one is evidenced | no material instances | **1 material record**: the LNMO study powder batch behind all four LNMO designs |
| R4 | The electrode is the disc in the cell | 12 batch records; per-cell figures parked on `test.conditions` | **95 electrode records**, one per cell, each with that cell's six as-built figures; batch statistics moved up to the electrode spec with structured `standard_deviation` / `sample_count` |
| R5 | Cells link their electrodes | join by matching batch labels | **95 cells carry `working_electrode_id`**; `counter_electrode_id` deliberately unset |

Everything from rounds 1-2 stands: electrodes named by role and no polarity anywhere (D2 - literally nowhere as of v4.1, the electrode specs included), `cell_configuration = half_cell`, one cell spec per electrode design (D1), the per-unit rounding rule (D5), and CC BY 4.0 + the IntelLiGent grant + all nine contributors on every record.

## Counts

| type | v3 | v4 | |
|---|---:|---:|---|
| organization | 0 | **1** | Topsoe, into the shared `records/organization/` corpus |
| material-spec | 1 | **7** | one powder per kind |
| material | 0 | **1** | the LNMO study powder lot |
| electrode-spec | 12 | 12 | now carrying the batch statistics |
| electrode | 12 | **95** | the disc inside each cell |
| cell-spec | 12 | 12 | |
| cell-instance | 95 | 95 | each now linking its disc |
| test-protocol | 4 | 4 | |
| test | 95 | 95 | conditions reduced to what is a test condition |
| dataset | 95 | 95 | all 95 now carry their plot figure |
| **total** | **326** | **416** | + 1 organization outside the batch |

## The LNMO chain, ten records deep

One thread, from the company that made the powder to the figure on the dataset page. Staged path, canonical IRI, and the live URL on the local stack.

| # | record | what it is | staged path | live URL (127.0.0.1:3100) |
|---|---|---|---|---|
| 1 | organization | Topsoe | `records/organization/topsoe/record.json` (repo root) | [/registry/organization/vz1v-rvhz-n77h-344c](http://127.0.0.1:3100/registry/organization/vz1v-rvhz-n77h-344c) |
| 2 | material-spec | LNMO (LiNi0.5Mn1.5O4), high Mn/Ni disorder spinel | `records/material-spec/material-spec-aexf-ysdh-9z93-bs7m.json` | [/registry/spec/aexf-ysdh-9z93-bs7m](http://127.0.0.1:3100/registry/spec/aexf-ysdh-9z93-bs7m) |
| 3 | material | LNMO study powder batch | `records/material/material-y7n3-npze-ed51-94jq.json` | [/registry/material/y7n3-npze-ed51-94jq](http://127.0.0.1:3100/registry/material/y7n3-npze-ed51-94jq) |
| 4 | electrode-spec | LNMO electrode, NMP processed (IntelLiGent batch 2, SINTEF) | `records/electrode-spec/electrode-spec-93f0-n525-w6pr-t8gh.json` | [/registry/spec/93f0-n525-w6pr-t8gh](http://127.0.0.1:3100/registry/spec/93f0-n525-w6pr-t8gh) |
| 5 | electrode | LNMO-NMP-2 disc 2f9459 | `records/electrode/electrode-gfa4-pb59-tgvn-psvs.json` | [/registry/electrode/gfa4-pb59-tgvn-psvs](http://127.0.0.1:3100/registry/electrode/gfa4-pb59-tgvn-psvs) |
| 6 | cell-spec | LNMO R2032 half-cell (intelligent2, LNMO-NMP-2) | `records/cell-spec/cell-spec-y8wz-n740-tarr-8gk7.json` | [/registry/spec/y8wz-n740-tarr-8gk7](http://127.0.0.1:3100/registry/spec/y8wz-n740-tarr-8gk7) |
| 7 | cell-instance | LNMO-NMP-2 cell 2f9459 | `records/cell-instance/cell-xw1k-b1ce-8m7d-9fwa.json` | [/registry/cell/xw1k-b1ce-8m7d-9fwa](http://127.0.0.1:3100/registry/cell/xw1k-b1ce-8m7d-9fwa) |
| 8 | test-protocol | GITT | `records/test-protocol/test-protocol-rd8x-1nqr-3dp2-0we8.json` | [/registry/spec/rd8x-1nqr-3dp2-0we8](http://127.0.0.1:3100/registry/spec/rd8x-1nqr-3dp2-0we8) |
| 9 | test | LNMO-NMP-2 cell 2f9459 GITT | `records/test/test-3hyc-4m5p-tctw-sry3.json` | [/registry/test/3hyc-4m5p-tctw-sry3](http://127.0.0.1:3100/registry/test/3hyc-4m5p-tctw-sry3) |
| 10 | dataset | LNMO-NMP-2 cell 2f9459 GITT half-cell OCV (BDF) | `records/dataset/dataset-50hd-jyge-hvj1-hsfh.json` | [/registry/dataset/50hd-jyge-hvj1-hsfh](http://127.0.0.1:3100/registry/dataset/50hd-jyge-hvj1-hsfh) |

Row by row, what to look at:

- **1 Topsoe.** Type `Corporation`, `alternateName` carries `Haldor Topsoe`, and the editorial note says the fact came from the corpus maintainer rather than the Zenodo record. The IRI is minted from a pinned seed, not drawn at random, so the build is re-runnable.
- **2 The powder.** `manufacturer` links row 1 by IRI and name. `Theoretical Capacity 140 mAh/g` renders as one field. The `kind` value `lnmo` links to `/registry/kind/lnmo`. The description says what the source does not give: no grade, no product id, no supplier.
- **3 The lot.** `material_spec_id` points at row 2. Its notes name the four LNMO designs it was coated into, say why it has no `processing` block (one lot, both routes), and record why the electrode side cannot point back at it (gap E8).
- **4 The design.** No `polarity` row on the page as of v4.1 (B3); the `@type` in the emitted JSON-LD is the chemistry class alone, `LithiumNickelManganeseOxideElectrode`, with no `PositiveElectrode` stacked on it. `active_material_spec_id` points at row 2. The property block is where the batch statistics now live, with the spread on the quantity rather than in prose: `9.5173 ± 0.3213 mg/cm2 (8.9505 to 9.99, n=8)` for the loading, `90 ± 0 um (n=8)` for the dry thickness, `1.3324 ± 0.045 mAh/cm2 (1.2531 to 1.3986, n=8)` for the areal capacity. The `± 0` is meaningful: `metadata.csv` declares one dry thickness for every disc of the batch, and the spec's notes say that is a repeated declaration, not a measured spread.
- **5 The disc.** `batch_id` is the public label `LNMO-NMP-2`; `electrode_spec_id` is row 4. Six as-built figures for this cell alone: loading 9.297 mg/cm2, dry thickness 90 um, areal capacity 1.3016 mAh/cm2, diameter 14 mm, coating mass 15.562 mg, active-material fraction 92.002 %. The registry's reverse index shows **Used by cells -> 1**: the cell in row 7.
- **6 The cell spec.** Unchanged from v3: `half_cell`, `working_electrode` / `counter_electrode` by role, `working_electrode_spec_id` -> row 4, no polarity anywhere.
- **7 The cell.** `working_electrode_id` -> row 5. `counter_electrode_id` is absent, and that is the ruling: the lithium counters are not individually tracked by the source.
- **8 The protocol.** Structured EMMO method, material-agnostic, shared by all twelve cell specs.
- **9 The test.** `conditions` is now two entries - ambient temperature and voltage reference - because the four as-built figures it used to carry are on row 5.
- **10 The dataset.** Two distributions: the 308 MB Zenodo parquet (md5-checked) and the 84 KB derived plot figure, which the registry promotes to role `plot_data` and the platform renders as the **Interactive data explorer** panel. This one ran clean, so it carries no `Known issue:` prefix; for one that did not, see [06xa](http://127.0.0.1:3100/registry/dataset/06xa-nxne-46kw-3cjy), whose description opens "Known issue: Cell failed at the end of 1st cycle." (B1). No "Related publications" panel on any of the 95 as of v4.1 - the Zenodo record is data with no companion paper, and the DOI now sits only where it means self-reference (S5).

## Verification on the local stack

Reseeded on current code: `battinfo-registry` at `2a88439` (PR #49 kind filter + reverse edges + value/unit display, PR #50 vendored schemas at `a7661d2`), 416 records published and approved, 2 organizations synthesized from the batch's own references.

### v4.1 re-verification

Reseeded again on `battinfo-registry` `0323415` (`origin/main`, through PR #54) with `preview_stack.py --reset` + `rerender_record_pages.py --apply --persist-display`: 416 published, 416 promoted, 0 failed, 418 pages rendered. Platform restarted so nothing was served from the pre-reseed render cache.

| check | result |
|---|---|
| Electrode-spec page has no Polarity row | [93f0](http://127.0.0.1:3100/registry/spec/93f0-n525-w6pr-t8gh): 0 occurrences of "Polarity" on the page, and none in the registry's `metadata`. Emitted `@type` is `LithiumNickelManganeseOxideElectrode` alone; all 12 keep their chemistry class and none carries a polarity class |
| Cells browse shows distinct names | [/registry?type=cell](http://127.0.0.1:3100/registry?type=cell): 50 distinct `<label> cell <serial>` titles on the first page, 0 bare batch labels |
| Cell IRIs did not move | 0 of 416 identifiers changed. The supersede map is untouched |
| Known-issue dataset carries the warning | [06xa](http://127.0.0.1:3100/registry/dataset/06xa-nxne-46kw-3cjy): the record's `description` opens "Known issue: Cell failed at the end of 1st cycle.", the notes carry the full statement, and both are in the registry's `page-model`. On the platform they reach the page only inside the collapsed structured payload - see caveat 6 |
| Clean datasets are unmarked | [50hd](http://127.0.0.1:3100/registry/dataset/50hd-jyge-hvj1-hsfh): no "Known issue" anywhere; 84 of 95 datasets are unchanged in this respect |
| No circular citation panel | "Related publications" is absent from every dataset page (0 occurrences on both pages above). `metadata.doi` still resolves to the full `10.5281/zenodo.20086298`, derived from the typed self-citation |
| Data explorer still renders | Yes, on both dataset pages |

| check | result |
|---|---|
| Dataset page shows the plot - GITT | Explorer panel present ([50hd](http://127.0.0.1:3100/registry/dataset/50hd-jyge-hvj1-hsfh), [06xa](http://127.0.0.1:3100/registry/dataset/06xa-nxne-46kw-3cjy)); the figure URL 404s, see caveat below |
| Dataset page shows the plot - p-OCV | Explorer panel present ([061x](http://127.0.0.1:3100/registry/dataset/061x-x0df-cmjt-ck28)); same caveat |
| `kind` links to `/registry/kind/{kind}` | Yes, from the powder and electrode-spec pages |
| Kind page compiles specs | [/registry/kind/lnmo](http://127.0.0.1:3100/registry/kind/lnmo) shows 1 material spec + 4 electrode specs, and the badge reads **"Filtered by the registry"** - the platform detected the new `?kind=` parameter in `/openapi.json` |
| Powder shows "Used by" electrode specs | In the registry: `display.linked_resources` gives **Used by electrode specs (4)**, **Used by cell specs (4)** and **Materials (1)**. Not on the platform, see caveat |
| Disc links its spec | Yes |
| Disc links its cell | In the registry (**Used by cells -> 1**). Not on the platform, see caveat |
| Cell links its disc | In the record and in the registry's reverse index. Not rendered on either page, see caveat |
| Value + unit as one field, with `± sd (n=)` | Yes: `9.5173 ± 0.3213 mg/cm2 (8.9505 to 9.99, n=8)` on the electrode spec, `15.872 mg` on a disc |
| Manufacturer links the Topsoe org page | Yes, from the LNMO powder page |
| Test page embeds its dataset | Yes, with the dataset's `plot_data` distribution |

### Caveats found while verifying

1. **The plot figures are not uploaded.** The dataset records point at the R2 key layout `ws.upload()` uses, and `upload_profiles.py` is what puts the files there - a production write, so it was not run. The explorer panel renders and the record carries the distribution, but the figure fetch 404s until a republish. `python upload_profiles.py --dry-run` lists all 95 objects, 7.1 MB.
2. **Reverse edges are not computed by the publish path.** `publishing/normalizers.py` calls `build_display(model)` with no `inbound=`/`peers=`, so a plain seed leaves `display.linked_resources` empty for every record. They appear only after `scripts/rerender_record_pages.py --apply --persist-display`, which was run here. Worth knowing before the next reseed.
3. **The platform does not render `display.linked_resources`.** `lib/contracts.ts` models `RegistryDisplay` as `{summaryFields, metricFields}` only, so PR #49's "Used by" panels reach the registry's own HTML and `page-model` but are dropped on the way to a platform page. This is why three rows above pass in the registry and not on `:3100`. It is a platform-side gap, not a corpus one.
4. **`working_electrode_id` is not surfaced forward.** The registry indexed it in the reverse direction (the disc knows its cell) but its `metadata` normalizer dropped the field, so the cell page neither displayed nor linked the disc. *Fixed upstream since:* on `0323415` the field is in the cell's `metadata` and the platform shows a **Working Electrode Id** row - as a bare IRI, not yet a link.
5. **A duplicate Topsoe.** `records/organization/haldor-topsoe/` is a Battery Knowledge Graph stub for the same legal entity under its pre-2022 name (`organization/j50f-3ebx-sssw-svnm`). Merge before publishing either. The new record carries the old name in `alternateName` and says so in its editorial note.
6. **A dataset's own prose does not reach its page.** `publishing/normalizers.py::_dataset_metadata` maps six keys - `license`, `created_at`, `media_type`, `record_url`, `doi`, `version` - and `description` is not among them, though it is for `test_spec`, `material_spec` and `electrode_spec`. The record-envelope `notes` are not mapped for any type. So the v4.1 known-issue warning is in the record, in the `page-model` and in the emitted JSON-LD, but on the platform it appears only inside the collapsed structured payload. The platform side is wired for it and unused: `registry-object-page.tsx` computes `const narrative = getNarrative(page)` and never renders it, and `getNarrative` reads exactly `metadata.description`. Corpus-side there is nothing left to do; this is a registry/platform fix.

## Validation

```
material-spec   records=  7  errors=0  warnings=0  shacl_non_conforming=0
material        records=  1  errors=0  warnings=0  shacl_non_conforming=0
electrode-spec  records= 12  errors=0  warnings=0  shacl_non_conforming=0
electrode       records= 95  errors=0  warnings=0  shacl_non_conforming=0
cell-spec       records= 12  errors=0  warnings=0  shacl_non_conforming=0
cell-instance   records= 95  errors=0  warnings=0  shacl_non_conforming=0
test-protocol   records=  4  errors=0  warnings=0  shacl_non_conforming=0
test            records= 95  errors=0  warnings=0  shacl_non_conforming=0
dataset         records= 95  errors=0  warnings=0  shacl_non_conforming=0
TOTAL records=416  errors=0  warnings=0  shacl_non_conforming=0
```

Deposit graph: 416 of 416 records reach `bundle/deposit.jsonld`, all nine types including the 95 discs, in a 418-node graph. Idempotence: a second run of `build_records.py` reports `[unchanged]` for every record and writes nothing.

Two property choices exist to keep that zero-warning line honest rather than to dodge the validator, and both are documented in `build_records.py`:

- **Active-material mass is not a seventh key on the disc.** `mass` is the only key in the curated property map that means Mass, so a second mass key would fall back to a non-canonical term or collapse onto the first in JSON-LD. The disc carries the two exact factors the source multiplies - coating mass and active-material weight fraction - and states the product in its notes. No number is lost.
- **The coating mass is stated in mg, not the source's g.** Same quantity. The semantic validator's plausible range for a mass in grams is a whole-cell one, `[0.05, 70000] g`, and a 16 mg electrode coating sits below it - not implausible, just not a cell.

## Supersede map

`superseded/supersede-map.json`, regenerated for v4 against the live v1 corpus:

| status | count | |
|---|---:|---|
| retained | 154 | same identifier, content updated |
| replaced | 147 | one successor under a new identifier |
| split | 18 | 6 cell specs that covered two designs each, and the 12 v1 "material lots" - coated electrode batches - which become the 7-9 discs cut from each |
| **published identifiers** | **319** | |

Successors under new identifiers: 254. Records that supersede nothing are counted separately under `new_in_v4`: 7 material specs and 1 material lot describe a level v1 never had. The Topsoe organization is also new; it lives in the shared organization corpus and is not part of this batch's count.

## Profiles

All 95 extracted and committed (7.3 MB, 61-98 KB each). GITT figures preserve the pulse train: the min/max decimator keeps each bucket's extremes at their true timestamps, and the emitted traces show 14-180 mV peak-to-peak per 3 hours against 8 mV for a p-OCV sweep of the same cell chemistry.

The 47 GITT lower panels are built from the relaxed rest endpoints, which is the quantity the technique exists to measure. `extract_profiles.py` detects 368-1704 of them per file and then keeps the longest single-direction run, because `Cumulative Capacity` restarts on every half cycle and plotting the raw pairs would overlay five sweeps on top of each other. What each panel actually plots is that run: **83-1019 points, median 118**, with 44 of the 47 below 368 and only three files (903, 967, 1019 points) keeping most of their endpoints. The earlier reading of this line quoted the detected count as if it were the plotted one. p-OCV lower panels are the longest single-direction sweep of the file itself, 2018-3557 points.

## Reproducing

```bash
cd batches/flores-ocv-halfcells
python extract_profiles.py --cache <scratch-dir>   # network; resumable, md5-verified
python build_records.py                            # 416 records, deterministic
python build_bundle.py                             # records/, JSON-LD, deposit, evidence
python build_supersede_map.py                      # superseded/supersede-map.json
```
