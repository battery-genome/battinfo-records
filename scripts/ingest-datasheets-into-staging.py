#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


UID_ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"
CORP_TOKENS = {
    "co",
    "company",
    "corp",
    "corporation",
    "inc",
    "limited",
    "ltd",
    "sdi",
}
GENERIC_MODEL_TOKENS = {"alt", "bg", "brochure", "catalog", "datasheet", "tentative", "spec", "specification"}
TEXT_SKIP_DIRS = {"_sources"}


@dataclass
class StagedRecord:
    path: Path
    payload: dict[str, Any]

    @property
    def manufacturer(self) -> str:
        product = self.payload.get("product", {})
        manufacturer = product.get("manufacturer", {})
        if isinstance(manufacturer, dict):
            return str(manufacturer.get("name", "")).strip()
        return str(manufacturer).strip()

    @property
    def model(self) -> str:
        return str(self.payload.get("product", {}).get("model", "")).strip()


@dataclass
class DatasheetCandidate:
    source_path: Path
    text_path: Path | None
    manufacturer: str
    model: str
    stem: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Supplement BattINFO staging cell-type records from local datasheets.")
    parser.add_argument(
        "--staging-dir",
        default=r"c:\Users\simonc\Documents\Github-local\battery-genome\battinfo-records\records\_staging\cell-type",
    )
    parser.add_argument("--datasheets-dir", default=r"D:\datasheets")
    parser.add_argument(
        "--report-path",
        default=r"c:\Users\simonc\Documents\Github-local\battery-genome\battinfo-records\.battinfo\datasheet-intake-report.json",
    )
    parser.add_argument(
        "--battinfo-src",
        default=r"c:\Users\simonc\Documents\Github-local\battery-genome\BattINFO\src",
    )
    return parser.parse_args()


def stable_uid(seed: str) -> str:
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    bits = "".join(f"{byte:08b}" for byte in digest)
    chars = "".join(UID_ALPHABET[int(bits[i * 5 : (i + 1) * 5], 2)] for i in range(16))
    return f"{chars[0:4]}-{chars[4:8]}-{chars[8:12]}-{chars[12:16]}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def normalize_manufacturer(value: str, *, loose: bool) -> str:
    tokens = re.findall(r"[a-z0-9]+", value.lower())
    if loose:
        tokens = [token for token in tokens if token not in CORP_TOKENS]
    return "".join(tokens)


def normalize_model(value: str, *, loose: bool) -> str:
    tokens = re.findall(r"[a-z0-9]+", value.lower())
    if loose:
        tokens = [token for token in tokens if token not in GENERIC_MODEL_TOKENS]
    return "".join(tokens)


