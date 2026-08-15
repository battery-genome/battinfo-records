#!/usr/bin/env python3
"""Author the BattINFO semantic layer for the Flores et al. half-cell OCV dataset.

Zenodo record: https://zenodo.org/records/20086298
DOI (version):  10.5281/zenodo.20086298
DOI (concept):  10.5281/zenodo.19107294
License:        CC BY 4.0

CORPUS V2 - re-authored on the first-class electrode model (BIG-MAP/BattINFO#342).
The ratified principle is that the material spec describes the POWDER and the
electrode spec describes the ELECTRODE. Corpus v1 broke it: it minted nine
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
  * 9  cell specs       (R2032 coin half-cells, cell_configuration = half_cell)
  * 95 cell instances   (one per parquet; serial = 6-char id, name = public label)
  * 4  test protocols   (p-OCV, p-OCV hold, GITT, GITT hold; structured EMMO method)
  * 95 tests            (cell x protocol; 11 known issues -> conformance)
  * 95 datasets         (each references the published Zenodo parquet + md5 + size)

Authoring surface: everything except the datasets is authored through the blessed
``battinfo.workspace()`` API (``ws.add`` / ``ws.load`` / ``ws.save``), including the
new ``ws.add("electrode_spec", ...)`` / ``ws.add("electrode", ...)`` pair. The engine
handle ``ws._ws`` is never touched. Datasets that describe an already-published
remote file have no blessed workspace entry point, so they are built from the public
``battinfo.Dataset`` model and written with the public ``battinfo.save_dataset``;
see READINESS-REPORT.md (gap G1).

Nothing here submits: this build stages records for review only.

Run:  python build_records.py
Requires BattINFO from git main at or after 63da080b (#342).
"""
from __future__ import annotations

import csv
import json
import re
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

# Controlled positive_electrode_basis terms. domain-battery only curates
# positive-electrode classes for materials normally used as cathodes; graphite,
# silicon, silicon-graphite and LNMO have no positive-electrode term, so the
# field is omitted for them rather than emitted as an unmapped value. Under v2
# the chemistry is no longer lost when the field is omitted: the cell spec cites
# its electrode spec, whose node is typed with the chemistry class directly
# (SiliconBasedElectrode, LithiumNickelManganeseOxideElectrode, ...). See G8.
POSITIVE_BASIS = {
    "lfp": "lfp",
    "nmc111": "nmc",
    "nmc532": "nmc",
}

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


def q(value, unit):
    return {"value": value, "unit": unit}


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

    by_cell_spec: dict[tuple[str, str], list[dict]] = defaultdict(list)
    by_batch: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_cell_spec[(r["kind"], r["src"])].append(r)
        by_batch[r["label"]].append(r)

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
            f"Active-material weight percentage and dry thickness are as published in "
            f"metadata.csv for batch {label}."
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
        thick = only_value(items, "thick_um")
        if thick is not None:
            as_built["dry_thickness"] = q(thick, "um")
        fields: dict = {
            "spec": spec, "batch": label, "name": label,
            "property": as_built or None,
            "notes": [
                BATCH_NOTE[label],
                f"Dry thickness as published in metadata.csv for this batch; "
                f"{len(items)} of the 95 published measurements were made on cells built "
                f"from it.",
            ],
            "source_type": "measurement", "citation": DOI_URL,
        }
        role, org, _org_iri = SOURCE_ORG[r0["src"]]
        if role == "supplier":
            fields["supplier"] = org
        electrode_by_label[label] = ws.add("electrode", **fields)[0]

    # --- 4. Cell specs: nine R2032 coin half-cells ------------------------------
    # Unchanged from v1 in identity: manufacturer, model, format, chemistry and
    # size_code are the cell-spec identity seed, and all five are byte-identical, so
    # the nine published IRIs (and every cell, test and dataset IRI derived from
    # them) are preserved. What changes is the electrode reference.
    print("\n== cell specs ==")
    spec_by_key: dict[tuple[str, str], object] = {}
    cell_spec_electrode_designs: dict[tuple[str, str], list[str]] = {}
    for (kind, src), items in sorted(by_cell_spec.items()):
        labels = sorted({i["label"] for i in items})
        cell_spec_electrode_designs[(kind, src)] = labels
        lo, hi = VWINDOW[kind]
        model = f"{KIND_LABEL[kind]} R2032 half-cell ({src})"
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
            "negative_electrode_basis": "lithium-metal",
            "rechargeable": True,
            "citation": DOI_URL,
            "properties": {
                "charging_voltage": q(hi, "V"),
                "discharging_cutoff_voltage": q(lo, "V"),
            },
        }
        if kind in POSITIVE_BASIS:
            draft["positive_electrode_basis"] = POSITIVE_BASIS[kind]
        path = write_draft(DRAFTS / f"{kind}-{src}.cell-spec.json", draft)
        cs = ws.load(path)
        cs.manufacturer_id = SINTEF_IRI

        # Working electrode: the material under study. It links to the designed
        # electrode when this spec is realized by exactly one design, and to the
        # powder record when the source identifies one.
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
        cs.positive_electrode = electrode(
            bom=bom(active_material=am),
            diameter=q(diam, "mm") if diam is not None else None,
            properties=properties(**we_props) if we_props else None,
            comment=f"Working electrode; {SOURCE_LABEL[src]}.",
        )
        cs.negative_electrode = electrode(
            bom=bom(active_material=material("Lithium metal")),
            comment="Counter and reference electrode: lithium metal foil.",
        )
        design_note = (
            f"Electrode design realizing this spec: "
            f"{electrode_spec_by_label[labels[0]]['electrode_spec']['name']}."
        )
        if len(labels) == 1:
            # One design: state it structurally. The emitter merges the electrode
            # spec's @id onto this cell spec's positive-electrode node.
            cs.positive_electrode_spec_id = (
                electrode_spec_by_label[labels[0]]["electrode_spec"]["id"])
        else:
            # More than one design under one published cell spec. The seam is
            # single-valued and the cell-spec IRIs are already published, so the
            # designs are named in prose rather than silently collapsing two
            # different electrodes onto one link. See READINESS-REPORT.md gap E3.
            design_note = (
                "This cell spec is realized by more than one electrode design "
                + "; ".join(
                    electrode_spec_by_label[label]["electrode_spec"]["name"]
                    for label in labels)
                + ". Because a cell spec can cite only one electrode spec, no "
                  "electrode_spec_id is stated; the designs are reachable through the "
                  "electrode batches named below."
            )
        cs.specification_comment = [
            "R2032 coin half-cell. The working electrode is the named active material; "
            "the counter and reference electrode is lithium metal. All voltages are "
            "reported vs Li/Li+.",
            f"Half-cell voltage window: {lo:.2f}-{hi:.2f} V.",
            f"Public electrode label(s) grouped under this spec: {', '.join(labels)}.",
            design_note,
            "Electrolyte and separator are not reported in the source record and are omitted.",
        ]
        spec_by_key[(kind, src)] = cs

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
            spec=spec_by_key[(kind, src)],
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

    linked = sum(1 for key in spec_by_key
                 if len(cell_spec_electrode_designs[key]) == 1)
    print(f"\ncell specs citing one electrode design: {linked} of {len(spec_by_key)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
