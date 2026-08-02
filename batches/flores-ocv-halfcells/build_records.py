#!/usr/bin/env python3
"""Author the BattINFO semantic layer for the Flores et al. half-cell OCV dataset.

Zenodo record: https://zenodo.org/records/20086298
DOI (version):  10.5281/zenodo.20086298
DOI (concept):  10.5281/zenodo.19107294
License:        CC BY 4.0

This script is deterministic: it reads the two committed source snapshots
(``sources/metadata.csv`` and ``sources/zenodo-record.json``, both verbatim
captures of the Zenodo API) and writes canonical BattINFO records into
``.battinfo/records/`` under this directory. Re-running against an existing
workspace is a no-op (records carry content-derived IRIs; unchanged records
report ``[unchanged]``).

Records authored (one published Zenodo dataset -> per-test granularity):
  * 7  material specs   (active materials)
  * 9  cell specs       (R2032 coin half-cells, working electrode vs Li metal)
  * 95 cell instances   (one per parquet, serial = 6-char batch id)
  * 4  test protocols   (p-OCV, p-OCV hold, GITT, GITT hold)
  * 95 tests            (cell x protocol; 11 known issues -> conformance)
  * 95 datasets         (each references the existing Zenodo parquet + md5 + size)

Run:  python build_records.py
Requires BattINFO >= 0.7 (`pip install git+https://github.com/BIG-MAP/BattINFO.git`).
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import warnings
from pathlib import Path

warnings.simplefilter("ignore")

import battinfo as B
from battinfo import testmethod as tm
from battinfo.authoring import bom, electrode, material, properties
from battinfo.api import create_material_spec, save_material_spec

HERE = Path(__file__).resolve().parent
SOURCES = HERE / "sources"
RECORDS_ROOT = HERE / ".battinfo" / "records"

SINTEF_IRI = "https://w3id.org/battinfo/organization/b4qq-aawd-zesa-kh4q"
DOI = "10.5281/zenodo.20086298"
DOI_URL = f"https://doi.org/{DOI}"
CONCEPT_DOI = "10.5281/zenodo.19107294"
ZENODO_PUBLISHED = "2026-05-08"
PARQUET_MEDIA = "application/vnd.apache.parquet"

# All nine creators of the published record, in author order, all with ORCIDs.
# NOTE: the task brief listed six; the live Zenodo record lists nine (7 SINTEF +
# 2 IREC). We author all nine to stay faithful to the published dataset.
CONTRIBUTORS = [
    ("0000-0003-2954-1233", "Eibar Flores", "SINTEF"),
    ("0009-0006-0805-6713", "Sridevi Krishnamurthi", "SINTEF"),
    ("0000-0002-6299-1319", "Killian Stokes-Rodriguez", "SINTEF"),
    ("0009-0005-4059-7715", "Julie Cathrine Guldahl", "SINTEF"),
    ("0000-0003-0931-5466", "Charifa Hakim", "SINTEF"),
    ("0000-0002-8758-6109", "Simon Clark", "SINTEF"),
    ("0000-0002-8014-4324", "Nils Peter Wagner", "SINTEF"),
    ("0009-0003-1413-0770", "Sergi Obrador", "Institut de Recerca de l'Energia de Catalunya"),
    ("0000-0001-9591-6422", "Andres Bernabeu Santisteban", "Institut de Recerca de l'Energia de Catalunya"),
]

# Active-material reference facts. Theoretical capacities are taken from
# metadata.csv where the file provides them; commercial electrodes (LFP, NMC111,
# NMC532) leave the column blank, so we do not invent a value. Formulae are the
# chemical compositions stated in the Zenodo description.
MATERIALS = {
    "graphite": dict(name="Graphite", formula="C", family="graphite",
                     polarity="negative", theo=372.0,
                     desc="Graphite negative-electrode active material (aqueous-processed electrode)."),
    "silicon": dict(name="Silicon", formula="Si", family="silicon",
                    polarity="negative", theo=3579.0,
                    desc="Silicon negative-electrode active material (aqueous-processed electrode)."),
    "silicongraphite": dict(name="Silicon-graphite composite", formula=None, family="silicon-graphite",
                            polarity="negative", theo=None,
                            desc="Silicon-graphite composite negative-electrode active material. "
                                 "Theoretical capacity is batch-dependent (510-1150 mAh/g across the "
                                 "SiGr-AQ-1/2/3 batches); recorded per cell instance."),
    "lnmo": dict(name="LNMO (LiNi0.5Mn1.5O4)", formula="LiNi0.5Mn1.5O4", family="lnmo",
                 polarity="positive", theo=140.0,
                 desc="High Mn/Ni-disorder LNMO spinel positive-electrode active material."),
    "lfp": dict(name="LFP (LiFePO4)", formula="LiFePO4", family="lfp",
                polarity="positive", theo=None,
                desc="LiFePO4 olivine positive-electrode active material (commercial electrode)."),
    "nmc111": dict(name="NMC111 (LiNi1/3Mn1/3Co1/3O2)", formula="LiNi0.33Mn0.33Co0.33O2", family="nmc",
                   polarity="positive", theo=None,
                   desc="LiNi1/3Mn1/3Co1/3O2 layered oxide positive-electrode active material (commercial electrode)."),
    "nmc532": dict(name="NMC532 (LiNi0.5Mn0.3Co0.2O2)", formula="LiNi0.5Mn0.3Co0.2O2", family="nmc",
                   polarity="positive", theo=None,
                   desc="LiNi0.5Mn0.3Co0.2O2 layered oxide positive-electrode active material (commercial electrode)."),
}

# Half-cell voltage cutoffs vs Li/Li+ (lower, upper), from the Zenodo description.
VWINDOW = {
    "graphite": (0.01, 1.00), "silicon": (0.01, 1.00), "silicongraphite": (0.01, 1.00),
    "lnmo": (3.50, 4.80), "lfp": (2.50, 3.65), "nmc111": (3.00, 4.30), "nmc532": (3.00, 4.30),
}

# Electrode-supplier display names for the working-electrode source token.
SUPPLIER = {
    "intelligent": "IntelLiGent project (SINTEF)",
    "intelligent1": "IntelLiGent project (SINTEF)",
    "intelligent2": "IntelLiGent project (SINTEF)",
    "gelon": "Gelon LIB (commercial electrode)",
    "customcells": "Customcells (commercial electrode)",
}

PROTOCOLS = {
    "p-ocv": dict(
        name="p-OCV", ttype="quasi_ocv", hold=False,
        desc=("Pseudo-OCV: constant-current cycling at C/50. A rest period of 8 h is applied "
              "upon reaching the upper and lower voltage cutoffs. 5 cycles, room temperature."),
        technique="quasi_ocv"),
    "p-ocvhold": dict(
        name="p-OCV hold", ttype="quasi_ocv", hold=True,
        desc=("Pseudo-OCV with voltage hold: constant-current cycling at C/50. The voltage is held "
              "for 6 h under potentiostatic control upon reaching the upper and lower voltage cutoffs. "
              "5 cycles, room temperature."),
        technique="quasi_ocv"),
    "gitt": dict(
        name="GITT", ttype="gitt", hold=False,
        desc=("Galvanostatic Intermittent Titration Technique: a sequence of current pulses (C/50) "
              "each followed by a 150-minute rest. A rest period of 6 h is applied upon reaching the "
              "upper and lower voltage cutoffs. 5 cycles, room temperature."),
        technique="gitt"),
    "gitthold": dict(
        name="GITT hold", ttype="gitt", hold=True,
        desc=("GITT with voltage hold: a sequence of current pulses (C/50) each followed by a 150-minute "
              "rest. The voltage is held for 6 h under potentiostatic control upon reaching the upper and "
              "lower voltage cutoffs. 5 cycles, room temperature."),
        technique="gitt"),
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

_ALPHA = "0123456789abcdefghjkmnpqrstvwxyz"


def stable_uid(seed: str) -> str:
    """Deterministic 4-4-4-4 UID in the BattINFO alphabet (matches repo convention)."""
    bits = "".join(f"{byte:08b}" for byte in hashlib.sha256(seed.encode("utf-8")).digest())
    chars = "".join(_ALPHA[int(bits[i * 5:(i + 1) * 5], 2)] for i in range(16))
    return f"{chars[0:4]}-{chars[4:8]}-{chars[8:12]}-{chars[12:16]}"


def num(value):
    value = (value or "").strip()
    if value == "":
        return None
    try:
        f = float(value)
    except ValueError:
        return None
    return f


def yyyymmdd(value: str) -> str:
    return f"{value[0:4]}-{value[4:6]}-{value[6:8]}"


def load_metadata() -> list[dict]:
    rows = list(csv.DictReader((SOURCES / "metadata.csv").open(encoding="utf-8-sig")))
    parsed = []
    for r in rows:
        name = r["BDF names"]
        m = FILENAME_RE.match(name)
        if not m:
            raise SystemExit(f"Unrecognised BDF filename: {name}")
        parsed.append({
            "file": name, "mat": m["mat"], "src": m["src"], "hex": m["hex"],
            "date": m["date"], "proto": m["proto"], "label": r["Public Labels"].strip(),
            "am_mass_mg": num(r["Mass of Active Material / mg"]),
            "coating_mass_g": num(r["Electrode Coating Mass / g"]),
            "wt_pct": num(r["Weight percentage of Active Material / %"]),
            "theo": num(r["Theoretical Capacity /  mAh g-1"]),
            "diam_mm": num(r["Electrode Diameter / mm"]),
            "thick_um": num(r["Dry Thickness / um"]),
            "areal_mahcm2": num(r["Nominal Areal Capacity / mAh cm-2"]),
            "loading_gcm2": num(r["Electrode Loading / g cm-2"]),
            "issue": (r["Known Issues"] or "").strip(),
        })
    return parsed


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


def deviation_for(issue: str) -> B.Deviation:
    low = issue.lower()
    if "failed" in low or "stopped" in low:
        cat = "premature_termination"
    elif "anomalous" in low or "high voltage" in low:
        cat = "out_of_tolerance"
    else:
        cat = "other"
    return B.Deviation(category=cat, description=issue)


def build_method(proto_key: str) -> list[tm.Step]:
    """Structured, material-agnostic test method. Rates/durations/cycle count are the
    values stated in the record; per-material voltage cutoffs live on the cell spec."""
    p = PROTOCOLS[proto_key]
    c50 = {"c_rate": tm.Quantity(value=0.02, unit="1/h")}  # C/50

    def cutoff_hold(where: str):
        if p["hold"]:
            return tm.Step(mode="cv", duration=tm.Quantity(value=6, unit="h"),
                           description=f"Potentiostatic hold for 6 h at the {where} voltage cutoff")
        hours = 6 if p["ttype"] == "gitt" else 8
        return tm.Step(mode="rest", duration=tm.Quantity(value=hours, unit="h"),
                       description=f"Rest for {hours} h at the {where} voltage cutoff")

    if p["ttype"] == "quasi_ocv":
        half = lambda where: [
            tm.Step(mode="cc", setpoints=c50, description=f"Constant current at C/50 toward the {where} voltage cutoff"),
            cutoff_hold(where),
        ]
        return [tm.Step(mode="group", count=5, description="5 cycles",
                        steps=half("lower") + half("upper"))]

    # GITT / GITT hold: pulse train (C/50 pulse + 150 min rest) to each cutoff, then cutoff hold/rest.
    pulse_train = lambda where: tm.Step(
        mode="group", description=f"Current pulses at C/50 with 150-min rests toward the {where} voltage cutoff",
        steps=[
            tm.Step(mode="cc", setpoints=c50, description="Current pulse at C/50"),
            tm.Step(mode="rest", duration=tm.Quantity(value=150, unit="min"), description="Rest for 150 minutes"),
        ])
    return [tm.Step(mode="group", count=5, description="5 cycles",
                    steps=[pulse_train("lower"), cutoff_hold("lower"),
                           pulse_train("upper"), cutoff_hold("upper")])]


def main() -> int:
    rows = load_metadata()
    zfiles = load_zenodo_files()

    ws = B.workspace(root=str(HERE), registry_url=None)
    ws.license("cc-by-4.0")
    for orcid, name, aff in CONTRIBUTORS:
        ws.contributor(orcid, name=name, affiliation=aff)
    # Explicit project fields (values from the OpenAIRE/CORDIS resolver) so the run
    # is fully offline and deterministic.
    ws.project(
        "101069765",
        name="Innovative and Sustainable High Voltage Li-ion Cells for Next Generation (EV) Batteries",
        acronym="IntelLiGent", funder="European Commission", program="HE",
        id="https://cordis.europa.eu/project/id/101069765",
    )
    eng = ws._ws

    # --- 1. Material specs (saved first; capture content-derived ids for linking) ---
    material_ids: dict[str, str] = {}
    for key, m in MATERIALS.items():
        prop = {}
        if m["theo"] is not None:
            prop["theoretical_specific_capacity"] = {"value": m["theo"], "unit": "mAh/g"}
        # create_material_spec auto-mints a RANDOM id per call (not content-derived),
        # so we pin a deterministic id seeded on the material key to keep re-runs idempotent.
        draft = create_material_spec(
            id=f"https://w3id.org/battinfo/spec/{stable_uid('flores-ocv:material:' + key)}",
            name=m["name"], material_class="active_material", electrode_polarity=m["polarity"],
            formula=m["formula"], chemistry_family=m["family"], property=prop,
            description=m["desc"], source_type="literature", citation=DOI_URL,
        )
        saved = save_material_spec(draft, source_root=RECORDS_ROOT, mode="upsert",
                                   duplicate_policy="return_existing", validation_policy="strict")
        material_ids[key] = saved["id"]

    # --- 2. Consistency check per (material, source) spec key ---
    from collections import defaultdict
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        groups[(r["mat"], r["src"])].append(r)

    def consistent(items, field):
        vals = {i[field] for i in items if i[field] is not None}
        return vals.pop() if len(vals) == 1 else None

    # --- 3. Cell specs (half-cells) ---
    spec_by_key: dict[tuple[str, str], object] = {}
    for (mat, src), items in sorted(groups.items()):
        labels = sorted({i["label"] for i in items})
        lo, hi = VWINDOW[mat]
        thick = consistent(items, "thick_um")
        wt = consistent(items, "wt_pct")
        model = f"{mat} R2032 half-cell ({src})"
        cs = eng.cell_spec(
            manufacturer="SINTEF", model=model, format="coin", chemistry="Li half-cell",
            positive_electrode_basis=mat, negative_electrode_basis="Li", size_code="R2032",
            specs={
                "charging_voltage": {"value": hi, "unit": "V"},
                "discharging_cutoff_voltage": {"value": lo, "unit": "V"},
            },
            source_type="lab", citation=DOI_URL,
        )
        cs.manufacturer_id = SINTEF_IRI
        # Working electrode = the material under study.
        we_props = {"diameter": {"value": 14, "unit": "mm"}}
        if thick is not None:
            we_props["dry_thickness"] = {"value": thick, "unit": "um"}
        am = material(MATERIALS[mat]["name"],
                      **({"mass_fraction": {"value": wt, "unit": "%"}} if wt is not None else {}))
        am.material_spec_id = material_ids[mat]
        we = electrode(bom=bom(active_material=am), properties=properties(**we_props),
                       comment=f"Working electrode; electrode source: {SUPPLIER.get(src, src)}.")
        we.supplier = SUPPLIER.get(src, src)
        ce = electrode(bom=bom(active_material=material("Lithium metal")),
                       comment="Counter and reference electrode: lithium metal foil.")
        cs.positive_electrode = we
        cs.negative_electrode = ce
        cs.specification_comment = [
            ("R2032 coin half-cell. Working electrode = the named active material; "
             "counter and reference electrode = lithium metal. All voltages are vs Li/Li+."),
            f"Half-cell voltage window: {lo:.2f}-{hi:.2f} V.",
            f"Public electrode label(s) grouped under this spec: {', '.join(labels)}.",
            "Electrolyte and separator are not reported in the source record and are omitted.",
        ]
        spec_by_key[(mat, src)] = cs

    # --- 4. Cell instances (one per parquet) ---
    # As-built electrode figures are recorded per instance. The cell-instance
    # `measured` field is a closed cell-performance vocabulary (67 keys: capacity,
    # voltage, resistance, ...) with no slot for electrode-build parameters, and the
    # Test model exposes no `conditions` field, so the structured "test conditions"
    # fallback is unavailable via the object graph. We therefore attach the values
    # as a clearly-labelled, parseable block on the instance comment (the instance
    # is the correct semantic owner). See README-semantic-layer.md and the readiness
    # report for the model gap this exposes.
    def build_notes(r) -> list[str]:
        route = "aqueous-processed" if "-AQ-" in r["label"] else (
            "NMP/organic-solvent-processed" if "-NMP-" in r["label"] else "processing route not stated")
        lines = [
            f"Public label {r['label']}; {route}; electrode source {SUPPLIER.get(r['src'], r['src'])}.",
            "As-built electrode figures for this specific cell (from metadata.csv):",
        ]
        fields = [
            ("active_material_mass", r["am_mass_mg"], "mg"),
            ("electrode_coating_mass", r["coating_mass_g"], "g"),
            ("active_material_mass_fraction", r["wt_pct"], "%"),
            ("theoretical_specific_capacity", r["theo"], "mAh/g"),
            ("electrode_diameter", r["diam_mm"], "mm"),
            ("dry_thickness", r["thick_um"], "um"),
            ("nominal_areal_capacity", r["areal_mahcm2"], "mAh/cm2"),
            ("electrode_loading", r["loading_gcm2"], "g/cm2"),
        ]
        for name, val, unit in fields:
            if val is not None:
                lines.append(f"  {name} = {val} {unit}")
        return lines

    cell_by_hex: dict[str, object] = {}
    for r in rows:
        cs = spec_by_key[(r["mat"], r["src"])]
        cell = eng.cell(
            cs, serial_number=r["hex"], name=r["label"], manufactured_at=yyyymmdd(r["date"]),
            source_type="lab", citation=DOI_URL, comment=build_notes(r),
        )
        cell_by_hex[r["hex"]] = cell

    # --- 5. Test protocols ---
    proto_by_key: dict[str, object] = {}
    for key, p in PROTOCOLS.items():
        ts = eng.test_spec(name=p["name"], type=p["ttype"], kind="cycling",
                           description=p["desc"], method=build_method(key), version="1.0",
                           source_type="manual", citation=DOI_URL)
        proto_by_key[key] = ts

    # --- 6. Tests (cell x protocol; known issues -> conformance) ---
    test_by_hex: dict[str, object] = {}
    for r in rows:
        cell = cell_by_hex[r["hex"]]
        ts = proto_by_key[r["proto"]]
        conf = None
        if r["issue"]:
            conf = B.TestConformance(status="non-conformant", note=r["issue"],
                                     deviations=[deviation_for(r["issue"])])
        test = eng.test(cell, kind="cycling", protocol_ref=ts, status="completed",
                        started_at=yyyymmdd(r["date"]), conformance=conf,
                        source_type="measurement", citation=DOI_URL,
                        description=f"{PROTOCOLS[r['proto']]['name']} half-cell OCV measurement on "
                                    f"{r['label']} cell {r['hex']} at room temperature.")
        test_by_hex[r["hex"]] = test

    # --- 7. Datasets (reference the published Zenodo parquet files) ---
    for r in rows:
        cell = cell_by_hex[r["hex"]]
        test = test_by_hex[r["hex"]]
        zf = zfiles[r["file"]]
        ds = eng.dataset(
            cell, test=test,
            title=f"{r['label']} cell {r['hex']} {PROTOCOLS[r['proto']]['name']} half-cell OCV (BDF)",
            description=(f"Half-cell OCV electrochemical time series for {r['label']} coin cell {r['hex']} "
                         f"measured with the {PROTOCOLS[r['proto']]['name']} protocol at room temperature. "
                         f"Apache Parquet in Battery Data Format (BDF). Part of Zenodo record {DOI}."),
            access_url=DOI_URL, download_url=zf["url"], format=PARQUET_MEDIA,
            checksum_algorithm="md5", checksum_value=zf["md5"],
            license="cc-by-4.0", created_at=ZENODO_PUBLISHED, source_type="measurement",
        )
        ds.published_at = ZENODO_PUBLISHED
        ds.checksum = B.ChecksumInfo(algorithm="md5", value=zf["md5"])
        ds.distributions = [B.distribution(
            zf["url"], encoding_format=PARQUET_MEDIA, name=r["file"],
            description="BDF parquet file hosted on Zenodo.",
            content_size=str(zf["size"]), access_level="open",
            checksum_value=B.checksum("md5", zf["md5"]),
        )]
        ds.variable_measured = [B.measured_variable(n, unit_text=u, description=d) for n, u, d in BDF_COLUMNS]
        ds.measurement_techniques = [PROTOCOLS[r["proto"]]["technique"]]
        ds.keywords = ["open circuit voltage", "OCV", "half-cell", "GITT", "quasi-OCV", r["mat"]]
        ds.citations = [{"kind": "dataset", "doi": DOI, "url": DOI_URL,
                         "citation_key": "flores2026ocv"}]
        ds.same_as = [DOI_URL]

    # --- 8. Save + report ---
    result = ws.save(validation_policy="strict")
    counts = {
        "material_spec": len(material_ids),
        "cell_spec": len(result.get("cell_specs", [])),
        "cell_instance": len(result.get("cell_instances", [])),
        "test_spec": len(result.get("test_specs", [])),
        "test": len(result.get("tests", [])),
        "dataset": len(result.get("datasets", [])),
    }
    print("\n=== record counts ===")
    for k, v in counts.items():
        print(f"  {k:14s} {v}")
    print(f"  {'TOTAL':14s} {sum(counts.values())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
