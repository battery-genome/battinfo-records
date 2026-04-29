"""
sync_battery_knowledge_graph.py

Syncs organization records from the Battery Knowledge Graph (BKG)
https://battery.knowledge-graph.eu into battinfo-records.

For each of the 171 BKG organizations:
  - If a matching battinfo-records directory exists → adds/updates sameAs
  - If no match → creates a new record stub with data fetched from BKG

Usage:
    python scripts/sync_battery_knowledge_graph.py [--dry-run]

Requirements: Python 3.10+, no third-party deps.
"""
from __future__ import annotations

import argparse
import json
import re
import secrets
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BKG_API = "https://battery.knowledge-graph.eu/w/api.php"
BKG_WIKI = "https://battery.knowledge-graph.eu/wiki"
BATTINFO_BASE_IRI = "https://w3id.org/battinfo/organization"
RECORDS_ROOT = Path(__file__).parent.parent / "records" / "organization"
SCHEMA_VERSION = "0.1.0"

# Crockford base32 alphabet (no i, l, o, u)
_B32 = "0123456789abcdefghjkmnpqrstvwxyz"


def _new_battinfo_id() -> str:
    """Generate a random BattINFO opaque ID: xxxx-xxxx-xxxx-xxxx (Crockford base32)."""
    raw = secrets.token_bytes(10)
    bits = []
    for b in raw:
        for shift in range(7, -1, -1):
            bits.append((b >> shift) & 1)
    chars = []
    for i in range(0, 80, 5):
        val = (bits[i] << 4) | (bits[i+1] << 3) | (bits[i+2] << 2) | (bits[i+3] << 1) | bits[i+4]
        chars.append(_B32[val])
    return f"{''.join(chars[0:4])}-{''.join(chars[4:8])}-{''.join(chars[8:12])}-{''.join(chars[12:16])}"


# ---------------------------------------------------------------------------
# Full BKG organization list (171 entries) — name, machine_name, type
# ---------------------------------------------------------------------------

