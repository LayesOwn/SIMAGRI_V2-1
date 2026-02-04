# domain/dssat/run_dssat.py - VERSION DOCKER (basée sur SIMAGRI V1)

import os
import subprocess
from pathlib import Path


# Mapping cultures → exécutables DSSAT
CROP_MODELS = {
    'ML': 'MLCER047',  # Mil
    'SG': 'SGCER047',  # Sorgho
    'RI': 'RICER047',  # Riz
    'PN': 'CRGRO047',  # Arachide
}


def run_dssat_simulation(snx_file, dssat_workdir=None):
    """
    Lance DSSAT dans Docker - EXACTEMENT comme V1
    
    ✅ Utilise os.system() avec commandes Linux
    ✅ Pas de subprocess.run()
    ✅ Pas de références Windows
    """
    
    print(f"\n{'='*60}")
    print(f"🌾 DSSAT SIMULATION (Docker)")
    print(f"{'='*60}")
    
    snx_file = Path(snx_file).resolve()
    
    if dssat_workdir is None:
        dssat_workdir = snx_file.parent.parent  # Dossier dssat/
    else:
        dssat_workdir = Path(dssat_workdir).resolve()

    # ✅ Vérification de base
    if not snx_file.exists():
        print(f"❌ SNX file not found: {snx_file}")
        return {"returncode": 2, "stdout": "", "stderr": "SNX not found"}

    print(f"✅ SNX file: {snx_file.name}")
    print(f"📂 Working directory: {dssat_workdir}")
    
    try:
        # 1️⃣ EXTRAIRE LA CULTURE DU FICHIER SNX
        crop_code = extract_crop_from_snx(snx_file)
        
        if crop_code not in CROP_MODELS:
            print(f"❌ Culture non reconnue: {crop_code}")
            return {"returncode": 3, "stdout": "", "stderr": f"Unknown crop: {crop_code}"}
        
        model = CROP_MODELS[crop_code]
        print(f"🌱 Crop: {crop_code} → Model: {model}")
        
        # 2️⃣ CHANGER LE RÉPERTOIRE DE TRAVAIL
        original_dir = os.getcwd()
        os.chdir(dssat_workdir)
        print(f"📁 Changed to: {os.getcwd()}")
        
        # 3️⃣ CRÉER DSBATCH.V47 (comme V1)
        batch_file = create_batch_file(snx_file.name, model)
        print(f"📋 Batch file created: {batch_file}")
        
        # 4️⃣ LANCER DSSAT (comme V1)
        # Commande: ./dscsm047 MLCER047 B DSSBatch.V47
        cmd = f"./dscsm047 {model} B DSSBatch.V47"
        print(f"🚀 Running: {cmd}")
        
        returncode = os.system(cmd)
        
        # 5️⃣ RÉSULTAT
        if returncode == 0:
            print(f"✅ SIMULATION SUCCESS")
            
            # Vérifier Summary.OUT
            summary_file = Path("Summary.OUT")
            if summary_file.exists():
                print(f"✅ Summary.OUT found ({summary_file.stat().st_size} bytes)")
            else:
                print(f"⚠️  Summary.OUT not found (mais simulation réussie)")
        else:
            print(f"❌ DSSAT error (code {returncode})")
        
        # Retourner au répertoire original
        os.chdir(original_dir)
        
        return {
            "returncode": returncode,
            "stdout": "",
            "stderr": ""
        }
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        os.chdir(original_dir)
        return {
            "returncode": 99,
            "stdout": "",
            "stderr": str(e)
        }


def extract_crop_from_snx(snx_file):
    """
    Extraire le code de la culture du fichier SNX
    
    Cherche la ligne avec le cultivar, ex:
    @C CR INGENO CNAME
     1 ML IB0066 SIMAGRI
    """
    
    try:
        with open(snx_file, 'r') as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines):
            if '@C CR INGENO' in line or '@C   CR INGENO' in line:
                # Ligne suivante contient la culture
                if i + 1 < len(lines):
                    data_line = lines[i + 1]
                    # Format: " 1 ML IB0066 SIMAGRI"
                    parts = data_line.split()
                    if len(parts) >= 2:
                        crop = parts[1]  # Le code culture
                        return crop
        
        # Fallback: chercher dans la section *CULTIVARS
        for i, line in enumerate(lines):
            if '*CULTIVARS' in line:
                for j in range(i+2, min(i+5, len(lines))):
                    parts = lines[j].split()
                    if len(parts) >= 2 and parts[1] in ['ML', 'SG', 'RI', 'PN']:
                        return parts[1]
        
        # Default
        return 'ML'
    
    except Exception as e:
        print(f"⚠️  Erreur extraction culture: {e}, utilisant ML par défaut")
        return 'ML'


def create_batch_file(snx_name, model):
    """
    Créer le fichier DSSBatch.V47 (comme V1)
    
    Format:
    *DSSAT Batch File
    FILEIO
    MLCER047
    file.SNX
    """
    
    batch_content = f"""*DSSAT Batch File
FILEIO
{model}
{snx_name}
"""
    
    with open("DSSBatch.V47", "w") as f:
        f.write(batch_content)
    
    return "DSSBatch.V47"