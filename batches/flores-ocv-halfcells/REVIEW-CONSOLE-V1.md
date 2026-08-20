# Console review - Flores 2026 corpus on the record console

**Staged only; nothing republished.** The corpus is v4.1 (416 records, PR #6 at `51671d4`), re-verified 2026-08-20: `build_records.py` reproduces all 416 records byte-identically on the pinned toolchain (BattINFO `dc9b905`), `build_bundle.py` validates 0 errors / 0 warnings / 0 SHACL non-conformances across all nine types. The only rebuild delta was the RO-Crate `datePublished` build stamp, reverted.

What changed since REVIEW-TABLE-V4 is the *presentation*: anchor records (cells, datasets) now render as the four-band record console (registry `feat/record-dossier`, PR #56; platform `feat/record-dossier`, PR #81 - both unmerged). Leaf records keep the classic layout. This review is of that surface, over the unchanged corpus.

Local stack: registry :8010 (preview DB, display persisted from the dossier branch), platform :3100 (dev server from `plat-dossier`). Add a `?x=1` cache-buster if a page looks stale.

## The representative set

### Cells (console)

| # | page | why it is in the set |
|---|---|---|
| 1 | [LNMO-NMP-2 cell 2f9459](http://127.0.0.1:3100/registry/cell/xw1k-b1ce-8m7d-9fwa) | The reference chain anchor, clean GITT run. Full console: KPIs with calculated capacity (2.00 mAh, labeled), materials tile "Lithium \|\| LNMO" linking the kind page, coin glyph + QR, batch sub-lines under the as-built figures, hierarchy-ordered metadata, sources table, citation block, 7 siblings + 3 kindred batches |
| 2 | [NMC111-NMP-1 cell e5a00e](http://127.0.0.1:3100/registry/cell/1dm8-xf5g-h0ha-8jxq) | A cell whose run failed: the amber conformance chip reads the test's own note, "Cycling stopped unexpectedly during cycle 4" |
| 3 | [Si-AQ-1 cell 882755](http://127.0.0.1:3100/registry/cell/21rr-mqz9-svwa-aq27) | Different chemistry, aqueous route: materials tile "Lithium \|\| Silicon", calculated capacity 3.58 mAh, kindred table shows the SiGr designs |
| 4 | [LFP-NMP-1 cell 182031](http://127.0.0.1:3100/registry/cell/3dgx-4x7b-61yk-kg15) | Third chemistry for tile/kindred variety |

### Datasets (console)

| # | page | why |
|---|---|---|
| 5 | [GITT half-cell OCV, clean](http://127.0.0.1:3100/registry/dataset/50hd-jyge-hvj1-hsfh) | Plot leads the evidence band; parquet Download row (308 MB, md5); no chip - clean runs state no conformance, and a green badge would assert what no record states |
| 6 | [GITT half-cell OCV, known issue](http://127.0.0.1:3100/registry/dataset/06xa-nxne-46kw-3cjy) | Amber chip: "Cell failed at the end of 1st cycle" - one of the 11 non-conformant runs, previously invisible on the page |
| 7 | [p-OCV hold, SiGr](http://127.0.0.1:3100/registry/dataset/061x-x0df-cmjt-ck28) | The other protocol family's dataset page |

### Leaves (classic layout, deliberately untouched)

| # | page | why |
|---|---|---|
| 8 | [LNMO powder spec](http://127.0.0.1:3100/registry/spec/aexf-ysdh-9z93-bs7m) | No dossier furniture; reverse "used by" panels intact |
| 9 | [LNMO electrode spec (NMP)](http://127.0.0.1:3100/registry/spec/93f0-n525-w6pr-t8gh) | Batch statistics with sd/n on its own page |
| 10 | [Electrode gfa4 (was "disc")](http://127.0.0.1:3100/registry/electrode/gfa4-pb59-tgvn-psvs) | As-built figures; note the record *title* still says "disc" - titles are corpus data, renaming them is a v5 decision |
| 11 | [GITT protocol](http://127.0.0.1:3100/registry/spec/rd8x-1nqr-3dp2-0we8) | Where the protocol prose lives; the console links here via "protocol details" |
| 12 | [Topsoe](http://127.0.0.1:3100/registry/organization/vz1v-rvhz-n77h-344c) | Org page, linked from the materials tile sub-line |

### Compilations

| # | page | why |
|---|---|---|
| 13 | [Kind: lnmo](http://127.0.0.1:3100/registry/kind/lnmo) | Linked from every LNMO materials tile |
| 14 | [Kind: silicon_graphite](http://127.0.0.1:3100/registry/kind/silicon_graphite) | Second kind for comparison |
| 15 | [Browse cells](http://127.0.0.1:3100/registry?type=cell) | Serial-distinct titles across the 95 |

All 14 record/kind pages sweep-verified 2026-08-20: HTTP 200, console on exactly the seven anchors, no error boundaries.

## What to exercise beyond clicking through

- **Datasheet (PDF)** on pages 1 and 6: the print stylesheet drops chrome and the Related band, forces the light palette; the QR survives to print (scan it from paper).
- **Copy IRI / Copy citation** buttons.
- **Related tables**: whole rows click through; totals are honest (7 of 7 shown).
- **Theme toggle**: both themes are deliberate, including the QR redraw.
- **Sidebar scroll-spy** tracks the reading position through the four bands.

## Known caveats (unchanged from v4.1)

1. Plot figures 404 on the local stack until `upload_profiles.py` runs at republication (production write; `--dry-run` verified: 95 objects, 7.1 MB). The explorer panel and distribution rows render regardless.
2. `file:///` artifact links are local-stack configuration; the production R2 base gets confirmed at republish (S13).
3. Clean tests state no conformance field, so clean pages carry no chip. Stamping `conformance: conformant` on clean tests is a corpus v5 decision if a green badge is wanted.

## Republication note

This review changes nothing in the runbook: corpus v4.1 stands as staged, S10 is fixed on the PR train, and the console ships with registry #56 + platform #81. Merge order: BattINFO #350 -> registry #55 -> #56 -> platform #81, then the standing republish sequence.
