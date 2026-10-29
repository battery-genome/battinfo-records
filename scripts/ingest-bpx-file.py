#!/usr/bin/env python3
"""Ingest a BPX parameter file as one published, runnable parameter-set record.

One BPX file becomes ONE parameter-set record: every value in the file as a
claim, grouped by part (cell, each electrode's material and build, separator,
electrolyte, initial state), the User-defined block verbatim, and the file
itself under ``distributions``:

- ``source``: the bytes exactly as their authors published them;
- ``runnable``: a declared conversion, made only when the official parser
  rejects the source (for example a v0.x layout declared as BPX 1.0);
- ``mirror``: the same bytes held elsewhere (the source repository at a pinned
  commit), with the same checksum.

The record is addressed by the file's parameters (IDENTIFIER_POLICY 6.3), so
its IRI always resolves to the same values.

Which cell the file describes is stated per source, never guessed:

- ``existing``: a cell spec already in the genome; the record links to it and
  nothing else is created;
- ``new``: a real cell not yet in the genome; the script searches the registry
  and this corpus for the maker and model first and stops on a match, then
  writes an identity-only cell spec (name, maker, model, format, chemistry; the
  BPX numbers stay on the parameter set) and, if missing, the maker's
  organization record;
- ``virtual``: no cell record.

Checks recorded on each file: the official ``bpx`` parser's verdict, and a
PyBaMM smoke run (1C discharge to the lower cut-off, the model the header
names, particle phases set from the file) when ``--sim-python`` points at an
interpreter with pybamm and bpx.

The files are NOT committed here: they are written to ``--out-dir`` for upload
to the registry's artifact store, and the record carries their sha256.

Requires BattINFO with ``to_parameter_set`` (BIG-MAP/BattINFO#421). Run from
the repo root with that checkout's environment:

    ../BattINFO/.venv/Scripts/python scripts/ingest-bpx-file.py schmitt2026-hydra \\
        --artifacts-base-url https://<public artifacts base> \\
        --sim-python C:/t/bpxsim/Scripts/python.exe --out-dir ../bpx-artifacts

Licences are set here, as conditions of the source. Funding and contributor
are stamped at publish, as for every corpus publication.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

REPO = Path(__file__).resolve().parent.parent
PARAMETER_SET_DIR = REPO / "records" / "parameter-set"
CELL_SPEC_DIR = REPO / "records" / "cell-spec"
ORGANIZATION_DIR = REPO / "records" / "organization"

# One entry per published BPX file. The URL pins a commit, so the bytes the
# record describes can always be fetched again from the source as well.
SOURCES: dict[str, dict] = {
    "schmitt2026-hydra": {
        "url": (
            "https://raw.githubusercontent.com/BattMoTeam/schmitt-2026-lnmo-graphite-hydra-publication/"
            "51092701d66b8dcaa88febaa132ff877f7ebc6db/parameters/"
            "IMP5-70-120-H0B_graphite-lnmo_schmitt-2026_validation.bpx.json"
        ),
        "license": "cc-by-4.0",
        "attribution": (
            "Parameters from Schmitt et al. 2026, 'Comprehensive parameter and electrochemical dataset "
            "for a 1 Ah graphite/LNMO battery cell for physical modelling' (arXiv:2601.10507), "
            "released by the authors under CC-BY-4.0. The file is the BPX export in "
            "BattMoTeam/schmitt-2026-lnmo-graphite-hydra-publication at commit 5109270; that "
            "repository's GPL-3.0-or-later licence covers its code."
        ),
        "citation": "https://arxiv.org/abs/2601.10507",
        "notes": [
            "Calibrated against the HYDRA0 measurements published at https://doi.org/10.5281/zenodo.18256663 "
            "(CC-BY-4.0). The file's Validation section holds five discharge-rate curves from that campaign.",
        ],
        "materials": {"negative": "graphite", "positive": "lnmo"},
        # Published under spec/ on 2026-10-11, before parameter sets moved to dataset/.
        "supersedes": "https://w3id.org/battinfo/spec/szxp-xwnx-vhyf-rvm0",
        "software_requirements": None,
        "cell": {
            "case": "new",
            "slug": "cea--imp5-70-120-h0b--2026",
            "spec": {
                "name": "HYDRA0 1 Ah graphite|LNMO prototype pouch cell",
                "manufacturer": "CEA",
                "model": "IMP5-70-120-H0B",
                "format": "pouch",
                "chemistry": "li-ion",
                "positive_electrode_basis": "LNMO",
                "negative_electrode_basis": "graphite",
                "rechargeable": True,
                "specification_comment": (
                    "Prototype pouch cell developed within the Horizon Europe project HYDRA "
                    "(https://doi.org/10.5281/zenodo.18256663)."
                ),
            },
            "organization": {
                "slug": "cea",
                "fields": {
                    "name": "CEA",
                    "type": "ResearchOrganization",
                    "legal_name": "Commissariat à l'énergie atomique et aux énergies alternatives",
                    "alternate_name": ["French Alternative Energies and Atomic Energy Commission"],
                    "location": {"address_country": "FR"},
                },
            },
        },
    },
}

# PyBaMM run in a separate interpreter. Particle phases come from the file:
# a BPX 1.x electrode with a Particle block of N phases needs N phases in the
# model, or PyBaMM asks for parameters the file does not have.
SMOKE_RUN = r"""
import json, sys, time
import pybamm
doc = json.load(open(sys.argv[1], encoding="utf-8"))
model_name = sys.argv[2]
params = doc.get("Parameterisation", {})
phases = tuple(
    str(len(params.get(block, {}).get("Particle") or {}) or 1)
    for block in ("Negative electrode", "Positive electrode")
)
options = {"particle phases": phases} if phases != ("1", "1") else {}
pv = pybamm.ParameterValues.create_from_bpx_obj(doc)
low = pv["Lower voltage cut-off [V]"]
model = {"DFN": pybamm.lithium_ion.DFN, "SPMe": pybamm.lithium_ion.SPMe, "SPM": pybamm.lithium_ion.SPM}[model_name](options)
start = time.time()
sim = pybamm.Simulation(model, parameter_values=pv, experiment=pybamm.Experiment([f"Discharge at 1C until {low} V"]))
sol = sim.solve()
print(json.dumps({
    "pybamm": pybamm.__version__,
    "seconds": round(time.time() - start, 2),
    "capacity_ah": float(sol["Discharge capacity [A.h]"].entries[-1]),
    "lower_cutoff_v": float(low),
    "options": options,
}))
"""

# The examples distributed with the BPX standard, at a pinned commit. None describes a real cell.
_BPX_EXAMPLES = "https://raw.githubusercontent.com/FaradayInstitution/BPX/9b73d69fb758b9422e463478989bd3d3e0807024/examples/"
_BPX_ATTRIBUTION = (
    "Example parameter set distributed with the BPX standard (FaradayInstitution/BPX, MIT licence), "
    "at commit 9b73d69."
)
for _key, _file, _name, _materials, _notes in (
    ("bpx-example-nmc-pouch", "nmc_pouch_cell_BPX.json", "BPX example: NMC111 pouch cell",
     {"negative": "graphite", "positive": "nmc111"}, []),
    ("bpx-example-nmc-pouch-spm", "nmc_pouch_cell_BPX_SPM.json", "BPX example: NMC111 pouch cell (SPM)",
     {"negative": "graphite", "positive": "nmc111"},
     ["PyBaMM 26.10 cannot read SPM parameter files (its BPX importer needs an electrolyte section), "
      "so its smoke run fails."]),
    # The positive electrode is a blend: BattINFO cannot name its materials yet.
    ("bpx-example-nmc-pouch-blended", "nmc_pouch_cell_BPX_blended_electrode.json",
     "BPX example: NMC111 pouch cell, blended positive electrode", {"negative": "graphite"}, []),
    ("bpx-example-nmc-pouch-hysteresis", "nmc_pouch_cell_BPX_user-defined_hysteresis.json",
     "BPX example: NMC111 pouch cell with OCP hysteresis", {"negative": "silicon_graphite", "positive": "nmc111"}, []),
    ("bpx-example-lfp-18650", "lfp_18650_cell_BPX.json", "BPX example: LFP 18650 cell",
     {"negative": "graphite", "positive": "lfp"}, []),
):
    SOURCES[_key] = {
        "url": _BPX_EXAMPLES + _file,
        "name": _name,
        "license": "mit",
        "attribution": _BPX_ATTRIBUTION,
        "citation": "https://github.com/FaradayInstitution/BPX",
        "notes": _notes,
        "materials": _materials,
        "software_requirements": None,
        "cell": {"case": "virtual"},
    }

# PyBaMM's speed-benchmark parameter sets, exported to BPX by scripts/export-pybamm-bpx.py
# (files and their checks in --exports-dir). Only sets whose BPX file reproduces PyBaMM's native
# set (within about 1 mV) are listed: ORegan2022 and Ai2020 use a thermodynamic factor and
# exchange-current forms that BPX cannot express.
_PYBAMM_PARAMETERS = (
    "https://github.com/pybamm-team/PyBaMM/blob/pybamm-v26.10.1.1/packages/pybamm/src/pybamm/input/parameters/lithium_ion/"
)
for _key, _name, _doi, _materials, _cell, _notes in (
    ("pybamm-chen2020", "Chen2020", "10.1149/1945-7111/ab9050",
     {"negative": "silicon_graphite", "positive": "nmc811"},
     {"case": "existing", "cell_spec_id": "https://w3id.org/battinfo/spec/2c16-qpzn-d6xc-3shs"}, []),  # LG INR21700 M50
    # Positive electrode LiNiCoO2 (NCO): no BattINFO material kind yet, so only the negative is named.
    ("pybamm-ecker2015", "Ecker2015", "10.1149/2.0551509jes", {"negative": "graphite"},
     {"case": "existing", "cell_spec_id": "https://w3id.org/battinfo/spec/c9g2-kj3e-mqsg-2rjp"},  # Kokam SLPB75106100
     ["The file describes one electrode pair (0.156 Ah) of the 7.5 Ah cell. Its positive electrode is NCO, "
      "which has no BattINFO material kind yet."]),
    # PyBaMM names a Kokam SLPB78205130H, but the values are compiled from several sources (Dualfoil,
    # Capiglia et al. 1999, Moura et al. 2016 functions), so the set is not that cell's parameterisation.
    ("pybamm-marquis2019", "Marquis2019", "10.1149/2.0341915jes", {"negative": "graphite", "positive": "lco"},
     {"case": "virtual"},
     ["PyBaMM names a Kokam SLPB78205130H, but the values are compiled from several sources, so no cell is linked."]),
    ("pybamm-nca-kim2011", "NCA_Kim2011", "10.1149/1.3597614", {"negative": "graphite", "positive": "nca"},
     {"case": "virtual"}, []),  # a "nominal design" cell
    ("pybamm-prada2013", "Prada2013", "10.1149/2.053304jes", {"negative": "graphite", "positive": "lfp"},
     {"case": "virtual"}, []),  # no specific cell named; graphite OCP and j0 from Chen2020
    ("pybamm-ramadass2004", "Ramadass2004", "10.1149/1.1634273", {"negative": "graphite", "positive": "lco"},
     {"case": "virtual"}, []),  # assembled from several papers
):
    SOURCES[_key] = {
        "file": f"{_name.lower()}--pybamm.bpx.json",
        "check": f"{_name.lower()}--pybamm.check.json",
        "source_url": f"{_PYBAMM_PARAMETERS}{_name}.py",
        "source_description": f"Exported from PyBaMM's {_name} parameter set by scripts/export-pybamm-bpx.py.",
        "license": "bsd-3-clause",
        "attribution": (
            f"Parameter values from https://doi.org/{_doi} as implemented in PyBaMM's {_name} parameter set "
            "(PyBaMM 26.10.1.1, BSD-3-Clause), exported to BPX by battinfo-records."
        ),
        "citation": f"https://doi.org/{_doi}",
        "citation_doi": _doi,
        "notes": _notes,
        "materials": _materials,
        "software_requirements": None,
        "cell": _cell,
    }


def export_check_notes(check_path: Path) -> list[str]:
    """The export check, as one short note: the largest difference from PyBaMM's native set."""
    report = json.loads(check_path.read_text(encoding="utf-8"))
    runs = [r for r in report["check"] if "error" not in r]
    if not runs:
        return ["PyBaMM's native set and this file could not be compared."]
    rms = max(r["voltage_rms_difference_mV"] for r in runs)
    capacity = max(abs(r["capacity_difference_percent"]) for r in runs)
    rates = ", ".join(f"{r['c_rate']:g}C" for r in runs if "temperature_K" not in r)
    warm = " and 1C 20 K warmer" if any("temperature_K" in r for r in runs) else ""
    notes = [f"Matches PyBaMM {report['pybamm']}'s native set within {rms:g} mV RMS and {capacity:g}% capacity "
             f"(DFN discharges at {rates}{warm})."]
    return notes + list(report.get("notes", []))


