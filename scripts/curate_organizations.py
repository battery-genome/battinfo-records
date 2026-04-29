"""
Applies curated metadata to organization stubs and merges duplicates.
Safe to re-run: preserves existing opaque IRIs, only adds/updates fields.

Merges: the duplicate directory is deleted; the canonical record gains
the duplicate's name as an alternateName entry.

Usage:
    python scripts/curate_organizations.py [--dry-run]
"""

import argparse
import json
import shutil
from pathlib import Path

ORG_DIR = Path(__file__).parent.parent / "records" / "organization"

# ---------------------------------------------------------------------------
# Duplicate → canonical slug. The duplicate's record.json is deleted;
# the duplicate's original name is added to the canonical's alternateName.
# ---------------------------------------------------------------------------
MERGES: dict[str, str] = {
    "amita":                          "amita-technologies",
    "eve":                            "eve-energy",
    "eagle-picher":                   "eagle-picher-technologies-llc",
    "eas":                            "eas-batteries",
    "enerdel-inc":                    "enerdel",
    "frey":                           "jiangsu-frey",
    "generalelectronics":             "general-electronics-battery-co",
    "e-one-moli-energy-canada-limited": "molicel",
}

# ---------------------------------------------------------------------------
# Curated metadata keyed by directory slug.
# Fields present here are merged into the organization block; existing
# fields not present here are left untouched.
# ---------------------------------------------------------------------------
KNOWN: dict[str, dict] = {
    "a123": {
        "name": "A123 Systems",
        "legalName": "A123 Systems LLC",
        "type": "Manufacturer",
        "location": {"addressCountry": "US"},
        "foundingDate": "2001",
        "sameAs": ["https://www.wikidata.org/wiki/Q193793"],
        "alternateName": ["A123"],
        "description": (
            "US manufacturer of lithium iron phosphate (LFP) batteries, "
            "founded at MIT. Acquired by Wanxiang Group (China) in 2013."
        ),
    },
    "amita-technologies": {
        "name": "AMITA Technologies",
        "legalName": "AMITA Technologies, Inc.",
        "type": "Manufacturer",
        "location": {"addressCountry": "TW"},
        "alternateName": ["AMITA"],
        "description": "Taiwanese manufacturer of lithium-ion battery cells and packs.",
    },
    "atl-amperex-technology": {
        "name": "Amperex Technology Limited",
        "legalName": "Amperex Technology Limited",
        "type": "Manufacturer",
        "location": {"addressCountry": "CN", "addressLocality": "Hong Kong"},
        "foundingDate": "1999",
        "sameAs": ["https://www.wikidata.org/wiki/Q4756494"],
        "alternateName": ["ATL", "ATL Amperex Technology"],
        "description": (
            "Leading manufacturer of lithium-ion polymer batteries, "
            "subsidiary of TDK Corporation (Japan)."
        ),
    },
    "bak": {
        "name": "BAK Power",
        "legalName": "Shenzhen BAK Power Battery Co., Ltd.",
        "type": "Manufacturer",
        "location": {"addressCountry": "CN", "addressLocality": "Shenzhen"},
        "alternateName": ["BAK", "Shenzhen BAK Battery", "China BAK Battery"],
        "description": "Chinese manufacturer of lithium-ion cylindrical and prismatic cells.",
    },
    "calb": {
        "name": "CALB",
        "legalName": "China Aviation Lithium Battery Co., Ltd.",
        "type": "Manufacturer",
        "location": {"addressCountry": "CN", "addressLocality": "Luoyang"},
        "alternateName": ["China Aviation Lithium Battery", "中航锂电"],
        "description": "Major Chinese manufacturer of lithium iron phosphate batteries.",
    },
    "catl": {
        "name": "CATL",
        "legalName": "Contemporary Amperex Technology Co., Limited",
        "type": "Manufacturer",
        "location": {"addressCountry": "CN", "addressLocality": "Ningde"},
        "foundingDate": "2011",
        "sameAs": ["https://www.wikidata.org/wiki/Q20731953"],
        "alternateName": ["Contemporary Amperex Technology", "宁德时代"],
        "description": "World's largest manufacturer of lithium-ion batteries for electric vehicles.",
    },
    "coslight": {
        "name": "Coslight",
        "legalName": "Coslight Technology Co., Ltd.",
        "type": "Manufacturer",
        "location": {"addressCountry": "CN", "addressLocality": "Beijing"},
        "alternateName": ["COSLIGHT"],
    },
    "duracell": {
        "name": "Duracell",
        "legalName": "Duracell Inc.",
        "type": "Manufacturer",
        "location": {"addressCountry": "US"},
        "sameAs": ["https://www.wikidata.org/wiki/Q672808"],
        "alternateName": ["DURACELL"],
        "description": "US consumer battery brand, owned by Berkshire Hathaway.",
    },
    "eagle-picher-technologies-llc": {
        "name": "EaglePicher Technologies",
        "legalName": "EaglePicher Technologies, LLC",
        "type": "Manufacturer",
        "location": {"addressCountry": "US", "addressLocality": "Joplin, MO"},
        "sameAs": ["https://www.wikidata.org/wiki/Q3050826"],
        "alternateName": ["Eagle Picher Technologies LLC", "EAGLE PICHER", "EaglePicher"],
        "description": (
            "US manufacturer of specialty batteries for defence, space, and medical applications."
        ),
    },
    "eas-batteries": {
        "name": "EAS Batteries",
        "legalName": "EAS Batteries GmbH",
        "type": "Manufacturer",
        "location": {"addressCountry": "DE", "addressLocality": "Nordhausen"},
        "alternateName": ["EAS"],
        "description": "German manufacturer of large-format lithium-ion prismatic cells.",
    },
    "eemb-co": {
        "name": "EEMB",
        "legalName": "EEMB Co., Ltd.",
        "type": "Manufacturer",
        "location": {"addressCountry": "CN"},
        "alternateName": ["Eemb Co"],
    },
    "elerix": {
        "name": "Elerix",
        "type": "Manufacturer",
        "location": {"addressCountry": "CZ"},
        "alternateName": ["ELERIX"],
        "description": "Czech distributor and rebrander of lithium-ion cells.",
    },
    "enax": {
        "name": "ENAX",
        "legalName": "ENAX, Inc.",
        "type": "Manufacturer",
        "location": {"addressCountry": "JP"},
        "alternateName": ["ENAX"],
        "description": "Japanese manufacturer of large-format lithium-ion pouch cells.",
    },
    "enerdel": {
        "name": "EnerDel",
        "legalName": "EnerDel, Inc.",
        "type": "Manufacturer",
        "location": {"addressCountry": "US", "addressLocality": "Indianapolis, IN"},
        "alternateName": ["ENERDEL", "EnerDel. INC"],
        "description": "US manufacturer of lithium-ion battery modules and packs.",
    },
    "energizer": {
        "name": "Energizer",
        "legalName": "Energizer Holdings, Inc.",
        "type": "Manufacturer",
        "location": {"addressCountry": "US", "addressLocality": "St. Louis, MO"},
        "sameAs": ["https://www.wikidata.org/wiki/Q1340474"],
        "alternateName": ["ENERGIZER"],
        "description": "US manufacturer and marketer of primary and rechargeable batteries.",
    },
    "enertech": {
        "name": "Enertech International",
        "legalName": "Enertech International Inc.",
        "type": "Manufacturer",
        "location": {"addressCountry": "KR"},
        "alternateName": ["ENERTECH"],
        "description": "South Korean manufacturer of lithium-ion polymer cells.",
    },
    "eve-energy": {
        "name": "EVE Energy",
        "legalName": "EVE Energy Co., Ltd.",
        "type": "Manufacturer",
        "location": {"addressCountry": "CN", "addressLocality": "Huizhou"},
        "alternateName": ["EVE", "亿纬锂能"],
        "description": "Chinese manufacturer of primary lithium and lithium-ion batteries.",
    },
    "gaia": {
        "name": "Gaia",
        "legalName": "Gaia Akkumulatorenwerke GmbH",
        "type": "Manufacturer",
        "location": {"addressCountry": "DE"},
        "description": "German manufacturer of large-format lithium-ion cells (now inactive).",
    },
    "general-electronics-battery-co": {
        "name": "General Electronics Battery",
        "legalName": "General Electronics Battery Co.",
        "type": "Manufacturer",
        "location": {"addressCountry": "US"},
        "alternateName": ["General Electronics Battery Co", "GeneralElectronics", "GEB"],
    },
    "gotion": {
        "name": "Gotion High-tech",
        "legalName": "Gotion High-tech Co., Ltd.",
        "type": "Manufacturer",
        "location": {"addressCountry": "CN", "addressLocality": "Hefei"},
        "alternateName": ["GOTION", "国轩高科"],
        "description": "Chinese manufacturer of LFP and NCM cells for EV and energy storage.",
    },
    "gs-yuasa-technology": {
        "name": "GS Yuasa",
        "legalName": "GS Yuasa Technology Ltd.",
        "type": "Manufacturer",
        "location": {"addressCountry": "JP"},
        "sameAs": ["https://www.wikidata.org/wiki/Q1571799"],
        "alternateName": ["GS Yuasa Technology", "ジーエス・ユアサ"],
        "description": "Japanese battery manufacturer producing lead-acid and lithium-ion cells.",
    },
    "headway-group": {
        "name": "Headway",
        "legalName": "Headway Group Co., Ltd.",
        "type": "Manufacturer",
        "location": {"addressCountry": "CN"},
        "alternateName": ["Headway Group"],
        "description": "Chinese manufacturer of large-format cylindrical LFP cells.",
    },
    "hitachi": {
        "name": "Hitachi",
        "legalName": "Hitachi, Ltd.",
        "type": "Corporation",
        "location": {"addressCountry": "JP", "addressLocality": "Tokyo"},
        "sameAs": ["https://www.wikidata.org/wiki/Q190125"],
        "description": "Japanese multinational conglomerate with battery divisions.",
    },
    "jiangsu-frey": {
        "name": "Jiangsu Frey New Energy",
        "type": "Manufacturer",
        "location": {"addressCountry": "CN", "addressRegion": "Jiangsu"},
        "alternateName": ["Jiangsu FREY", "FREY"],
    },
    "kokam": {
        "name": "Kokam",
        "legalName": "Kokam Co., Ltd.",
        "type": "Manufacturer",
        "location": {"addressCountry": "KR"},
        "sameAs": ["https://www.wikidata.org/wiki/Q17022028"],
        "description": (
            "South Korean manufacturer of high-performance lithium polymer cells, "
            "widely used in research and aerospace. Acquired by SolarEdge Technologies."
        ),
    },
    "leclanch": {
        "name": "Leclanché",
        "legalName": "Leclanché SA",
        "type": "Manufacturer",
        "location": {"addressCountry": "CH", "addressLocality": "Yverdon-les-Bains"},
        "sameAs": ["https://www.wikidata.org/wiki/Q2724618"],
        "alternateName": ["LECLANCHÉ", "Leclanche"],
        "description": "Swiss manufacturer of lithium-ion cells and energy storage systems.",
    },
    "lg": {
        "name": "LG Energy Solution",
        "legalName": "LG Energy Solution, Ltd.",
        "type": "Manufacturer",
        "location": {"addressCountry": "KR", "addressLocality": "Seoul"},
        "foundingDate": "2020",
        "sameAs": ["https://www.wikidata.org/wiki/Q104997810"],
        "alternateName": ["LG", "LG Chem", "LG Chem Battery", "LGCS", "LGES"],
        "description": (
            "South Korean battery manufacturer, spun off from LG Chem in 2020. "
            "Records predating 2020 may reference LG Chem."
        ),
    },
    "lishen": {
        "name": "Lishen",
        "legalName": "Tianjin Lishen Battery Joint-Stock Co., Ltd.",
        "type": "Manufacturer",
        "location": {"addressCountry": "CN", "addressLocality": "Tianjin"},
        "alternateName": ["天津力神"],
        "description": "One of China's oldest lithium-ion battery manufacturers.",
    },
    "lithiumwerks": {
        "name": "LithiumWerks",
        "legalName": "LithiumWerks B.V.",
        "type": "Manufacturer",
        "location": {"addressCountry": "NL"},
        "alternateName": ["LITHIUMWERKS"],
        "description": (
            "Dutch company that acquired A123 Systems' LFP cell manufacturing "
            "operations in 2017."
        ),
    },
    "molicel": {
        "name": "Molicel",
        "legalName": "E-One Moli Energy (Canada) Limited",
        "type": "Manufacturer",
        "location": {"addressCountry": "CA", "addressLocality": "Maple Ridge, BC"},
        "alternateName": ["MOLICEL", "E-One Moli Energy (Canada) Limited", "Moli Energy"],
        "description": "Canadian manufacturer of high-rate lithium-ion cylindrical cells.",
    },
    "murata": {
        "name": "Murata",
        "legalName": "Murata Manufacturing Co., Ltd.",
        "type": "Manufacturer",
        "location": {"addressCountry": "JP", "addressLocality": "Kyoto"},
        "sameAs": ["https://www.wikidata.org/wiki/Q696128"],
        "alternateName": ["MURATA", "村田製作所", "Sony Energy Devices"],
        "description": (
            "Japanese electronics manufacturer that acquired Sony's battery business "
            "in 2017. Cells previously sold under the Sony brand are now Murata-branded."
        ),
    },
    "panasonic": {
        "name": "Panasonic",
        "legalName": "Panasonic Holdings Corporation",
        "type": "Manufacturer",
        "location": {"addressCountry": "JP", "addressLocality": "Osaka"},
        "sameAs": ["https://www.wikidata.org/wiki/Q183230"],
        "alternateName": ["パナソニック", "Panasonic Energy"],
        "description": (
            "Japanese electronics manufacturer and major global producer of "
            "lithium-ion cylindrical cells."
        ),
    },
    "quallion-llc": {
        "name": "Quallion",
        "legalName": "Quallion LLC",
        "type": "Manufacturer",
        "location": {"addressCountry": "US", "addressLocality": "Sylmar, CA"},
        "alternateName": ["Quallion LLC"],
        "description": "US manufacturer of speciality lithium-ion cells for medical and defence.",
    },
    "saft": {
        "name": "Saft",
        "legalName": "Saft Groupe S.A.",
        "type": "Manufacturer",
        "location": {"addressCountry": "FR", "addressLocality": "Bagnolet"},
        "sameAs": ["https://www.wikidata.org/wiki/Q1380143"],
        "description": (
            "French manufacturer of high-performance batteries for industrial, "
            "defence, and space applications. Subsidiary of TotalEnergies since 2016."
        ),
    },
    "samsung": {
        "name": "Samsung SDI",
        "legalName": "Samsung SDI Co., Ltd.",
        "type": "Manufacturer",
        "location": {"addressCountry": "KR", "addressLocality": "Yongin"},
        "sameAs": ["https://www.wikidata.org/wiki/Q491229"],
        "alternateName": ["Samsung", "삼성SDI"],
        "description": (
            "South Korean battery manufacturer and subsidiary of Samsung Group. "
            "Produces cylindrical, prismatic, and pouch lithium-ion cells."
        ),
    },
    "sanyo": {
        "name": "Sanyo",
        "legalName": "Sanyo Electric Co., Ltd.",
        "type": "Manufacturer",
        "location": {"addressCountry": "JP"},
        "foundingDate": "1947",
        "dissolutionDate": "2012",
        "sameAs": ["https://www.wikidata.org/wiki/Q186168"],
        "alternateName": ["SANYO"],
        "parentOrganization": {
            "id": "https://w3id.org/battinfo/organization/en1a-v2t1-0qt5-n6w8",
            "name": "Panasonic",
        },
        "description": (
            "Japanese electronics and battery manufacturer, fully absorbed into "
            "Panasonic by 2012."
        ),
    },
    "ses": {
        "name": "SES AI",
        "legalName": "SES AI Corporation",
        "type": "Manufacturer",
        "location": {"addressCountry": "US", "addressLocality": "Boston, MA"},
        "alternateName": ["SES", "Solid Energy Systems"],
        "description": "US developer of lithium-metal batteries.",
    },
    "sinopoly": {
        "name": "Sinopoly Battery",
        "legalName": "Sinopoly Battery Limited",
        "type": "Manufacturer",
        "location": {"addressCountry": "HK"},
        "alternateName": ["Sinopoly"],
        "description": "Hong Kong-listed manufacturer of large-format LFP batteries.",
    },
    "ski": {
        "name": "SK Innovation",
        "legalName": "SK Innovation Co., Ltd.",
        "type": "Manufacturer",
        "location": {"addressCountry": "KR"},
        "alternateName": ["SKI", "SK On"],
        "description": (
            "South Korean energy company; battery division spun off as SK On in 2021."
        ),
    },
    "sunwoda": {
        "name": "Sunwoda",
        "legalName": "Sunwoda Electronic Co., Ltd.",
        "type": "Manufacturer",
        "location": {"addressCountry": "CN", "addressLocality": "Shenzhen"},
        "alternateName": ["新旺达"],
    },
    "thunder-sky": {
        "name": "Thunder Sky Winston Battery",
        "legalName": "Thunder Sky Winston Battery Limited",
        "type": "Manufacturer",
        "location": {"addressCountry": "CN"},
        "alternateName": ["Thunder-Sky", "Winston Battery"],
        "description": "Chinese manufacturer of large-format lithium iron yttrium (LiFeYPO4) cells.",
    },
    "wuhan-lisun-power-corp-ltd": {
        "name": "Wuhan Lisun Power",
        "legalName": "Wuhan Lisun Power Corp. Ltd.",
        "type": "Manufacturer",
        "location": {"addressCountry": "CN", "addressLocality": "Wuhan"},
        "alternateName": ["Wuhan Lisun Power Corp. Ltd"],
    },
    "yinlong": {
        "name": "Yinlong",
        "legalName": "Guangzhou Yinlong New Energy Co., Ltd.",
        "type": "Manufacturer",
        "location": {"addressCountry": "CN", "addressLocality": "Guangzhou"},
        "alternateName": ["YINLONG", "银隆新能源"],
        "description": "Chinese manufacturer of lithium titanate (LTO) batteries.",
    },
    "zenlabs-envia": {
        "name": "Zenlabs Energy",
        "legalName": "Zenlabs Energy, Inc.",
        "type": "Manufacturer",
        "location": {"addressCountry": "US"},
        "alternateName": ["Zenlabs_Envia", "Envia Systems"],
        "description": "US developer of high-energy lithium-ion cells; successor to Envia Systems.",
    },
    # --- leave as stubs with notes ------------------------------------------
    "bmz-sony": {
        "notes_append": (
            "Name 'BMZ_Sony' in source records reflects cells made by BMZ "
            "using Sony/Murata cells. BMZ is a German battery pack integrator."
        ),
        "editorial_update": {"review_status": "needs-review"},
    },
    "bmz-terrae": {
        "notes_append": (
            "Name 'BMZ_TerraE' in source records reflects BMZ packs using "
            "TerraE cells. BMZ is a German battery pack integrator."
        ),
        "editorial_update": {"review_status": "needs-review"},
    },
    "amprius-wuxi-lead": {
        "notes_append": (
            "Name 'Amprius_Wuxi Lead' in source records reflects silicon-anode "
            "cells developed by Amprius (US) manufactured by Wuxi Lead (CN)."
        ),
        "editorial_update": {"review_status": "needs-review"},
    },
}


