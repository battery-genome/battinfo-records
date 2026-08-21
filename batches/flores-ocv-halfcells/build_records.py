#!/usr/bin/env python3
"""Author the BattINFO semantic layer for the Flores et al. half-cell OCV dataset.

Zenodo record: https://zenodo.org/records/20086298
DOI (version):  10.5281/zenodo.20086298
DOI (concept):  10.5281/zenodo.19107294
License:        CC BY 4.0

CORPUS V4 - the maintainer's review-round-3 rulings, on top of v3's one-spec-per-
design split (D1), the role-based half-cell model (BIG-MAP/BattINFO#345) and the
first-class electrode model (#342). What v4 changes:

  R1  The active-material powders are described for EVERY kind, not only where the
      source volunteers something extra. Curator-complete replaces evidence-only:
      seven material specs (graphite, silicon, silicon-graphite, LNMO, LFP,
      NMC111, NMC532), each carrying its kind, the theoretical specific capacity
      metadata.csv states for it, a manufacturer only where one is known, and a
      description that says plainly what the source does NOT report. All twelve
      electrode specs now carry `active_material_spec_id`, so no electrode design
      is left pointing at a bare vocabulary key. See POWDER DISPOSITION below.
  R2  Topsoe made the LNMO powder (maintainer-supplied fact; the Zenodo record
      names no supplier). A Topsoe organization record joins the shared corpus and
      the LNMO material spec's `manufacturer` carries its IRI and name.
  R3  A material INSTANCE where a physical lot is evidenced. The source describes
      one study powder - "The LNMO material used in this study targeted high Mn/Ni
      disorder, therefore the OCVs is a highly disordered spinel" - singular,
      covering all four LNMO designs across both processing routes. That is one
      lot, so one `material` record is authored for it. No other kind gets an
      instance: for the other six the source evidences no lot at all, and a lot
      record per kind would be a fabricated batch. See LOT DISPOSITION.
  R4  The electrode record is now the DISC IN THE CELL, one per cell, 95 of them.
      Each carries its design (`electrode_spec_id`), the public label
      (`batch_id`), and the per-cell as-built figures metadata.csv publishes -
      which is where they belong, and where they now live instead of on
      `test.conditions`. The v3 batch-level electrode records (12, staged only,
      never published) give way; their batch statistics move up to the electrode
      SPEC and are stated with the structured `standard_deviation` /
      `sample_count` fields BattINFO#346 added, so the prose workaround of v3
      (gap E7) retires. See DISC IDENTITY and BATCH STATISTICS.
  R5  Every cell record links the disc physically inside it through
      `working_electrode_id` (BattINFO#346). `counter_electrode_id` is deliberately
      left unset: the lithium counter electrodes are not individually tracked by
      the source, so there is no disc to point at. The cell spec's counter-electrode
      holder describes them, which is the honest level for a component the study
      treats as interchangeable.

V4.1 is a content patch on top of that build, from the review of the staged corpus.
Four things changed and nothing was re-modelled:

  B3  No `polarity` on the twelve electrode specs. battinfo derives it from the
      kind's family, and derived or not it contradicts both the half-cell ruling
      (D2, no sides to name) and this batch's own voltage convention, in which a
      "negative" graphite design charges to 1.00 V vs Li/Li+.
  B5  Cell names carry the serial: "LNMO-NMP-2 cell 2f9459", the way the disc, the
      test and the dataset are already named. Ninety-five cells sharing twelve
      batch names made a browse listing unreadable. Display text only - identity
      is the (spec, serial) seed and no IRI moves.
  B1  The eleven known issues reach the DATASET, not only the test's conformance
      block: a `Known issue: ...` prefix on the description (which the JSON-LD
      emitter carries) and the full statement in the record's notes. Somebody
      downloading the parquet now learns that "Cell failed at the end of 1st cycle"
      means one usable cycle where the protocol specifies five.
  S5  The Zenodo DOI leaves `provenance.citation`. It stays in the three slots that
      mean self-reference (`access_url`, `same_as`, `is_based_on`) and as the typed
      `kind: "dataset"` self-citation, but the untyped provenance citation is the
      field the platform renders as "Peer-reviewed papers this dataset supports",
      and a dataset cannot be the paper it supports.

Everything that survived rounds 1-3 stands: electrodes named by ROLE, not polarity
(D2); `cell_configuration = half_cell`; one cell spec per electrode design (D1);
the rounding rule (D5); and the license, funding and nine-contributor attribution
on every record.

v2's remodel still stands too: the material spec describes the POWDER and the
electrode spec describes the ELECTRODE. Corpus v1 broke that: it minted nine
"material specs" that were really electrode products and twelve "material lots"
that were really coated electrode batches. Those 21 records are retired here (see
superseded/README.md) and replaced by 7 material specs, 1 material lot, 12
electrode specs and 95 electrode discs.

Deterministic: the script reads two committed source snapshots (``sources/metadata.csv``
and ``sources/zenodo-record.json``, verbatim captures of the Zenodo API), writes the
cell-spec / test-spec drafts it authors from into ``drafts/``, and writes canonical
BattINFO records into ``.battinfo/records/``. Re-running is a no-op: every record
carries a content-derived IRI and unchanged records report ``[unchanged]``.

Records authored (one published Zenodo dataset -> per-test granularity):
  * 1  organization     (Topsoe, into the shared records/organization/ corpus - R2)
  * 7  material specs   (one POWDER per active-material kind - R1)
  * 9  material lots    (one per spec by curator ruling 2026-08-21; LNMO is the
                        one the source evidences, silicon-graphite splits into its
                        three evidenced blends)
  * 12 electrode specs  (one per electrode DESIGN: kind x source x processing route,
                         each citing its powder and carrying the batch statistics)
  * 95 electrodes       (the DISC inside each cell, with its as-built figures - R4)
  * 12 cell specs       (R2032 coin half-cells, cell_configuration = half_cell,
                         one per electrode design - D1)
  * 95 cell instances   (one per parquet; serial = 6-char id, name = "<label> cell
                         <serial>" - B5, each linking its working-electrode disc - R5)
  * 4  test protocols   (p-OCV, p-OCV hold, GITT, GITT hold; structured EMMO method)
  * 95 tests            (cell x protocol; 11 known issues -> conformance)
  * 95 datasets         (each references the published Zenodo parquet + md5 + size,
                         plus the derived plot profile the dataset page renders)

ROUNDING (D5). Every numeric quantity is written through ``q()``, which rounds to a
fixed number of decimals per unit (``_DECIMALS_BY_UNIT``, 6 significant digits where
a unit is not listed). Two kinds of noise disappear: the conversion artifacts this
script used to create (0.0204 g/cm2 * 1000 -> 20.400000000000002 mg/cm2 -> 20.4) and
the full-float-precision columns metadata.csv itself carries for its own derived
values (active-material mass 0.9040957492000021 mg -> 0.9041 mg, the product of a
4-digit coating mass and an 8-digit weight percentage). The decimals are chosen per
physical quantity, at or above the precision the source's own rounded columns use -
``Electrode Loading / g cm-2`` is published to 6 significant digits, and none of the
underlying instrument readings support more. No identity seed contains a number, so
no identifier moves because of this.

DISC IDENTITY (R4). An electrode record's IRI is minted from
``electrode_identity_seed(electrode_spec_id, batch)``, a two-part seed built for one
record per coating batch. Ninety-five discs cut from twelve batches need a third
part, so the seed's batch slot carries the disc's full batch context,
``"<public label>/<6-char cell id>"``, and ``batch_id`` keeps the public label on its
own for display and joins. The uid is computed with BattINFO's own
``entities.stable_uid`` / ``electrode_identity_seed`` - the same primitives the
minting surfaces use - so the identity is deterministic, re-running is a no-op, and
nothing is hand-numbered.

BATCH STATISTICS (R4, closing gap E7). The batch-level aggregates that v3 put on the
twelve electrode-batch records now sit in the ELECTRODE SPEC's property block, as
structured quantities rather than prose. Conventions, applied to all twelve designs
(each is realized by 7-9 discs, so the n >= 2 gate never bites):
  * the mean is over the per-cell rows of metadata.csv for that public label, and
    rides ``value``; the sample (n-1) standard deviation rides ``standard_deviation``
    and the number of discs rides ``sample_count`` (BattINFO#346). Both are emitted
    as named schema:PropertyValue qualifiers on the property node, so the spread is
    machine-readable for the first time and the v3 note text retires;
  * ``min_value`` / ``max_value`` still bracket the observed range where the discs
    differ, as they always did;
  * ``Electrode Loading / g cm-2`` is the ACTIVE-material loading, not the coating
    loading - the column equals active mass / disc area for every row, which is why
    it lands on the mapped key ``loading`` (EMMO ActiveMassLoading);
  * where metadata.csv states ONE value for every cell of a batch (all twelve dry
    thicknesses, and the loading and areal capacity of the three purchased
    electrodes), the mean is that stated value and ``standard_deviation`` is 0.
    Zero is meaningful here and the schema says so: it records that every disc
    carried the same declared number, which is not the same claim as a measured
    spread. The spec's notes say which of the two a reader is looking at.

PER-DISC FIGURES (R4). Each disc carries the six as-built quantities metadata.csv
publishes for its cell, on property keys that resolve to EMMO classes so nothing is
dropped or warned about on the JSON-LD path:

    loading        mg/cm2    ActiveMassLoading         per-cell active-mass loading
    dry_thickness  um        DryCoatingThickness       the batch's stated dry thickness
    areal_capacity mAh/cm2   AreicCapacity             per-cell nominal areal capacity
    diameter       mm        Diameter                  punched disc diameter
    mass           mg        Mass                      the disc's electrode coating mass
    mass_fraction  %         MassFraction              active-material weight percentage

metadata.csv's seventh column, ``Mass of Active Material / mg``, is deliberately not
a seventh key: it is the product of the two columns above it (coating mass x weight
percentage - which is why the source publishes it to sixteen digits), and ``mass``
is the only key in the curated property map that means Mass, so a second mass key
would either fall back to a non-canonical term or collapse onto the first one in
JSON-LD. Both factors are stated exactly, the product is stated in the disc's
comment for a human reader, and no number is lost.

Authoring surface: everything except the datasets is authored through the blessed
``battinfo.workspace()`` API (``ws.add`` / ``ws.load`` / ``ws.save``), including the
new ``ws.add("electrode_spec", ...)`` / ``ws.add("electrode", ...)`` pair. The engine
handle ``ws._ws`` is never touched. Datasets that describe an already-published
remote file have no blessed workspace entry point, so they are built from the public
``battinfo.Dataset`` model and written with the public ``battinfo.save_dataset``;
see READINESS-REPORT.md (gap G1).

Nothing here submits: this build stages records for review only.

Run:  python build_records.py
Requires BattINFO from git main at or after a7661d2 (#346: cell working/counter
electrode links, and standard_deviation / sample_count on a Quantity).
"""
from __future__ import annotations