BKG_ORGS: list[tuple[str, str, str]] = [
    ("24M Technologies", "24mTechnologies", "Corporation"),
    ("Aalborg University", "AalborgUniversity", "University"),
    ("Aalto University", "Aalto", "University"),
    ("Aarhus University", "AarhusUniversity", "University"),
    ("Anodox Energy Systems", "Anodox", "Corporation"),
    ("Arbin", "Arbin", "Corporation"),
    ("Arkema", "Arkema", "Corporation"),
    ("Asociación Instituto Tecnológico de la Energía", "AsociaciNInstitutoTecnolGicoDeLaEnergA", "Research Organization"),
    ("Austrian Institute of Technology", "AIT", "Research Organization"),
    ("AutomotiveCellsCompany", "ACC", "Corporation"),
    ("Avesta Battery and Energy Engineering", "ABEE", "Corporation"),
    ("BASF SE", "BASF", "Corporation"),
    ("Basque Center for Macromolecular Design and Engineering", "BasqueCenterForMacromolecularDesignAndEngineering", "Research Organization"),
    ("BaSyTec", "BaSyTec", "Corporation"),
    ("Battery Associates", "BatteryAssociates", "Organization"),
    ("Battery Data Alliance", "BatteryDataAlliance", "Organization"),
    ("Bayerische Motoren Werke AG", "BMW", "Corporation"),
    ("BeDimensional", "BeDimensional", "Corporation"),
    ("Belenos Clean Power Holding AG", "Belenos", "Corporation"),
    ("BEPA", "BEPA", "Organization"),
    ("Bern University of Applied Sciences", "BFH", "Educational Organization"),
    ("Beyonder", "Beyonder", "Corporation"),
    ("Biologic", "Biologic", "Corporation"),
    ("Blackstone Resources AG", "BlackstoneResources", "Corporation"),
    ("Blackstone Technology GmbH", "BlackstoneTechnology", "Corporation"),
    ("BTR New Material Group", "BTR", "Corporation"),
    ("Cameron Sino Technology Limited", "CameronSinoTechnologyLimited", "Corporation"),
    ("Cellforce Group GmbH", "Cellforce", "Corporation"),
    ("Cellonic", "Cellonic", "Corporation"),
    ("Center for Solar Energy and Hydrogen Research", "CenterForSolarEnergyAndHydrogenResearch", "Organization"),
    ("Chalmers University of Technology", "Chalmers", "Educational Organization"),
    ("Changzhou Liyuan New Energy Technology", "LBM", "Corporation"),
    ("CIC energiGUNE", "CICenergiGUNE", "Research Organization"),
    ("CIDETEC Foundation", "CIDETEC", "Research Organization"),
    ("Circunomics GmbH", "CircunomicsGmbh", "Corporation"),
    ("Cleancarb Sarl", "Cleancarb", "Corporation"),
    ("College de France", "CollegeDeFrance", "Educational Organization"),
    ("Contemporary Amperex Technology Co., Ltd.", "CATL", "Corporation"),
    ("Corvus Energy", "CorvusEnergy", "Corporation"),
    ("Cuberg", "Cuberg", "Corporation"),
    ("CustomCells Itzehoe GmbH", "CustomCells", "Corporation"),
    ("Danish Battery Society", "DanishBatterySociety", "Organization"),
    ("Dassault Systemes Germany GmbH", "3DS", "Corporation"),
    ("Delft University of Technology", "TU Delft", "Educational Organization"),
    ("E-Lyte Innovations GmbH", "ELYTE", "Corporation"),
    ("EAS Batteries GmbH", "EAS", "Corporation"),
    ("Eindhoven University of Technology", "TU/e", "Educational Organization"),
    ("ElevenEs", "ElevenEs", "Corporation"),
    ("Elinor Batteries", "ElinorBatteries", "Corporation"),
    ("Elkem AS", "Elkem", "Corporation"),
    ("ElringKlinger", "ElringKlinger", "Corporation"),
    ("Empa - Swiss Federal Laboratories for Materials Science and Technology", "EmpaSwissFederalLaboratoriesForMaterialsScienceAndTechnology", "Organization"),
    ("Energy Materials Industrial Research Initiative", "EMIRI", "Association"),
    ("Enwair Enerji Teknolojileri Anonimisrketi", "Enwair", "Corporation"),
    ("European Association for Storage of Energy", "EASE", "Association"),
    ("European Energy Research Alliance", "EuropeanEnergyResearchAlliance", "Organization"),
    ("European Synchotron Radiation Facility", "ESRF", "Research Organization"),
    ("European Union", "EU", "Goverment Organization"),
    ("EVE Energy Co., Ltd.", "EVE", "Corporation"),
    ("Evyon", "Evyon", "Corporation"),
    ("FAAM", "FAAM", "Corporation"),
    ("Faraday Institution", "FaradayInstitution", "Organization"),
    ("Faurecia", "Faurecia", "Corporation"),
    ("Flanders Make", "Flanders Make", "Corporation"),
    ("Fraunhofer Society", "FraunhoferSociety", "Research Organization"),
    ("French Alternative Energies and Atomic Energy Commission", "CEA", "Research Organization"),
    ("French National Centre for Scientific Research", "CNRS", "Research Organization"),
    ("French National Synchrotron Facility", "SOLEIL", "Research Organization"),
    ("FREYR Battery", "FREYR", "Corporation"),
    ("Georgia Tech", "GeorgiaTech", "Organization"),
    ("German Aerospace Center", "DLR", "Research Organization"),
    ("Graphene Batteries", "GrapheneBatteries", "Corporation"),
    ("Hagal", "Hagal", "Corporation"),
    ("Haldor Topsoe", "Topsoe", "Corporation"),
    ("HiNa Battery Technology Co., Ltd", "HinaBatteryTechnologyCoLtd", "Corporation"),
    ("Hydrovolt AS", "Hydrovolt", "Corporation"),
    ("IBU-tec advanced materials AG", "IBUtec", "Corporation"),
    ("ICSI", "ICSI", "Research Organization"),
    ("IFE Invest AS", "IfeInvestAs", "Corporation"),
    ("Ikerlan", "Ikerlan", "Corporation"),
    ("Industry & Information Technologies Research Development and Implementation Inc", "TAGES", "Corporation"),
    ("Infineon Technologies", "Infineon", "Corporation"),
    ("InoBat", "InoBat", "Corporation"),
    ("Institut de Recerca de l'Energia de Catalunya", "IREC", "Research Organization"),
    ("Institut Laue Langevin", "ILL", "Research Organization"),
    ("Institut National des Sciences Appliquees de Lyon", "INSA", "Educational Organization"),
    ("Institute for Energy Technology", "InstituteForEnergyTechnology", "Research Organization"),
    ("Ionic Liquids Technologies", "IoLiTec", "Corporation"),
    ("Ionworks", "Ionworks", "Corporation"),
    ("IT University of Copenhagen", "ITU", "Educational Organization"),
    ("Italvolt SPA", "Italvolt", "Corporation"),
    ("Justus Liebig University Giessen (JLU)", "JustusLiebigUniversityGiessenJlu", "University"),
    ("Karlsruhe Institute of Technology", "KIT", "Research Organization"),
    ("Keysight", "Keysight", "Corporation"),
    ("KU Leuven", "KuLeuven", "University"),
    ("Leclanche", "Leclanche", "Corporation"),
    ("LG Energy Solution", "LGEnergySolution", "Corporation"),
    ("Maccor", "Maccor", "Corporation"),
    ("Martin Luther University Halle-Wittenberg", "MLU", "University"),
    ("Melasta", "Melasta", "Corporation"),
    ("Metrohm Autolab", "MetrohmAutolab", "Organization"),
    ("Millor Battery", "MillorBattery", "Corporation"),
    ("Morrow Batteries", "MORROW", "Corporation"),
    ("National Agency for New Technologies, Energy and Sustainable Economic Development", "ENEA", "Research Organization"),
    ("National Institute of Chemistry", "NIC", "Research Organization"),
    ("National Research Council", "CNR", "Research Organization"),
    ("Neware", "Neware", "Corporation"),
    ("Norsk Hydro ASA", "Hydro", "Corporation"),
    ("Northvolt AB", "Northvolt", "Corporation"),
    ("Norwegian University of Science and Technology", "NorwegianUniversityOfScienceAndTechnology", "University"),
    ("NXP", "NXP", "Corporation"),
    ("O'Cell New Energy Technology Co., Ltd", "OCell", "Corporation"),
    ("Paul Scherrer Institute", "PSI", "Research Organization"),
    ("POLIS Post Lithium Storage Cluster of Excellence", "PolisPostLithiumStorageClusterOfExcellence", "Organization"),
    ("Polykey Polymers SL", "PolykeyPolymersSl", "Corporation"),
    ("Polytechnic University of Turin", "POLITO", "Educational Organization"),
    ("PowerCo SE", "PowerCo", "Corporation"),
    ("RECHARGE", "RECHARGE", "Association"),
    ("Research Centre Juelich", "FZJ", "Research Organization"),
    ("RISE", "RISE", "Research Organization"),
    ("RTD Talos", "RTD Talos", "Corporation"),
    ("Saft", "Saft", "Corporation"),
    ("Samsung SDI", "SamsungSDI", "Corporation"),
    ("SINTEF", "SINTEF", "Research Organization"),
    ("SK Innovation", "SKInnovation", "Corporation"),
    ("Solvay S.A.", "Solvay", "Corporation"),
    ("Spanish National Research Council", "CSIC", "Research Organization"),
    ("Specific Polymers", "SpecificPolymers", "Corporation"),
    ("SVOLT Energy Technology (Europe) GmbH", "SVOLTEurope", "Corporation"),
    ("SVOLT Energy Technology Co., Ltd.", "SVOLT", "Corporation"),
    ("Swiss Center for Electronics and Microtechnology", "CSEM", "Research Organization"),
    ("Swiss Federal Institute of Technology Lausanne", "EPFL", "Educational Organization"),
    ("Swiss Federal Laboratories for Materials Science and Technology", "EMPA", "Research Organization"),
    ("Technical University of Crete", "TechnicalUniversityOfCrete", "University"),
    ("Technical University of Denmark", "DTU", "University"),
    ("Tesla, Inc.", "Tesla", "Corporation"),
    ("The Chancellor, Masters and Scholars of the University of Cambridge", "University of Cambridge", "Educational Organization"),
    ("The Chancellor, Masters and Scholars of the University of Oxford", "UniversityOfOxford", "Educational Organization"),
    ("Tiamat", "Tiamat", "Corporation"),
    ("Tufts University", "TuftsUniversity", "University"),
    ("UCLouvain", "UCLouvain", "Research Organization"),
    ("Ulm University", "UlmUniversity", "Educational Organization"),
    ("Umicore N.V.", "Umicore", "Corporation"),
    ("Uniresearch BV", "Uniresearch", "Corporation"),
    ("UniverCell", "UniverCell", "Corporation"),
    ("Universidad Complutense de Madrid", "UCM", "Educational Organization"),
    ("Universidad Del Pais Vasco", "UniversidadDelPaisVasco", "Educational Organization"),
    ("University of Aveiro", "UniversityOfAveiro", "Educational Organization"),
    ("University of Basel", "UNIBAS", "Educational Organization"),
    ("University of Liverpool", "UniversityOfLiverpool", "Educational Organization"),
    ("University of Modena and Reggio Emilia", "UNIMORE", "Educational Organization"),
    ("University of Oslo", "UniversityOfOslo", "Educational Organization"),
    ("University of Picardie Jules Verne", "UPJV", "Educational Organization"),
    ("University of Southern Denmark", "UniversityOfSouthernDenmark", "University"),
    ("University of Tartu", "UT", "Educational Organization"),
    ("University of Toronto", "UniversityOfToronto", "Educational Organization"),
    ("University of Vienna", "UniversityOfVienna", "Educational Organization"),
    ("University of Warwick", "UniversityOfWarwick", "Educational Organization"),
    ("Univerzita Pardubice", "UniverzitaPardubice", "Educational Organization"),
    ("Uppsala University", "UppsalaUniversity", "Educational Organization"),
    ("VARTA AG", "VARTA", "Corporation"),
    ("VARTA Micro Innovation", "VARTAMicroInnovation", "Corporation"),
    ("Varta Microbattery GmbH", "VARTAMicrobattery", "Corporation"),
    ("Verkor", "Verkor", "Corporation"),
    ("Vestel Elektronik Sanayi ve Ticaret", "Vestel", "Corporation"),
    ("Vianode AS", "Vianode", "Corporation"),
    ("Volta Foundation", "VoltaFoundation", "Organization"),
    ("Vrije Universiteit Brussel", "VUB", "Educational Organization"),
    ("VTT Technical Research Centre of Finland", "VTT", "Research Organization"),
    ("Warsaw University of Technology", "WUT", "Educational Organization"),
    ("Westphalian Wilhelm University of Munster", "WWU", "Educational Organization"),
]