def apply_curation(org: dict, patch: dict) -> dict:
    """Merge patch fields into the organization block."""
    special = {"notes_append", "editorial_update"}
    for key, value in patch.items():
        if key in special:
            continue
        if key == "alternateName":
            existing = org.get("alternateName", [])
            if isinstance(existing, str):
                existing = [existing]
            merged = list(dict.fromkeys(existing + value))
            org[key] = merged
        elif key == "sameAs":
            existing = org.get("sameAs", [])
            if isinstance(existing, str):
                existing = [existing]
            merged = list(dict.fromkeys(existing + value))
            org[key] = merged if len(merged) > 1 else merged[0] if merged else None
            if org[key] is None:
                del org[key]
        else:
            org[key] = value
    return org


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # ---- collect names from stubs that will be deleted ---------------------
    merge_alternate_names: dict[str, list[str]] = {}
    for del_slug, keep_slug in MERGES.items():
        del_path = ORG_DIR / del_slug / "record.json"
        if del_path.exists():
            d = json.loads(del_path.read_text(encoding="utf-8"))
            name = d.get("organization", {}).get("name", "")
            merge_alternate_names.setdefault(keep_slug, [])
            if name:
                merge_alternate_names[keep_slug].append(name)

    # ---- apply curation and collect alternate names from merges ------------
    curated = 0
    for slug, patch in KNOWN.items():
        record_path = ORG_DIR / slug / "record.json"
        if not record_path.exists():
            print(f"  MISSING  {slug}  (skipped)")
            continue

        rec = json.loads(record_path.read_text(encoding="utf-8"))
        org = rec.get("organization", {})

        # Add alternate names from merged-away duplicates
        extra_alts = merge_alternate_names.get(slug, [])
        if extra_alts:
            existing = patch.get("alternateName", [])
            patch = dict(patch)  # shallow copy to avoid mutating KNOWN
            patch["alternateName"] = list(dict.fromkeys(existing + extra_alts))

        org = apply_curation(org, patch)
        rec["organization"] = org

        # Handle notes_append
        if "notes_append" in patch:
            rec.setdefault("notes", [])
            if patch["notes_append"] not in rec["notes"]:
                rec["notes"].append(patch["notes_append"])

        # Handle editorial_update
        if "editorial_update" in patch:
            rec.setdefault("editorial", {})
            rec["editorial"].update(patch["editorial_update"])
        else:
            if rec.get("editorial", {}).get("review_status") == "stub":
                rec["editorial"]["review_status"] = "curated"

        if args.dry_run:
            print(f"  would update  {slug}")
        else:
            record_path.write_text(
                json.dumps(rec, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            print(f"  updated  {slug}")
        curated += 1

    # ---- delete duplicates -------------------------------------------------
    deleted = 0
    for del_slug in MERGES:
        del_dir = ORG_DIR / del_slug
        if del_dir.exists():
            if args.dry_run:
                print(f"  would delete  {del_slug}/")
            else:
                shutil.rmtree(del_dir)
                print(f"  deleted  {del_slug}/")
            deleted += 1

    verb = "would" if args.dry_run else ""
    print(f"\nDone. {verb} Updated: {curated}  Deleted: {deleted}")


if __name__ == "__main__":
    main()
