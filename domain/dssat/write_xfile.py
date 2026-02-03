# domain/dssat/write_xfile.py - VERSION ULTRA-STRICTE
# Format DSSAT v4.7 - Alignement FORTRAN parfait

from pathlib import Path
from datetime import datetime


def write_x_file(scenario, output_dir):
    """
    Écrit un fichier DSSAT .X avec format FORTRAN ULTRA-STRICT
    """

    d = scenario["dssat"]
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{d['sce_name']}.X"
    filepath = output_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:

        # ====== EN-TÊTE ======
        f.write("*EXP.DETAILS: SIMAGRI\n")
        f.write("*GENERAL\n")
        f.write("@PEOPLE\n")
        f.write(" SIMAGRI\n")
        f.write("@SITE\n")
        f.write(" SIMAGRI\n")
        f.write("\n")

        # ====== CULTIVARS ======
        f.write("*CULTIVARS\n")
        f.write("@C CR INGENO CNAME\n")
        crop = str(d.get('Crop', 'ML'))[:2].ljust(2)
        cultivar = str(d.get('Cultivar', 'IB0066'))[:8].ljust(8)
        f.write(f" 1 {crop} {cultivar} SIMAGRI\n")
        f.write("\n")

        # ====== PLANTING ======
        f.write("*PLANTING DETAILS\n")
        f.write("@P PDATE EDATE  PPOP  PPOE  PLME  PLDS\n")

        # Parse date
        pltdate_str = str(d.get('PltDate', '2026-06-15')).strip()
        try:
            if '-' in pltdate_str:
                dt = datetime.strptime(pltdate_str, "%Y-%m-%d")
            elif len(pltdate_str) == 8:
                dt = datetime.strptime(pltdate_str, "%Y%m%d")
            else:
                dt = datetime(2026, 6, 15)
            
            doy = dt.timetuple().tm_yday
            year = dt.year
            pdate = f"{year}{doy:03d}"
        except:
            pdate = "2026166"

        ppop = int(d.get('plt_density', 5))
        
        # Format FORTRAN strict : I5 pour pdate, I5 pour ppop
        f.write(f" 1 {int(pdate):>5} -99  {ppop:>4} -99 -99 -99\n")
        f.write("\n")

        # ====== FERTILIZERS ======
        f.write("*FERTILIZERS (INORGANIC)\n")
        f.write("@F FDATE FMCD  FACD  FDEP  FAMN  FAMP  FAMK\n")

        fert_count = 0
        for i in range(1, 4):
            doy = int(d.get(f"Fert_{i}_DOY", -99))
            if doy == -99:
                continue
            
            fert_count += 1
            n_kg = float(d.get(f"N_{i}_Kg", 0)) if d.get(f"N_{i}_Kg", -99) != -99 else 0.0
            p_kg = float(d.get(f"P_{i}_Kg", 0)) if d.get(f"P_{i}_Kg", -99) != -99 else 0.0
            k_kg = float(d.get(f"K_{i}_Kg", 0)) if d.get(f"K_{i}_Kg", -99) != -99 else 0.0
            
            f.write(f" {fert_count} {doy:>5} FE001 -99 -99 {n_kg:>6.1f} {p_kg:>6.1f} {k_kg:>6.1f}\n")

        f.write("\n")

        # ====== IRRIGATION ======
        f.write("*IRRIGATION\n")
        f.write("@I IDATE  IROP  IRVAL\n")

        ir_count = 0
        if d.get("IR_method") == "MANUAL":
            for i in range(1, 6):
                doy = int(d.get(f"IR_{i}_DOY", -99))
                if doy == -99:
                    continue
                
                ir_count += 1
                amt = float(d.get(f"IR_{i}_amt", 0)) if d.get(f"IR_{i}_amt", -99) != -99 else 0.0
                f.write(f" {ir_count} {doy:>5} IR001 {amt:>6.1f}\n")

        f.write("\n")

        # ====== ECONOMICS ======
        f.write("*ECONOMICS\n")
        f.write("@E CPRICE FCOST SCOST ICOST OCOST FIXC\n")

        cprice = float(d.get('CropPrice', 200))
        fcost = float(d.get('NFertCost', 0))
        scost = float(d.get('SeedCost', 0))
        icost = float(d.get('IrrigCost', 0))
        ocost = float(d.get('OtherVariableCosts', 0))
        fixc = float(d.get('FixedCosts', 0))

        f.write(f" 1 {cprice:>7.1f} {fcost:>7.1f} {scost:>7.1f} {icost:>7.1f} {ocost:>7.1f} {fixc:>7.1f}\n")

    return filepath