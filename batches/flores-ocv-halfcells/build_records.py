#!/usr/bin/env python3
"""Author the BattINFO semantic layer for the Flores et al. half-cell OCV dataset.

Zenodo record: https://zenodo.org/records/20086298
DOI (version):  10.5281/zenodo.20086298
DOI (concept):  10.5281/zenodo.19107294
License:        CC BY 4.0

CORPUS V3 - the maintainer's review-round-2 rulings, on top of v2's first-class
electrode model (BIG-MAP/BattINFO#342) and the role-based half-cell model
(BIG-MAP/BattINFO#345). What v3 changes:

  D1  One cell spec per electrode design. Three v2 specs each covered two designs
      and could therefore cite neither; they are split into six, so all twelve
      specs cite exactly one electrode spec. The six specs that already covered a
      single design keep their published IRIs - the cell-spec identity seed is
      (manufacturer, model, format, chemistry, size_code) and none of those five
      changes for them. The six new ones re-mint, and with them the 47 cells, 47
      tests and 47 datasets seeded from them. superseded/README.md maps every
      published v1 identifier onto its v3 successor.
  D2  Half cells name their electrodes by ROLE. `working_electrode` /
      `counter_electrode` replace `positive_electrode` / `negative_electrode`, and
      `working_electrode_spec_id` replaces `positive_electrode_spec_id`. The
      polarity BASIS fields go with them: a cell with no positive and no negative
      side should not describe its electrodes as either. Nothing is lost - the
      chemistry is typed on the working electrode through its electrode spec, and
      the cell still types as BatteryHalfCell + HalfCellDevice from
      cell_configuration.
  D5  Float artifacts are rounded away (see ROUNDING below).
  EES Electrode batches carry the per-batch active-mass loading and dry thickness
      computed from the per-cell rows of metadata.csv (see BATCH STATISTICS).

v2's remodel still stands: the material spec describes the POWDER and the
electrode spec describes the ELECTRODE. Corpus v1 broke that: it minted nine
"material specs" that were really electrode products and twelve "material lots"
that were really coated electrode batches. Those 21 records are retired here (see
superseded/README.md) and replaced by 1 material spec, 12 electrode specs and 12
electrode batches.

Deterministic: the script reads two committed source snapshots (``sources/metadata.csv``
and ``sources/zenodo-record.json``, verbatim captures of the Zenodo API), writes the
cell-spec / test-spec drafts it authors from into ``drafts/``, and writes canonical
BattINFO records into ``.battinfo/records/``. Re-running is a no-op: every record
carries a content-derived IRI and unchanged records report ``[unchanged]``.

Records authored (one published Zenodo dataset -> per-test granularity):
  * 1  material spec    (the LNMO powder - the only powder the source identifies)
  * 12 electrode specs  (one per electrode DESIGN: kind x source x processing route)
  * 12 electrodes       (the published electrode BATCHES, one per public label)
  * 12 cell specs       (R2032 coin half-cells, cell_configuration = half_cell,
                         one per electrode design - D1)
  * 95 cell instances   (one per parquet; serial = 6-char id, name = public label)
  * 4  test protocols   (p-OCV, p-OCV hold, GITT, GITT hold; structured EMMO method)
  * 95 tests            (cell x protocol; 11 known issues -> conformance)
  * 95 datasets         (each references the published Zenodo parquet + md5 + size)

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

BATCH STATISTICS (EES tier 1). Each electrode batch carries the mean of its cells'
active-mass loading and dry thickness, with the observed minimum and maximum where
the cells differ. Conventions, applied to all twelve batches (each has 7-9 cells, so
the n >= 2 gate never bites):
  * the mean is over the per-cell rows of metadata.csv for that public label;
  * ``Electrode Loading / g cm-2`` is the ACTIVE-material loading, not the coating
    loading - the column equals active mass / disc area for every row, which is why
    it lands on the mapped key ``loading`` (EMMO ActiveMassLoading);
  * the standard deviation is the SAMPLE standard deviation (n-1) and is stated in
    the batch's notes, not in the property block: no ``standard_deviation`` field
    exists on a Quantity and no EMMO class in the curated property map means it, so
    a structured key would be dropped from the JSON-LD and warned about. Gap E7 in
    READINESS-REPORT.md.
  * where metadata.csv states ONE value for every cell of a batch (all twelve dry
    thicknesses, and the loading of the three purchased electrodes), the mean is
    that stated value and the standard deviation is 0 by construction. The batch
    note says so rather than letting a repeated declaration read as a measured
    spread.

Authoring surface: everything except the datasets is authored through the blessed
``battinfo.workspace()`` API (``ws.add`` / ``ws.load`` / ``ws.save``), including the
new ``ws.add("electrode_spec", ...)`` / ``ws.add("electrode", ...)`` pair. The engine
handle ``ws._ws`` is never touched. Datasets that describe an already-published
remote file have no blessed workspace entry point, so they are built from the public
``battinfo.Dataset`` model and written with the public ``battinfo.save_dataset``;
see READINESS-REPORT.md (gap G1).

Nothing here submits: this build stages records for review only.

Run:  python build_records.py
Requires BattINFO from git main at or after 33615d6 (#345).
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
from battinfo.metadata import checksum, distribution, measured_variable

HERE = Path(__file__).resolve().parent
SOURCES = HERE / "sources"
DRAFTS = HERE / "drafts"
RECORDS_ROOT = HERE / ".battinfo" / "records"

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
# MATERIAL-SPEC DISPOSITION (v2). A material spec is authored only where the
# source states something about the POWDER that the kind does not already carry.
# Evidence, kind by kind, from the Zenodo description and metadata.csv:
#
#   lnmo             AUTHORED. "The LNMO material used in this study targeted high
#                    Mn/Ni disorder, therefore the OCVs is a highly disordered
#                    spinel" - a statement about the material itself, singular,
#                    covering the whole study. metadata.csv states one theoretical
#                    specific capacity (140 mAh/g) for all four LNMO batches. One
#                    powder, four electrode designs across two processing routes.
#   silicon          NOT AUTHORED. The description says the opposite: "OCVs from
#                    Si-containing electrodes might exhibit large variations
#                    depending on material properties, such as particle size,
#                    crystallinity, surface chemistry, percentage of silicon in
#                    Si-Graphite blends, etc. None of these material and electrode
#                    properties are available from the suppliers." The only powder
#                    number in metadata.csv is 3579 mAh/g, the textbook theoretical
#                    capacity of silicon, i.e. the kind restated.
#   silicon_graphite NOT AUTHORED, same statement - and it names "percentage of
#                    silicon in Si-Graphite blends" as one of the unavailable
#                    properties, so a powder record claiming a blend composition
#                    would contradict the source. The three blends ARE
#                    distinguishable (510 / 1150 / 900 mAh/g theoretical), so that
#                    number rides the electrode spec of each design instead.
#   graphite         NOT AUTHORED. 372 mAh/g is the textbook value for the kind;
#                    nothing else is stated.
#   lfp, nmc111,     NOT AUTHORED. Purchased complete electrodes ("commercial
#   nmc532           electrode" in the batch table). The manufacturers supplied
#                    electrode-level figures (weight percentage, loading, areal
#                    capacity - see the V3 version note), never a powder identity.
#                    Their electrode specs carry `kind` with no
#                    `active_material_spec_id`, which is exactly the tolerance the
#                    optional field exists for.
#
# Where a powder record exists, the theoretical specific capacity of the active
# material lives on it; where none does, it lives in the electrode spec's design
# property block. It is never stated twice.
# ---------------------------------------------------------------------------
LNMO_SPEC_NAME = "LNMO (LiNi0.5Mn1.5O4), high Mn/Ni disorder spinel"
LNMO_DISORDER_NOTE = (
    "The Zenodo record states: \"The OCVs from LiNi0.5Mn1.5O4 (LNMO) electrodes vary "
    "depending on the degree of Mn/Ni disorder (see Sun et al.). The LNMO material used "
    "in this study targeted high Mn/Ni disorder, therefore the OCVs is a highly "
    "disordered spinel.\" No supplier, grade or product identifier is given for the "
    "powder, so none is stated here."
)

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

    # --- 1. Material specs: the powders the source actually identifies -----------
    # One: the LNMO active material. See the MATERIAL-SPEC DISPOSITION block above
    # for the kind-by-kind evidence, including why the silicon-containing powders
    # deliberately get none.
    print("\n== material specs (powders) ==")
    lnmo_rows = [r for r in rows if r["kind"] == "lnmo"]
    lnmo_theo = only_value(lnmo_rows, "theo_mahg")
    lnmo_spec = ws.add(
        "material_spec",
        name=LNMO_SPEC_NAME,
        kind="lnmo",
        material_class="active_material",
        formula="LiNi0.5Mn1.5O4",
        chemistry_family="spinel",
        description=(
            "LNMO active material used across all four LNMO electrode batches of the "
            "dataset, aqueous and NMP processed alike. The study targeted high Mn/Ni "
            "disorder, so these OCVs are those of a highly disordered spinel."),
        property=({"theoretical_capacity": q(lnmo_theo, "mAh/g")} if lnmo_theo else None),
        source_type="literature",
        citation=DOI_URL,
        notes=[LNMO_DISORDER_NOTE],
    )[0]
    lnmo_spec_id = lnmo_spec["material_spec"]["id"]
    material_spec_by_kind = {"lnmo": lnmo_spec_id}

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
        # Design values the manufacturer states for the purchased electrodes: they
        # are constant across every cell of the batch, unlike the SINTEF-coated
        # ones where loading and areal capacity are computed per cell and stay on
        # the tests (gap G2).
        loading = only_value(items, "loading_gcm2")
        if loading is not None:
            # Reported in g/cm2; expressed in mg/cm2, the symbol that resolves to a
            # dereferenceable EMMO unit. Same quantity, no rounding beyond float.
            design["loading"] = q(loading * 1000.0, "mg/cm2")
        areal = only_value(items, "areal_mahcm2")
        if areal is not None:
            design["areal_capacity"] = q(areal, "mAh/cm2")
        # Theoretical specific capacity is a property of the active material. It
        # rides the electrode spec only where no powder record exists to hold it.
        theo = only_value(items, "theo_mahg")
        if theo is not None and kind not in material_spec_by_kind:
            design["theoretical_capacity"] = q(theo, "mAh/g")

        fields: dict = {
            "name": DESIGN_NAME[label],
            "kind": kind,
            "manufacturer": producer,
            "description": (
                f"{BATCH_NOTE[label]} Electrode design of the {SOURCE_LABEL[r0['src']]}, "
                f"published under the label {label}. Active-material type as stated in "
                f"metadata.csv: \"{r0['am_type']}\"."),
            "property": design or None,
            "source_type": "literature",
            "citation": DOI_URL,
        }
        if kind in material_spec_by_kind:
            fields["active_material_spec_id"] = material_spec_by_kind[kind]
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
            f"batch that realizes this design; the as-built dry thickness is on the "
            f"electrode record."
        ]
        if kind not in material_spec_by_kind:
            notes.append(
                "No material spec is authored for this electrode's active material: the "
                "source states no powder identity for it. `kind` carries the chemistry.")
        fields["notes"] = notes
        electrode_spec_by_label[label] = ws.add("electrode_spec", **fields)[0]

    # --- 3. Electrodes: the twelve published batches ----------------------------
    # The batch record is where the public label lives and where the as-built
    # figures that are constant across the batch sit. Per-CELL figures (active
    # material mass, coating mass, per-cell loading and areal capacity) stay on the
    # tests, because the model has no per-cell electrode slot (gap G2).
    print("\n== electrodes (batches) ==")
    electrode_by_label: dict[str, dict] = {}
    for label, items in sorted(by_batch.items()):
        r0 = items[0]
        spec = electrode_spec_by_label[label]
        as_built: dict = {}
        stat_notes: list[str] = []

        # EES tier 1: the batch's own as-built figures, averaged over its cells.
        # `loading` maps to EMMO ActiveMassLoading, `dry_thickness` to
        # DryCoatingThickness; both are computed from the per-cell rows of
        # metadata.csv for this public label. See BATCH STATISTICS in the module
        # docstring for the conventions this follows.
        loading_stats = spread([r["loading_gcm2"] * 1000.0
                                for r in items if r["loading_gcm2"] is not None])
        thickness_stats = spread([r["thick_um"] for r in items if r["thick_um"] is not None])
        for key, unit, quantity, what in (
            ("loading", "mg/cm2", loading_stats, "Active-mass loading"),
            ("dry_thickness", "um", thickness_stats, "Dry thickness"),
        ):
            if quantity is None:
                continue
            varies = quantity["max"] > quantity["min"]
            as_built[key] = q(
                quantity["mean"], unit,
                min_value=quantity["min"] if varies else None,
                max_value=quantity["max"] if varies else None,
            )
            if varies:
                stat_notes.append(
                    f"{what}: {_round(quantity['mean'], unit)} +/- "
                    f"{_round(quantity['sd'], unit)} {unit} (mean +/- sample standard "
                    f"deviation, n = {quantity['n']} cells; range "
                    f"{_round(quantity['min'], unit)}-{_round(quantity['max'], unit)} {unit}), "
                    f"over the per-cell values metadata.csv publishes for this batch."
                )
            else:
                stat_notes.append(
                    f"{what}: {_round(quantity['mean'], unit)} {unit}. metadata.csv states "
                    f"this one value for every one of the {quantity['n']} cells of the batch, "
                    f"so the mean is that stated value and the standard deviation is 0 by "
                    f"construction - not a measured spread."
                )

        fields: dict = {
            "spec": spec, "batch": label, "name": label,
            "property": as_built or None,
            "notes": [
                BATCH_NOTE[label],
                f"{len(items)} of the 95 published measurements were made on cells built "
                f"from this batch.",
                *stat_notes,
            ],
            "source_type": "measurement", "citation": DOI_URL,
        }
        role, org, _org_iri = SOURCE_ORG[r0["src"]]
        if role == "supplier":
            fields["supplier"] = org
        electrode_by_label[label] = ws.add("electrode", **fields)[0]

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
        cells = ws.add(
            "cell",
            spec=spec_by_key[(kind, src, label)],
            serial_numbers=[i["hex"] for i in items],
            production_date=yyyymmdd(date),
        )
        for cell, item in zip(cells, items):
            # The public label is the electrode batch this cell was built from. It is
            # also the batch_id of the electrode record, which is the only join
            # available: cell instances have no electrode reference (gap E4).
            cell.name = label
            cell.batch_id = label
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
        # Ambient conditions plus the as-built electrode figures for this specific
        # cell. These per-cell values normalise the measurement (specific capacity,
        # C-rate) and have no other structured home in the model - the cell-instance
        # `measured` block is a closed cell-performance vocabulary, and the electrode
        # batch record describes the batch, not the disc punched for one cell. See
        # gap G2 in READINESS-REPORT.md.
        conditions: dict = {
            "ambient_temperature": "room temperature",
            "voltage_reference": "Li/Li+",
        }
        if r["am_mass_mg"] is not None:
            conditions["active_material_mass"] = q(r["am_mass_mg"], "mg")
        if r["coating_mass_g"] is not None:
            conditions["electrode_coating_mass"] = q(r["coating_mass_g"], "g")
        if r["areal_mahcm2"] is not None:
            conditions["nominal_areal_capacity"] = q(r["areal_mahcm2"], "mAh/cm2")
        if r["loading_gcm2"] is not None:
            conditions["electrode_loading"] = q(r["loading_gcm2"] * 1000.0, "mg/cm2")
        test.conditions = conditions
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

    print("\n== datasets ==")
    dataset_results = []
    for r in rows:
        p = PROTOCOLS[r["proto"]]
        zf = zfiles[r["file"]]
        dataset = B.Dataset(
            name=dataset_title(r),
            description=(
                f"Half-cell OCV electrochemical time series for {r['label']} coin cell "
                f"{r['hex']}, measured with the {p['name']} protocol at room temperature. "
                f"Apache Parquet in Battery Data Format (BDF). File "
                f"{r['file']} of Zenodo record {DOI}."),
            license="cc-by-4.0",
            data_format=PARQUET_MEDIA,
            access_url=DOI_URL,
            download_url=zf["url"],
            created_at=ZENODO_PUBLISHED,
            published_at=ZENODO_PUBLISHED,
            checksum=ChecksumInfo(algorithm="md5", value=zf["md5"]),
            cell=cell_by_hex[r["hex"]],
            test=test_by_hex[r["hex"]],
            distributions=[distribution(
                zf["url"], encoding_format=PARQUET_MEDIA, name=r["file"],
                description="BDF parquet file hosted on Zenodo.",
                content_size=str(zf["size"]), access_level="open",
                checksum_value=checksum("md5", zf["md5"]))],
            variable_measured=[measured_variable(n, unit_text=u, description=d)
                               for n, u, d in BDF_COLUMNS],
            measurement_techniques=[p["technique"]],
            keywords=["open circuit voltage", "OCV", "half-cell", "GITT", "quasi-OCV",
                      r["kind"].replace("_", "-")],
            citations=[{"kind": "dataset", "doi": DOI, "url": DOI_URL,
                        "citation_key": "flores2026ocv"}],
            same_as=[DOI_URL],
            source=B.ProvenanceInfo(type="measurement", url=DOI_URL, citation=DOI_URL),
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

    # The IRIs this run authored, by record subdirectory. build_bundle.py mirrors
    # exactly these into records/. Needed since D1: re-seeding an identity leaves the
    # predecessor behind in the (gitignored) workspace, and a record no run authored
    # must never ride into the tracked corpus or the bundle. The file is also the
    # input to superseded/supersede-map.json.
    def _iri(obj, key: str) -> str:
        return obj[key]["id"] if isinstance(obj, dict) else obj.id

    manifest = {
        "material-spec": [lnmo_spec_id],
        "electrode-spec": [_iri(o, "electrode_spec") for o in electrode_spec_by_label.values()],
        "electrode": [_iri(o, "electrode") for o in electrode_by_label.values()],
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
    body_keys = {"material-spec": "material_spec", "electrode-spec": "electrode_spec",
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
