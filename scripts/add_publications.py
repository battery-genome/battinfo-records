"""
Adds publication links (from CellInfoRepository schema:subjectOf fields)
to matching battinfo-records cell-type record.json files.

Matching is done by provenance.source_file → CellInfoRepository filename.
"""

import json
import os
from pathlib import Path

# --- Publication mapping: CellInfoRepository filename → list of URLs ---
PUBLICATIONS: dict[str, list[str]] = {
    "A123_AMP20M1HD-A.json": [
        "https://doi.org/10.1016/j.etran.2020.100073",
        "https://doi.org/10.1016/j.apenergy.2017.04.022",
        "https://doi.org/10.1016/j.apenergy.2021.116737",
        "https://doi.org/10.1016/j.enconman.2020.113715",
        "https://doi.org/10.3390/en14175434",
        "https://doi.org/10.1088/1755-1315/268/1/012103",
        "https://doi.org/10.1016/j.jpowsour.2017.11.011",
        "https://doi.org/10.3390/batteries5040070",
        "https://doi.org/10.1149/1945-7111/abff35",
        "https://www.semanticscholar.org/paper/61f62eca106796d592d9cac19339b989bf5fde9b",
    ],
    "BAK_N21700CG-50.json": [
        "https://doi.org/10.1016/j.energy.2021.120072",
    ],
    "CALB_CA60.json": [
        "https://doi.org/10.12783/dtetr/mcee2016/6395",
    ],
    "CALB_CAM72.json": [
        "https://doi.org/10.1007/978-3-319-69950-9/8",
    ],
    "CALB_L135F72_(CAM72).json": [
        "https://doi.org/10.1007/978-3-319-69950-9/8",
    ],
    "Eagle_Picher_Technologies_LLC_LP_32770.json": [
        "https://doi.org/10.1016/j.commatsci.2021.110343",
    ],
    "Eagle_Picher_Technologies_LLC_LP_33450.json": [
        "https://doi.org/10.3390/en16114422",
    ],
    "GS_Yuasa_Technology_LVP10.json": [
        "https://doi.org/10.15368/theses.2014.127",
    ],
    "Gaia_HP_602030.json": [
        "https://doi.org/10.1016/j.jpowsour.2012.04.055",
        "https://doi.org/10.1016/j.engfailanal.2015.03.025",
    ],
    "Kokam_SLPB065070180.json": [
        "https://doi.org/10.1016/j.jpowsour.2023.233295",
        "https://doi.org/10.1002/batt.202200518",
        "https://doi.org/10.1149/1945-7111/acdd1e",
    ],
    "Kokam_SLPB080085270.json": [
        "https://www.semanticscholar.org/paper/47f0a69588a997c00a57c4908c3132b06e440779",
    ],
    "Kokam_SLPB100216216H.json": [
        "https://doi.org/10.1016/j.est.2022.105467",
        "https://doi.org/10.1016/j.apenergy.2012.09.030",
        "https://doi.org/10.1016/j.applthermaleng.2017.06.094",
        "https://doi.org/10.1016/j.jpowsour.2013.05.111",
        "https://doi.org/10.3390/en13174518",
    ],
    "Kokam_SLPB11543140H5.json": [
        "https://doi.org/10.1016/j.jpowsour.2018.02.065",
        "https://doi.org/10.1016/j.est.2017.08.001",
        "https://doi.org/10.1016/j.jpowsour.2016.09.008",
        "https://doi.org/10.1016/j.apenergy.2019.04.108",
        "https://doi.org/10.1016/j.jpowsour.2021.229772",
        "https://doi.org/10.1016/j.apenergy.2021.116737",
        "https://doi.org/10.1016/j.applthermaleng.2022.118573",
        "https://doi.org/10.1016/j.est.2022.105217",
        "https://doi.org/10.1016/j.energy.2017.12.032",
        "https://doi.org/10.1149/2.0011902jes",
        "https://doi.org/10.1149/2.0901813jes",
        "https://doi.org/10.1149/1945-7111/ab6985",
    ],
    "Kokam_SLPB120216216.json": [
        "https://www.semanticscholar.org/paper/5c79160b70f3d10ea832ae5ffbc21ac0d9c94660",
        "https://doi.org/10.6113/jpe.2013.13.4.516",
    ],
    "Kokam_SLPB120216216G1.json": [
        "https://www.semanticscholar.org/paper/5c79160b70f3d10ea832ae5ffbc21ac0d9c94660",
        "https://doi.org/10.6113/jpe.2013.13.4.516",
    ],
    "Kokam_SLPB120216216G1H.json": [
        "https://www.semanticscholar.org/paper/5c79160b70f3d10ea832ae5ffbc21ac0d9c94660",
        "https://doi.org/10.6113/jpe.2013.13.4.516",
    ],
    "Kokam_SLPB120216216G2.json": [
        "https://www.semanticscholar.org/paper/5c79160b70f3d10ea832ae5ffbc21ac0d9c94660",
        "https://doi.org/10.6113/jpe.2013.13.4.516",
    ],
    "Kokam_SLPB120216216HR2.json": [
        "https://doi.org/10.1016/j.jpowsour.2021.229572",
        "https://www.semanticscholar.org/paper/5c79160b70f3d10ea832ae5ffbc21ac0d9c94660",
        "https://doi.org/10.6113/jpe.2013.13.4.516",
    ],
    "Kokam_SLPB120255255.json": [
        "https://doi.org/10.3390/en13174518",
    ],
    "Kokam_SLPB125255255H.json": [
        "https://doi.org/10.3390/en13174518",
        "https://doi.org/10.3390/batteries8050042",
    ],
    "Kokam_SLPB50106100.json": [
        "https://doi.org/10.1016/j.electacta.2018.04.203",
        "https://doi.org/10.1149/1945-7111/ab78ff",
        "https://doi.org/10.3390/BATTERIES7010009",
        "https://doi.org/10.1149/2.0401707jes",
    ],
    "Kokam_SLPB55205130H.json": [
        "https://doi.org/10.3390/electronics8121395",
    ],
    "Kokam_SLPB75106100.json": [
        "https://doi.org/10.1016/j.est.2021.103669",
        "https://doi.org/10.1016/j.applthermaleng.2022.118530",
        "https://doi.org/10.1016/j.ijheatmasstransfer.2021.121918",
        "https://doi.org/10.1016/j.jpowsour.2012.03.015",
        "https://doi.org/10.1016/j.est.2022.104585",
        "https://doi.org/10.1016/j.jpowsour.2021.230034",
        "https://doi.org/10.1149/1945-7111/ab8f5a",
        "https://doi.org/10.1149/1945-7111/ab90ac",
        "https://doi.org/10.1149/1945-7111/ab6985",
        "https://doi.org/10.1149/2.0191912jes",
        "https://doi.org/10.1149/1945-7111/ac79d3",
    ],
    "Kokam_SLPB75106205.json": [
        "https://doi.org/10.1016/j.etran.2020.100045",
        "https://doi.org/10.1016/j.enconman.2022.116015",
        "https://doi.org/10.1016/j.jpowsour.2015.02.130",
    ],
    "Kokam_SLPB78216216H.json": [
        "https://doi.org/10.1016/j.electacta.2020.137487",
    ],
    "Kokam_SLPB90216216.json": [
        "https://doi.org/10.1109/tie.2017.2714118",
        "https://doi.org/10.3390/en13174518",
        "https://doi.org/10.1149/06609.0203ecst",
        "https://doi.org/10.1016/j.ijhydene.2020.01.067",
    ],
    "LG_Chem_E63.json": [
        "https://doi.org/10.1149/2.0501913jes",
        "https://doi.org/10.1016/j.est.2022.105676",
        "https://www.semanticscholar.org/paper/4af78e654e570c4a68fc66ff8d41111af3652cd0",
    ],
    "LG_Chem_E63B.json": [
        "https://doi.org/10.1149/2.0501913jes",
        "https://doi.org/10.1016/j.est.2022.105676",
        "https://www.semanticscholar.org/paper/4af78e654e570c4a68fc66ff8d41111af3652cd0",
    ],
    "LG_Chem_E66A.json": [
        "https://doi.org/10.1016/j.est.2023.107580",
    ],
    "LG_Chem_INR18650_MJ1.json": [
        "https://doi.org/10.1016/j.dib.2020.106033",
        "https://doi.org/10.1016/j.jpowsour.2019.226834",
        "https://doi.org/10.1016/j.est.2023.108029",
        "https://doi.org/10.1016/j.jpowsour.2019.03.109",
        "https://doi.org/10.1016/j.egyai.2021.100081",
        "https://doi.org/10.1016/j.est.2019.100900",
        "https://doi.org/10.1016/j.jpowsour.2018.11.043",
        "https://doi.org/10.1016/j.est.2022.105303",
        "https://doi.org/10.1016/j.jpowsour.2022.231296",
        "https://doi.org/10.1016/j.electacta.2022.139878",
        "https://doi.org/10.1016/j.jpowsour.2021.230645",
        "https://doi.org/10.1016/j.jpowsour.2021.230030",
        "https://doi.org/10.1016/j.est.2019.101170",
        "https://doi.org/10.1016/j.est.2022.106146",
        "https://doi.org/10.1016/j.est.2023.108241",
    ],
    "LG_Chem_INR21700_M50.json": [
        "https://doi.org/10.1016/j.dib.2021.106894",
        "https://doi.org/10.1016/j.est.2020.102133",
        "https://doi.org/10.3390/en13020489",
        "https://doi.org/10.1016/j.est.2022.104362",
        "https://doi.org/10.1109/icmect.2019.8932115",
        "https://doi.org/10.1016/j.est.2022.104291",
        "https://doi.org/10.1007/s00502-020-00814-9",
        "https://doi.org/10.3390/batteries9050274",
        "https://doi.org/10.3390/batteries9010006",
        "https://doi.org/10.1002/ente.202200547",
        "https://doi.org/10.3390/batteries8110204",
    ],
    "LG_Chem_INR21700_M50T.json": [
        "https://doi.org/10.1016/j.dib.2021.106894",
        "https://doi.org/10.1016/j.est.2020.102133",
        "https://doi.org/10.3390/en13020489",
        "https://doi.org/10.1016/j.est.2022.104362",
        "https://doi.org/10.1109/icmect.2019.8932115",
        "https://doi.org/10.1016/j.est.2022.104291",
        "https://doi.org/10.1016/j.dib.2022.107995",
        "https://doi.org/10.1016/j.apenergy.2022.118925",
        "https://doi.org/10.1016/j.est.2022.105217",
        "https://doi.org/10.1016/j.jpowsour.2021.229594",
        "https://doi.org/10.1016/j.est.2023.108046",
        "https://doi.org/10.1007/s00502-020-00814-9",
        "https://doi.org/10.3390/batteries9050274",
        "https://doi.org/10.3390/batteries9010006",
    ],
    "Lishen_LR2170SA.json": [
        "https://doi.org/10.3390/batteries8100145",
    ],
    "Molicel_INR-21700-P42A.json": [
        "https://doi.org/10.1016/j.jpowsour.2022.232068",
        "https://doi.org/10.1016/j.jpowsour.2022.232214",
        "https://doi.org/10.3390/batteries8020017",
        "https://doi.org/10.3390/app13084681",
        "https://doi.org/10.3390/batteries8080076",
    ],
    "Murata_US21700VTC6A.json": [
        "https://doi.org/10.3390/batteries9060309",
    ],
    "Panasonic_NCR18650BF.json": [
        "https://doi.org/10.1007/s42452-020-2675-6",
        "https://doi.org/10.1016/j.jpowsour.2021.229463",
        "https://doi.org/10.1016/j.sna.2021.113061",
        "https://doi.org/10.3390/en11051073",
        "https://doi.org/10.1016/j.egyr.2023.04.148",
        "https://doi.org/10.1155/2017/2579084",
        "https://doi.org/10.1016/j.compeleceng.2021.107306",
        "https://doi.org/10.1016/j.applthermaleng.2017.04.017",
        "https://doi.org/10.1016/j.applthermaleng.2020.116338",
        "https://doi.org/10.1016/j.renene.2019.08.077",
        "https://doi.org/10.1016/j.energy.2023.128126",
        "https://doi.org/10.1016/j.jpowsour.2020.228189",
        "https://doi.org/10.1016/j.egyr.2021.11.089",
        "https://doi.org/10.3390/en10091284",
        "https://doi.org/10.1016/j.est.2021.102466",
    ],
    "Panasonic_NCR20700B.json": [
        "https://doi.org/10.3390/batteries9060309",
    ],
    "Quallion_LLC_QL015KA.json": [
        "https://doi.org/10.1016/B978-0-444-59513-3.00014-5",
    ],
    "Saft_MP176065.json": [
        "https://doi.org/10.1051/e3sconf/20171606001",
        "https://doi.org/10.1109/acc.2010.5530710",
        "https://www.semanticscholar.org/paper/18b337d7e53fa2e7de07c3fab3c2059e208b8301",
    ],
    "Saft_MP176065xtd.json": [
        "https://doi.org/10.1051/e3sconf/20171606001",
        "https://doi.org/10.1109/acc.2010.5530710",
        "https://www.semanticscholar.org/paper/18b337d7e53fa2e7de07c3fab3c2059e208b8301",
    ],
    "Saft_VES180.json": [
        "https://doi.org/10.11591/IJAAS.V8.I1.PP54-63",
    ],
    "Saft_VL_41M.json": [
        "https://doi.org/10.2172/925388",
    ],
    "Saft_VL_45E.json": [
        "https://doi.org/10.2172/925388",
    ],
    "Saft_VL_45E_FE.json": [
        "https://doi.org/10.2172/925388",
    ],
    "Samsung_INR21700-30T.json": [
        "https://doi.org/10.1149/1945-7111/ace1a7",
        "https://doi.org/10.3390/en16010211",
        "https://doi.org/10.3390/en15186803",
    ],
    "Samsung_INR21700-40T.json": [
        "https://doi.org/10.1016/j.est.2023.107424",
        "https://doi.org/10.3390/batteries9010006",
        "https://doi.org/10.3390/batteries9060309",
        "https://doi.org/10.3390/s23020753",
    ],
    "Samsung_INR21700-48G.json": [
        "https://doi.org/10.1109/itec.2019.8790449",
        "https://doi.org/10.1007/s00502-020-00814-9",
        "https://doi.org/10.3390/BATTERIES5010023",
    ],
    "Samsung_INR21700-48X.json": [
        "https://doi.org/10.1016/j.est.2023.107424",
    ],
    "Samsung_INR21700-50E.json": [
        "https://doi.org/10.1016/j.apenergy.2021.118498",
        "https://doi.org/10.1016/j.est.2021.102257",
        "https://doi.org/10.1007/s00502-020-00814-9",
        "https://doi.org/10.3390/en14175434",
        "https://doi.org/10.1149/1945-7111/ace1a7",
        "https://doi.org/10.3390/batteries9060309",
        "https://doi.org/10.1149/1945-7111/acb669",
        "https://doi.org/10.3390/en15072431",
        "https://doi.org/10.1007/s10694-023-01425-4",
    ],
    "Samsung_SDI_94Ah_.json": [
        "https://doi.org/10.3390/wevj14040094",
    ],
    "Thunder-Sky_WB-LYP100AHA.json": [
        "https://www.semanticscholar.org/paper/d86ac0b0cb22085e5a2ffb8f85ec310bee3847f2",
    ],
    "Thunder-Sky_WB-LYP40AHA.json": [
        "https://www.semanticscholar.org/paper/107b1d0eb9a2f79f6bf1614771ffed155eaca1da",
        "https://www.semanticscholar.org/paper/5057b0c72900ef3d90a9b9f93fe0d564abaf0ce7",
        "https://www.semanticscholar.org/paper/7b9d934eaf10114c091e1229ed4d65de3a1002a0",
        "https://doi.org/10.3390/EN9030123",
        "https://doi.org/10.1088/1757-899X/53/1/012014",
    ],
}


def main() -> None:
    records_dir = Path(__file__).parent.parent / "records" / "cell-type"
    updated = 0
    skipped = 0
    no_match = 0

    for record_path in sorted(records_dir.glob("*/record.json")):
        with open(record_path, encoding="utf-8") as f:
            record = json.load(f)

        source_file = record.get("provenance", {}).get("source_file", "")
        source_filename = Path(source_file).name if source_file else ""

        if source_filename not in PUBLICATIONS:
            no_match += 1
            continue

        urls = PUBLICATIONS[source_filename]

        if "publications" in record:
            skipped += 1
            continue

        record["publications"] = [{"url": u} for u in urls]

        with open(record_path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)
            f.write("\n")

        print(f"  updated: {record_path.parent.name} ({len(urls)} publications)")
        updated += 1

    print(f"\nDone. Updated: {updated}  Already had pubs: {skipped}  No match: {no_match}")


if __name__ == "__main__":
    main()
