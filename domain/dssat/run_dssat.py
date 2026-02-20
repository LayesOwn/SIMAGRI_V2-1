# domain/dssat/run_dssat.py - VERSION FINALE CORRIGÉE

import os
import subprocess
from pathlib import Path
import shutil
import re


# Mapping cultures → exécutables DSSAT
CROP_MODELS = {
    'ML': 'MLCER047',  # Mil
    'SG': 'SGCER047',  # Sorgho
    'RI': 'RICER047',  # Riz
    'PN': 'CRGRO047',  # Arachide
}

CROP_NAMES = {
    'MLCER047': 'PEARL MILLET',
    'SGCER047': 'GRAIN SORGHUM',
    'RICER047': 'GRAIN RICE',
    'CRGRO047': 'PEANUT',
}


def run_dssat_simulation(snx_file, dssat_workdir=None):
    """
    Lance DSSAT dans Docker - EXACTEMENT comme V1
    
    ✅ Utilise os.system() avec commandes Linux
    ✅ Chemin DSSAT correct pour Docker
    ✅ Format batch file correct
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
        
        # 3️⃣ S'assurer que le SNX est dans le répertoire de travail DSSAT
        snx_in_workdir = dssat_workdir / snx_file.name
        if snx_file.resolve() != snx_in_workdir.resolve():
            shutil.copy2(snx_file, snx_in_workdir)

        # 4️⃣ CRÉER DSBATCH.V47 (format CORRECT)
        batch_file = create_batch_file(snx_in_workdir.name, model)
        print(f"📋 Batch file created: {batch_file}")

        # 4bis️⃣ Assurer les alias météo 4-caractères (KAOL.WTH, etc.)
        ensure_weather_aliases(dssat_workdir)

        # 4ter️⃣ Nettoyer les sorties DSSAT précédentes pour éviter
        # la lecture de lignes anciennes dans Summary/Evaluate.
        for stale in ("Summary.OUT", "Evaluate.OUT", "WARNING.OUT", "ERROR.OUT"):
            p = Path(stale)
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass
        
        # DEBUG : afficher le contenu du batch file
        with open("DSSBatch.V47", "r") as f:
            print(f"📋 Batch file content:\n{f.read()}")
        
        # 5️⃣ LANCER DSSAT (Docker version)
        # Chemin complet DSSAT dans Docker
        dssat_path = "/home/SIMAGRI/DSSAT/dssat-base-files/dscsm047"
        cmd = f"{dssat_path} {model} B DSSBatch.V47"
        print(f"🚀 Running: {cmd}")
        
        proc = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        stdout, stderr = proc.communicate()
        stdout = stdout or ""
        stderr = stderr or ""
        if stdout:
            print(stdout)
        if stderr:
            print(stderr)
        returncode = proc.returncode

        # DSSAT may return shell code 0 even if model ends with internal error.
        warning_file = Path("WARNING.OUT")
        if warning_file.exists():
            try:
                warning_txt = warning_file.read_text(encoding="latin-1", errors="ignore")
                m = re.search(r"Simulation ended with error code\s+(\d+)", warning_txt)
                if m:
                    internal_code = int(m.group(1))
                    print(f"❌ DSSAT internal error code detected in WARNING.OUT: {internal_code}")
                    returncode = internal_code if internal_code != 0 else 1
            except Exception:
                pass
        
        # 6️⃣ RÉSULTAT
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
            "stdout": stdout,
            "stderr": stderr
        }
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        os.chdir(original_dir)
        return {
            "returncode": 99,
            "stdout": "",
            "stderr": str(e)
        }


def ensure_weather_aliases(dssat_workdir):
    """
    DSSAT peut demander des fichiers météo en code station 4 caractères.
    On crée des alias *.WTH (ex: KAOL.WTH -> KAOLA.WTH) si absents.
    """
    workdir = Path(dssat_workdir)
    for wth in workdir.glob("*.WTH"):
        stem = wth.stem
        if len(stem) < 4:
            continue
        alias = workdir / f"{stem[:4]}.WTH"
        try:
            if alias.exists() or alias.resolve() == wth.resolve():
                continue
            shutil.copy2(wth, alias)
            print(f"✅ Weather alias created: {alias.name} -> {wth.name}")
        except Exception as e:
            print(f"⚠️  Weather alias skipped ({alias.name}): {e}")


def extract_crop_from_snx(snx_file):
    """
    Extraire le code de la culture du fichier SNX
    """
    
    try:
        with open(snx_file, 'r') as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines):
            if '@C CR INGENO' in line or '@C   CR INGENO' in line:
                if i + 1 < len(lines):
                    data_line = lines[i + 1]
                    parts = data_line.split()
                    if len(parts) >= 2:
                        crop = parts[1]
                        return crop
        
        for i, line in enumerate(lines):
            if '*CULTIVARS' in line:
                for j in range(i+2, min(i+5, len(lines))):
                    parts = lines[j].split()
                    if len(parts) >= 2 and parts[1] in ['ML', 'SG', 'RI', 'PN']:
                        return parts[1]
        
        return 'ML'
    
    except Exception as e:
        print(f"⚠️  Erreur extraction culture: {e}, utilisant ML par défaut")
        return 'ML'


def create_batch_file(snx_name, model):
    """
    Créer le fichier DSSBatch.V47 au format DSSAT v4.7 CORRECT
    
    Format basé sur les templates V1 de SIMAGRI
    """
    
    crop_name = CROP_NAMES.get(model, 'CROP')
    
    header = [
        f"$BATCH({crop_name})",
        "!",
        "! Experiment generated by SIMAGRI V2",
        f"! Command Line : {model} B DSSBatch.V47",
        "!",
        "@FILEX                                                                                        TRTNO     RP     SQ     OP     CO",
    ]

    # Fixed-width data line matching DSSAT templates.
    filex_col = f"{snx_name:<92}"
    data_line = f"{filex_col}{1:>6}{1:>7}{0:>7}{0:>7}{0:>7}"

    # DSSAT parser in this stack is sensitive to line endings.
    batch_content = "\r\n".join(header + [data_line, ""])  # final newline

    with open("DSSBatch.V47", "w", encoding="ascii", newline="") as f:
        f.write(batch_content)
    
    return "DSSBatch.V47"
