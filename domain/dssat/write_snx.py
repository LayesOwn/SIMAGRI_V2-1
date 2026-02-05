# domain/dssat/write_snx.py - ADAPTÉ DE V1 POUR SIMAGRI V2

import numpy as np
import pandas as pd
from os import path
import os
import datetime
import calendar
from pathlib import Path


def write_snx_file(scenario, x_filename, output_dir):
    """
    Génère un fichier SNX en adaptant la logique V1
    
    scenario : dict complet SIMAGRI avec dssat
    x_filename : nom du fichier X (ex: SCE_1.X)
    output_dir : dossier de sortie (/app/dssat/snx)
    """
    
    d = scenario["dssat"]
    DSSAT_PATH = "/app/dssat"  # Docker path
    
    # Extraire les paramètres
    station = d['stn_name']
    planting_date = d['PltDate']  # Format: YYYYMMDD
    crop = d['Crop']
    cultivar = d['Cultivar']
    soil_type = "SN-N15Rain"  # Senegal soil
    planting_density = str(d['plt_density'])
    scenario_name = d['sce_name']
    
    # Irrigation & Fertilisation
    irrig_app = "repr_irrig" if scenario["irrigation"]["enabled"] else "N"
    irrig_method = "IR001" if scenario["irrigation"]["enabled"] else "N"
    
    fert_app = "Fert" if scenario["fertilization"]["enabled"] else "N"
    
    # Créer dataframes pour irrigation et fertilisation
    irrig_plan = scenario["irrigation"]["schedule"]
    df_irrig = create_irrig_df(irrig_plan)
    
    fert_plan = scenario["fertilization"]["applications"]
    df_fert = create_fert_df(fert_plan)
    
    # Appeler la vraie fonction de V1 adaptée
    writeSNX_clim(
        DSSAT_PATH=DSSAT_PATH,
        station=station,
        planting_date=planting_date,
        crop=crop,
        cultivar=cultivar,
        soil_type=soil_type,
        initial_soil_moisture=0.5,  # Default
        initial_soil_no3_content=1,  # Default
        planting_density=planting_density,
        scenario=scenario_name,
        fert_app=fert_app,
        df_fert=df_fert,
        p_sim="P_no",
        p_level="M",
        irrig_app=irrig_app,
        irrig_method=irrig_method,
        df_irrig=df_irrig,
        ir_depth=30,
        ir_threshold=50,
        ir_eff=1.0,
        output_dir=output_dir
    )
    
    return Path(output_dir) / f"CL{crop}{scenario_name[:4]}.SNX"


def create_irrig_df(irrig_plan):
    """Convertir le plan d'irrigation en DataFrame"""
    if not irrig_plan:
        return pd.DataFrame({"DAP": [], "WAmount": []})
    
    data = []
    for ir in irrig_plan:
        data.append({
            "DAP": ir.get("doy", 0),
            "WAmount": ir.get("mm", 0)
        })
    
    return pd.DataFrame(data)


def create_fert_df(fert_plan):
    """Convertir le plan de fertilisation en DataFrame"""
    if not fert_plan:
        return pd.DataFrame({"DAP": [], "NAmount": [], "PAmount": [], "KAmount": []})
    
    data = []
    for f in fert_plan:
        data.append({
            "DAP": f.get("doy", 0),
            "NAmount": f.get("N", 0),
            "PAmount": f.get("P", 0),
            "KAmount": f.get("K", 0)
        })
    
    return pd.DataFrame(data)


