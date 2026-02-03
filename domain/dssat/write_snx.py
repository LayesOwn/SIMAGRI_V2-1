# domain/dssat/write_snx_file.py

from pathlib import Path


def write_snx_file(scenario, x_filename, output_dir):
    """
    Écrit un fichier DSSAT .SNX
    - scenario : dict complet SIMAGRI
    - x_filename : nom du fichier .X (ex: SCE_1.X)
    - output_dir : dossier de sortie
    """

    d = scenario["dssat"]

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    snx_name = f"{d['sce_name']}.SNX"
    snx_path = output_dir / snx_name

    # Récupérer les années
    year1 = d.get('FirstYear', 1983)
    year2 = d.get('LastYear', 2016)

    with open(snx_path, "w", encoding="utf-8") as f:

        # ==================================================
        # 📍 EN-TÊTE
        # ==================================================
        f.write("*SIMULATION CONTROL\n")
        f.write("*GENERAL\n")
        f.write("@PEOPLE\n")
        f.write(" SIMAGRI DSSAT\n\n")

        # ==================================================
        # 📍 TREATMENTS
        # ==================================================
        f.write("*TREATMENTS\n")
        f.write("@N R O C TNAME\n")
        f.write(
            f" 1 1 1 1 SIMAGRI_{d['sce_name']}\n\n"
        )

        # ==================================================
        # 📍 CULTIVARS
        # ==================================================
        f.write("*CULTIVARS\n")
        f.write("@C CR INGENO\n")
        f.write(
            f" 1 {d['Crop']:<2} {d['Cultivar']}\n\n"
        )

        # ==================================================
        # 📍 FIELDS
        # ==================================================
        f.write("*FIELDS\n")
        f.write("@F WSTA  FLSA  FLOB  FLDT  FLDD  FLSD  FLND  FLPF  TXTL\n")
        f.write(
            f" 1 {d['stn_name']:<5} -99 -99 -99 -99 -99 -99 -99 -99\n\n"
        )

        # ==================================================
        # 📍 SOIL
        # ==================================================
        f.write("*SOIL\n")
        f.write("@S SLNO\n")
        f.write(
            f" 1 {d['soil']}\n\n"
        )

        # ==================================================
        # 📍 WEATHER
        # ==================================================
        f.write("*WEATHER\n")
        f.write("@W WSTA\n")
        # ✅ Utiliser le code de station correct (courts, 4 caractères max)
        stn_code = d['stn_name'][:4].upper()
        f.write(
            f" 1 {stn_code}\n\n"
        )

        # ==================================================
        # 📍 MANAGEMENT
        # ==================================================
        f.write("*MANAGEMENT\n")
        f.write("@M FILEX\n")
        f.write(
            f" 1 {x_filename}\n\n"
        )

        # ==================================================
        # 📍 SIMULATION DETAILS
        # ==================================================
        f.write("*SIMULATION\n")
        f.write("@N NSIM SQ SMSC SMSL SABC SBUD SRID APD\n")
        f.write(
            f" 1 1    N   2   1   0   0   0   Y\n\n"
        )

        # ==================================================
        # 📍 PLANTING SCHEDULE
        # ==================================================
        f.write("*PLANTING\n")
        f.write("@P PFRST PLAST PH2O PH2D\n")
        f.write(
            f" 1 1983001 2016365 40 9\n\n"
        )

        # ==================================================
        # 📍 OUTPUTS
        # ==================================================
        f.write("*OUTPUTS\n")
        f.write("@O OUTN OUTD OUTF OUTC OUTL OUTS OUTG OUTU\n")
        f.write(
            f" 1    N    Y    Y    N    N    N    N    N\n\n"
        )

    return snx_path