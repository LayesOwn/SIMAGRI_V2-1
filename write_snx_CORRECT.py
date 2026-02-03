# domain/dssat/write_snx.py - VERSION CORRECTE (basée sur templates DSSAT v4.7.5)

from pathlib import Path


def write_snx_file(scenario, x_filename, output_dir):
    """
    Écrit un fichier DSSAT .SNX au format CORRECT v4.7.5
    Basé sur les templates officiels SIMAGRI V1
    """

    d = scenario["dssat"]
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    snx_name = f"{d['sce_name']}.SNX"
    snx_path = output_dir / snx_name

    crop = d.get('Crop', 'ML')
    stn_name = d.get('stn_name', 'KAOL')[:4]
    soil = d.get('soil', 'SN-N15Rain')

    with open(snx_path, "w", encoding="utf-8") as f:

        # ====== EXP.DETAILS ======
        f.write("*EXP.DETAILS: SIMAGRI v2\n")
        f.write("\n")

        # ====== GENERAL ======
        f.write("*GENERAL\n")
        f.write("@PEOPLE\n")
        f.write("SIMAGRI\n")
        f.write("@ADDRESS\n")
        f.write("Senegal\n")
        f.write("@SITE\n")
        f.write(f"{stn_name}\n")
        f.write("@ PAREA  PRNO  PLEN  PLDR  PLSP  PLAY HAREA  HRNO  HLEN  HARM\n")
        f.write("    -99   -99   -99   -99   -99   -99   -99   -99   -99   -99\n")
        f.write("\n")

        # ====== TREATMENTS ======
        f.write("*TREATMENTS\n")
        f.write("@N R O C TNAME.................... CU FL SA IC MP MI MF MR MC MT ME MH SM\n")
        f.write(f" 1 1 0 0 SIMAGRI_{d['sce_name']:<20} 1  1  0  1  1  0  0  0  0  0  0  0  1\n")
        f.write("\n")

        # ====== CULTIVARS ======
        f.write("*CULTIVARS\n")
        f.write("@C CR INGENO CNAME\n")
        cultivar = d.get('Cultivar', 'IB0066')[:8]
        f.write(f" 1 {crop:<2} {cultivar:<8} SIMAGRI\n")
        f.write("\n")

        # ====== FIELDS ======
        f.write("*FIELDS\n")
        f.write("@L ID_FIELD WSTA....  FLSA  FLOB  FLDT  FLDD  FLDS  FLST SLTX  SLDP  ID_SOIL    FLNAME\n")
        f.write(f" 1 SIMAGRI01 {stn_name}       -99   -99 DR000   -99   -99     0   -99    50  {soil:<10} FIELD\n")
        f.write("@L ...........XCRD ...........YCRD .....ELEV .............AREA .SLEN .FLWR .SLAS FLHST FHDUR\n")
        lat = d.get('lat', 14.15)
        lon = d.get('lon', -16.07)
        f.write(f" 1            {lat:<14.2f} {lon:<14.2f}       30               -99   -99   -99   -99   -99   -99\n")
        f.write("\n")

        # ====== INITIAL CONDITIONS ======
        f.write("*INITIAL CONDITIONS\n")
        f.write("@C   PCR ICDAT  ICRT  ICND  ICRN  ICRE  ICWD ICRES ICREN ICREP ICRIP ICRID ICNAME\n")
        f.write(f" 1    {crop:<2} 81168   -99     0     1     1   -99     0     0     0   100    15 -99\n")
        f.write("@C  ICBL  SH2O  SNH4  SNO3\n")
        f.write(" 1    20  .147    .6   1.5\n")
        f.write(" 1    30  .197    .6   1.5\n")
        f.write("\n")

        # ====== PLANTING DETAILS ======
        f.write("*PLANTING DETAILS\n")
        f.write("@P PDATE EDATE  PPOP  PPOE  PLME  PLDS  PLRS  PLRD  PLDP  PLWT  PAGE  PENV  PLPH  SPRL                        PLNAME\n")
        
        # Convertir la date en format DSSAT (YYDDD)
        pltdate_str = str(d.get('PltDate', '2026-06-15')).strip()
        try:
            from datetime import datetime
            if '-' in pltdate_str:
                dt = datetime.strptime(pltdate_str, "%Y-%m-%d")
            else:
                dt = datetime(2026, 6, 15)
            
            doy = dt.timetuple().tm_yday
            year = dt.year
            # Format YYDDD (2 chiffres année, 3 jour)
            pdate = f"{str(year)[-2:]}{doy:03d}"
        except:
            pdate = "26166"

        ppop = int(d.get('plt_density', 6))
        f.write(f" 1 {pdate:>5} 99365     {ppop:>2}     6     S     R    60     0     5   -99   -99   -99   -99   -99                        FIELD\n")
        f.write("\n")

        # ====== FERTILIZERS (INORGANIC) ======
        f.write("*FERTILIZERS (INORGANIC)\n")
        f.write("@F FDATE  FMCD  FACD  FDEP  FAMN  FAMP  FAMK  FAMC  FAMO  FOCD FERNAME\n")
        
        fert_count = 0
        for i in range(1, 4):
            doy = int(d.get(f"Fert_{i}_DOY", -99))
            if doy == -99:
                continue
            
            fert_count += 1
            n_kg = float(d.get(f"N_{i}_Kg", 0)) if d.get(f"N_{i}_Kg", -99) != -99 else -99
            p_kg = float(d.get(f"P_{i}_Kg", 0)) if d.get(f"P_{i}_Kg", -99) != -99 else -99
            k_kg = float(d.get(f"K_{i}_Kg", 0)) if d.get(f"K_{i}_Kg", -99) != -99 else -99
            
            f.write(f" {fert_count}     {doy:>3} FE005 AP002     4   {n_kg:>3.0f}   {p_kg:>3.0f}   {k_kg:>3.0f}   -99   -99   -99 -99\n")

        f.write("\n")

        # ====== SIMULATION CONTROLS ======
        f.write("*SIMULATION CONTROLS\n")
        f.write("@N GENERAL     NYERS NREPS START SDATE RSEED SNAME.................... SMODEL\n")
        f.write(f" 1 GE              1     1     S 81168  2150 DEFAULT SIMULATION CONTR  {crop}CER\n")
        f.write("@N OPTIONS     WATER NITRO SYMBI PHOSP POTAS DISES  CHEM  TILL   CO2\n")
        f.write(" 1 OP              Y     Y     Y     N     N     N     N     N     D\n")
        f.write("@N METHODS     WTHER INCON LIGHT EVAPO INFIL PHOTO HYDRO NSWIT MESOM MESEV MESOL\n")
        f.write(" 1 ME              M     M     E     R     S     C     R     1     G     S     2\n")
        f.write("@N MANAGEMENT  PLANT IRRIG FERTI RESID HARVS\n")
        f.write(" 1 MA              R     N     D     N     M\n")
        f.write("@N OUTPUTS     FNAME OVVEW SUMRY FROPT GROUT CAOUT WAOUT NIOUT MIOUT DIOUT VBOSE CHOUT OPOUT FMOPT\n")
        f.write(" 1 OU              N     Y     Y     1     N     N     N     N     N     N     N     N     Y     A\n")
        f.write("\n")

        # ====== AUTOMATIC MANAGEMENT ======
        f.write("@  AUTOMATIC MANAGEMENT\n")
        f.write("@N PLANTING    PFRST PLAST PH2OL PH2OU PH2OD PSTMX PSTMN\n")
        f.write(" 1 PL          13109 13109    40   100    30    40    10\n")
        f.write("@N IRRIGATION  IMDEP ITHRL ITHRU IROFF IMETH IRAMT IREFF\n")
        f.write(" 1 IR             30    50   100 GS000 IR001    10     1\n")
        f.write("@N NITROGEN    NMDEP NMTHR NAMNT NCODE NAOFF\n")
        f.write(" 1 NI              5    50    25 FE005 GS000\n")
        f.write("@N RESIDUES    RIPCN RTIME RIDEP\n")
        f.write(" 1 RE            100     1    20\n")
        f.write("@N HARVEST     HFRST HLAST HPCNP HPCNR\n")
        f.write(" 1 HA              0 13109   100     0\n")
        f.write("\n")

    return snx_path
