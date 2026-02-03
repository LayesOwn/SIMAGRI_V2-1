# domain/dssat/write_xfile.py

from pathlib import Path
from datetime import datetime


def write_x_file(scenario, output_dir):
    """
    Écrit un fichier DSSAT .X à partir de scenario["dssat"]
    Retourne le chemin du fichier
    
    Format DSSAT : 
    - PDATE : YYYYDDD (année + jour julien)
    - Nombres : avec décimales .1f
    """

    d = scenario["dssat"]

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{d['sce_name']}.X"
    filepath = output_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:

        # ==================================================
        # 🌾 EN-TÊTE EXPÉRIMENT
        # ==================================================
        f.write("*EXP.DETAILS: SIMAGRI DSSAT EXPERIMENT\n")
        f.write("*GENERAL\n")
        f.write("@PEOPLE\n")
        f.write(" SIMAGRI\n\n")

        # ==================================================
        # 🌱 CULTURE
        # ==================================================
        f.write("*CULTIVARS\n")
        f.write("@C CR INGENO CNAME\n")
        f.write(
            f" 1 {d['Crop']:<2} {d['Cultivar']:<8} SIMAGRI\n\n"
        )

        # ==================================================
        # 🌱 PLANTING DETAILS
        # ==================================================
        f.write("*PLANTING DETAILS\n")
        f.write("@P PDATE EDATE  PPOP  PPOE  PLME  PLDS\n")

        # ✅ Format DSSAT : YYYYDDD (année + jour julien)
        pltdate_str = str(d['PltDate']).strip()
        
        try:
            # Essayer format YYYY-MM-DD
            if '-' in pltdate_str:
                dt = datetime.strptime(pltdate_str, "%Y-%m-%d")
            # Essayer format YYYYMMDD
            elif len(pltdate_str) == 8 and pltdate_str.isdigit():
                dt = datetime.strptime(pltdate_str, "%Y%m%d")
            else:
                # Défaut
                dt = datetime(2026, 6, 15)
            
            # Jour julien (day of year)
            doy = dt.timetuple().tm_yday
            year = dt.year
            pltdate_dssat = f"{year}{doy:03d}"
        except Exception as e:
            print(f"⚠️ Erreur conversion date : {e}, utilisation date par défaut")
            pltdate_dssat = "2026166"
        
        f.write(
            f" 1 {pltdate_dssat:>6} -99 {d['plt_density']:>5.0f} "
            f"-99 -99 -99\n\n"
        )

        # ==================================================
        # 🌿 FERTILIZATION
        # ==================================================
        f.write("*FERTILIZERS (INORGANIC)\n")
        f.write("@F FDATE FMCD  FACD  FDEP  FAMN  FAMP  FAMK\n")

        fert_count = 0
        for i in range(1, 4):
            doy = d[f"Fert_{i}_DOY"]
            if doy == -99:
                continue

            fert_count += 1
            n_kg = float(d[f'N_{i}_Kg']) if d[f'N_{i}_Kg'] != -99 else 0.0
            p_kg = float(d[f'P_{i}_Kg']) if d[f'P_{i}_Kg'] != -99 else 0.0
            k_kg = float(d[f'K_{i}_Kg']) if d[f'K_{i}_Kg'] != -99 else 0.0

            f.write(
                f" {fert_count} {int(doy):>5} FE001 -99 -99 "
                f"{n_kg:>6.1f} {p_kg:>6.1f} {k_kg:>6.1f}\n"
            )

        f.write("\n")

        # ==================================================
        # 💧 IRRIGATION
        # ==================================================
        f.write("*IRRIGATION\n")
        f.write("@I IDATE  IROP  IRVAL\n")

        ir_count = 0
        if d.get("IR_method") == "MANUAL":
            for i in range(1, 6):
                doy = d.get(f"IR_{i}_DOY", -99)
                amt = d.get(f"IR_{i}_amt", -99)

                if doy == -99:
                    continue

                ir_count += 1
                f.write(
                    f" {ir_count} {int(doy):>5} IR001 {float(amt):>6.1f}\n"
                )

        f.write("\n")

        # ==================================================
        # 💰 ECONOMICS
        # ==================================================
        f.write("*ECONOMICS\n")
        f.write("@E CPRICE FCOST SCOST ICOST OCOST FIXC\n")

        cprice = float(d.get('CropPrice', 200)) if d.get('CropPrice') != -99 else 200.0
        fcost = float(d.get('NFertCost', 0)) if d.get('NFertCost') != -99 else 0.0
        scost = float(d.get('SeedCost', 0)) if d.get('SeedCost') != -99 else 0.0
        icost = float(d.get('IrrigCost', 0)) if d.get('IrrigCost') != -99 else 0.0
        ocost = float(d.get('OtherVariableCosts', 0)) if d.get('OtherVariableCosts') != -99 else 0.0
        fixc = float(d.get('FixedCosts', 0)) if d.get('FixedCosts') != -99 else 0.0

        f.write(
            f" 1 {cprice:>7.1f} {fcost:>7.1f} {scost:>7.1f} "
            f"{icost:>7.1f} {ocost:>7.1f} {fixc:>7.1f}\n"
        )

    return filepath