def fetch(url: str) -> bytes:
    with urlopen(url, timeout=120) as response:
        return response.read()


def smoke_check(sim_python: str, path: Path, model: str) -> dict:
    """Run a 1C discharge in PyBaMM in a separate interpreter and report it as a check."""
    today = date.today().isoformat()
    proc = subprocess.run(
        [sim_python, "-c", SMOKE_RUN, str(path), model],
        capture_output=True, text=True, timeout=1800,
    )
    if proc.returncode != 0:
        lines = [line for line in proc.stderr.strip().splitlines() if line.strip()]
        return {
            "check": "simulation_smoke",
            "tool": "pybamm",
            "passed": False,
            "detail": f"{model}, 1C discharge to the lower cut-off failed: {lines[-1] if lines else 'no output'}"[:600],
            "checked_at": today,
        }
    result = json.loads(proc.stdout.strip().splitlines()[-1])
    options = f" with {result['options']}" if result["options"] else ""
    return {
        "check": "simulation_smoke",
        "tool": f"pybamm {result['pybamm']}",
        "passed": True,
        "detail": (
            f"{model}{options}, 1C discharge to {result['lower_cutoff_v']:g} V solved in {result['seconds']:g} s; "
            f"{result['capacity_ah']:.3f} Ah delivered."
        ),
        "checked_at": today,
    }