import csv
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import battinfo as B
from battinfo.authoring import bom, electrode, material, properties
from battinfo.bundle import ChecksumInfo
from battinfo.entities import (
    cell_instance_identity_seed,
    electrode_identity_seed,
    stable_uid,
)
from battinfo.metadata import checksum, distribution, measured_variable

HERE = Path(__file__).resolve().parent
SOURCES = HERE / "sources"
DRAFTS = HERE / "drafts"
RECORDS_ROOT = HERE / ".battinfo" / "records"
PROFILES = HERE / "profiles"
# The shared organization corpus of this repository, where every organization a
# record cites already lives (245 of them, SINTEF among them). Topsoe joins it there
# rather than inside this batch: organizations are corpus-wide, and they are the one
# record type BattINFO does not emit JSON-LD for - a cell spec or material spec cites
# an organization inline, by IRI and name.
ORG_RECORDS = HERE.parents[1] / "records" / "organization"

# Public base of the object store that serves dataset files to the platform. ws.upload()
# writes each distribution to the key datasets/{short_id}/{filename} under this base and
# rewrites the record to match; the plot profiles follow the same convention so the
# upload is a straight sync (see upload_profiles.py) and the URLs here are the final ones.
R2_PUBLIC_BASE = "https://pub-5d124607e4b748eea681efca486508ab.r2.dev"

# SINTEF's registry organization IRI, carried by the cell specs (manufacturer_id) and
# by the manufacturer block of the nine SINTEF-made electrode specs. IREC
# (9hrt-w8hx-7cca-4z2v) is equally live in the registry but has no attachment point
# here: its two people appear only as contributors, and contributor affiliations take
# a plain name, not an organization IRI (see gap G10 in READINESS-REPORT.md).
SINTEF_IRI = "https://w3id.org/battinfo/organization/b4qq-aawd-zesa-kh4q"
DOI = "10.5281/zenodo.20086298"
DOI_URL = f"https://doi.org/{DOI}"
CONCEPT_DOI = "10.5281/zenodo.19107294"
ZENODO_PUBLISHED = "2026-05-08"
PARQUET_MEDIA = "application/vnd.apache.parquet"

# All nine creators of the published record, in Zenodo creator order, all with ORCIDs.
CONTRIBUTORS = [
    ("0000-0003-2954-1233", "Eibar Flores", "SINTEF"),
    ("0009-0006-0805-6713", "Sridevi Krishnamurthi", "SINTEF"),
    ("0000-0002-6299-1319", "Killian Stokes-Rodriguez", "SINTEF"),
    ("0009-0005-4059-7715", "Julie Cathrine Guldahl", "SINTEF"),
    ("0000-0003-0931-5466", "Charifa Hakim", "SINTEF"),
    ("0000-0002-8758-6109", "Simon Clark", "SINTEF"),
    ("0000-0002-8014-4324", "Nils Peter Wagner", "SINTEF"),
    ("0009-0003-1413-0770", "Sergi Obrador", "Institut de Recerca de l'Energia de Catalunya"),
    ("0000-0001-9591-6422", "Andres Bernabeu Santisteban",
     "Institut de Recerca de l'Energia de Catalunya"),
]

# ---------------------------------------------------------------------------
# Level 1: active-material KINDS. Vocabulary entries in BattINFO's curated
# material_kinds, not records - each carries the EMMO class, the chemical-substance
# anchor and the external identity anchors. Under the electrode model the kind is
# what an electrode spec names; a powder record is only authored when the source
# says something about the powder that the kind does not already carry.
# ---------------------------------------------------------------------------
KIND_BY_TOKEN = {
    "graphite": "graphite",
    "silicon": "silicon",
    "silicongraphite": "silicon_graphite",
    "lnmo": "lnmo",
    "lfp": "lfp",
    "nmc111": "nmc111",
    "nmc532": "nmc532",
}

KIND_LABEL = {
    "graphite": "Graphite",
    "silicon": "Silicon",
    "silicon_graphite": "Silicon-graphite composite",
    "lnmo": "LNMO (LiNi0.5Mn1.5O4)",
    "lfp": "LFP (LiFePO4)",
    "nmc111": "NMC111 (LiNi1/3Mn1/3Co1/3O2)",
    "nmc532": "NMC532 (LiNi0.5Mn0.3Co0.2O2)",
}

# NOTE (D2). v1 and v2 carried `positive_electrode_basis` / `negative_electrode_basis`
# on these specs. v3 carries neither: a half cell has no positive and no negative
# side, and describing its electrodes by polarity is the thing the upstream ruling
# rejects. The bases were the last polarity language left after the holders moved to
# working/counter, and dropping them costs nothing that is not stated better
# elsewhere - the working electrode is typed with its chemistry class through the
# electrode spec it cites (SiliconBasedElectrode, LithiumIronPhosphateElectrode, ...),
# the lithium-metal counter electrode is an authored holder rather than a basis
# string, and the cell itself still types as BatteryHalfCell + HalfCellDevice from
# cell_configuration. See docs/electrodes-model.md, "Half cells name their electrodes
# by role, not by polarity".

# Electrode source token -> (organization role, display name, registry IRI).
# The tokens are the batch-identifier field of the dataset's own file-name
# convention ("dataOwner__manufacturer-chemistry-factor-batchID-6characterID"),
# and the Zenodo batch table calls the gelon/customcells ones "commercial
# electrode", so those two are purchased electrodes and the intelligent* ones
# are the electrodes SINTEF coated in the IntelLiGent project.
SOURCE_ORG = {
    "intelligent": ("manufacturer", "SINTEF", SINTEF_IRI),
    "intelligent1": ("manufacturer", "SINTEF", SINTEF_IRI),
    "intelligent2": ("manufacturer", "SINTEF", SINTEF_IRI),
    "gelon": ("supplier", "Gelon LIB", None),
    "customcells": ("supplier", "Customcells", None),
}
SOURCE_LABEL = {
    "intelligent": "IntelLiGent project batch (SINTEF)",
    "intelligent1": "IntelLiGent project batch 1 (SINTEF)",
    "intelligent2": "IntelLiGent project batch 2 (SINTEF)",
    "gelon": "commercial electrode supplied by Gelon LIB",
    "customcells": "commercial electrode supplied by Customcells",
}

# Half-cell voltage cutoffs vs Li/Li+ (lower, upper), from the Zenodo description.
VWINDOW = {
    "graphite": (0.01, 1.00), "silicon": (0.01, 1.00), "silicon_graphite": (0.01, 1.00),
    "lnmo": (3.50, 4.80), "lfp": (2.50, 3.65), "nmc111": (3.00, 4.30), "nmc532": (3.00, 4.30),
}

# Batch-level statements from the Zenodo "Electrode batches" table, keyed by public
# label. These are the source's own words about each batch and are the evidence for
# both the electrode-spec description and the batch note.
BATCH_NOTE = {
    "Gr-AQ-1": "Graphite (aqueous processed).",
    "Si-AQ-1": "Silicon (aqueous processed).",
    "SiGr-AQ-1": "Lower Si % silicon-graphite composite (aqueous processed).",
    "SiGr-AQ-2": "Higher Si % silicon-graphite composite (aqueous processed).",
    "SiGr-AQ-3": "Higher Si % silicon-graphite composite (aqueous processed).",
    "LNMO-AQ-1": "LiNi0.5Mn1.5O4 (aqueous processed); high Mn/Ni disorder spinel.",
    "LNMO-AQ-2": "LiNi0.5Mn1.5O4 (aqueous processed); high Mn/Ni disorder spinel.",
    "LNMO-NMP-1": "LiNi0.5Mn1.5O4 (organic solvent processed); high Mn/Ni disorder spinel.",
    "LNMO-NMP-2": "LiNi0.5Mn1.5O4 (organic solvent processed); high Mn/Ni disorder spinel.",
    "LFP-NMP-1": "LiFePO4 (commercial electrode).",
    "NMC111-NMP-1": "LiNi0.33Mn0.33Co0.33O2 (commercial electrode).",
    "NMC532-NMP-1": "LiNi0.5Mn0.3Co0.2O2 (commercial electrode).",
}

# Human-readable design name per public label. The name is the product half of the
# electrode-spec identity seed (producer, product, grade, kind, route). It is our
# descriptive label, deliberately NOT a fabricated producer part number: the source
# states no product id or grade for any of these electrodes, so `product_id` and
# `grade` are left unset rather than invented.
DESIGN_NAME = {
    "Gr-AQ-1": "Graphite electrode, aqueous processed (IntelLiGent, SINTEF)",
    "Si-AQ-1": "Silicon electrode, aqueous processed (IntelLiGent, SINTEF)",
    "SiGr-AQ-1": "Silicon-graphite electrode, aqueous processed, lower Si % "
                 "(IntelLiGent batch 1, SINTEF)",
    "SiGr-AQ-2": "Silicon-graphite electrode, aqueous processed, higher Si % "
                 "(IntelLiGent batch 2, SINTEF)",
    "SiGr-AQ-3": "Silicon-graphite electrode, aqueous processed, higher Si %, "
                 "'B/Silicon Graphite' active material (IntelLiGent batch 2, SINTEF)",
    "LNMO-AQ-1": "LNMO electrode, aqueous processed (IntelLiGent batch 1, SINTEF)",
    "LNMO-AQ-2": "LNMO electrode, aqueous processed (IntelLiGent batch 2, SINTEF)",
    "LNMO-NMP-1": "LNMO electrode, NMP processed (IntelLiGent batch 1, SINTEF)",
    "LNMO-NMP-2": "LNMO electrode, NMP processed (IntelLiGent batch 2, SINTEF)",
    "LFP-NMP-1": "LFP electrode, NMP processed (commercial, Gelon LIB)",
    "NMC111-NMP-1": "NMC111 electrode, NMP processed (commercial, Customcells)",
    "NMC532-NMP-1": "NMC532 electrode, NMP processed (commercial, Gelon LIB)",
}

# The public label encodes "chemical composition and manufacturing route"
# (metadata schema, Zenodo description), and the batch table spells the route out
# in words ("aqueous processed" / "organic solvent processed"), so the -AQ- /
# -NMP- token is the authors' own statement of the route. Under the electrode
# model the route is part of the DESIGN identity, not a build detail.
ROUTE_TOKENS = {"AQ": ("aqueous", "water"), "NMP": ("nmp", "NMP")}

