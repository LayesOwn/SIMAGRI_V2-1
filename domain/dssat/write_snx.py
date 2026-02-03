# domain/dssat/write_snx.py - VERSION FINALE CORRIGÉE

from pathlib import Path
from datetime import datetime


def write_snx_file(scenario, x_filename, output_dir):
    """
    Écrit un fichier DSSAT .SNX
    SANS dépendre d'un template - génération complète et propre
    """
    
    d = scenario["dssat"]
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ========== EXTRACT DATA ==========
    crop = d.get('Crop', 'ML')[:2]
    stn_name = d.get('stn_name', 'KAOL')[:4].upper()
    soil = d.get('soil', 'SN-N15Rain')[:10]
    cultivar = d.get('Cultivar', 'IB0066')[:8]
    
    # Date conversion
    pltdate_str = str(d.get('PltDate', '2026-06-15')).strip()
    try:
        if '-' in pltdate_str:
            dt = datetime.strptime(pltdate_str, "%Y-%m-%d")
        else:
            dt = datetime(2026, 6, 15)
        
        doy = dt.timetuple().tm_yday
        year = dt.year
        pdate = f"{str(year)[-2:]}{doy:03d}"
    except:
        pdate = "26166"

    ppop = int(d.get('plt_density', 6))
    sce_name = d.get('sce_name', 'SCE_1')
    
    snx_name = f"{sce_name}.SNX"
    snx_path = output_dir / snx_name
    
    # ========== WRITE SNX - COMPLÈTEMENT GÉNÉRÉ ==========
    with open(snx_path, "w") as f:
        
        # En-tête
        f.write("*EXP.DETAILS: SIMAGRI\n\n")
        
        # GENERAL
        f.write("*GENERAL\n")
        f.write("@PEOPLE\n")
        f.write("SIMAGRI\n")
        f.write("@ADDRESS\n")
        f.write("Senegal\n")
        f.write("@SITE\n")
        f.write("Senegal\n")
        f.write("@ PAREA  PRNO  PLEN  PLDR  PLSP  PLAY HAREA  HRNO  HLEN  HARM.........\n")
        f.write("    -99   -99   -99   -99   -99   -99   -99   -99   -99   -99\n\n")
        
        # TREATMENTS
        f.write("*TREATMENTS                        -------------FACTOR LEVELS------------\n")
        f.write("@N R O C TNAME.................... CU FL SA IC MP MI MF MR MC MT ME MH SM\n")
        f.write(f"  1 1 0 0 SIMAGRI                    1  1  0  1  1  0  0  0  0  0  0  0  1\n\n")
        
        # CULTIVARS
        f.write("*CULTIVARS\n")
        f.write("@C CR INGENO CNAME\n")
        f.write(f"  1 {crop} {cultivar} SIMAGRI\n\n")
        
        # FIELDS
        f.write("*FIELDS\n")
        f.write("@L ID_FIELD WSTA....  FLSA  FLOB  FLDT  FLDD  FLDS  FLST SLTX  SLDP  ID_SOIL    FLNAME\n")
        f.write(f"  1 {stn_name}0001 {stn_name}       -99   -99 DR000   -99   -99     0   -99    50  {soil:<10} -99\n")
        f.write("@L ...........XCRD ...........YCRD .....ELEV .............AREA .SLEN .FLWR .SLAS FLHST FHDUR\n")
        f.write("  1            -99             -99       -99               -99   -99   -99   -99   -99   -99\n\n")
        
        # INITIAL CONDITIONS
        f.write("*INITIAL CONDITIONS\n")
        f.write("@C   PCR ICDAT  ICRT  ICND  ICRN  ICRE  ICWD ICRES ICREN ICREP ICRIP ICRID ICNAME\n")
        f.write(f"  1    {crop} 81168   -99     0     1     1   -99     0     0     0   100    15 -99\n")
        f.write("@C  ICBL  SH2O  SNH4  SNO3\n")
        f.write("  1    20  .147    .6   1.5\n")
        f.write("  1    30  .197    .6   1.5\n\n")
        
        # PLANTING DETAILS
        f.write("*PLANTING DETAILS\n")
        f.write("@P PDATE EDATE  PPOP  PPOE  PLME  PLDS  PLRS  PLRD  PLDP  PLWT  PAGE  PENV  PLPH  SPRL                        PLNAME\n")
        f.write(f"  1 {pdate:>5}   -99     {ppop:>2}     6     S     R    60     0     5   -99   -99   -99   -99   -99                        FIELD\n\n")
        
        # FERTILIZERS (INORGANIC)
        f.write("*FERTILIZERS (INORGANIC)\n")
        f.write("@F FDATE  FMCD  FACD  FDEP  FAMN  FAMP  FAMK  FAMC  FAMO  FOCD FERNAME\n")
        f.write("  1     1 FE005 AP002     4   -99   -99   -99   -99   -99   -99 -99\n\n")
        
        # SIMULATION CONTROLS
        f.write("*SIMULATION CONTROLS\n")
        f.write("@N GENERAL     NYERS NREPS START SDATE RSEED SNAME.................... SMODEL\n")
        f.write(f"  1 GE              1     1     S 81168  2150 DEFAULT SIMULATION CONTR  {crop}CER\n")
        f.write("@N OPTIONS     WATER NITRO SYMBI PHOSP POTAS DISES  CHEM  TILL   CO2\n")
        f.write("  1 OP              Y     Y     Y     N     N     N     N     N     D\n")
        f.write("@N METHODS     WTHER INCON LIGHT EVAPO INFIL PHOTO HYDRO NSWIT MESOM MESEV MESOL\n")
        f.write("  1 ME              M     M     E     R     S     C     R     1     G     S     2\n")
        f.write("@N MANAGEMENT  PLANT IRRIG FERTI RESID HARVS\n")
        f.write("  1 MA              R     N     D     N     M\n")
        f.write("@N OUTPUTS     FNAME OVVEW SUMRY FROPT GROUT CAOUT WAOUT NIOUT MIOUT DIOUT VBOSE CHOUT OPOUT FMOPT\n")
        f.write("  1 OU              N     Y     Y     1     N     N     N     N     N     N     N     N     Y     A\n\n")
        
        # AUTOMATIC MANAGEMENT
        f.write("@  AUTOMATIC MANAGEMENT\n")
        f.write("@N PLANTING    PFRST PLAST PH2OL PH2OU PH2OD PSTMX PSTMN\n")
        f.write("  1 PL          13109 13109    40   100    30    40    10\n")
        f.write("@N IRRIGATION  IMDEP ITHRL ITHRU IROFF IMETH IRAMT IREFF\n")
        f.write("  1 IR             30    50   100 GS000 IR001    10     1\n")
        f.write("@N NITROGEN    NMDEP NMTHR NAMNT NCODE NAOFF\n")
        f.write("  1 NI              5    50    25 FE005 GS000\n")
        f.write("@N RESIDUES    RIPCN RTIME RIDEP\n")
        f.write("  1 RE            100     1    20\n")
        f.write("@N HARVEST     HFRST HLAST HPCNP HPCNR\n")
        f.write("  1 HA              0 13109   100     0\n")
    
    return snx_path