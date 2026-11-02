"""Check that the files parameter-set records point at are uploaded and match their sha256.

CI runs it on the records a pull request adds or changes. Merging a record starts the Simulations
workflow, which fetches its files, so they must be in place first; the same check guards
publish_parameter_sets.py before it posts a record.

    python scripts/check-record-files.py records/parameter-set/<folder>/record.json [...]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from publish_parameter_sets import envelope_distributions, verify_files  # noqa: E402


def main(paths: list[str]) -> int:
    problems = 0
    for name in paths:
        path = Path(name)
        if not path.exists():
            print(f"{name}: no such file")
            problems += 1
            continue
        files = envelope_distributions(json.loads(path.read_text(encoding="utf-8")))
        # Simulations refuses a file without one, and verify_files has nothing to compare.
        found = [f"{entry['access_url']}: no sha256 in the record" for entry in files if not entry.get("checksum_sha256")]
        found += verify_files(files)
        for problem in found:
            print(f"{path.parent.name}: {problem}")
        if not found:
            print(f"{path.parent.name}: {len(files)} file(s) in place")
        problems += len(found)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
