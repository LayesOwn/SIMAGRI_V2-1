# domain/dssat/run_dssat.py - VERSION EXPERT
# Lancement DSSAT v4.7 - STRICT & FIABLE

from pathlib import Path
import subprocess
import shutil
import os
import platform


def get_dssat_path():
    """Détecte le chemin DSSAT"""
    system = platform.system()
    
    if system == "Windows":
        paths = [
            Path(r"C:\DSSAT47"),
            Path(r"C:\Users\Public\DSSAT47"),
        ]
    elif system == "Linux":
        paths = [Path("/opt/dssat"), Path.home() / "dssat"]
    else:
        paths = [Path.home() / "DSSAT47"]
    
    for path in paths:
        if path.exists():
            return path
    
    return paths[0]


DSSAT_ROOT = get_dssat_path()
DSSAT_EXE = DSSAT_ROOT / ("DSCSM047.exe" if platform.system() == "Windows" else "DSCSM047")


def run_dssat_simulation(snx_file, dssat_workdir=None):
    """
    Lance DSSAT - VERSION EXPERT
    
    ⚠️ CRUCIAL : Copie le fichier .X aussi !
    """
    
    print(f"\n{'='*60}")
    print(f"🌾 DSSAT SIMULATION")
    print(f"{'='*60}")
    
    snx_file = Path(snx_file).resolve()
    
    if dssat_workdir is None:
        dssat_workdir = DSSAT_ROOT
    else:
        dssat_workdir = Path(dssat_workdir).resolve()

    # ✅ Vérification DSSAT
    if not DSSAT_EXE.exists():
        print(f"❌ DSSAT not found: {DSSAT_EXE}")
        return {"returncode": 1, "stdout": "", "stderr": "DSSAT not found"}

    if not snx_file.exists():
        print(f"❌ SNX file not found: {snx_file}")
        return {"returncode": 2, "stdout": "", "stderr": "SNX not found"}

    print(f"✅ DSSAT found: {DSSAT_EXE}")

    try:
        # 1️⃣ Copier le SNX
        target_snx = dssat_workdir / snx_file.name
        shutil.copy(snx_file, target_snx)
        print(f"✅ SNX copied: {snx_file.name}")

        # 2️⃣ ⚠️ CRUCIAL : Copier le fichier .X
        x_filename = snx_file.stem + ".X"
        exp_dir = snx_file.parent.parent / "exp"
        x_file = exp_dir / x_filename
        
        if x_file.exists():
            target_x = dssat_workdir / x_file.name
            shutil.copy(x_file, target_x)
            print(f"✅ X file copied: {x_file.name}")
        else:
            print(f"⚠️  X file not found: {x_file}")
            # Continuons quand même, DSSAT peut s'en passer
        
        # 3️⃣ Vérifier que les fichiers .WTH existent dans le dossier DSSAT
        wth_files = list(dssat_workdir.glob("*.WTH"))
        print(f"✅ Weather files found: {len(wth_files)}")
        
        # 4️⃣ Lancer DSSAT
        cmd = [str(DSSAT_EXE), "A", snx_file.name]
        
        print(f"🚀 Running: {' '.join(cmd)}")
        print(f"📂 Working directory: {dssat_workdir}")
        
        result = subprocess.run(
            cmd,
            cwd=str(dssat_workdir),
            capture_output=True,
            text=True,
            timeout=300
        )

        # 5️⃣ Résultat
        if result.returncode == 0:
            print(f"✅ SIMULATION SUCCESS")
        else:
            print(f"❌ DSSAT error (code {result.returncode})")
            if result.stderr:
                print(f"   {result.stderr[:300]}")

        print(f"{'='*60}\n")
        
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return {
            "returncode": 99,
            "stdout": "",
            "stderr": str(e)
        }