# ---------------------------------------------------------------------------
# POWDER DISPOSITION (R1). v2 and v3 authored a material spec only where the source
# volunteered something about the POWDER that the kind key did not already carry,
# which left eleven of the twelve electrode designs citing no material at all. The
# round-3 ruling replaces that with a curator-complete policy: every active-material
# kind in the dataset gets a powder record, so every electrode design can cite one.
#
# What "curator-complete" does NOT mean is inventing the missing half. Each powder
# states only what the source states, and its description says out loud what the
# source withholds - a reader should never have to guess whether a blank field means
# "not measured", "not disclosed" or "nobody looked". Kind by kind:
#
#   lnmo             140 mAh/g (one value for all four LNMO batches) and, on the
#                    maintainer's authority, Topsoe as manufacturer. The Zenodo
#                    record adds the one substantive material statement in the whole
#                    dataset: the powder targeted high Mn/Ni disorder.
#   graphite         372 mAh/g. Nothing else is stated - no supplier, no particle
#                    size, no grade.
#   silicon          3579 mAh/g. The description is explicit that the rest is
#                    unavailable: "OCVs from Si-containing electrodes might exhibit
#                    large variations depending on material properties, such as
#                    particle size, crystallinity, surface chemistry, percentage of
#                    silicon in Si-Graphite blends, etc. None of these material and
#                    electrode properties are available from the suppliers."
#   silicon_graphite No theoretical capacity on the powder: metadata.csv states
#                    THREE (510 / 1150 / 900 mAh/g), one per blend, so the number is
#                    a property of each design and stays on the three electrode
#                    specs. The blend ratio is named by the source itself as one of
#                    the properties the suppliers did not provide, so none is stated.
#   lfp, nmc111,     No theoretical capacity at all: metadata.csv leaves the column
#   nmc532           EMPTY for all three. These arrived as finished electrodes
#                    ("commercial electrode" in the batch table) and the suppliers
#                    described them electrode-side (weight percentage, loading,
#                    areal capacity), never powder-side. The powder record exists so
#                    the design has a material to cite, and says exactly that.
#
# The theoretical specific capacity is stated once, never twice: on the powder where
# the source gives one value per kind, on the electrode spec where it gives one per
# design (the three silicon-graphite blends), nowhere where it gives none.
#
# LOT DISPOSITION (R3). A material INSTANCE is a physical batch of powder that was
# opened and used, and is authored only where the source evidences one. It does for
# LNMO and only for LNMO: "The LNMO material used in this study targeted high Mn/Ni
# disorder, therefore the OCVs is a highly disordered spinel" is singular and covers
# the whole study, so the four LNMO designs - two processing routes, two batches
# each - were coated from one powder batch. That is a lot, and it gets a record.
#
# For the other six kinds the source evidences no lot: it names no supplier, no
# batch, no delivery, and for the purchased electrodes it never saw the powder at
# all. A lot record per kind would assert a physical batch nobody wrote down.
#
# MODEL GAP (E8, new in v4). Neither an electrode spec nor an electrode record has a
# field pointing at a material INSTANCE - `active_material_spec_id` and the coating's
# `material_spec_id` both take a spec. So the LNMO lot is linked as far as the model
# allows: the lot cites its spec, the four LNMO electrode specs cite that same spec,
# and the prose on both sides names the other. A structured electrode -> material-lot
# edge is the field this corpus would use next.
# ---------------------------------------------------------------------------

# Topsoe: the LNMO powder's manufacturer, on the maintainer's authority. The Zenodo
# record names no supplier for any powder, so this is the one fact in the corpus that
# comes from outside the source, and it is attributed as such on the material spec.
#
# The IRI is minted from a stated seed rather than drawn at random the way
# scripts/sync_battery_knowledge_graph.py mints its BKG stubs, because this script
# must be re-runnable: a random id would give the organization a new identity on
# every build. The value is pinned so a change in the minting primitive fails the
# build instead of silently moving a published identifier.
#
# NOTE FOR REVIEW: records/organization/haldor-topsoe/ already holds a Battery
# Knowledge Graph stub for the same company under its pre-2022 legal name (IRI
# j50f-3ebx-sssw-svnm). The two are the same legal entity and should be merged
# before anything here is published; this record carries the former name in
# `alternateName` so the duplicate is findable rather than silent. Flagged in
# README-semantic-layer.md and in the pull request.
TOPSOE_SEED = "organization::topsoe"
TOPSOE_IRI = "https://w3id.org/battinfo/organization/vz1v-rvhz-n77h-344c"
TOPSOE_NAME = "Topsoe"
TOPSOE_SLUG = "topsoe"

# name, formula, chemistry family, and the sentence that says what the source does
# not report about this powder. `theoretical_capacity` is not listed here: it is read
# from metadata.csv, so the numbers in the corpus always come from the source file.
POWDERS = {
    "graphite": dict(
        name="Graphite active material",
        formula="C",
        family="graphitic-carbon",
        summary="Graphite active material of the aqueous-processed graphite electrodes of "
                "this dataset.",
        withheld="The source names no supplier, grade, particle size or surface area for "
                 "this powder; only its theoretical specific capacity is published.",
    ),
    "silicon": dict(
        name="Silicon active material",
        formula="Si",
        family="silicon",
        summary="Silicon active material of the aqueous-processed silicon electrodes of "
                "this dataset.",
        withheld="The Zenodo record states that particle size, crystallinity and surface "
                 "chemistry of the silicon-containing materials \"are not available from "
                 "the suppliers\", so none is stated here; only the theoretical specific "
                 "capacity is published.",
    ),
    "silicon_graphite": dict(
        name="Silicon-graphite composite active material",
        formula=None,
        family="silicon-graphite-composite",
        summary="Silicon-graphite composite active material of the aqueous-processed "
                "Si-Gr electrodes of this dataset.",
        withheld="No theoretical specific capacity is stated on this powder because the "
                 "source states three different ones - 510, 900 and 1150 mAh/g - one for "
                 "each of the three blends used, so the number belongs to the electrode "
                 "design and is carried there. The blend ratio itself is named by the "
                 "Zenodo record as one of the properties the suppliers did not provide.",
    ),
    "lnmo": dict(
        name="LNMO (LiNi0.5Mn1.5O4), high Mn/Ni disorder spinel",
        formula="LiNi0.5Mn1.5O4",
        family="spinel",
        summary="LNMO active material used across all four LNMO electrode batches of the "
                "dataset, aqueous and NMP processed alike. The study targeted high Mn/Ni "
                "disorder, so these OCVs are those of a highly disordered spinel.",
        withheld="The Zenodo record gives no grade or product identifier for the powder, "
                 "and no supplier; the manufacturer stated here was supplied by the "
                 "corpus maintainer, not by the source.",
    ),
    "lfp": dict(
        name="LFP (LiFePO4) active material",
        formula="LiFePO4",
        family="olivine",
        summary="LFP active material of the commercial LFP electrode supplied by Gelon "
                "LIB for this dataset.",
        withheld="This electrode was purchased finished, so the source describes it "
                 "electrode-side only: metadata.csv leaves the theoretical specific "
                 "capacity column empty and names no powder supplier, grade or "
                 "identifier. This record exists so the electrode design has a material "
                 "to name, and asserts nothing the supplier did not.",
    ),
    "nmc111": dict(
        name="NMC111 (LiNi1/3Mn1/3Co1/3O2) active material",
        formula="LiNi0.33Mn0.33Co0.33O2",
        family="layered-oxide",
        summary="NMC111 active material of the commercial NMC111 electrode supplied by "
                "Customcells for this dataset.",
        withheld="This electrode was purchased finished, so the source describes it "
                 "electrode-side only: metadata.csv leaves the theoretical specific "
                 "capacity column empty and names no powder supplier, grade or "
                 "identifier. This record exists so the electrode design has a material "
                 "to name, and asserts nothing the supplier did not.",
    ),
    "nmc532": dict(
        name="NMC532 (LiNi0.5Mn0.3Co0.2O2) active material",
        formula="LiNi0.5Mn0.3Co0.2O2",
        family="layered-oxide",
        summary="NMC532 active material of the commercial NMC532 electrode supplied by "
                "Gelon LIB for this dataset.",
        withheld="This electrode was purchased finished, so the source describes it "
                 "electrode-side only: metadata.csv leaves the theoretical specific "
                 "capacity column empty and names no powder supplier, grade or "
                 "identifier. This record exists so the electrode design has a material "
                 "to name, and asserts nothing the supplier did not.",
    ),
}

LNMO_DISORDER_NOTE = (
    "The Zenodo record states: \"The OCVs from LiNi0.5Mn1.5O4 (LNMO) electrodes vary "
    "depending on the degree of Mn/Ni disorder (see Sun et al.). The LNMO material used "
    "in this study targeted high Mn/Ni disorder, therefore the OCVs is a highly "
    "disordered spinel.\" No grade or product identifier is given for the powder, so "
    "none is stated here."
)

# The one lot the source evidences (R3). "The LNMO material used in this study" is
# singular and covers all four LNMO designs, so the lot label says exactly that and
# nothing that looks like a supplier batch number, which the source does not give.
LNMO_LOT_LABEL = "study powder batch"

PROTOCOLS = {
    "p-ocv": dict(
        name="p-OCV", type="quasi_ocv", hold=False, technique="quasi_ocv",
        desc=("Constant current cycling at C/50. A rest period of 8 h is applied upon "
              "reaching the upper and lower voltage cutoffs. 5 cycles, room temperature.")),
    "p-ocvhold": dict(
        name="p-OCV hold", type="quasi_ocv", hold=True, technique="quasi_ocv",
        desc=("Constant current cycling at C/50. The voltage is held for 6 h under "
              "potentiostatic control upon reaching the upper and lower voltage cutoffs. "
              "5 cycles, room temperature.")),
    "gitt": dict(
        name="GITT", type="gitt", hold=False, technique="gitt",
        desc=("Sequence of current pulses (C/50) followed by a period of rest (150 minutes). "
              "A rest period of 6 h is applied upon reaching the upper and lower voltage "
              "cutoffs. 5 cycles, room temperature.")),
    "gitthold": dict(
        name="GITT hold", type="gitt", hold=True, technique="gitt",
        desc=("Sequence of current pulses (C/50) followed by a period of rest (150 minutes). "
              "The voltage is held for 6 h under potentiostatic control upon reaching the "
              "upper and lower voltage cutoffs. 5 cycles, room temperature.")),
}