def writeSNX_clim(DSSAT_PATH, station, planting_date, crop, cultivar, soil_type, 
                  initial_soil_moisture, initial_soil_no3_content, planting_density, 
                  scenario, fert_app, df_fert, p_sim, p_level, irrig_app, 
                  irrig_method, df_irrig, ir_depth, ir_threshold, ir_eff, output_dir):
    """
    Version adaptée de writeSNX_clim de V1 pour SIMAGRI V2
    """
    
    # Convertir la date de format YYYYMMDD à YYYYDOY
    try:
        date_object = datetime.datetime.strptime(planting_date, '%Y%m%d').date()
    except:
        # Si format différent, essayer %Y-%m-%d
        date_object = datetime.datetime.strptime(planting_date, '%Y-%m-%d').date()
    
    plt_doy = date_object.timetuple().tm_yday
    plt_year = date_object.year
    
    # ICDAT (initial condition date - jour avant semis)
    IC_date = plt_year * 1000 + (plt_doy - 1)
    ICDAT = str(IC_date)
    
    # PDATE (planting date)
    PDATE = str(plt_year)[2:] + str(plt_doy).zfill(3)
    
    # Harvest date (environ 210 jours après semis)
    hv_doy = plt_doy + 210
    if hv_doy > 365:
        hv_doy = hv_doy - 365
    
    # Nombre d'années = 1 pour maintenant
    NYERS = "1"
    SDATE = ICDAT
    
    # Parseir le cultivar
    if len(cultivar) >= 7:
        INGENO = cultivar[0:6]
        CNAME = cultivar[7:]
    else:
        INGENO = cultivar
        CNAME = "SIMAGRI"
    
    # Soil info
    ID_SOIL = soil_type[0:10]
    PPOP = planting_density
    
    # Irrigation & Fertilisation flags
    if irrig_app == "repr_irrig":
        IRRIG = 'D'
        MI = "1"
    elif irrig_app == 'auto_irrig':
        IRRIG = 'A'
        MI = "1"
    else:
        IRRIG = 'N'
        MI = "0"
    
    if fert_app == "Fert":
        FERTI = 'D'
        MF = "1"
    else:
        FERTI = 'N'
        MF = "0"
    
    # Ouvrir le template SNX
    temp_snx = path.join(DSSAT_PATH, f"SN{crop}TEMP.SNX")
    snx_name = f"CL{crop}{scenario[:4]}.SNX"
    SNX_fname = path.join(output_dir, snx_name)
    
    print(f"📝 Reading template: {temp_snx}")
    print(f"📝 Writing SNX: {SNX_fname}")
    
    try:
        with open(temp_snx, "r") as fr, open(SNX_fname, "w") as fw:
            # Lire les 14 premières lignes du template
            for line in range(0, 14):
                temp_str = fr.readline()
                fw.write(temp_str)
            
            # Écrire les flags de traitement
            FL = "1"
            fw.write("{0:3s}{1:31s}{2:3s}{3:3s}{4:3s}{5:3s}{6:3s}{7:3s}{8:3s}{9:3s}{10:3s}{11:3s}{12:3s}{13:3s}".format(
                FL.rjust(3), "1 0 0 SN-SIMAGRI                 1",
                FL.rjust(3), "0".rjust(3), "1".rjust(3), "1".rjust(3), MI.rjust(3), 
                MF.rjust(3), "0".rjust(3), "0".rjust(3),
                "0".rjust(3), "0".rjust(3), "0".rjust(3), "1".rjust(3)))
            fw.write(" \n")
            
            # Lire 3 lignes
            for line in range(0, 3):
                temp_str = fr.readline()
                fw.write(temp_str)
            
            # Écrire *CULTIVARS
            temp_str = fr.readline()
            new_str = temp_str[0:3] + crop + temp_str[5:6] + INGENO + temp_str[12:13] + CNAME
            fw.write(new_str)
            fw.write(" \n")
            
            # Lire et écrire jusqu'à *FIELDS
            for line in range(0, 3):
                temp_str = fr.readline()
                fw.write(temp_str)
            
            # Écrire *FIELDS
            WSTA_ID = station
            ID_FIELD = WSTA_ID + "0001"
            SLTX = "SL"
            SLDP = "50"
            
            fw.write("{0:2s} {1:8s}{2:5s}{3:3s}{4:6s}{5:4s}  {6:10s}{7:4s}".format(
                FL.rjust(2), ID_FIELD, WSTA_ID.rjust(5),
                "       -99   -99   -99   -99   -99   -99 ",
                SLTX.ljust(6), SLDP.rjust(4), ID_SOIL,
                " -99"))
            fw.write(" \n")
            
            # Lire et écrire les sections suivantes
            for line in range(0, 2):
                temp_str = fr.readline()
                fw.write(temp_str)
            
            temp_str = fr.readline()
            fw.write("{0:2s} {1:89s}".format(FL.rjust(2),
                                            "            -99             -99       -99               -99   -99   -99   -99   -99   -99"))
            fw.write(" \n")
            fw.write(" \n")
            
            # Sauter les sections jusqu'à *INITIAL CONDITIONS
            for nline in range(0, 50):
                temp_str = fr.readline()
                if "*INITIAL CONDITIONS" in temp_str:
                    fw.write(temp_str)
                    break
            
            # Écrire *INITIAL CONDITIONS
            temp_str = fr.readline()  # @C   PCR ICDAT
            fw.write(temp_str)
            temp_str = fr.readline()
            new_str = temp_str[0:3] + crop.rjust(3) + " " + ICDAT + temp_str[16:]
            fw.write(new_str)
            fw.write(" \n")
            
            # Lire jusqu'à *PLANTING
            for nline in range(0, 50):
                temp_str = fr.readline()
                if "*PLANTING" in temp_str:
                    fw.write(temp_str)
                    break
            
            # Écrire *PLANTING DETAILS
            temp_str = fr.readline()  # @P PDATE EDATE
            fw.write(temp_str)
            temp_str = fr.readline()
            PPOE = PPOP
            new_str = temp_str[0:3] + PDATE + "   -99" + PPOP.rjust(6) + PPOE.rjust(6) + temp_str[26:]
            fw.write(new_str)
            fw.write("  \n")
            
            # Écrire *IRRIGATION si nécessaire
            if irrig_app == 'repr_irrig' and len(df_irrig) > 0:
                fw.write('*IRRIGATION AND WATER MANAGEMENT' + "\n")
                fw.write('@I  EFIR  IDEP  ITHR  IEPT  IOFF  IAME  IAMT IRNAME' + "\n")
                fw.write(' 1     1    30    50   100 GS000 IR001    10 -99' + "\n")
                fw.write('@I IDATE  IROP IRVAL' + "\n")
                
                df_irrig = df_irrig.astype(float)
                df_filtered = df_irrig[(df_irrig["DAP"] >= 0) & (df_irrig["WAmount"] >= 0)]
                
                for i, row in df_filtered.iterrows():
                    fw.write(' 1   ' + str(int(row["DAP"])).rjust(3) + " " + irrig_method + " " + str(int(row["WAmount"])).rjust(5) + "\n")
                fw.write(" \n")
            
            # Lire jusqu'à *FERTILIZERS
            for nline in range(0, 50):
                temp_str = fr.readline()
                if "*FERTILIZERS" in temp_str:
                    fw.write(temp_str)
                    break
            
            # Écrire *FERTILIZERS
            temp_str = fr.readline()  # @F FDATE
            fw.write(temp_str)
            temp_str = fr.readline()
            
            if fert_app == "Fert" and len(df_fert) > 0:
                df_fert = df_fert.astype(float)
                df_filtered = df_fert[(df_fert["DAP"] >= 0) & (df_fert["NAmount"] >= 0)]
                
                for i, row in df_filtered.iterrows():
                    new_str = temp_str[0:5] + str(int(row["DAP"])).rjust(3) + " FE005 AP001     5 " + str(int(row["NAmount"])).rjust(5) + " " + str(int(row["PAmount"])).rjust(5) + " " + str(int(row["KAmount"])).rjust(5) + temp_str[44:]
                    fw.write(new_str)
                fw.write(" \n")
            
            fw.write("  \n")
            
            # Lire jusqu'à *SIMULATION
            for nline in range(0, 50):
                temp_str = fr.readline()
                if "*SIMULATION" in temp_str:
                    fw.write(temp_str)
                    break
            
            # Écrire *SIMULATION CONTROLS
            temp_str = fr.readline()
            fw.write(temp_str)
            temp_str = fr.readline()
            new_str = temp_str[0:17] + NYERS.rjust(3) + temp_str[20:33] + SDATE + temp_str[38:]
            fw.write(new_str)
            
            # Lire et écrire le reste
            for line in range(0, 20):
                temp_str = fr.readline()
                if temp_str.strip():
                    fw.write(temp_str)
                else:
                    break
    
    except Exception as e:
        print(f"❌ ERROR writing SNX: {e}")
        raise

    print(f"✅ SNX file written: {SNX_fname}")
    return path(SNX_fname)