def kebab(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    text = re.sub(r"-{2,}", "-", text)
    return text or "unknown"


def infer_filename_parts(stem: str) -> tuple[str, list[str]]:
    parts = [part for part in stem.split("__") if part]
    if len(parts) >= 2:
        manufacturer = parts[0].replace("_", " ").strip()
        models = [part.replace("_", " ").strip() for part in parts[1:] if part.strip()]
        return manufacturer, models
    match = re.match(r"^([A-Za-z0-9]+)[_-]{1,2}(.+)$", stem)
    if match:
        return match.group(1).replace("_", " ").strip(), [match.group(2).replace("_", " ").strip()]
    return stem.replace("_", " ").strip(), []


def discover_text_map(datasheets_dir: Path) -> dict[str, list[Path]]:
    text_map: dict[str, list[Path]] = {}
    for path in datasheets_dir.rglob("*.txt"):
        if any(part in TEXT_SKIP_DIRS for part in path.parts):
            continue
        key = normalize_text(path.stem)
        text_map.setdefault(key, []).append(path)
    return text_map


def choose_text_path(candidate: DatasheetCandidate, text_map: dict[str, list[Path]]) -> Path | None:
    keys = [
        normalize_text(candidate.stem),
        normalize_text(candidate.model),
        normalize_text(f"{candidate.manufacturer}{candidate.model}"),
    ]
    for key in keys:
        paths = text_map.get(key, [])
        if paths:
            return sorted(paths, key=lambda item: (len(item.stem), item.name.lower()))[0]
    model_key = normalize_text(candidate.model)
    if model_key:
        fuzzy = [
            path
            for key, paths in text_map.items()
            if model_key in key or key in model_key
            for path in paths
        ]
        if fuzzy:
            return sorted(fuzzy, key=lambda item: (len(item.stem), item.name.lower()))[0]
    return None


def load_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    if path.suffix.lower() == ".html":
        raw = path.read_text(encoding="utf-8", errors="ignore")
        return re.sub(r"<[^>]+>", " ", raw)
    return path.read_text(encoding="utf-8", errors="ignore")


def extract_doi(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    match = re.search(r"(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)", text)
    return match.group(1) if match else None


def set_if_missing(product: dict[str, Any], key: str, value: Any) -> bool:
    if value in (None, "", "unknown"):
        return False
    current = product.get(key)
    if current in (None, "", "unknown"):
        product[key] = value
        return True
    return False


def add_note(payload: dict[str, Any], note: str) -> None:
    notes = payload.setdefault("notes", [])
    if note not in notes:
        notes.append(note)


def convert_capacity(value: float, unit: str) -> tuple[float, str]:
    lowered = unit.lower()
    if lowered == "mah":
        return value / 1000.0, "Ah"
    return value, "Ah"


def convert_current(value: float, unit: str) -> tuple[float, str]:
    lowered = unit.lower()
    if lowered == "ma":
        return value / 1000.0, "A"
    return value, "A"


def convert_mass(value: float, unit: str) -> tuple[float, str]:
    lowered = unit.lower()
    if lowered == "g":
        return value / 1000.0, "kg"
    return value, "kg"


def convert_length(value: float, unit: str) -> tuple[float, str]:
    lowered = unit.lower()
    if lowered == "mm":
        return value / 1000.0, "m"
    if lowered == "cm":
        return value / 100.0, "m"
    return value, "m"


def convert_resistance(value: float, unit: str) -> tuple[float, str]:
    lowered = unit.lower()
    if lowered in {"mω", "mohm", "milli ohm", "milliohm"}:
        return value, "mohm"
    return value, "ohm"


def parse_float(text: str) -> float | None:
    cleaned = text.replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_year(text: str) -> int | None:
    for pattern in [
        r"©\s*(20\d{2})",
        r"Date of Application.*?(\d{4})/\d{2}/\d{2}",
        r"\b(20\d{2})\b",
    ]:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            year = int(match.group(1))
            if 1990 <= year <= 2035:
                return year
    return None


def infer_cell_format(model: str, text: str) -> tuple[str, str | None]:
    model_upper = model.upper()
    text_lower = text.lower()
    match = re.search(r"(18650|18500|20700|21700|26650|26700|32135|32140|32650|32700|66160|4680)", model_upper)
    if match:
        return "cylindrical", f"R{match.group(1)}"
    coin = re.search(r"\b(CR|LIR|LR)(\d{3,5})\b", model_upper)
    if coin:
        return "coin", None
    if "cylindrical" in text_lower:
        return "cylindrical", None
    if "pouch" in text_lower:
        return "pouch", None
    if "prismatic" in text_lower:
        return "prismatic", None
    return "unknown", None


def infer_chemistry(model: str, text: str) -> tuple[str, str | None, str | None]:
    blob = f"{model} {text}".lower()
    if "lifepo4" in blob or "lithium iron phosphate" in blob or "nanophosphate" in blob:
        return "Li-ion", "LFP", None
    if "lithium titanate" in blob or re.search(r"\blto\b", blob):
        return "Li-ion", None, "LTO"
    if "nickel manganese cobalt" in blob or re.search(r"\bnmc\b", blob):
        return "Li-ion", "NMC", None
    if "nickel cobalt aluminum" in blob or "nickel cobalt aluminium" in blob or re.search(r"\bnca\b", blob):
        return "Li-ion", "NCA", None
    if "lithium cobalt oxide" in blob or re.search(r"\blco\b", blob):
        return "Li-ion", "LCO", None
    if "lithium manganese oxide" in blob or re.search(r"\blmo\b", blob):
        return "Li-ion", "LMO", None
    if re.search(r"\bcr\d{3,5}\b", model.lower()) or "lithium manganese dioxide" in blob:
        return "Li-primary", "MnO2", "Li-metal"
    if "lithium-metal" in blob or "lithium metal" in blob:
        return "Li-metal", None, "Li-metal"
    if "lithium-ion" in blob or "li-ion" in blob:
        return "Li-ion", None, None
    return "unknown", None, None


def add_spec(specs: dict[str, Any], key: str, value: float | None, unit: str | None) -> None:
    if value is None or unit is None or key in specs:
        return
    specs[key] = {"value": value, "unit": unit}


def parse_specs(text: str, cell_format: str) -> dict[str, Any]:
    specs: dict[str, Any] = {}
    for pattern, target in [
        (r"Rated discharge Capacity.*?([0-9][0-9,]*(?:\.[0-9]+)?)\s*(mAh|Ah)", "rated_capacity"),
        (r"Standard discharge Capacity.*?([0-9][0-9,]*(?:\.[0-9]+)?)\s*(mAh|Ah)", "nominal_capacity"),
        (r"Cell Capacity \(nominal/minimum\).*?([0-9][0-9,]*(?:\.[0-9]+)?)\s*/\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(mAh|Ah)", "nominal_min"),
        (r"Nominal Capacity.*?([0-9][0-9,]*(?:\.[0-9]+)?)\s*(mAh|Ah)", "nominal_capacity"),
        (r"Minimum Capacity.*?([0-9][0-9,]*(?:\.[0-9]+)?)\s*(mAh|Ah)", "minimum_capacity"),
    ]:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        if target == "nominal_min":
            nominal = parse_float(match.group(1))
            minimum = parse_float(match.group(2))
            unit = match.group(3)
            if nominal is not None:
                value, out_unit = convert_capacity(nominal, unit)
                add_spec(specs, "nominal_capacity", value, out_unit)
            if minimum is not None:
                value, out_unit = convert_capacity(minimum, unit)
                add_spec(specs, "minimum_capacity", value, out_unit)
        else:
            value = parse_float(match.group(1))
            if value is not None:
                numeric, out_unit = convert_capacity(value, match.group(2))
                add_spec(specs, target, numeric, out_unit)

    for pattern, key in [
        (r"Nominal Voltage.*?([0-9]+(?:\.[0-9]+)?)\s*V", "nominal_voltage"),
        (r"Charging Voltage.*?([0-9]+(?:\.[0-9]+)?)\s*V", "charging_voltage"),
        (r"Discharge Cut-?off Voltage.*?([0-9]+(?:\.[0-9]+)?)\s*V", "discharging_cutoff_voltage"),
        (r"Internal (?:Impedance|Resistance).*?([0-9]+(?:\.[0-9]+)?)\s*(mΩ|mohm|Ohm|ohm)", "internal_resistance"),
    ]:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        value = parse_float(match.group(1))
        if value is None:
            continue
        if key == "internal_resistance":
            numeric, unit = convert_resistance(value, match.group(2))
        else:
            numeric, unit = value, "V"
        add_spec(specs, key, numeric, unit)

    for pattern, key in [
        (r"Maximum Continuous Discharge.*?([0-9][0-9,]*(?:\.[0-9]+)?)\s*(mA|A)", "maximum_continuous_discharging_current"),
        (r"Max\. Discharge Current.*?([0-9][0-9,]*(?:\.[0-9]+)?)\s*(mA|A).*?continuous discharge", "maximum_continuous_discharging_current"),
        (r"Maximum Pulse Discharge.*?([0-9][0-9,]*(?:\.[0-9]+)?)\s*(mA|A)", "pulse_discharging_current"),
        (r"Max\. Discharge Current.*?([0-9][0-9,]*(?:\.[0-9]+)?)\s*(mA|A).*?not for continuous discharge", "pulse_discharging_current"),
        (r"Recommended Standard Charge Method.*?([0-9][0-9,]*(?:\.[0-9]+)?)\s*(mA|A)", "nominal_continuous_charging_current"),
        (r"Charging Current.*?Standard charge:\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(mA|A)", "nominal_continuous_charging_current"),
        (r"Max\. Charge Current.*?([0-9][0-9,]*(?:\.[0-9]+)?)\s*(mA|A)", "maximum_continuous_charging_current"),
        (r"Charging Time.*?([0-9]+(?:\.[0-9]+)?)\s*(hours|hour|min|minutes)", "charging_time"),
    ]:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        value = parse_float(match.group(1))
        if value is None:
            continue
        if key == "charging_time":
            unit = "h" if "hour" in match.group(2).lower() else "min"
            add_spec(specs, key, value, unit)
        else:
            numeric, unit = convert_current(value, match.group(2))
            add_spec(specs, key, numeric, unit)

    cycle_match = re.search(r"Cycle Life.*?([0-9][0-9,]*(?:\.[0-9]+)?)\s*cycles", text, flags=re.IGNORECASE | re.DOTALL)
    if cycle_match:
        value = parse_float(cycle_match.group(1))
        add_spec(specs, "cycle_life", value, "count")

    mass_match = re.search(r"(?:Cell Weight|Weight).*?([0-9][0-9,]*(?:\.[0-9]+)?)\s*(g|kg)\b", text, flags=re.IGNORECASE | re.DOTALL)
    if mass_match:
        value = parse_float(mass_match.group(1))
        if value is not None:
            numeric, unit = convert_mass(value, mass_match.group(2))
            add_spec(specs, "mass", numeric, unit)

    if cell_format == "cylindrical":
        dia_match = re.search(r"Diameter.*?([0-9]+(?:\.[0-9]+)?)\s*mm", text, flags=re.IGNORECASE | re.DOTALL)
        height_match = re.search(r"Cell height.*?([0-9]+(?:\.[0-9]+)?)\s*mm", text, flags=re.IGNORECASE | re.DOTALL)
        if dia_match:
            value = parse_float(dia_match.group(1))
            if value is not None:
                numeric, unit = convert_length(value, "mm")
                add_spec(specs, "diameter", numeric, unit)
        if height_match:
            value = parse_float(height_match.group(1))
            if value is not None:
                numeric, unit = convert_length(value, "mm")
                add_spec(specs, "height", numeric, unit)
        size_match = re.search(r"\b([0-9]{2})\s*[xX]\s*([0-9]{2,3}(?:\.[0-9]+)?)\s*mm\b", text)
        if size_match:
            diameter = parse_float(size_match.group(1))
            height = parse_float(size_match.group(2))
            if diameter is not None and "diameter" not in specs:
                numeric, unit = convert_length(diameter, "mm")
                add_spec(specs, "diameter", numeric, unit)
            if height is not None and "height" not in specs:
                numeric, unit = convert_length(height, "mm")
                add_spec(specs, "height", numeric, unit)
    else:
        dims = re.search(
            r"([0-9]+(?:\.[0-9]+)?)\s*[xX]\s*([0-9]+(?:\.[0-9]+)?)\s*[xX]\s*([0-9]+(?:\.[0-9]+)?)\s*mm",
            text,
            flags=re.IGNORECASE,
        )
        if dims:
            values = sorted([parse_float(dims.group(1)), parse_float(dims.group(2)), parse_float(dims.group(3))])
            if all(value is not None for value in values):
                thickness, width, length = values
                for key, raw in [("thickness", thickness), ("width", width), ("length", length)]:
                    numeric, unit = convert_length(float(raw), "mm")
                    add_spec(specs, key, numeric, unit)

    for pattern, key in [
        (r"Charge\s*:\s*([\-0-9]+)\s*to\s*([\-0-9]+)\s*°?C", ("minimum_charging_temperature", "maximum_charging_temperature")),
        (r"Discharge\s*:\s*([\-0-9]+)\s*to\s*([\-0-9]+)\s*°?C", ("minimum_discharging_temperature", "maximum_discharging_temperature")),
        (r"Storage Temperature.*?([\-0-9]+)\s*[~to]+\s*([\-0-9]+)\s*°?C", ("minimum_storage_temperature", "maximum_storage_temperature")),
    ]:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        low = parse_float(match.group(1))
        high = parse_float(match.group(2))
        if low is not None:
            add_spec(specs, key[0], low, "°C")
        if high is not None:
            add_spec(specs, key[1], high, "°C")
    return specs


def build_indexes(records: list[StagedRecord]) -> tuple[dict[tuple[str, str], list[StagedRecord]], dict[tuple[str, str], list[StagedRecord]]]:
    strict: dict[tuple[str, str], list[StagedRecord]] = {}
    loose: dict[tuple[str, str], list[StagedRecord]] = {}
    for record in records:
        strict_key = (normalize_manufacturer(record.manufacturer, loose=False), normalize_model(record.model, loose=False))
        loose_key = (normalize_manufacturer(record.manufacturer, loose=True), normalize_model(record.model, loose=True))
        strict.setdefault(strict_key, []).append(record)
        loose.setdefault(loose_key, []).append(record)
    return strict, loose


def match_record(
    candidate: DatasheetCandidate,
    strict_index: dict[tuple[str, str], list[StagedRecord]],
    loose_index: dict[tuple[str, str], list[StagedRecord]],
) -> tuple[StagedRecord | None, str]:
    strict_key = (normalize_manufacturer(candidate.manufacturer, loose=False), normalize_model(candidate.model, loose=False))
    matches = strict_index.get(strict_key, [])
    if len(matches) == 1:
        return matches[0], "strict"
    if len(matches) > 1:
        return None, "ambiguous_strict"
    loose_key = (normalize_manufacturer(candidate.manufacturer, loose=True), normalize_model(candidate.model, loose=True))
    matches = loose_index.get(loose_key, [])
    if len(matches) == 1:
        return matches[0], "loose"
    if len(matches) > 1:
        return None, "ambiguous_loose"
    return None, "none"


def choose_source_text(candidate: DatasheetCandidate) -> str:
    return load_text(candidate.text_path)


def supplement_record(record: StagedRecord, candidate: DatasheetCandidate, parsed: dict[str, Any]) -> bool:
    changed = False
    product = record.payload.setdefault("product", {})
    specs = record.payload.setdefault("specs", {})
    for key in ["cell_format", "chemistry", "positive_electrode_basis", "negative_electrode_basis", "size_code", "year"]:
        if set_if_missing(product, key, parsed.get(key)):
            changed = True
    for key, value in parsed["specs"].items():
        if key not in specs:
            specs[key] = value
            changed = True
        elif specs[key] != value:
            add_note(record.payload, f"Datasheet {candidate.source_path.name} reports {key}={value['value']} {value['unit']} but existing value was kept.")
    if changed:
        add_note(record.payload, f"Supplemented from datasheet {candidate.source_path.name}.")
    return changed


def build_new_record(candidate: DatasheetCandidate, parsed: dict[str, Any], retrieved_at: int) -> dict[str, Any]:
    uid = stable_uid(f"datasheet::{candidate.manufacturer.lower()}::{candidate.model.lower()}")
    record: dict[str, Any] = {
        "schema_version": "0.1.0",
        "product": {
            "id": f"https://w3id.org/battinfo/spec/{uid}",
            "short_id": uid.replace("-", "")[:6],
            "identifier": f"datasheet:{candidate.stem}::{candidate.model}" if "__" in candidate.stem else f"datasheet:{candidate.stem}",
            "name": f"{candidate.manufacturer} {candidate.model}".strip(),
            "model": candidate.model,
            "manufacturer": {"type": "Organization", "name": candidate.manufacturer},
            "category": "battery cell",
            "cell_format": parsed["cell_format"],
            "chemistry": parsed["chemistry"],
        },
        "specs": parsed["specs"],
        "provenance": {
            "source_type": "datasheet",
            "source_file": candidate.source_path.as_posix(),
            "retrieved_at": retrieved_at,
            "file_hash": sha256_file(candidate.source_path),
        },
        "notes": ["Created from local datasheet intake."],
    }
    for key in ["positive_electrode_basis", "negative_electrode_basis", "size_code", "year"]:
        value = parsed.get(key)
        if value not in (None, "", "unknown"):
            record["product"][key] = value
    return record


def parse_candidate(candidate: DatasheetCandidate) -> dict[str, Any]:
    text = choose_source_text(candidate)
    cell_format, size_code = infer_cell_format(candidate.model, text)
    chemistry, positive_electrode_basis, negative_electrode_basis = infer_chemistry(candidate.model, text)
    specs = parse_specs(text, cell_format)
    return {
        "cell_format": cell_format,
        "size_code": size_code,
        "chemistry": chemistry,
        "positive_electrode_basis": positive_electrode_basis,
        "negative_electrode_basis": negative_electrode_basis,
        "year": parse_year(text),
        "specs": specs,
    }


def load_staged_records(staging_dir: Path) -> list[StagedRecord]:
    records: list[StagedRecord] = []
    for path in sorted(staging_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            continue
        if "product" not in payload:
            continue
        records.append(StagedRecord(path=path, payload=payload))
    return records


def collect_datasheet_candidates(datasheets_dir: Path) -> list[DatasheetCandidate]:
    entries: list[DatasheetCandidate] = []
    text_map = discover_text_map(datasheets_dir)
    for path in sorted(datasheets_dir.rglob("*")):
        if not path.is_file():
            continue
        if any(part in TEXT_SKIP_DIRS or part == "_txt" for part in path.parts):
            continue
        if path.suffix.lower() not in {".pdf", ".html"}:
            continue
        manufacturer, models = infer_filename_parts(path.stem)
        if not models:
            continue
        for model in models:
            normalized_model = normalize_model(model, loose=True)
            if not normalized_model:
                continue
            if "catalog" in model.lower() or "brochure" in model.lower() or model.lower().startswith("actually-"):
                continue
            candidate = DatasheetCandidate(
                source_path=path,
                text_path=None,
                manufacturer=manufacturer,
                model=model,
                stem=path.stem,
            )
            candidate.text_path = choose_text_path(candidate, text_map)
            entries.append(candidate)
    return entries


def validate_payload(payload: dict[str, Any], battinfo_src: Path) -> tuple[bool, list[str]]:
    sys.path.insert(0, str(battinfo_src))
    try:
        from battinfo.validate import ValidationPolicy, validate_record_report

        report = validate_record_report(payload, policy=ValidationPolicy(name="strict", semantic="error"))
        return report.ok, [issue.message for issue in report.errors]
    finally:
        try:
            sys.path.remove(str(battinfo_src))
        except ValueError:
            pass


def main() -> int:
    args = parse_args()
    staging_dir = Path(args.staging_dir)
    datasheets_dir = Path(args.datasheets_dir)
    battinfo_src = Path(args.battinfo_src)
    report_path = Path(args.report_path)
    retrieved_at = int(time.time())

    records = load_staged_records(staging_dir)
    strict_index, loose_index = build_indexes(records)
    candidates = collect_datasheet_candidates(datasheets_dir)
    report: dict[str, Any] = {
        "generated_at": retrieved_at,
        "staging_dir": str(staging_dir),
        "datasheets_dir": str(datasheets_dir),
        "candidate_count": len(candidates),
        "supplemented": [],
        "created": [],
        "unchanged_matches": [],
        "ambiguous": [],
        "validation_failures": [],
    }

    for candidate in candidates:
        record, mode = match_record(candidate, strict_index, loose_index)
        parsed = parse_candidate(candidate)
        if record is not None:
            original = json.loads(json.dumps(record.payload))
            changed = supplement_record(record, candidate, parsed)
            if changed:
                ok, errors = validate_payload(record.payload, battinfo_src)
                if ok:
                    record.path.write_text(json.dumps(record.payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                    report["supplemented"].append({"file": str(record.path), "datasheet": str(candidate.source_path), "match_mode": mode})
                else:
                    record.payload = original
                    report["validation_failures"].append(
                        {"file": str(record.path), "datasheet": str(candidate.source_path), "errors": errors}
                    )
            else:
                report["unchanged_matches"].append(
                    {"file": str(record.path), "datasheet": str(candidate.source_path), "match_mode": mode}
                )
            continue

        if mode.startswith("ambiguous"):
            report["ambiguous"].append({"datasheet": str(candidate.source_path), "model": candidate.model, "reason": mode})
            continue

        new_payload = build_new_record(candidate, parsed, retrieved_at)
        target_name = kebab(f"{candidate.manufacturer}-{candidate.model}") + ".json"
        target_path = staging_dir / target_name
        if target_path.exists():
            report["ambiguous"].append(
                {
                    "datasheet": str(candidate.source_path),
                    "model": candidate.model,
                    "reason": f"target_exists:{target_name}",
                }
            )
            continue
        ok, errors = validate_payload(new_payload, battinfo_src)
        if ok:
            target_path.write_text(json.dumps(new_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            report["created"].append({"file": str(target_path), "datasheet": str(candidate.source_path)})
        else:
            report["validation_failures"].append(
                {"file": str(target_path), "datasheet": str(candidate.source_path), "errors": errors}
            )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(
        {
            "candidate_count": len(candidates),
            "supplemented": len(report["supplemented"]),
            "created": len(report["created"]),
            "unchanged_matches": len(report["unchanged_matches"]),
            "ambiguous": len(report["ambiguous"]),
            "validation_failures": len(report["validation_failures"]),
            "report_path": str(report_path),
        },
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