# BKG type → BattINFO org type mapping
TYPE_MAP: dict[str, str] = {
    "Corporation": "Manufacturer",
    "University": "EducationalOrganization",
    "Educational Organization": "EducationalOrganization",
    "Research Organization": "ResearchOrganization",
    "Goverment Organization": "GovernmentOrganization",
    "Association": "Organization",
    "Organization": "Organization",
}


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _slug(name: str) -> str:
    """Convert a name to a kebab-case directory slug."""
    s = name.lower()
    s = re.sub(r"[''`]", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _normalize(name: str) -> str:
    """Lowercase + strip punctuation for fuzzy matching."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "battinfo-sync/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _search_bkg(name: str) -> str | None:
    """Search BKG for an org by name; return the wiki item URL or None."""
    params = urllib.parse.urlencode({
        "action": "query",
        "list": "search",
        "srsearch": name,
        "srlimit": 5,
        "srnamespace": 7000,  # Item namespace
        "format": "json",
    })
    try:
        data = _fetch_json(f"{BKG_API}?{params}")
        results = data.get("query", {}).get("search", [])
        if results:
            title = results[0]["title"]  # e.g. "Item:OSWabc123..."
            slug = title.replace("Item:", "")
            return f"https://battery.knowledge-graph.eu/wiki/{title}"
    except Exception as e:
        print(f"  [warn] BKG search failed for '{name}': {e}")
    return None


def _fetch_bkg_page(item_url: str) -> dict:
    """Fetch a BKG wiki page and extract structured org info."""
    # Use the MW API to get page content / properties
    title = item_url.split("/wiki/")[-1]
    params = urllib.parse.urlencode({
        "action": "query",
        "titles": title,
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
        "format": "json",
    })
    try:
        data = _fetch_json(f"{BKG_API}?{params}")
        pages = data.get("query", {}).get("pages", {})
        page = next(iter(pages.values()))
        content = page.get("revisions", [{}])[0].get("slots", {}).get("main", {}).get("*", "")
        return {"title": page.get("title", ""), "content": content}
    except Exception as e:
        print(f"  [warn] Failed to fetch BKG page {item_url}: {e}")
    return {}


def _existing_records() -> dict[str, Path]:
    """Return {normalized_name: record_dir} for all existing org records."""
    result: dict[str, Path] = {}
    for d in RECORDS_ROOT.iterdir():
        if not d.is_dir():
            continue
        rec_file = d / "record.json"
        if not rec_file.exists():
            continue
        try:
            rec = json.loads(rec_file.read_text(encoding="utf-8"))
            org = rec.get("organization", {})
            names = [org.get("name", ""), org.get("legalName", "")]
            alts = org.get("alternateName", [])
            if isinstance(alts, str):
                alts = [alts]
            names.extend(alts)
            for n in names:
                key = _normalize(n)
                if len(key) >= 3:  # skip empty or trivially short keys
                    result[key] = d
        except Exception:
            pass
        # Also index by directory slug
        slug_key = _normalize(d.name.replace("-", " "))
        if len(slug_key) >= 3:
            result[slug_key] = d
    return result


def _update_same_as(rec_path: Path, bkg_url: str, dry_run: bool) -> None:
    """Add the BKG URL to sameAs in an existing record."""
    rec = json.loads(rec_path.read_text(encoding="utf-8"))
    org = rec.setdefault("organization", {})
    same_as = org.get("sameAs", [])
    if isinstance(same_as, str):
        same_as = [same_as]
    if bkg_url not in same_as:
        same_as.append(bkg_url)
        org["sameAs"] = same_as
        if not dry_run:
            rec_path.write_text(
                json.dumps(rec, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        print(f"  [updated] {rec_path.parent.name}: added sameAs → {bkg_url}")
    else:
        print(f"  [skip] {rec_path.parent.name}: sameAs already present")


def _create_record(
    name: str,
    bkg_type: str,
    bkg_url: str,
    dry_run: bool,
    extra: dict | None = None,
) -> None:
    """Create a new org record stub."""
    battinfo_id = _new_battinfo_id()
    short_id = battinfo_id.replace("-", "")[:8]
    org_type = TYPE_MAP.get(bkg_type, "Organization")

    org: dict = {
        "id": f"{BATTINFO_BASE_IRI}/{battinfo_id}",
        "short_id": short_id,
        "type": org_type,
        "name": name,
        "sameAs": [bkg_url],
    }
    if extra:
        org.update(extra)

    rec = {
        "schema_version": SCHEMA_VERSION,
        "organization": org,
        "provenance": {
            "source_type": "knowledge_base",
            "source_url": "https://battery.knowledge-graph.eu/wiki/Category:OSW1969007d5acf40539642877659a02c23",
            "retrieved_at": int(datetime.now(timezone.utc).timestamp()),
        },
        "editorial": {
            "review_status": "stub",
            "promoted_at": datetime.now(timezone.utc).date().isoformat(),
            "note": "Auto-generated stub from Battery Knowledge Graph (CC BY-SA 4.0). Review and enrich.",
        },
    }

    slug = _slug(name)
    target_dir = RECORDS_ROOT / slug
    # Avoid collisions
    if target_dir.exists():
        target_dir = RECORDS_ROOT / f"{slug}-bkg"

    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "record.json").write_text(
            json.dumps(rec, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    print(f"  [created] {target_dir.name}: {name}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing files")
    args = parser.parse_args()

    if args.dry_run:
        print("=== DRY RUN — no files will be written ===\n")

    existing = _existing_records()
    print(f"Found {sum(1 for d in RECORDS_ROOT.iterdir() if d.is_dir())} existing org record dirs.")

    created = 0
    updated = 0
    skipped = 0

    for name, machine_name, bkg_type in BKG_ORGS:
        print(f"\n> {name} ({bkg_type})")

        # 1. Find BKG URL
        bkg_url = _search_bkg(name)
        if not bkg_url:
            print(f"  [warn] Could not find BKG URL — skipping")
            skipped += 1
            continue

        print(f"  BKG: {bkg_url}")

        # 2. Check if record exists (exact normalized match only)
        norm = _normalize(name)
        matched_dir: Path | None = existing.get(norm)

        if matched_dir:
            _update_same_as(matched_dir / "record.json", bkg_url, args.dry_run)
            updated += 1
        else:
            _create_record(name, bkg_type, bkg_url, args.dry_run)
            created += 1

        time.sleep(0.3)  # be polite to the BKG server

    print(f"\n{'=== DRY RUN COMPLETE ===' if args.dry_run else '=== DONE ==='}")
    print(f"Created: {created}  Updated: {updated}  Skipped: {skipped}")


if __name__ == "__main__":
    main()
