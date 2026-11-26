"""A BPX file's top-level Metadata and @context never reach the bpx parser.

The tests need PyBaMM with bpx, as the scripts do:

    uv run --no-project --with "pybamm[bpx]==26.10.1.1" --with pytest pytest tests
"""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("pybamm")
pytest.importorskip("bpx")

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import simulation_protocol as protocol  # noqa: E402

CONTEXT = "https://example.org/bpx/context.jsonld"
METADATA = {
    "Licence": "https://spdx.org/licenses/CC-BY-4.0.html",
    "Cell": {"Record": "https://w3id.org/battinfo/spec/0000-0000-0000-0000"},
    "Citation": "https://example.org/papers/1",
    "Derived from": "https://example.org/data/1",
}


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def plain() -> dict:
    """A BPX 1.1 file as export-pybamm-bpx.py writes it, from PyBaMM's Prada2013 set."""
    return load_script("export-pybamm-bpx").export("Prada2013")[0]


@pytest.fixture(scope="module")
def with_metadata(plain: dict) -> dict:
    return {"@context": CONTEXT, **plain, "Metadata": METADATA}


def test_only_the_two_top_level_keys_are_dropped(plain: dict, with_metadata: dict) -> None:
    before = copy.deepcopy(with_metadata)
    assert protocol.without_metadata(with_metadata) == plain
    assert with_metadata == before  # the caller's dict is untouched


def test_the_simulations_read_the_same_parameters_from_a_file_with_metadata(plain: dict, with_metadata: dict) -> None:
    expected = protocol.parameter_values(json.dumps(plain).encode())
    values = protocol.parameter_values(json.dumps(with_metadata).encode())
    assert sorted(values.keys()) == sorted(expected.keys())
    for key in expected.keys():
        if isinstance(expected[key], (int, float)):
            assert values[key] == expected[key], key


def test_the_ingest_smoke_run_reads_a_file_with_metadata(with_metadata: dict, tmp_path: Path) -> None:
    path = tmp_path / "with-metadata.bpx.json"
    path.write_text(json.dumps(with_metadata), encoding="utf-8")
    check = load_script("ingest-bpx-file").smoke_check(sys.executable, path, "SPM")
    assert check["passed"], check["detail"]
