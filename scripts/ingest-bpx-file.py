#!/usr/bin/env python3
"""Ingest a BPX parameter file as a published, runnable parameter set.

One BPX file becomes:

- a parameterisation-set record that carries the file itself under
  ``distributions`` (role ``source``: the bytes as published; role
  ``runnable``: a declared conversion when current parsers reject the source),
  addressed by the file's content, so its IRI always resolves to the same
  parameters (IDENTIFIER_POLICY 6.3);
- one member record per BPX block (materials, electrode builds, separator,
  electrolyte) carrying the claims, for search and collation;
- the cell-spec record the set targets.

Records land under ``records/parameter-set/<target>--<source>--bpx/`` and
``records/cell-spec/<slug>/``. The files themselves are NOT committed here:
they are written to ``--out-dir`` for upload to the registry's immutable
artifact store, and the records carry their sha256 so anyone can verify them.

Checks recorded on each file: the official ``bpx`` parser's verdict, and a
PyBaMM smoke run (1C discharge to the lower cut-off, the model the header
names) when ``--sim-python`` points at an interpreter with pybamm and bpx.

Requires BattINFO with ``bpx_file_distribution`` (BIG-MAP/BattINFO#421). Run
from the repo root with that checkout's environment:

    ../BattINFO/.venv/Scripts/python scripts/ingest-bpx-file.py schmitt2026-hydra \\
        --artifacts-base-url https://<public artifacts base> \\
        --sim-python C:/t/bpxsim/Scripts/python.exe --out-dir ../bpx-artifacts

Then upload the printed files with the registry's artifact-release CLI (the
script prints the exact command), and publish with
``scripts/publish_parameter_sets.py --match '*--<source>--bpx'``, which checks
each file URL against its sha256 before posting.

Licenses are set here, as conditions of the source. Funding and contributor
are stamped at publish, as for every corpus publication.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from urllib.request import urlopen

REPO = Path(__file__).resolve().parent.parent
PARAMETER_SET_DIR = REPO / "records" / "parameter-set"
CELL_SPEC_DIR = REPO / "records" / "cell-spec"

# One entry per published BPX file. The URL pins a commit, so the bytes the
# record describes can always be fetched again from the source as well.
SOURCES: dict[str, dict] = {
    "schmitt2026-hydra": {
        "url": (
            "https://raw.githubusercontent.com/BattMoTeam/schmitt-2026-lnmo-graphite-hydra-publication/"
            "51092701d66b8dcaa88febaa132ff877f7ebc6db/parameters/"
            "IMP5-70-120-H0B_graphite-lnmo_schmitt-2026_validation.bpx.json"
        ),
        "repository": "https://github.com/BattMoTeam/schmitt-2026-lnmo-graphite-hydra-publication",
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
        "cell_spec_slug": "hydra--imp5-70-120-h0b--2026",
        "cell_spec": {
            "name": "HYDRA0 1 Ah graphite|LNMO prototype pouch cell",
            "model": "IMP5-70-120-H0B",
            # The cell was developed within the Horizon Europe project HYDRA
            # (Zenodo 10.5281/zenodo.18256663). Replace with the building lab
            # once confirmed; the parameter-set IRIs do not depend on it.
            "manufacturer": "HYDRA project (Horizon Europe)",
            "format": "pouch",
            "chemistry": "li-ion",
            "positive_electrode_basis": "LNMO",
            "negative_electrode_basis": "graphite",
            "rechargeable": True,
        },
        "software_requirements": None,
    },
}

# Member record slugs: block key -> target part of "<target>--<source>--bpx".
MEMBER_SLUG = {
    "negative_electrode": "negative-electrode",
    "positive_electrode": "positive-electrode",
    "separator": "separator",
    "electrolyte": "electrolyte",
    "set": "cell",
}

SMOKE_RUN = r"""
import json, sys, time
import pybamm
doc = json.load(open(sys.argv[1], encoding="utf-8"))
model_name = sys.argv[2]
pv = pybamm.ParameterValues.create_from_bpx_obj(doc)
low = pv["Lower voltage cut-off [V]"]
model = {"DFN": pybamm.lithium_ion.DFN, "SPMe": pybamm.lithium_ion.SPMe, "SPM": pybamm.lithium_ion.SPM}[model_name]()
start = time.time()
sim = pybamm.Simulation(model, parameter_values=pv, experiment=pybamm.Experiment([f"Discharge at 1C until {low} V"]))
sol = sim.solve()
print(json.dumps({
    "pybamm": pybamm.__version__,
    "seconds": round(time.time() - start, 2),
    "capacity_ah": float(sol["Discharge capacity [A.h]"].entries[-1]),
    "lower_cutoff_v": float(low),
}))
"""


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
    return {
        "check": "simulation_smoke",
        "tool": f"pybamm {result['pybamm']}",
        "passed": True,
        "detail": (
            f"{model}, 1C discharge to {result['lower_cutoff_v']:g} V solved in {result['seconds']:g} s; "
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


def write_record(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("source", choices=sorted(SOURCES))
    parser.add_argument("--artifacts-base-url", required=True,
                        help="public base URL of the registry artifact store (STORAGE_ARTIFACTS_BASE_URL)")
    parser.add_argument("--artifact-version", default="v1")
    parser.add_argument("--out-dir", type=Path, default=REPO.parent / "bpx-artifacts",
                        help="where the files to upload are written (outside the repo)")
    parser.add_argument("--sim-python", default=None,
                        help="python with pybamm and bpx installed, for the smoke run")
    parser.add_argument("--dry-run", action="store_true", help="build and validate; write no records")
    args = parser.parse_args()

    import battinfo
    from battinfo.api import save_cell_spec
    from battinfo.interop import (
        bpx_file_distribution,
        check_bpx,
        from_bpx,
        from_bpx_parameters,
        upgrade_bpx,
    )
    from battinfo.validate import validate_record_report

    source = SOURCES[args.source]
    raw = fetch(source["url"])
    file_name = source["url"].rsplit("/", 1)[-1]

    # The uid is the file's: known before any record exists, so the upload
    # path and the records agree by construction.
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
    upgraded = upgrade_bpx(source_path)
    runnable_path = None
    if upgraded.changed:
        runnable_path = file_dir / file_name.replace(".bpx.json", ".bpx-1.1.json")
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
            description="The BPX file exactly as its authors published it.",
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
                description="The source rewritten in the BPX 1.1 layout, which current PyBaMM requires.",
                derived_from=distributions[0]["checksum"]["value"],
                conversion=upgraded.conversion_note(f"{battinfo_label(battinfo)} upgrade_bpx"),
                software_requirements=source["software_requirements"],
                checks=runnable_checks,
            )
        )

    # The cell spec the set targets: identity from the natural key, geometry
    # and limits from the file's Cell block.
    cell = from_bpx(source_path)
    spec_fields = dict(source["cell_spec"])
    spec_fields["properties"] = dict(cell.specs)
    # save_cell_spec mints and validates; it writes into a scratch root under
    # --out-dir, and the record is read back from there.
    saved = save_cell_spec(spec_fields, source_root=args.out_dir / "_cell-spec", mode="upsert",
                           build_jsonld=False, build_html=False)
    cell_record = json.loads(Path(saved["path"]).read_text(encoding="utf-8"))
    cell_record["provenance"].update({"source_type": "literature", "source_url": source["url"],
                                      "citation": source["citation"]})
    cell_record["license"] = source["license"]
    cell_record["notes"] = [source["attribution"]]
    cell_spec_id = cell_record["cell_spec"]["id"]

    records = imported.to_records(
        materials=source["materials"],
        cell_spec_id=cell_spec_id,
        by_block=True,
        distributions=distributions,
        citation=source["citation"],
        source_url=source["url"],
        notes=[source["attribution"], *source["notes"]],
    )
    out: dict[Path, dict] = {CELL_SPEC_DIR / source["cell_spec_slug"] / "record.json": cell_record}
    for block, record in records.items():
        record["license"] = source["license"]
        if block in MEMBER_SLUG:
            target = MEMBER_SLUG[block]
        else:  # negative_material / positive_material: the material kind
            target = record["parameter_set"]["material_kind"]
        out[PARAMETER_SET_DIR / f"{target}--{args.source}--bpx" / "record.json"] = record

    for path, record in out.items():
        report = validate_record_report(record)
        if not report.ok:
            raise SystemExit(f"{path.parent.name}: invalid record: {report.errors}")

    for warning in imported.warnings:
        print(f"import note: {warning[:300]}")
    for distribution in distributions:
        verdicts = ", ".join(f"{c['check']}={'pass' if c['passed'] else 'FAIL'}" for c in distribution["checks"])
        print(f"{distribution['role']:9s} {distribution['name']}  sha256 {distribution['checksum']['value'][:16]}...  {verdicts}")
    print(f"set IRI: {records['set']['parameter_set']['id']}")
    print(f"cell spec: {cell_spec_id}")
    if args.dry_run:
        print("dry run: no records written")
        return 0
    for path, record in out.items():
        write_record(path, record)
        print(f"wrote {path.relative_to(REPO)}")

    upload = [
        "uv run python scripts/publish_artifact_release.py --resource-type parameter_set",
        f"--resource-id {uid} --version {args.artifact_version}",
    ]
    for distribution, path in zip(distributions, [source_path, runnable_path]):
        upload.append(f'--file "{path}" --role {distribution["role"]} --conforms-to "{distribution["conforms_to"]}"')
    print("\nUpload the files from the battinfo-registry checkout:\n  " + " \\\n    ".join(upload))
    print(f"\nThen publish the cell spec, and: python scripts/publish_parameter_sets.py --match '*--{args.source}--bpx' ...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
