#!/usr/bin/env python3
"""Author the BattINFO semantic layer for the Flores et al. half-cell OCV dataset.

Zenodo record: https://zenodo.org/records/20086298
DOI (version):  10.5281/zenodo.20086298
DOI (concept):  10.5281/zenodo.19107294
License:        CC BY 4.0

Deterministic: the script reads two committed source snapshots (``sources/metadata.csv``
and ``sources/zenodo-record.json``, verbatim captures of the Zenodo API), writes the
cell-spec / test-spec drafts it authors from into ``drafts/``, and writes canonical
BattINFO records into ``.battinfo/records/``. Re-running is a no-op: every record
carries a content-derived IRI and unchanged records report ``[unchanged]``.

Records authored (one published Zenodo dataset -> per-test granularity):
  * 9  material specs   (electrode products: active-material kind x electrode source)
  * 12 material lots    (one per public electrode label, carrying the processing route)
  * 9  cell specs       (R2032 coin half-cells, cell_configuration = half_cell)
  * 95 cell instances   (one per parquet; serial = 6-char id, name = public label)
  * 4  test protocols   (p-OCV, p-OCV hold, GITT, GITT hold; structured EMMO method)
  * 95 tests            (cell x protocol; 11 known issues -> conformance)
  * 95 datasets         (each references the published Zenodo parquet + md5 + size)

Authoring surface: everything except the datasets is authored through the blessed
``battinfo.workspace()`` API (``ws.add`` / ``ws.load`` / ``ws.save``). The engine
handle ``ws._ws`` is never touched. Datasets that describe an already-published
remote file have no blessed workspace entry point, so they are built from the public
``battinfo.Dataset`` model and written with the public ``battinfo.save_dataset``;
see READINESS-REPORT.md (gap G1).

Run:  python build_records.py
Requires BattINFO from git main (`pip install git+https://github.com/BIG-MAP/BattINFO.git`).
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
# by the manufacturer block of the six SINTEF-made material specs. IREC
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
# Level 1: active-material KINDS. These are vocabulary entries in BattINFO's
# curated material_kinds, not records - each carries the EMMO class, the
# chemical-substance anchor and the external identity anchors. The filename
# token in the BDF names maps onto a kind key.
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

# Display name and idealised composition per kind, as stated in the Zenodo record.
KIND_LABEL = {
    "graphite": "Graphite",
    "silicon": "Silicon",
    "silicon_graphite": "Silicon-graphite composite",
    "lnmo": "LNMO (LiNi0.5Mn1.5O4)",
    "lfp": "LFP (LiFePO4)",
    "nmc111": "NMC111 (LiNi1/3Mn1/3Co1/3O2)",
    "nmc532": "NMC532 (LiNi0.5Mn0.3Co0.2O2)",
}
KIND_FORMULA = {
    "graphite": "C",
    "silicon": "Si",
    "silicon_graphite": None,          # blend; composition not reported
    "lnmo": "LiNi0.5Mn1.5O4",
    "lfp": "LiFePO4",
    "nmc111": "LiNi0.33Mn0.33Co0.33O2",
    "nmc532": "LiNi0.5Mn0.3Co0.2O2",
}
KIND_FAMILY = {
    "graphite": "graphitic-carbon",
    "silicon": "silicon",
    "silicon_graphite": "silicon-graphite-composite",
    "lnmo": "spinel",
    "lfp": "olivine",
    "nmc111": "layered-oxide",
    "nmc532": "layered-oxide",
}
# Electrode polarity of the working electrode in the coin half-cells. In every
# Li half-cell the lithium metal counter electrode is the lower-potential
# (negative) electrode, so the material under study is always the positive one -
# consistent with the positive voltage windows reported vs Li/Li+.
KIND_POLARITY = {k: "positive" for k in KIND_LABEL}

# Controlled positive_electrode_basis terms. domain-battery only curates
# positive-electrode classes for materials normally used as cathodes; graphite,
# silicon, silicon-graphite and LNMO have no positive-electrode term, so the
# field is omitted for them rather than emitted as an unmapped value. The
# material identity is carried losslessly by the electrode bill of materials,
# which links each active material to its material spec (and thence its kind).
POSITIVE_BASIS = {
    "lfp": "lfp",
    "nmc111": "nmc",
    "nmc532": "nmc",
}

# Electrode source token -> (organization role, display name, registry IRI).
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

# Batch-level notes from the Zenodo "Electrode batches" table, keyed by public label.
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

# The public label encodes "chemical composition and manufacturing route"
# (metadata schema, Zenodo description), so the -AQ- / -NMP- token is the
# authors' own statement of the processing route. Labels with neither token
# would leave `processing` unset rather than guessed; all 12 carry one.
ROUTE_TOKENS = {"AQ": ("aqueous", "water"), "NMP": ("nmp", "NMP")}

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

    by_product: dict[tuple[str, str], list[dict]] = defaultdict(list)
    by_batch: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_product[(r["kind"], r["src"])].append(r)
        by_batch[r["label"]].append(r)

    # --- 1. Material specs: one per electrode product (kind x electrode source) ---
    print("\n== material specs ==")
    spec_by_product: dict[tuple[str, str], dict] = {}
    for (kind, src), items in sorted(by_product.items()):
        role, org, org_iri = SOURCE_ORG[src]
        org_ref = {"type": "Organization", "name": org, "id": org_iri} if org_iri else org
        labels = sorted({i["label"] for i in items})
        fields = dict(
            name=f"{KIND_LABEL[kind]} electrode - {SOURCE_LABEL[src]}",
            kind=kind,
            grade=src,
            product_id=f"sintef-{kind}-{src}",
            material_class="active_material",
            electrode_polarity=KIND_POLARITY[kind],
            chemistry_family=KIND_FAMILY[kind],
            description=(
                f"{KIND_LABEL[kind]} active material in the electrodes of the "
                f"{SOURCE_LABEL[src]}. Electrode batches published under this product: "
                f"{', '.join(labels)}."),
            source_type="literature",
            citation=DOI_URL,
        )
        if KIND_FORMULA[kind]:
            fields["formula"] = KIND_FORMULA[kind]
        fields[role] = org_ref
        spec_by_product[(kind, src)] = ws.add("material_spec", **fields)[0]

    # --- 2. Material lots: one per published electrode batch (public label) ------
    # The processing route (aqueous vs NMP) is an instance/build property, never
    # part of the product identity - it lives here, exactly as the schema intends.
    print("\n== material lots ==")
    material_by_label: dict[str, dict] = {}
    for label, items in sorted(by_batch.items()):
        r0 = items[0]
        spec = spec_by_product[(r0["kind"], r0["src"])]
        route = route_for(label)
        prop: dict[str, dict] = {}
        wt = only_value(items, "wt_pct")
        if wt is not None:
            prop["mass_fraction"] = q(wt, "%")
        thick = only_value(items, "thick_um")
        if thick is not None:
            prop["thickness"] = q(thick, "um")
        theo = only_value(items, "theo_mahg")
        if theo is not None:
            prop["theoretical_capacity"] = q(theo, "mAh/g")
        fields = dict(
            spec=spec, lot=label, name=label,
            property=prop or None,
            notes=[BATCH_NOTE[label]],
            source_type="measurement", citation=DOI_URL,
        )
        if route is not None:
            route_word = "aqueous" if route[0] == "aqueous" else "organic-solvent"
            fields["processing"] = {
                "route": route[0], "solvent": route[1],
                "detail": f"{route_word.capitalize()} electrode coating ({route[1]}), as "
                          f"stated by the public electrode label {label}.",
            }
        role, org, org_iri = SOURCE_ORG[r0["src"]]
        if role == "supplier":
            fields["supplier"] = org
        material_by_label[label] = ws.add("material", **fields)[0]

    # --- 3. Cell specs: nine R2032 coin half-cells ------------------------------
    print("\n== cell specs ==")
    spec_by_key: dict[tuple[str, str], object] = {}
    for (kind, src), items in sorted(by_product.items()):
        labels = sorted({i["label"] for i in items})
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

        # Working electrode: the material under study, linked to its material spec.
        # Batch-level figures are only stated here when every batch under this
        # product agrees; otherwise they stay on the individual material lots.
        am_kwargs: dict = {}
        wt = only_value(items, "wt_pct")
        if wt is not None:
            am_kwargs["mass_fraction"] = q(wt, "%")
        am = material(KIND_LABEL[kind], **am_kwargs)
        am.material_spec_id = spec_by_product[(kind, src)]["material_spec"]["id"]
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
        cs.specification_comment = [
            "R2032 coin half-cell. The working electrode is the named active material; "
            "the counter and reference electrode is lithium metal. All voltages are "
            "reported vs Li/Li+.",
            f"Half-cell voltage window: {lo:.2f}-{hi:.2f} V.",
            f"Public electrode label(s) grouped under this spec: {', '.join(labels)}.",
            "Electrolyte and separator are not reported in the source record and are omitted.",
        ]
        spec_by_key[(kind, src)] = cs

    # --- 4. Cell instances: one per published parquet ---------------------------
    print("\n== cell instances ==")
    cell_by_hex: dict[str, object] = {}
    # ws.add("cell", ...) applies one production date per call and de-duplicates on
    # the cell label, so cells are added in (product, batch, date) groups keyed by
    # their unique 6-character id; the public label is set on the returned objects.
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
            # The public label is the batch this cell was built from; it is also the
            # lot_id of the material record, which makes the join explicit.
            cell.name = label
            cell.batch_id = label
            cell_by_hex[item["hex"]] = cell

    # --- 5. Test protocols ------------------------------------------------------
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

    # --- 6. Tests: cell x protocol; known issues become conformance --------------
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
        # `measured` block is a closed cell-performance vocabulary. See gap G2 in
        # READINESS-REPORT.md.
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
            # Reported in g/cm2; expressed in mg/cm2, the symbol that resolves to a
            # dereferenceable EMMO unit. Same quantity, no rounding beyond float.
            conditions["electrode_loading"] = q(r["loading_gcm2"] * 1000.0, "mg/cm2")
        test.conditions = conditions
        test_by_hex[r["hex"]] = test

    # --- 7. Save the blessed-API records ----------------------------------------
    result = ws.save(validation_policy="strict")

    # --- 8. Datasets ------------------------------------------------------------
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
    dataset_id_by_hex: dict[str, str] = {}
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
        dataset_id_by_hex[r["hex"]] = saved["id"]
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
