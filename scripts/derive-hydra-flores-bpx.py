#!/usr/bin/env python3
"""Build a BPX file from HYDRA's parameters with the Flores OCP claims in place of HYDRA's OCPs.

Start: the runnable BPX file of the HYDRA graphite/LNMO parameter set (Schmitt et al.
2026), fetched through its IRI with ``?format=bpx`` and checked against the sha256 its
record (``records/parameter-set/schmitt2026-hydra--bpx``) gives for that file.

Changes, and nothing else:

- each electrode's ``OCP [V]`` table becomes the average-branch ``ocp`` claim of one
  Flores claim batch (graphite: Gr-AQ-1; LNMO: LNMO-AQ-2), point for point;
- the ``Validation`` section is removed, since no cell with these OCPs was measured;
- the ``User-defined`` open-circuit voltages at 0% and 100% SOC, which HYDRA states for
  its own OCPs at its stoichiometry windows, are recomputed the same way for the new
  OCPs. PyBaMM sets a file's initial state from these two values; HYDRA's would be
  unreachable with the new curves and would move the windows;
- the upper voltage cut-off becomes the file's own open-circuit voltage at 100% SOC,
  rounded to the mV, so that charging does not go past the stated full state; HYDRA's 4.9 V lies
  beyond the Flores LNMO curve, which ends at 4.8 V vs Li/Li+;
- the header says what the file is.

The stoichiometry windows, kinetics, transport, geometry and state are HYDRA's. The
Flores LNMO is another powder than HYDRA's, so the file describes a virtual cell.

    python scripts/derive-hydra-flores-bpx.py --out-dir <folder>

The output is deterministic: the same inputs give the same bytes.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np

REPO = Path(__file__).resolve().parent.parent
PARAMETER_SET_DIR = REPO / "records" / "parameter-set"
HYDRA_RECORD = PARAMETER_SET_DIR / "schmitt2026-hydra--bpx" / "record.json"
OCP_CLAIMS = {"Negative electrode": "graphite--flores2026-gr-aq-1--p-ocv",
              "Positive electrode": "lnmo--flores2026-lnmo-aq-2--p-ocv"}
FILE_NAME = "hydra-graphite-lnmo_flores-2026-ocp.bpx.json"
USER_AGENT = "battinfo-records/derive-hydra-flores-bpx"  # the file host refuses Python's default
OCV_KEYS = ("Open-circuit voltage at 0% SOC [V]", "Open-circuit voltage at 100% SOC [V]")

TITLE = "HYDRA graphite/LNMO parameters with Flores 2026 OCPs"
DESCRIPTION = (
    "The HYDRA graphite/LNMO parameter set of Schmitt et al. 2026 with both electrode OCP tables replaced by "
    "average-branch p-OCV curves of Flores et al. 2026 (graphite Gr-AQ-1, LNMO LNMO-AQ-2), and the open-circuit "
    "voltages at 0% and 100% SOC in User-defined recomputed for them at HYDRA's stoichiometry windows. "
    "The upper voltage cut-off is the open-circuit voltage at 100% SOC, so that charging does not go past the "
    "full state. A virtual cell: the Flores LNMO is another powder, and no cell with these OCPs was measured, so the "
    "Validation section is removed. Everything else is HYDRA's, including its kinetics: each electrode's "
    "reaction-rate constant is a single BPX value fitted to a BattMo j0(soc) table."
)
REFERENCES = "Schmitt et al., arXiv:2601.10507; Flores et al., https://doi.org/10.5281/zenodo.20086298"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hydra_runnable(local: Path | None) -> bytes:
    """HYDRA's runnable file, checked against its record."""
    record = json.loads(HYDRA_RECORD.read_text(encoding="utf-8"))["parameter_set"]
    dist = next(d for d in record["distributions"] if d["role"] == "runnable")
    expected = dist["checksum"]["value"]
    if local is not None:
        raw = local.read_bytes()
    else:
        request = Request(f"{record['id']}?format=bpx", headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=300) as response:
            raw = response.read()
    if sha256(raw) != expected:
        raise SystemExit(f"HYDRA file sha256 {sha256(raw)} is not the record's runnable file ({expected})")
    return raw


def average_claim(slug: str) -> tuple[str, dict]:
    """The batch IRI and the one average-branch ocp curve of a Flores claim batch."""
    body = json.loads((PARAMETER_SET_DIR / slug / "record.json").read_text(encoding="utf-8"))["parameter_set"]
    curves = [c["curve"] for c in body["claims"] if c["parameter"] == "ocp" and c["curve"].get("branch") == "average"]
    if len(curves) != 1:
        raise SystemExit(f"{slug}: expected one average-branch ocp claim, found {len(curves)}")
    return body["id"], curves[0]


def derive(hydra: dict) -> dict:
    doc = copy.deepcopy(hydra)
    doc["Header"]["Title"] = TITLE
    doc["Header"]["Description"] = DESCRIPTION
    doc["Header"]["References"] = REFERENCES
    params = doc["Parameterisation"]
    tables = {}
    for block, slug in OCP_CLAIMS.items():
        _, curve = average_claim(slug)
        params[block]["OCP [V]"] = {"x": list(curve["x"]), "y": list(curve["y"])}
        tables[block] = curve
    doc.pop("Validation", None)

    # OCV at the window ends, read from the tables by linear interpolation as BPX tables are.
    def ocp(block: str, x: float) -> float:
        return float(np.interp(x, tables[block]["x"], tables[block]["y"]))

    neg, pos = params["Negative electrode"], params["Positive electrode"]
    empty = ocp("Positive electrode", pos["Maximum stoichiometry"]) - ocp("Negative electrode", neg["Minimum stoichiometry"])
    full = ocp("Positive electrode", pos["Minimum stoichiometry"]) - ocp("Negative electrode", neg["Maximum stoichiometry"])
    user = params.get("User-defined") or {}
    if not all(key in user for key in OCV_KEYS):
        raise SystemExit("HYDRA's User-defined block no longer states the open-circuit voltages at 0% and 100% SOC")
    user[OCV_KEYS[0]] = empty
    user[OCV_KEYS[1]] = full
    # Charging does not go past the stated full state or the end of the Flores LNMO curve.
    params["Cell"]["Upper voltage cut-off [V]"] = round(full, 3)
    return doc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out-dir", type=Path, required=True, help="where the BPX file is written (outside the repo)")
    parser.add_argument("--hydra-file", type=Path, default=None,
                        help="a local copy of HYDRA's runnable file (checked by sha256); fetched when not given")
    args = parser.parse_args()

    doc = derive(json.loads(hydra_runnable(args.hydra_file)))
    data = (json.dumps(doc, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / FILE_NAME
    out.write_bytes(data)
    user = doc["Parameterisation"]["User-defined"]
    print(f"wrote {out}  sha256 {sha256(data)}")
    for block, slug in OCP_CLAIMS.items():
        print(f"  {block} OCP: average branch of {average_claim(slug)[0]} ({slug})")
    print(f"  {OCV_KEYS[0]} = {user[OCV_KEYS[0]]}, {OCV_KEYS[1]} = {user[OCV_KEYS[1]]}")
    print(f"  Upper voltage cut-off [V] = {doc['Parameterisation']['Cell']['Upper voltage cut-off [V]']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