# 7 BDF data columns, from the Zenodo "Dataset Schema" table.
BDF_COLUMNS = [
    ("Test Time / s", "s", "Elapsed time since the start of the test"),
    ("Unix Time / s", "s", "Timestamp in Unix time format (seconds since 1970-01-01 UTC)"),
    ("Current / A", "A", "Instantaneous current"),
    ("Voltage / V", "V", "Instantaneous voltage"),
    ("Cumulative Capacity / Ah", "Ah", "Total capacity accumulated over a half cycle"),
    ("Cycle Count / 1", "1", "Monotonically increasing index of test cycles"),
    ("Step Index / 1", "1", "Index of the instantaneous step type within the measurement protocol"),
]

FILENAME_RE = re.compile(
    r"sintef__sintef-(?P<mat>[a-z0-9]+)-R2032-(?P<src>[a-z0-9]+)-(?P<hex>[0-9a-f]{6})"
    r"__(?P<date>\d{8})__(?P<proto>[a-z-]+)__RT\.bdf\.parquet"
)


# --------------------------------------------------------------------------- helpers
def num(value):
    value = (value or "").strip()
    if value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def yyyymmdd(value: str) -> str:
    return f"{value[0:4]}-{value[4:6]}-{value[6:8]}"


# D5: decimals per unit. Every quantity this script writes is rounded here, so the
# rule lives in one place and cannot drift between the design values, the per-cell
# test conditions and the batch statistics. A unit that is not listed falls back to
# 6 significant digits - the precision metadata.csv itself publishes for the one
# derived column its authors rounded (`Electrode Loading / g cm-2`).
_DECIMALS_BY_UNIT = {
    "mm": 2,        # disc diameter, stated to the millimetre
    "um": 1,        # dry thickness, stated to the micrometre
    "mg": 4,        # active-material mass, ~1 mg on a microbalance
    "g": 6,         # coating mass, stated as 0.001064 g
    "%": 3,         # weight percentage
    "mg/cm2": 4,    # active-mass loading
    "mAh/cm2": 4,   # areal capacity
    "mAh/g": 1,     # theoretical specific capacity
    "V": 3,         # voltage cutoffs
    "A/Ah": 4,      # C-rate
    "h": 3,
    "min": 3,
    "s": 3,
}