def battinfo_label(battinfo) -> str:
    """'battinfo <version>', plus the commit when it runs from a git checkout."""
    label = f"battinfo {battinfo.__version__}"
    try:
        sha = subprocess.run(
            ["git", "-C", str(Path(battinfo.__file__).parent), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=30, check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return label
    return f"{label} (BIG-MAP/BattINFO@{sha})" if sha else label


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def find_existing_cell(registry_url: str, manufacturer: str, model: str) -> list[str]:
    """Cell specs that already describe this maker and model: registry first, then this corpus."""
    hits: list[str] = []
    query = urlencode({"resource_type": "cell_spec", "q": model, "limit": 50})
    try:
        with urlopen(f"{registry_url.rstrip('/')}/resources?{query}", timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"duplicate search failed ({exc}); rerun when the registry answers, never skip it") from exc
    items = payload if isinstance(payload, list) else payload.get("items", [])
    for item in items:
        title = _norm(str(item.get("title") or ""))
        if _norm(model) in title:
            hits.append(f"{item.get('canonical_iri')} ({item.get('title')})")
    for path in CELL_SPEC_DIR.glob("*/record.json"):
        body = json.loads(path.read_text(encoding="utf-8")).get("cell_spec", {})
        maker = body.get("manufacturer") or {}
        maker_name = maker.get("name", "") if isinstance(maker, dict) else str(maker)
        if _norm(str(body.get("model", ""))) == _norm(model) and _norm(maker_name) == _norm(manufacturer):
            hits.append(f"{body.get('id')} ({path.parent.name})")
    return hits


def write_record(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("source", choices=sorted(SOURCES))
    parser.add_argument("--artifacts-base-url", required=True,
                        help="public base URL of the registry artifact store (STORAGE_ARTIFACTS_BASE_URL)")
    parser.add_argument("--artifact-version", default="v1")
    parser.add_argument("--exports-dir", type=Path, default=REPO.parent / "bpx-exports",
                        help="files made by export-pybamm-bpx.py, for sources that are local files")
    parser.add_argument("--out-dir", type=Path, default=REPO.parent / "bpx-artifacts",
                        help="where the files to upload are written (outside the repo)")
    parser.add_argument("--sim-python", default=None,
                        help="python with pybamm and bpx installed, for the smoke run")
    parser.add_argument("--registry-url", default="https://battinfo-registry.onrender.com",
                        help="registry searched for an existing description of a 'new' cell")
    parser.add_argument("--dry-run", action="store_true", help="build and validate; write no records")
    args = parser.parse_args()

    import battinfo
    from battinfo.api import create_organization, save_cell_spec
    from battinfo.interop import bpx_file_distribution, check_bpx, from_bpx_parameters, upgrade_bpx
    from battinfo.validate import validate_record_report

    source = SOURCES[args.source]
    cell = source["cell"]
    if "file" in source:
        raw = (args.exports_dir / source["file"]).read_bytes()
        file_name = source["file"]
    else:
        raw = fetch(source["url"])
        file_name = source["url"].rsplit("/", 1)[-1]

    # The uid is the file's: known before any record exists, so the upload
    # path and the record agree by construction.
    probe_dir = args.out_dir / "_incoming"
    probe_dir.mkdir(parents=True, exist_ok=True)
    (probe_dir / file_name).write_bytes(raw)
    imported = from_bpx_parameters(probe_dir / file_name)
    uid = imported.file_uid()
    file_dir = args.out_dir / uid
    file_dir.mkdir(parents=True, exist_ok=True)
    source_path = file_dir / file_name
    source_path.write_bytes(raw)
    (probe_dir / file_name).unlink()
    base = args.artifacts_base_url.rstrip("/")

    def content_url(name: str) -> str:
        return f"{base}/parameter-sets/{uid}/{args.artifact_version}/{name}"

    model = (imported.model_type or "DFN").strip()
    source_checks = [check_bpx(source_path)]
    runnable_path = None
    runnable_checks: list[dict] = []
    if not source_checks[0]["passed"]:
        upgraded = upgrade_bpx(source_path)
        if upgraded.changed:
            stem = file_name[: -len(".bpx.json")] if file_name.endswith(".bpx.json") else Path(file_name).stem
            runnable_path = file_dir / f"{stem}.bpx-v1.json"
            upgraded.save(runnable_path)
            runnable_checks = [check_bpx(runnable_path)]
    if args.sim_python:
        if source_checks[0]["passed"]:
            source_checks.append(smoke_check(args.sim_python, source_path, model))
        if runnable_path is not None and runnable_checks[0]["passed"]:
            runnable_checks.append(smoke_check(args.sim_python, runnable_path, model))

    distributions = [
        bpx_file_distribution(
            source_path,
            content_url=content_url(file_name),
            description=source.get("source_description", "The BPX file exactly as its authors published it."),
            software_requirements=source["software_requirements"],
            checks=source_checks,
        )
    ]
    if runnable_path is not None:
        distributions.append(
            bpx_file_distribution(
                runnable_path,
                content_url=content_url(runnable_path.name),
                role="runnable",
                description="The source in the BPX v1 layout, which the current parser and PyBaMM require; "
                "State defaults are added as the bpx package's own v0-to-v1 migration adds them.",
                derived_from=distributions[0]["checksum"]["value"],
                conversion=upgraded.conversion_note(f"{battinfo_label(battinfo)} upgrade_bpx"),
                software_requirements=source["software_requirements"],
                checks=runnable_checks,
            )
        )
    if "url" in source:
        distributions.append(
            bpx_file_distribution(
                source_path,
                content_url=source["url"],
                role="mirror",
                description="The same bytes in the source repository, at a pinned commit.",
            )
        )

    out: dict[Path, dict] = {}
    link: dict[str, object]
    if cell["case"] == "existing":
        link = {"cell_spec_id": cell["cell_spec_id"]}
    elif cell["case"] == "virtual":
        link = {"virtual_cell": True}
    elif cell["case"] == "new":
        spec_fields = dict(cell["spec"])
        matches = find_existing_cell(args.registry_url, spec_fields["manufacturer"], spec_fields["model"])
        own_path = CELL_SPEC_DIR / cell["slug"] / "record.json"
        matches = [m for m in matches if cell["slug"] not in m]
        if matches:
            raise SystemExit(
                "this cell may already be described; link it as case 'existing' instead of creating a duplicate:\n  "
                + "\n  ".join(matches)
            )
        org_info = cell.get("organization")
        if org_info:
            org_record = create_organization(**org_info["fields"])
            org_path = ORGANIZATION_DIR / org_info["slug"] / "record.json"
            if not org_path.exists():
                out[org_path] = org_record
            spec_fields["manufacturer_id"] = org_record["organization"]["id"]
        # Identity only: the BPX numbers stay on the parameter set.
        saved = save_cell_spec(spec_fields, source_root=args.out_dir / "_cell-spec", mode="upsert",
                               build_jsonld=False, build_html=False)
        cell_record = json.loads(Path(saved["path"]).read_text(encoding="utf-8"))
        cell_record["provenance"].update({"source_type": "literature", "citation": source["citation"]})
        cell_record["license"] = source["license"]
        out[own_path] = cell_record
        link = {"cell_spec_id": cell_record["cell_spec"]["id"]}
    else:
        raise SystemExit(f"unknown cell case {cell['case']!r}: use existing, new or virtual")

    record = imported.to_parameter_set(
        **link,
        materials=source["materials"],
        distributions=distributions,
        # BattINFO checks that the runnable copy is the layout upgrade of the source.
        **({"runnable_file": runnable_path} if runnable_path is not None else {}),
        **({"supersedes": source["supersedes"]} if source.get("supersedes") else {}),
        citation=source["citation"],
        **({"citation_doi": source["citation_doi"]} if source.get("citation_doi") else {}),
        **({"name": source["name"]} if source.get("name") else {}),
        source_url=source.get("source_url", source.get("url")),
        notes=[source["attribution"], *source["notes"],
               *(export_check_notes(args.exports_dir / source["check"]) if source.get("check") else [])],
    )
    record["license"] = source["license"]
    out[PARAMETER_SET_DIR / f"{args.source}--bpx" / "record.json"] = record

    for path, rec in out.items():
        report = validate_record_report(rec)
        errors = [i for i in getattr(report, "issues", []) if getattr(i, "severity", "") == "error"]
        if not report.ok or errors:
            raise SystemExit(f"{path.parent.name}: invalid record: {report.errors}")

    for warning in imported.warnings:
        print(f"import note: {warning[:300]}")
    for distribution in distributions:
        verdicts = ", ".join(
            f"{c['check']}={'pass' if c['passed'] else 'FAIL'}" for c in distribution.get("checks", [])
        )
        print(f"{distribution['role']:9s} {distribution['name']}  sha256 {distribution['checksum']['value'][:16]}...  {verdicts}")
    body = record["parameter_set"]
    print(f"parameter set: {body['id']}  ({len(body['parts'])} parts, "
          f"{sum(len(p['claims']) for p in body['parts'])} claims)")
    print(f"cell link: {link}")
    if args.dry_run:
        print("dry run: no records written")
        return 0
    for path, rec in out.items():
        write_record(path, rec)
        print(f"wrote {path.relative_to(REPO)}")

    upload = [
        "uv run python scripts/publish_artifact_release.py --resource-type parameter_set",
        f"--resource-id {uid} --version {args.artifact_version}",
    ]
    for distribution, path in zip(distributions, [source_path, runnable_path]):
        if path is not None and distribution["role"] in ("source", "runnable"):
            upload.append(f'--file "{path}" --role {distribution["role"]} --conforms-to "{distribution["conforms_to"]}"')
    print("\nUpload the files from the battinfo-registry checkout:\n  " + " \\\n    ".join(upload))
    print("\nThen publish, in order: the organization (if new), the cell spec (if new), and "
          f"python scripts/publish_parameter_sets.py --match '{args.source}--bpx' ...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
