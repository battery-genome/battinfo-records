# Console review - Flores 2026 corpus on the record console

**Staged only; nothing republished.** The corpus is v4.2 (424 records, PR #6): v4.1 re-verified byte-identical 2026-08-20, then extended 2026-08-21 with a material lot for every spec (curator ruling - eight new lots joining the LNMO one: two SINTEF-coated singles, three silicon-graphite blends evidenced by their distinct theoretical capacities, three purchased-electrode batches asserted as existence-only). Validation 0 errors / 0 warnings / 0 SHACL non-conformances across all 424; idempotent; all pre-existing identifiers unchanged.

What changed since REVIEW-TABLE-V4 is the *presentation*: every record type now renders as the four-band record console (registry `feat/record-dossier`, PR #56; platform `feat/record-dossier`, PR #81 - both unmerged), each at its own scale - cells and datasets tell their full chain; the other types get their own facts plus the records behind them, with the reverse "used by" rosters as clickable tables in the Related band. Organizations keep their profile page. This review is of that surface, over the unchanged corpus.

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

### Other record types (console, at their own scale)

| # | page | why |
|---|---|---|
| 8 | [LNMO powder spec](http://127.0.0.1:3100/registry/spec/aexf-ysdh-9z93-bs7m) | Console: theoretical-capacity KPI, Topsoe tile, and the "used by electrode specs / cell specs" rosters as clickable tables in Related |
| 9 | [LNMO electrode spec (NMP)](http://127.0.0.1:3100/registry/spec/93f0-n525-w6pr-t8gh) | Console: batch statistics with sd/n as KPIs, active-material section, used-by rosters |
| 10 | [Electrode gfa4 (was "disc")](http://127.0.0.1:3100/registry/electrode/gfa4-pb59-tgvn-psvs) | Console: as-built figures, its spec and powder as sections, the cell using it in Related. The record *title* still says "disc" - titles are corpus data, renaming is a v5 decision |
| 11 | [GITT protocol](http://127.0.0.1:3100/registry/spec/rd8x-1nqr-3dp2-0we8) | Console: the protocol prose leads as the page's narrative; the 47 tests using it in Related |
| 12 | [Topsoe](http://127.0.0.1:3100/registry/organization/vz1v-rvhz-n77h-344c) | Organizations keep their dedicated profile page - the one non-console type |
| 12b | [Graphite study powder batch](http://127.0.0.1:3100/registry/material/k1pt-wy97-tetf-fzsw) | One of the eight v4.2 lots: the instance behind the spec, honest about what the source does and does not evidence |

### Compilations

| # | page | why |
|---|---|---|
| 13 | [Kind: lnmo](http://127.0.0.1:3100/registry/kind/lnmo) | Linked from every LNMO materials tile |
| 14 | [Kind: silicon_graphite](http://127.0.0.1:3100/registry/kind/silicon_graphite) | Second kind for comparison |
| 15 | [Browse cells](http://127.0.0.1:3100/registry?type=cell) | Serial-distinct titles across the 95 |

All pages sweep-verified 2026-08-20: HTTP 200, console on every record type except organizations, no error boundaries. Content-verified: the powder's used-by rosters, the protocol's prose-as-narrative, and the electrode's spec/material sections all survive the console switch.

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