def _round(value, unit):
    """Round one numeric value for *unit*; pass anything else through unchanged.

    An integer stays an integer. Rounding is here to remove noise, not to turn a
    stated ``8`` hours into ``8.0``.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return value
    if isinstance(value, int):
        return value
    decimals = _DECIMALS_BY_UNIT.get(unit)
    if decimals is None:
        return float(f"{value:.6g}")
    return round(value, decimals)


def q(value, unit, *, min_value=None, max_value=None):
    """A Quantity, rounded (D5). ``min_value`` / ``max_value`` bracket an observed
    spread; they are schema.org QuantitativeValue fields, kept in the canonical
    record (the JSON-LD emitter carries the primary value only, by design)."""
    node = {"value": _round(value, unit), "unit": unit}
    if min_value is not None:
        node["min_value"] = _round(min_value, unit)
    if max_value is not None:
        node["max_value"] = _round(max_value, unit)
    return node


def spread(values: list[float]) -> dict | None:
    """Mean / sample standard deviation / n / min / max of per-cell values.

    ``None`` below two values: a single cell has no batch statistics. The standard
    deviation is the sample (n-1) one, because the cells of a batch are a sample of
    the coated web, not the population of interest.
    """
    if len(values) < 2:
        return None
    return {
        "mean": statistics.fmean(values),
        "sd": statistics.stdev(values),
        "n": len(values),
        "min": min(values),
        "max": max(values),
    }


def aggregate(stats: dict | None, unit: str) -> dict | None:
    """A batch statistic as one Quantity: mean, spread, n, and the observed range.

    R4/E7: ``standard_deviation`` and ``sample_count`` are schema fields on a
    Quantity since BattINFO#346, so the spread that v3 could only write as prose is
    now structured and survives into the JSON-LD as named qualifiers of the property
    node. ``min_value`` / ``max_value`` are only written where the discs actually
    differ - a range on a single declared value would read as a measurement.
    """
    if stats is None:
        return None
    varies = stats["max"] > stats["min"]
    node = q(
        stats["mean"], unit,
        min_value=stats["min"] if varies else None,
        max_value=stats["max"] if varies else None,
    )
    node["standard_deviation"] = _round(stats["sd"], unit)
    node["sample_count"] = stats["n"]
    return node


def load_metadata() -> list[dict]:
    rows = []
    with (SOURCES / "metadata.csv").open(encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            name = r["BDF names"]
            m = FILENAME_RE.match(name)
            if not m:
                raise SystemExit(f"Unrecognised BDF filename: {name}")
            rows.append({
                "file": name, "kind": KIND_BY_TOKEN[m["mat"]], "src": m["src"],
                "hex": m["hex"], "date": m["date"], "proto": m["proto"],
                "label": r["Public Labels"].strip(),
                "am_type": (r["Active Material type"] or "").strip(),
                "am_mass_mg": num(r["Mass of Active Material / mg"]),
                "coating_mass_g": num(r["Electrode Coating Mass / g"]),
                "wt_pct": num(r["Weight percentage of Active Material / %"]),
                "theo_mahg": num(r["Theoretical Capacity /  mAh g-1"]),
                "diam_mm": num(r["Electrode Diameter / mm"]),
                "thick_um": num(r["Dry Thickness / um"]),
                "areal_mahcm2": num(r["Nominal Areal Capacity / mAh cm-2"]),
                "loading_gcm2": num(r["Electrode Loading / g cm-2"]),
                "issue": (r["Known Issues"] or "").strip(),
            })
    return rows


def load_zenodo_files() -> dict[str, dict]:
    doc = json.loads((SOURCES / "zenodo-record.json").read_text(encoding="utf-8"))
    out = {}
    for f in doc["files"]:
        key = f["key"]
        if not key.endswith(".parquet"):
            continue
        _algo, _, digest = f["checksum"].partition(":")
        out[key] = {"md5": digest, "size": int(f["size"]), "url": f["links"]["self"]}
    return out


def route_for(label: str) -> tuple[str, str] | None:
    """Processing route from the public label, or None when not determinable."""
    for token, route in ROUTE_TOKENS.items():
        if f"-{token}-" in label:
            return route
    return None


def only_value(items, field):
    """The single distinct value of *field* across *items*, else None."""
    values = {i[field] for i in items if i[field] is not None}
    return values.pop() if len(values) == 1 else None


def deviation_for(issue: str) -> dict:
    """Map a free-text known issue onto the typed deviation vocabulary."""
    low = issue.lower()
    if "failed" in low or "stopped" in low:
        category = "premature_termination"
    elif "anomalous" in low or "high voltage" in low:
        category = "out_of_tolerance"
    else:
        category = "other"
    return {"category": category, "description": issue}


def known_issue_note(issue: str) -> str:
    """The dataset-level statement of a known issue (B1).

    A known issue is a fact about the DATA, not only about the run that produced
    it. v4 carried it on the test record's `conformance` block alone, so somebody
    who reached the dataset page, or downloaded the parquet from Zenodo, got no
    warning at all - "Cell failed at the end of 1st cycle" means one usable cycle
    where the protocol specifies five, and that is exactly what a consumer of the
    file needs to know first. The same sentence now rides the dataset: as a
    `Known issue:` prefix on the description, which is the one field the JSON-LD
    emitter carries into `dcterms:description` / `schema:description`, and in
    full here, in the record's notes.
    """
    category = deviation_for(issue)["category"]
    text = (
        f"Known issue reported by the source for this measurement: {issue}. The test "
        f"record that produced this file states it as a conformance deviation "
        f"(status non-conformant, category {category}); it is repeated here so the "
        f"warning travels with the data rather than only with the test.")
    if category == "premature_termination":
        text += (" The protocol specifies 5 cycles and this run did not finish them, "
                 "so the file holds fewer cycles than the protocol describes.")
    return text


C50 = {"c_rate": q(0.02, "A/Ah")}


def _cc(direction: str, description: str) -> dict:
    return {"mode": "cc", "direction": direction, "setpoints": C50, "description": description}


def _rest(value: float, unit: str, description: str) -> dict:
    return {"mode": "rest", "duration": q(value, unit), "description": description}


def _hold(description: str) -> dict:
    return {"mode": "cv", "duration": q(6, "h"), "description": description}


def _pulse_train(direction: str, where: str) -> dict:
    return {"mode": "group",
            "description": f"Current pulses at C/50 with 150-minute rests toward the "
                           f"{where} voltage cutoff",
            "steps": [_cc(direction, "Current pulse at C/50"),
                      _rest(150, "min", "Rest for 150 minutes")]}


def build_method(key: str) -> list[dict]:
    """Structured, material-agnostic method. The per-material voltage cutoffs live
    on the cell spec, so one protocol record serves all nine half-cell specs."""
    p = PROTOCOLS[key]

    def cutoff_step(where: str) -> dict:
        if p["hold"]:
            return _hold(f"Potentiostatic hold for 6 h at the {where} voltage cutoff")
        hours = 6 if p["type"] == "gitt" else 8
        return _rest(hours, "h", f"Rest for {hours} h at the {where} voltage cutoff")

    if p["type"] == "quasi_ocv":
        inner = [
            _cc("discharge", "Constant current at C/50 to the lower voltage cutoff"),
            cutoff_step("lower"),
            _cc("charge", "Constant current at C/50 to the upper voltage cutoff"),
            cutoff_step("upper"),
        ]
    else:
        inner = [
            _pulse_train("discharge", "lower"), cutoff_step("lower"),
            _pulse_train("charge", "upper"), cutoff_step("upper"),
        ]
    return [{"mode": "group", "count": 5, "description": "5 cycles", "steps": inner}]


def write_draft(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def write_topsoe_organization() -> str:
    """Write the Topsoe organization record into the shared corpus (R2).

    Organizations are not workspace records - BattINFO has no ``ws.add`` entry point
    and no JSON-LD emitter for them, because a record cites an organization inline by
    IRI and name. They live in ``records/organization/<slug>/record.json``, one per
    directory, and this writes Topsoe there in exactly the shape the other 245 use.
    Idempotent: the IRI is derived from a pinned seed and the file is rewritten only
    when its content changes.
    """
    minted = f"https://w3id.org/battinfo/organization/{stable_uid(TOPSOE_SEED)}"
    if minted != TOPSOE_IRI:
        raise SystemExit(
            f"Topsoe IRI drift: seed {TOPSOE_SEED!r} now mints {minted}, but the corpus "
            f"pins {TOPSOE_IRI}. Reconcile before rebuilding."
        )
    record = {
        "schema_version": "0.1.0",
        "organization": {
            "id": TOPSOE_IRI,
            "short_id": TOPSOE_IRI.rsplit("/", 1)[-1].replace("-", "")[:8],
            "type": "Corporation",
            "name": TOPSOE_NAME,
            "alternateName": ["Haldor Topsoe", "Haldor Topsoe A/S"],
            "url": "https://www.topsoe.com/",
            "description": (
                "Danish catalyst and materials company. Named by the corpus maintainer as "
                "the manufacturer of the LNMO active material measured in Zenodo record "
                f"{DOI}; the published record itself names no supplier for any of its "
                "active materials."),
            "location": {"addressCountry": "DK"},
        },
        "provenance": {
            "source_type": "manual",
            "source_url": DOI_URL,
            "retrieved_at": None,
        },
        "editorial": {
            "review_status": "stub",
            "note": (
                "Created for the Flores half-cell OCV batch, from a fact supplied by the "
                "corpus maintainer rather than by the source record. "
                "records/organization/haldor-topsoe/ is a Battery Knowledge Graph stub for "
                "the same legal entity under its pre-2022 name and should be merged into "
                "this record before either is published."),
        },
    }
    record["provenance"] = {k: v for k, v in record["provenance"].items() if v is not None}
    path = ORG_RECORDS / TOPSOE_SLUG / "record.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(record, indent=2, ensure_ascii=False) + "\n"
    state = "unchanged"
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8")
        state = "written"
    print(f"  organization:   {TOPSOE_NAME}  {TOPSOE_IRI}  [{state}]")
    return TOPSOE_IRI


# --------------------------------------------------------------------------- main
def main() -> int:
    rows = load_metadata()
    zfiles = load_zenodo_files()

    ws = B.workspace(root=str(HERE), registry_url=None)
    ws.license("cc-by-4.0")
    for orcid, name, affiliation in CONTRIBUTORS:
        ws.contributor(orcid, name=name, affiliation=affiliation)
    # Explicit project fields (the values the OpenAIRE/CORDIS resolver returns) so
    # the run is offline and deterministic.
    ws.project(
        "101069765",
        name="Innovative and Sustainable High Voltage Li-ion Cells for Next Generation (EV) Batteries",
        acronym="IntelLiGent", funder="European Commission", program="HE",
        id="https://cordis.europa.eu/project/id/101069765",
    )

    # D1: the cell-spec grouping key is (kind, electrode source, electrode DESIGN),
    # so every cell spec is realized by exactly one electrode design and can cite it.
    # v2 grouped on (kind, source) alone, which put two designs under one spec three
    # times over.
    by_cell_spec: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    by_batch: dict[str, list[dict]] = defaultdict(list)
    designs_per_source: dict[tuple[str, str], set[str]] = defaultdict(set)
    for r in rows:
        by_cell_spec[(r["kind"], r["src"], r["label"])].append(r)
        by_batch[r["label"]].append(r)
        designs_per_source[(r["kind"], r["src"])].add(r["label"])

    # --- 0. The Topsoe organization (R2) ----------------------------------------
    print("\n== organization ==")
    topsoe_iri = write_topsoe_organization()

    # --- 1. Material specs: one powder per active-material kind (R1) -------------
    # Curator-complete: seven records, one per kind, so all twelve electrode designs
    # can cite their active material. See POWDER DISPOSITION above for what each one
    # states and - just as important - what it says the source does not report.
    print("\n== material specs (powders) ==")
    material_spec_by_kind: dict[str, str] = {}
    material_spec_records: dict[str, dict] = {}
    lnmo_spec = None
    for kind in sorted({r["kind"] for r in rows}):
        powder = POWDERS[kind]
        kind_rows = [r for r in rows if r["kind"] == kind]
        # One value across the kind's rows, or None where the source states several
        # (silicon-graphite) or none at all (LFP, NMC111, NMC532).
        theo = only_value(kind_rows, "theo_mahg")
        fields: dict = {
            "name": powder["name"],
            "kind": kind,
            "material_class": "active_material",
            "chemistry_family": powder["family"],
            "description": f"{powder['summary']} {powder['withheld']}",
            "source_type": "literature",
            "citation": DOI_URL,
        }
        if theo:
            fields["property"] = {"theoretical_capacity": q(theo, "mAh/g")}
        if powder["formula"]:
            fields["formula"] = powder["formula"]
        notes: list[str] = []
        if kind == "lnmo":
            # The manufacturer is part of the material-spec identity seed, so this is
            # also what separates the LNMO powder's IRI from an anonymous one.
            fields["manufacturer"] = {
                "type": "Organization", "name": TOPSOE_NAME, "id": topsoe_iri}
            notes.append(LNMO_DISORDER_NOTE)
            notes.append(
                f"Manufacturer: {TOPSOE_NAME}. Supplied by the corpus maintainer, not by "
                f"the Zenodo record, which names no supplier for any active material.")
        else:
            notes.append(
                "No manufacturer or supplier is stated: the source names none for this "
                "powder, and the field is left unset rather than guessed.")
        if not theo:
            notes.append(powder["withheld"])
        fields["notes"] = notes
        record = ws.add("material_spec", **fields)[0]
        material_spec_by_kind[kind] = record["material_spec"]["id"]
        material_spec_records[kind] = record
        if kind == "lnmo":
            lnmo_spec = record
    lnmo_spec_id = material_spec_by_kind["lnmo"]

    # --- 1b. The one material lot the source evidences (R3) ----------------------
    # See LOT DISPOSITION above: one study powder for all four LNMO designs, and no
    # lot for any other kind. Model gap E8 - no electrode-side field points at a
    # material instance - so the link is carried by the shared material spec plus
    # prose on both sides.
    print("\n== material lots ==")
    lnmo_labels = sorted({r["label"] for r in rows if r["kind"] == "lnmo"})
    lnmo_lot = ws.add(
        "material",
        spec=lnmo_spec,
        lot=LNMO_LOT_LABEL,
        name=f"LNMO {LNMO_LOT_LABEL}",
        source_type="literature",
        citation=DOI_URL,
        notes=[
            "The single batch of LNMO powder this study coated. The Zenodo record speaks "
            "of \"the LNMO material used in this study\" in the singular while describing "
            "four electrode batches across two processing routes, so one lot supplied all "
            f"of them: {', '.join(lnmo_labels)}. No supplier lot number is published, so "
            "the label states what the lot is rather than inventing an identifier.",
            "No `processing` block: this one lot was coated by BOTH routes - two aqueous "
            "designs and two NMP ones - so no single route describes it. The route is a "
            "design decision and is carried by each electrode spec, which is where it is "
            "also part of the identity seed.",
            "The four LNMO electrode designs are coated from this lot. They cannot point "
            "at it directly: an electrode spec links a material SPEC "
            "(`active_material_spec_id`) and an electrode record links no material at "
            "all, so the electrode -> material-lot edge has no field in the model "
            "(gap E8). Both sides name the other in prose until it does.",
            "Every material spec carries at least one lot record (curator ruling, "
            "2026-08-21); this one is the only lot the source itself evidences in "
            "the singular.",
        ],
    )[0]
    lnmo_lot_id = lnmo_lot["material"]["id"]
    material_lot_ids: list[str] = [lnmo_lot_id]

    # --- 1c. A lot for every other spec (curator ruling, 2026-08-21) -------------
    # "We need both": every material spec gets a material instance. Three honest
    # flavours, matched to what the source supports:
    #   * SINTEF-coated single-blend kinds (graphite, silicon): the study coated
    #     the powder, so a physical batch necessarily existed; the single-lot
    #     claim is curator-asserted (no lot identity is published).
    #   * silicon_graphite: the source evidences THREE distinct blends - the
    #     designs state different theoretical specific capacities (510, 1150,
    #     900 mAh/g) - so one lot per blend, not one for the kind.
    #   * Purchased-electrode kinds (lfp, nmc111, nmc532): the powder exists only
    #     inside the finished electrodes and the study never handled it; the lot
    #     record asserts that batch's existence and nothing more.
    coated_single = {
        "graphite": "Gr-AQ-1",
        "silicon": "Si-AQ-1",
    }
    purchased_supplier = {
        "lfp": "Gelon LIB",
        "nmc111": "Customcells",
        "nmc532": "Gelon LIB",
    }
    for kind, label in sorted(coated_single.items()):
        lot_record = ws.add(
            "material",
            spec=material_spec_records[kind],
            lot=LNMO_LOT_LABEL,
            name=f"{POWDERS[kind]['name'].split(' active material')[0]} {LNMO_LOT_LABEL}",
            source_type="literature",
            citation=DOI_URL,
            notes=[
                f"The batch of {kind.replace('_', '-')} powder SINTEF coated as {label}. "
                "The study necessarily handled a physical batch to coat it; the "
                "single-lot claim is the corpus maintainer's (curator ruling, "
                "2026-08-21) - the source publishes no lot identity.",
                "No `processing` block: the route is a design decision and is carried "
                "by the electrode spec.",
            ],
        )[0]
        material_lot_ids.append(lot_record["material"]["id"])
    sigr_blends = sorted(
        {(r["label"], r["theo_mahg"]) for r in rows if r["kind"] == "silicon_graphite"}
    )
    for label, theo in sigr_blends:
        lot_record = ws.add(
            "material",
            spec=material_spec_records["silicon_graphite"],
            lot=f"{label} blend",
            name=f"Silicon-graphite blend coated as {label}",
            source_type="literature",
            citation=DOI_URL,
            notes=[
                f"The silicon-graphite blend SINTEF coated as {label}, stated at "
                f"{theo:g} mAh/g theoretical specific capacity. The three "
                "silicon-graphite designs state three different capacities (510, "
                "1150, 900 mAh/g), so they are three distinct physical blends and "
                "each gets its own lot; the blend ratios themselves are among the "
                "properties the source says the suppliers did not provide.",
            ],
        )[0]
        material_lot_ids.append(lot_record["material"]["id"])
    for kind, supplier in sorted(purchased_supplier.items()):
        lot_record = ws.add(
            "material",
            spec=material_spec_records[kind],
            lot="powder within the purchased electrodes",
            name=f"{POWDERS[kind]['name'].split(' active material')[0]} powder within the purchased electrodes",
            source_type="literature",
            citation=DOI_URL,
            notes=[
                f"The batch of powder inside the finished electrodes {supplier} "
                "supplied. Its existence is certain - the material is physically in "
                "the cells - but the study never handled the powder separately, and "
                "no supplier, grade or lot identity is published for it. This record "
                "asserts the batch and nothing more (curator ruling, 2026-08-21).",
            ],
        )[0]
        material_lot_ids.append(lot_record["material"]["id"])

    # --- 2. Electrode specs: one per electrode DESIGN ---------------------------
    # The design key is (kind, electrode source, processing route). In this dataset
    # that resolves 1:1 onto the twelve public labels, because the two designs that
    # share a key - SiGr-AQ-2 and SiGr-AQ-3, both silicon-graphite / IntelLiGent
    # batch 2 / aqueous - state different theoretical specific capacities for their
    # active material (1150 vs 900 mAh/g) and different active-material type labels
    # ("Silicon Graphite" vs "B/Silicon Graphite"), i.e. they are built from
    # different blends and are different designs.
    #
    # The route is part of the identity seed (producer, product, grade, kind, route),
    # which is why LNMO-AQ-1 and LNMO-NMP-1 are two designs and not one.
    print("\n== electrode specs (designs) ==")
    electrode_spec_by_label: dict[str, dict] = {}
    for label, items in sorted(by_batch.items()):
        r0 = items[0]
        kind = r0["kind"]
        route = route_for(label)
        role, org, org_iri = SOURCE_ORG[r0["src"]]
        producer = {"type": "Organization", "name": org, "id": org_iri} if org_iri else org

        design: dict = {}
        diam = only_value(items, "diam_mm")
        if diam is not None:
            design["diameter"] = q(diam, "mm")

        # R4: the batch statistics that v3 wrote as prose on the electrode BATCH
        # record now sit here, on the design, as structured quantities. There is no
        # batch record left to hold them - the electrode record is the disc in one
        # cell - and the design is the only level at which "the discs that realize
        # this" is a set. Mean + sample standard deviation + n over the per-cell rows
        # of metadata.csv; see BATCH STATISTICS in the module docstring.
        loading_stats = spread([r["loading_gcm2"] * 1000.0
                                for r in items if r["loading_gcm2"] is not None])
        thickness_stats = spread([r["thick_um"] for r in items if r["thick_um"] is not None])
        areal_stats = spread([r["areal_mahcm2"] for r in items if r["areal_mahcm2"] is not None])
        stat_notes: list[str] = []
        for key, unit, stats, what in (
            # Reported in g/cm2; expressed in mg/cm2, the symbol that resolves to a
            # dereferenceable EMMO unit. Same quantity, no rounding beyond float.
            ("loading", "mg/cm2", loading_stats, "Active-mass loading"),
            ("dry_thickness", "um", thickness_stats, "Dry thickness"),
            ("areal_capacity", "mAh/cm2", areal_stats, "Nominal areal capacity"),
        ):
            node = aggregate(stats, unit)
            if node is None:
                continue
            design[key] = node
            if stats["max"] > stats["min"]:
                stat_notes.append(
                    f"{what}: mean {node['value']} {unit}, sample standard deviation "
                    f"{node['standard_deviation']} {unit} over n = {stats['n']} discs "
                    f"(range {node['min_value']}-{node['max_value']} {unit}). Computed "
                    f"from the per-cell values metadata.csv publishes for this batch and "
                    f"carried on the quantity itself, not in this note.")
            else:
                stat_notes.append(
                    f"{what}: {node['value']} {unit} for every one of the {stats['n']} "
                    f"discs. metadata.csv states this one value per cell, so the standard "
                    f"deviation is 0 by construction - a repeated declaration, not a "
                    f"measured spread.")
        # Theoretical specific capacity is a property of the active material and
        # normally lives on the powder. It rides the design only where the source
        # states one value PER DESIGN rather than per kind, which happens for the
        # three silicon-graphite blends and nowhere else.
        theo = only_value(items, "theo_mahg")
        kind_theo = only_value([r for r in rows if r["kind"] == kind], "theo_mahg")
        if theo is not None and kind_theo is None:
            design["theoretical_capacity"] = q(theo, "mAh/g")

        fields: dict = {
            "name": DESIGN_NAME[label],
            "kind": kind,
            "manufacturer": producer,
            "active_material_spec_id": material_spec_by_kind[kind],
            "description": (
                f"{BATCH_NOTE[label]} Electrode design of the {SOURCE_LABEL[r0['src']]}, "
                f"published under the label {label}. Active-material type as stated in "
                f"metadata.csv: \"{r0['am_type']}\"."),
            "property": design or None,
            "source_type": "literature",
            "citation": DOI_URL,
        }
        wt = only_value(items, "wt_pct")
        if wt is not None:
            # Only the active-material weight percentage is stated; the balance of
            # binder and additive is not reported and is not invented.
            fields["composition"] = {"active": {"fraction": q(wt, "%")}}
        if route is not None:
            route_word = "Aqueous" if route[0] == "aqueous" else "Organic-solvent"
            fields["processing"] = {
                "route": route[0], "solvent": route[1],
                "detail": f"{route_word} electrode coating ({route[1]}), as stated by the "
                          f"public electrode label {label} and the Zenodo batch table.",
            }
        notes = [
            f"Design values are as published in metadata.csv for batch {label}, the one "
            f"batch that realizes this design. The as-built figures of each individual "
            f"disc are on the {len(items)} electrode records that cite this spec.",
            *stat_notes,
        ]
        if theo is not None and kind_theo is None:
            notes.append(
                f"Theoretical specific capacity is stated here rather than on the powder "
                f"because the source gives a different value for each "
                f"{KIND_LABEL[kind].lower()} blend ({theo:.0f} mAh/g for this one), which "
                f"makes it a property of the design.")
        if kind == "lnmo":
            notes.append(
                f"Coated from the LNMO study powder lot {lnmo_lot_id}. The link runs "
                f"through the material spec: no field on an electrode spec or an "
                f"electrode record points at a material INSTANCE (gap E8).")
        fields["notes"] = notes
        record = ws.add("electrode_spec", **fields)[0]
        # B3 (D2). battinfo derives `polarity` from the kind's family, so an anode
        # kind writes "negative" and a cathode kind "positive" without anyone
        # authoring either. This corpus drops the field. It is a sound field in the
        # model - a design's intended full-cell side is a real fact for a design
        # that has one - but it is not a fact THIS source states, and here it says
        # two wrong things at once: it re-introduces the polarity language D2 removed
        # from every other record in the batch, and it contradicts the batch's own
        # voltage convention, in which a "negative" graphite design is charged to
        # 1.00 V vs Li/Li+. Nothing else is lost: the JSON-LD emitter resolves the
        # chemistry class (GraphiteElectrode, SiliconGraphiteElectrode, ...) from
        # `kind` alone, and only the Positive/NegativeElectrode class drops out.
        record["electrode_spec"].pop("polarity", None)
        electrode_spec_by_label[label] = record

    # --- 3. Electrodes: the disc inside each cell (R4) ---------------------------
    # One electrode record per cell, 95 of them: the working-electrode disc that was
    # punched from the batch, weighed, and built into that coin cell. The as-built
    # figures metadata.csv publishes are per-CELL, so this is where they belong -
    # v3 had to park them on `test.conditions` for want of a per-cell electrode slot
    # (gap G2), and that workaround retires with this ruling.
    #
    # Identity: see DISC IDENTITY in the module docstring. `batch_id` stays the public
    # label, which is what joins a disc to its batch and to the Zenodo batch table.
    print("\n== electrodes (discs) ==")
    electrode_by_hex: dict[str, dict] = {}
    for r in rows:
        label = r["label"]
        spec = electrode_spec_by_label[label]
        spec_id = spec["electrode_spec"]["id"]

        as_built: dict = {}
        if r["loading_gcm2"] is not None:
            as_built["loading"] = q(r["loading_gcm2"] * 1000.0, "mg/cm2")
        if r["thick_um"] is not None:
            as_built["dry_thickness"] = q(r["thick_um"], "um")
        if r["areal_mahcm2"] is not None:
            as_built["areal_capacity"] = q(r["areal_mahcm2"], "mAh/cm2")
        if r["diam_mm"] is not None:
            as_built["diameter"] = q(r["diam_mm"], "mm")
        if r["coating_mass_g"] is not None:
            # `mass` is the disc's electrode coating mass. See PER-DISC FIGURES: it
            # is the only curated key that means Mass, so the active-material mass is
            # carried as its two exact factors (this and `mass_fraction`) rather than
            # as a second key that would collapse onto this one in JSON-LD.
            #
            # Stated in mg, not the source's g. Same quantity; mg is the scale of an
            # electrode disc (metadata.csv already uses it for the active-material
            # mass), and the semantic validator's plausible range for a mass in grams
            # is a whole-cell one - [0.05, 70000] g - which every one of these discs
            # sits below. A 16 mg coating is not implausible, it is simply not a cell.
            as_built["mass"] = q(r["coating_mass_g"] * 1000.0, "mg")
        if r["wt_pct"] is not None:
            as_built["mass_fraction"] = q(r["wt_pct"], "%")

        notes = [
            f"The working-electrode disc built into coin cell {r['hex']}, punched from "
            f"electrode batch {label}. {BATCH_NOTE[label]}",
            "Every figure here is the value metadata.csv publishes for this one cell, "
            "not a batch average; the batch averages are on the electrode spec.",
        ]
        if r["am_mass_mg"] is not None and r["coating_mass_g"] is not None:
            notes.append(
                f"Active-material mass {_round(r['am_mass_mg'], 'mg')} mg = coating mass "
                f"({_round(r['coating_mass_g'] * 1000.0, 'mg')} mg) x active-material "
                f"weight percentage ({_round(r['wt_pct'], '%')} %), the way metadata.csv "
                f"derives it. Both factors are structured properties of this record; the "
                f"product is not, because `mass` is the one curated key that means Mass "
                f"and a second one would collapse onto it in JSON-LD.")
        fields: dict = {
            "spec": spec,
            "batch": label,
            "name": f"{label} disc {r['hex']}",
            # The batch slot of the identity seed carries the disc's full context so
            # the 7-9 discs of a batch mint 7-9 identities, not one.
            "uid": stable_uid(electrode_identity_seed(
                electrode_spec_id=spec_id, batch=f"{label}/{r['hex']}")),
            "count": 1,
            "property": as_built or None,
            "notes": notes,
            "source_type": "measurement",
            "citation": DOI_URL,
        }
        role, org, _org_iri = SOURCE_ORG[r["src"]]
        if role == "supplier":
            fields["supplier"] = org
        electrode_by_hex[r["hex"]] = ws.add("electrode", **fields)[0]

    # --- 4. Cell specs: twelve R2032 coin half-cells (D1) ------------------------
    # One spec per electrode design. The identity seed is (manufacturer, model,
    # format, chemistry, size_code), so `model` is what decides whether a published
    # IRI holds. It is qualified by the electrode label ONLY where a (kind, source)
    # pair covers more than one design - which is exactly the case that has to
    # re-mint anyway, because one identifier cannot name two designs. The six specs
    # whose (kind, source) covers a single design keep the model string they were
    # published with, and with it their IRI and every cell, test and dataset IRI
    # seeded from it.
    #
    # D2: the electrodes are named by ROLE. A half cell has no positive and no
    # negative side, so `working_electrode` / `counter_electrode` carry them, the
    # working electrode cites its design through the top-level
    # `working_electrode_spec_id` sibling (docs/electrodes-model.md: prefer the
    # sibling when the cell spec's electrode simply IS the published design - which
    # is what D1 makes true for all twelve), and the polarity basis fields are gone
    # with the polarity holders.
    print("\n== cell specs ==")
    spec_by_key: dict[tuple[str, str, str], object] = {}
    for (kind, src, label), items in sorted(by_cell_spec.items()):
        lo, hi = VWINDOW[kind]
        one_design = len(designs_per_source[(kind, src)]) == 1
        model = (f"{KIND_LABEL[kind]} R2032 half-cell ({src})" if one_design
                 else f"{KIND_LABEL[kind]} R2032 half-cell ({src}, {label})")
        draft = {
            "manufacturer": "SINTEF",
            "model": model,
            "format": "coin",
            # The counter electrode is lithium metal in every cell; the half-cell
            # nature is stated structurally by cell_configuration, not by an
            # ad-hoc chemistry string.
            "chemistry": "li-metal",
            "size_code": "R2032",
            "cell_configuration": "half_cell",
            "reference_electrode": "lithium",
            "rechargeable": True,
            "citation": DOI_URL,
            "properties": {
                "charging_voltage": q(hi, "V"),
                "discharging_cutoff_voltage": q(lo, "V"),
            },
        }
        path = write_draft(DRAFTS / f"{kind}-{src}-{label}.cell-spec.json", draft)
        cs = ws.load(path)
        cs.manufacturer_id = SINTEF_IRI

        # Working electrode: the material under study, one design per spec. It cites
        # the powder record too where the source identifies one.
        am_kwargs: dict = {}
        wt = only_value(items, "wt_pct")
        if wt is not None:
            am_kwargs["mass_fraction"] = q(wt, "%")
        am = material(KIND_LABEL[kind], **am_kwargs)
        if kind in material_spec_by_kind:
            am.material_spec_id = material_spec_by_kind[kind]
        we_props: dict = {}
        thick = only_value(items, "thick_um")
        if thick is not None:
            we_props["thickness"] = q(thick, "um")
        diam = only_value(items, "diam_mm")
        cs.working_electrode = electrode(
            bom=bom(active_material=am),
            diameter=q(diam, "mm") if diam is not None else None,
            properties=properties(**we_props) if we_props else None,
            comment=f"Working electrode: {label}, {SOURCE_LABEL[src]}.",
        )
        cs.counter_electrode = electrode(
            bom=bom(active_material=material("Lithium metal")),
            comment="Counter electrode: lithium metal foil. In a half cell the counter "
                    "electrode is also the potential reference, so all voltages are "
                    "reported vs Li/Li+.",
        )
        cs.working_electrode_spec_id = (
            electrode_spec_by_label[label]["electrode_spec"]["id"])
        cs.specification_comment = [
            "R2032 coin half-cell. The working electrode is the named active material; "
            "the counter electrode, which is also the potential reference, is lithium "
            "metal. All voltages are reported vs Li/Li+, and the cell has no positive or "
            "negative side to name.",
            f"Half-cell voltage window vs Li/Li+: {lo:.2f}-{hi:.2f} V.",
            f"Public electrode label: {label}.",
            f"Electrode design realizing this spec: "
            f"{electrode_spec_by_label[label]['electrode_spec']['name']}.",
            "Electrolyte and separator are not reported in the source record and are omitted.",
        ]
        spec_by_key[(kind, src, label)] = cs

    # The cell identities are pinned (see the cell-instance block below) and the seed
    # they are pinned to contains the cell-spec IRI - which battinfo mints at save
    # time, not at ws.load(). So the specs are saved here, before the cells are added,
    # instead of only once at step 8. ws.save() is an upsert: the second call re-saves
    # them unchanged and writes nothing.
    ws.save(validation_policy="strict")

    # --- 5. Cell instances: one per published parquet ---------------------------
    print("\n== cell instances ==")
    cell_by_hex: dict[str, object] = {}
    # ws.add("cell", ...) applies one production date per call, so cells are added in
    # (product, batch, date) groups keyed by their unique 6-character id; the public
    # label is set on the returned objects.
    groups: dict[tuple[str, str, str, str], list[dict]] = defaultdict(list)
    for r in rows:
        groups[(r["kind"], r["src"], r["label"], r["date"])].append(r)
    for (kind, src, label, date), items in sorted(groups.items()):
        # B5. The name carries the serial, the way the disc, the test and the dataset
        # already name themselves: "LNMO-NMP-2 cell 2f9459". Naming all 95 cells after
        # their batch gave twelve names for ninety-five records and made a browse
        # listing unreadable - eight indistinguishable "LNMO-NMP-2" rows.
        #
        # IDENTITY IS PINNED, and it has to be. ws.add("cell", ...) documents the name
        # as display text several cells of a batch may share and the serial as the
        # identity, but `entities.cell_instance_identity_seed` folds the name into the
        # seed whenever one is set (``label = name or serial_number or batch_id``).
        # Renaming for display would therefore re-mint all 95 cell IRIs, and with them
        # the 95 test and 95 dataset IRIs seeded from the cells - 285 identifiers, 95 of
        # them live and RETAINED from v1, moved by a change of display text. So the
        # published identity is passed explicitly through `iris=`: the uid the published
        # seed produces, computed here with battinfo's own primitives rather than
        # hand-numbered, exactly as the discs are. Upstream note: the seed should prefer
        # the serial over display text when a serial is given, which is what its own
        # docstring promises.
        spec_obj = spec_by_key[(kind, src, label)]
        spec_id = getattr(spec_obj, "id", None)
        if not spec_id:
            raise RuntimeError(
                f"cell spec {label} has no IRI yet; cannot pin the cell identities.")
        pinned = [
            "https://w3id.org/battinfo/cell/" + stable_uid(cell_instance_identity_seed(
                cell_spec_id=spec_id, serial_number=i["hex"], batch_id=label, name=label))
            for i in items
        ]
        cells = ws.add(
            "cell",
            spec=spec_obj,
            names=[f"{label} cell {i['hex']}" for i in items],
            serial_numbers=[i["hex"] for i in items],
            iris=pinned,
            production_date=yyyymmdd(date),
        )
        for cell, item in zip(cells, items):
            # The batch label stays on `batch_id`, which is the field that joins a cell
            # to its batch and to the disc inside it.
            cell.batch_id = label
            # R5 (BattINFO#346): the cell points at the disc physically inside it.
            # This is the join that v3 could only make by matching batch labels
            # (gap E4), and it is now a typed edge - the emitted node carries the
            # working-electrode role class and merges with the electrode record by
            # @id, so the chemistry and the design link stay on the disc.
            cell.working_electrode_id = electrode_by_hex[item["hex"]]["electrode"]["id"]
            # counter_electrode_id is deliberately left unset. The counter electrodes
            # are lithium metal foil, and the source tracks them not at all: no label,
            # no batch, no thickness, nothing that distinguishes the disc in one cell
            # from the disc in the next. Minting 95 electrode records for them would
            # assert 95 individually-tracked components that nobody recorded. What IS
            # known about them - lithium metal, and that the counter electrode is also
            # the potential reference - is on the cell spec's counter-electrode holder,
            # which is the right level for a component the study treats as
            # interchangeable. See README-semantic-layer.md, "What is not linked".
            cell_by_hex[item["hex"]] = cell

    # --- 6. Test protocols ------------------------------------------------------
    print("\n== test protocols ==")
    proto_by_key: dict[str, object] = {}
    for key, p in PROTOCOLS.items():
        draft = {
            "name": p["name"],
            "type": p["type"],
            "description": p["desc"],
            "version": "1.0",
            "cycles": 5,
            "method": build_method(key),
            "citation": DOI_URL,
        }
        path = write_draft(DRAFTS / f"{key}.test-spec.json", draft)
        proto_by_key[key] = ws.load(path)

    # --- 7. Tests: cell x protocol; known issues become conformance --------------
    def dataset_title(row: dict) -> str:
        return (f"{row['label']} cell {row['hex']} {PROTOCOLS[row['proto']]['name']} "
                f"half-cell OCV (BDF)")

    print("\n== tests ==")
    test_by_hex: dict[str, object] = {}
    for r in rows:
        p = PROTOCOLS[r["proto"]]
        conformance = None
        if r["issue"]:
            conformance = {"status": "non-conformant", "note": r["issue"],
                           "deviations": [deviation_for(r["issue"])]}
        test = ws.add(
            "test",
            cell=cell_by_hex[r["hex"]],
            spec=proto_by_key[r["proto"]],
            name=f"{r['label']} cell {r['hex']} {p['name']}",
            status="completed",
            conformance=conformance,
            description=(f"{p['name']} half-cell OCV measurement on {r['label']} coin cell "
                         f"{r['hex']} at room temperature."),
        )[0]
        test.started_at = yyyymmdd(r["date"])
        # R4: test conditions are now only what is genuinely a condition OF THE TEST.
        # v3 also carried the cell's as-built electrode figures here - active-material
        # mass, coating mass, loading, areal capacity - because the model had nowhere
        # per-cell to put them (gap G2). It does now: they are properties of the disc,
        # they were true before the test started, and they would still be true if the
        # test had never run. They live on the electrode record this test's cell links
        # through `working_electrode_id`, one hop away.
        test.conditions = {
            "ambient_temperature": "room temperature",
            "voltage_reference": "Li/Li+",
        }
        test_by_hex[r["hex"]] = test

    # --- 8. Save the blessed-API records ----------------------------------------
    result = ws.save(validation_policy="strict")

    # --- 9. Datasets ------------------------------------------------------------
    # MODEL GAP G1: the blessed workspace API cannot author a dataset that describes
    # an already-published remote file. ws.add("test", data=...) only accepts local
    # paths and exposes no dataset-level metadata (checksum, byte size, distribution,
    # variable_measured, citations). Rather than reach into the deprecated engine
    # (ws._ws), these records are built from the public battinfo.Dataset model and
    # written with the public battinfo.save_dataset, re-applying the same workspace
    # attribution stamp that ws.save() applies to every other record type.
    funding_block = ws.project()
    contributor_blocks = ws.contributor()
    license_id = ws.license()

    def stamp(doc: dict) -> None:
        if funding_block and doc.get("funding") != funding_block:
            doc["funding"] = funding_block
        if contributor_blocks:
            current = doc.get("contributor")
            current = current if isinstance(current, list) else []
            present = {c.get("same_as") for c in current if isinstance(c, dict)}
            for person in contributor_blocks:
                if person.get("same_as") not in present:
                    current.append(person)
                    present.add(person.get("same_as"))
            doc["contributor"] = current
        if license_id:
            body = doc.get("dataset")
            if isinstance(body, dict) and not body.get("license"):
                body["license"] = license_id

    # Derived plot profiles, if extract_profiles.py has been run. Each dataset gets a
    # second distribution pointing at its <stem>.plot.json: a ~70 KB Plotly figure of
    # the voltage curve and the open-circuit curve. ws.submit() promotes any
    # *.plot.json distribution to the page-model role `plot_data`, which is what makes
    # the platform's data explorer appear on the dataset page. The inner role stays
    # `other` because the record schema's role enum has no plot value.
    profile_index = {}
    profile_index_path = PROFILES / "index.json"
    if profile_index_path.is_file():
        profile_index = json.loads(profile_index_path.read_text(encoding="utf-8"))
    profiles_by_source = {
        entry["source_file"]: {"name": name, **entry} for name, entry in profile_index.items()
    }

    def profile_distribution(source_file: str) -> dict | None:
        entry = profiles_by_source.get(source_file)
        if entry is None:
            return None
        dist = distribution(
            f"{R2_PUBLIC_BASE}/datasets/{entry['short_id']}/{entry['name']}",
            encoding_format="application/json",
            name=entry["name"],
            description=(
                "Downsampled voltage and open-circuit curves derived from the BDF file, "
                "as a Plotly figure for the dataset page."),
            content_size=str(entry["bytes"]),
            access_level="open",
            checksum_value=checksum("sha256", entry["sha256"]))
        dist["role"] = "other"
        return dist

    print("\n== datasets ==")
    dataset_results = []
    for r in rows:
        p = PROTOCOLS[r["proto"]]
        zf = zfiles[r["file"]]
        dists = [distribution(
            zf["url"], encoding_format=PARQUET_MEDIA, name=r["file"],
            description="BDF parquet file hosted on Zenodo.",
            content_size=str(zf["size"]), access_level="open",
            checksum_value=checksum("md5", zf["md5"]))]
        profile_dist = profile_distribution(r["file"])
        if profile_dist is not None:
            dists.append(profile_dist)
        # B1: the eleven runs with a known issue say so on the dataset too. The
        # prefix goes first because the description is what a search result, a
        # dataset page and `schema:description` all show, and a warning at the end
        # of a paragraph about file formats is a warning nobody reads.
        issue = r["issue"]
        dataset = B.Dataset(
            name=dataset_title(r),
            description=(
                (f"Known issue: {issue}. " if issue else "") +
                f"Half-cell OCV electrochemical time series for {r['label']} coin cell "
                f"{r['hex']}, measured with the {p['name']} protocol at room temperature. "
                f"Apache Parquet in Battery Data Format (BDF). File "
                f"{r['file']} of Zenodo record {DOI}."),
            notes=[known_issue_note(issue)] if issue else None,
            license="cc-by-4.0",
            data_format=PARQUET_MEDIA,
            access_url=DOI_URL,
            download_url=zf["url"],
            created_at=ZENODO_PUBLISHED,
            published_at=ZENODO_PUBLISHED,
            checksum=ChecksumInfo(algorithm="md5", value=zf["md5"]),
            cell=cell_by_hex[r["hex"]],
            test=test_by_hex[r["hex"]],
            distributions=dists,
            variable_measured=[measured_variable(n, unit_text=u, description=d)
                               for n, u, d in BDF_COLUMNS],
            measurement_techniques=[p["technique"]],
            keywords=["open circuit voltage", "OCV", "half-cell", "GITT", "quasi-OCV",
                      r["kind"].replace("_", "-")],
            # S5. The Zenodo DOI is this dataset's OWN archive DOI, and every slot
            # it sits in has to mean self-reference. Three do: `access_url` (where
            # the file lives), `same_as` (the archived representation of this same
            # dataset) and `is_based_on` (this record describes one file of that
            # deposit). The typed self-citation stays too - `kind: "dataset"` is the
            # model's way of saying "cite the deposit", and the registry derives the
            # dataset's DOI from it.
            #
            # `provenance.citation` is the one that had to go. It means "a citable
            # reference for this record", it is a bare string with no kind, and the
            # platform reads exactly that field - see platform lib/dataset-citations.ts,
            # which skips citations typed `dataset` and then treats an untyped
            # provenance citation as an article - into the panel headed "Peer-reviewed
            # papers this dataset supports". The Zenodo record is data, has no
            # companion paper, and a dataset listed as the paper it supports is a
            # circular claim. `provenance.url` still carries the DOI, so the source
            # link and `prov:hadPrimarySource` are unchanged.
            citations=[{"kind": "dataset", "name": "Flores et al., half-cell OCV dataset "
                                                   "(Zenodo record)",
                        "doi": DOI, "url": DOI_URL, "citation_key": "flores2026ocv"}],
            same_as=[DOI_URL],
            is_based_on=[DOI_URL],
            source=B.ProvenanceInfo(type="measurement", url=DOI_URL),
        )
        saved = B.save_dataset(
            dataset, source_root=RECORDS_ROOT, mode="upsert",
            duplicate_policy="return_existing", resolve_references=False,
            validation_policy="strict", build_jsonld=False, build_html=False,
            stamp=stamp)
        dataset_results.append(saved)
    written = sum(1 for d in dataset_results if d.get("status") == "created"
                  or d.get("content_changed"))
    print(f"  dataset:    {len(dataset_results)} record(s); {written} written this run")
    # NOTE (gap G1): the reverse link - test -> dataset (schema:result / prov:generated)
    # - is deliberately NOT authored. ws.save() rebuilds test.dataset_ids from the
    # datasets the ENGINE holds and blanks the field for every other test, so writing
    # it would be undone and rewritten on every single run. The forward direction
    # (dataset -> cell + test, via `about`) is authored and complete.

    counts = {
        "material_spec": len(result.get("material_specs", [])),
        "material": len(result.get("materials", [])),
        "electrode_spec": len(result.get("electrode_specs", [])),
        "electrode": len(result.get("electrodes", [])),
        "cell_spec": len(result.get("cell_specs", [])),
        "cell_instance": len(result.get("cell_instances", [])),
        "test_protocol": len(result.get("test_specs", [])),
        "test": len(result.get("tests", [])),
        "dataset": len(dataset_results),
    }
    print("\n=== record counts ===")
    for key, value in counts.items():
        print(f"  {key:15s} {value}")
    print(f"  {'TOTAL':15s} {sum(counts.values())}")
    print(f"  (+ 1 organization record in {ORG_RECORDS.relative_to(ORG_RECORDS.parents[1])})")

    # The IRIs this run authored, by record subdirectory. build_bundle.py mirrors
    # exactly these into records/. Needed since D1: re-seeding an identity leaves the
    # predecessor behind in the (gitignored) workspace, and a record no run authored
    # must never ride into the tracked corpus or the bundle. The file is also the
    # input to superseded/supersede-map.json.
    def _iri(obj, key: str) -> str:
        return obj[key]["id"] if isinstance(obj, dict) else obj.id

    manifest = {
        "material-spec": sorted(material_spec_by_kind.values()),
        "material": sorted(material_lot_ids),
        "electrode-spec": [_iri(o, "electrode_spec") for o in electrode_spec_by_label.values()],
        "electrode": [_iri(o, "electrode") for o in electrode_by_hex.values()],
        "cell-spec": [_iri(o, "cell_spec") for o in spec_by_key.values()],
        "cell-instance": [_iri(o, "cell_instance") for o in cell_by_hex.values()],
        "test-protocol": [_iri(o, "test_spec") for o in proto_by_key.values()],
        "test": [_iri(o, "test") for o in test_by_hex.values()],
        "dataset": [d["id"] for d in dataset_results],
    }
    manifest = {key: sorted(set(values)) for key, values in manifest.items()}
    written = sum(len(v) for v in manifest.values())
    (RECORDS_ROOT.parent / "authored.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"\nauthored manifest: {written} IRIs -> .battinfo/authored.json")

    # Prune identities this run did not author. D1 re-seeds six cell specs and the
    # 141 cells, tests and datasets under them; their predecessors stay behind in the
    # workspace, from where build_bundle.py would mirror them into records/ and
    # ws.preview_jsonld would fold them into the deposit graph. The workspace is
    # gitignored and wholly rebuilt by this script, so the files go; the retired
    # identifiers live in superseded/supersede-map.json, which is what a republish
    # needs. The workspace index is rewritten by the next run of ws.save() - run this
    # script twice (which is the idempotence check anyway) for a clean index.
    authored = {iri for values in manifest.values() for iri in values}
    body_keys = {"material-spec": "material_spec", "material": "material",
                 "electrode-spec": "electrode_spec",
                 "electrode": "electrode", "cell-spec": "cell_spec",
                 "cell-instance": "cell_instance", "test-protocol": "test_spec",
                 "test": "test", "dataset": "dataset"}
    retired: list[str] = []
    for path in sorted(RECORDS_ROOT.rglob("*.json")):
        body_key = body_keys.get(path.parent.name)
        if body_key is None:
            continue
        body = json.loads(path.read_text(encoding="utf-8")).get(body_key) or {}
        iri = body.get("id")
        if isinstance(iri, str) and iri not in authored:
            retired.append(f"{path.parent.name}/{iri}")
            path.unlink()
    if retired:
        print(f"pruned {len(retired)} record(s) this run did not author "
              f"(re-seeded identities; see superseded/supersede-map.json)")

    kept = sum(1 for (kind, src, _label) in spec_by_key
               if len(designs_per_source[(kind, src)]) == 1)
    print(f"\ncell specs citing one electrode design: {len(spec_by_key)} of {len(spec_by_key)}")
    print(f"cell specs keeping their published model string (and IRI): {kept}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
