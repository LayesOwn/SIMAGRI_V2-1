# ==========================================================
# domain/dssat/run_dssat.py
# Lancement DSSAT v4.7 (Batch mode) - Multi-plateforme
# ==========================================================

from pathlib import Path
from shutil import copy
import subprocess
import shutil
import os
import platform


# ==========================================================
# CONFIGURATION DSSAT (Multi-plateforme)
# ==========================================================

def get_dssat_path():
    """
    Détecte le chemin DSSAT selon le système d'exploitation
    """
    system = platform.system()
    
    if system == "Windows":
        # Windows : C:\DSSAT47
        possible_paths = [
            Path(r"C:\DSSAT47"),
            Path(r"C:\Users\Public\DSSAT47"),
            Path(os.getenv("DSSAT_ROOT", r"C:\DSSAT47"))
        ]
    elif system == "Linux":
        # Linux : /opt/dssat/ ou ~/dssat/
        possible_paths = [
            Path("/opt/dssat"),
            Path.home() / "dssat",
            Path("/usr/local/dssat")
        ]
    else:  # macOS
        # macOS : ~/DSSAT47 ou /Applications/DSSAT47
        possible_paths = [
            Path.home() / "DSSAT47",
            Path("/Applications/DSSAT47"),
            Path("/opt/dssat")
        ]
    
    # Chercher le premier chemin qui existe
    for path in possible_paths:
        if path.exists():
            return path
    
    # Retourner le chemin par défaut si aucun n'existe
    return possible_paths[0]


DSSAT_ROOT = get_dssat_path()
DSSAT_EXE = DSSAT_ROOT / ("DSCSM047.exe" if platform.system() == "Windows" else "DSCSM047")
BATCH_FILE = DSSAT_ROOT / "DSSBATCH.V47"


# ==========================================================
# 1️⃣ VÉRIFIER DSSAT
# ==========================================================

def check_dssat():
    """
    Vérifie que DSSAT est correctement installé
    """
    if not DSSAT_EXE.exists():
        print(f"⚠️ AVERTISSEMENT : DSSAT introuvable à {DSSAT_EXE}")
        print(f"   Chemins testés :")
        print(f"   - Windows : C:\\DSSAT47")
        print(f"   - Linux : /opt/dssat")
        print(f"   - macOS : ~/DSSAT47")
        print(f"   Veuillez vérifier votre installation DSSAT")
        return False
    
    print(f"✅ DSSAT trouvé : {DSSAT_EXE}")
    return True


# ==========================================================
# 2️⃣ PRÉPARER LES FICHIERS SNX
# ==========================================================

def prepare_snx_files(snx_paths):
    """
    Copie les fichiers SNX dans le dossier DSSAT
    """
    if isinstance(snx_paths, str):
        snx_paths = [snx_paths]
    
    copied = []

    for snx in snx_paths:
        snx = Path(snx)
        if not snx.exists():
            raise FileNotFoundError(f"SNX introuvable : {snx}")

        target = DSSAT_ROOT / snx.name
        copy(snx, target)
        copied.append(target)
        print(f"  📄 Copié : {snx.name}")

    return copied


# ==========================================================
# 3️⃣ ÉCRIRE DSSBATCH.V47
# ==========================================================

def write_batch_file(snx_files):
    """
    Génère le fichier DSSBATCH.V47
    """
    with open(BATCH_FILE, "w") as f:
        f.write("*DSSAT Batch File\n")
        for snx in snx_files:
            f.write(f"{snx.name}\n")

    print(f"  📝 Fichier batch créé : {BATCH_FILE.name}")
    return BATCH_FILE


# ==========================================================
# 4️⃣ LANCER DSSAT
# ==========================================================

def run_dssat_batch(snx_file, workdir=None):
    """
    Lance DSSAT en mode batch sur un fichier SNX
    
    Args:
        snx_file (str): Chemin du fichier SNX
        workdir (str): Répertoire de travail (par défaut : DSSAT_ROOT)
    
    Returns:
        dict: {"returncode": int, "stdout": str, "stderr": str}
    """
    snx_file = Path(snx_file).resolve()
    
    if workdir is None:
        workdir = DSSAT_ROOT
    else:
        workdir = Path(workdir).resolve()

    if not DSSAT_EXE.exists():
        raise FileNotFoundError(f"❌ DSSAT introuvable : {DSSAT_EXE}")

    if not snx_file.exists():
        raise FileNotFoundError(f"❌ SNX introuvable : {snx_file}")

    # Copier le SNX dans le répertoire de travail
    target_snx = workdir / snx_file.name
    shutil.copy(snx_file, target_snx)
    print(f"  📄 SNX copié dans {workdir}")

    # Construire la commande
    cmd = [
        str(DSSAT_EXE),
        "A",                    # Run all treatments
        snx_file.name           # Le SNX doit être dans le workdir
    ]

    print(f"  🚀 Commande DSSAT : {' '.join(cmd)}")
    print(f"  📂 Répertoire : {workdir}")

    # Exécuter DSSAT
    result = subprocess.run(
        cmd,
        cwd=str(workdir),
        capture_output=True,
        text=True,
        timeout=300  # 5 minutes max
    )

    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr
    }


# ==========================================================
# 5️⃣ FONCTION PRINCIPALE (API)
# ==========================================================

def run_dssat_simulation(snx_file, dssat_workdir=None):
    """
    Lance une simulation DSSAT pour un fichier SNX
    
    Args:
        snx_file (str): Chemin du fichier SNX
        dssat_workdir (str): Répertoire de travail (par défaut : DSSAT_ROOT)
    
    Returns:
        dict: {"returncode": int, "stdout": str, "stderr": str}
    
    Example:
        >>> result = run_dssat_simulation("dssat/snx/SCE_1.SNX", "dssat")
        >>> if result["returncode"] == 0:
        ...     print("✅ Simulation réussie")
        ... else:
        ...     print(f"❌ Erreur : {result['stderr']}")
    """
    
    print(f"\n{'='*60}")
    print(f"🌾 LANCEMENT SIMULATION DSSAT")
    print(f"{'='*60}")
    
    # 1️⃣ Vérification
    if not check_dssat():
        return {
            "returncode": 1,
            "stdout": "",
            "stderr": "DSSAT introuvable. Veuillez vérifier votre installation."
        }

    try:
        # 2️⃣ Lancer DSSAT
        snx_file = Path(snx_file).resolve()
        result = run_dssat_batch(snx_file, dssat_workdir)

        # 3️⃣ Analyser le résultat
        if result["returncode"] == 0:
            print(f"✅ SIMULATION RÉUSSIE")
        else:
            print(f"❌ ERREUR DSSAT (code {result['returncode']})")
            if result["stderr"]:
                print(f"   Message : {result['stderr'][:200]}")

        print(f"{'='*60}\n")
        return result

    except FileNotFoundError as e:
        print(f"❌ ERREUR : {e}")
        return {
            "returncode": 2,
            "stdout": "",
            "stderr": str(e)
        }
    
    except subprocess.TimeoutExpired:
        print(f"❌ TIMEOUT : Simulation DSSAT a dépassé 5 minutes")
        return {
            "returncode": 3,
            "stdout": "",
            "stderr": "Timeout: Simulation took too long"
        }
    
    except Exception as e:
        print(f"❌ ERREUR INTERNE : {e}")
        return {
            "returncode": 4,
            "stdout": "",
            "stderr": str(e)
        }