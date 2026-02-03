#!/usr/bin/env python3
"""
🔍 VÉRIFICATION COMPLÈTE DES FICHIERS SIMAGRI
Vérifie tous les fichiers obligatoires pour le fonctionnement
"""

from pathlib import Path
import json

print("\n" + "="*80)
print("🔍 VÉRIFICATION COMPLÈTE - SIMAGRI V3")
print("="*80 + "\n")

# Dossier racine
ROOT = Path.cwd()
print(f"📂 Répertoire racine : {ROOT}\n")

# Dictionnaire des fichiers obligatoires
REQUIRED_FILES = {
    "🏗️ STRUCTURE": {
        "ui/__init__.py": "Package UI",
        "ui/callbacks.py": "Callbacks Dash",
        "ui/layout_main.py": "Layout principal",
        "ui/layout_home.py": "Layout accueil",
        "ui/components.py": "Composants réutilisables",
        "domain/__init__.py": "Package domaine",
        "domain/crop.py": "Gestion des cultures",
        "domain/fertilisation.py": "Gestion fertilisation",
        "domain/irrigation.py": "Gestion irrigation",
        "domain/scenario.py": "Construction scénarios",
        "domain/decision.py": "Évaluation scénarios",
        "domain/socio_eco.py": "Socio-économie",
    },
    "🌍 CLIMAT": {
        "domain/climate/__init__.py": "Package climat",
        "domain/climate/enacts.py": "Données ENACTS",
        "domain/climate/historical.py": "Analyse historique",
        "domain/climate/onset.py": "Début de saison",
    },
    "🌾 DSSAT": {
        "domain/dssat/__init__.py": "Package DSSAT",
        "domain/dssat/run_dssat.py": "Lancement DSSAT",
        "domain/dssat/write_xfile.py": "Écriture fichier .X",
        "domain/dssat/write_snx.py": "Écriture fichier .SNX",
        "domain/dssat/write_weather.py": "Écriture météo",
    },
    "📊 DONNÉES": {
        "data/geojson/senegal_departments.json": "GeoJSON départements",
        "dssat/SENEGAL.SOL": "Fichier sol DSSAT",
    },
    "🌡️ MÉTÉO": {
        "dssat/KAOLA.WTH": "Météo Kaolack",
        "dssat/DAKAR.WTH": "Météo Dakar",
        "dssat/LOUGA.WTH": "Météo Louga",
        "dssat/BAMBY.WTH": "Météo Bambey",
        "dssat/THIES.WTH": "Météo Thiès",
    },
    "⚙️ CONFIG": {
        "app.py": "Application Flask/Dash",
        "run.py": "Script lancement",
        "requirements.txt": "Dépendances Python",
    }
}

# Vérifier les fichiers
results = {}
for category, files in REQUIRED_FILES.items():
    print(f"\n{category}")
    print("-" * 80)
    results[category] = {"total": len(files), "ok": 0, "missing": []}
    
    for filepath, description in files.items():
        full_path = ROOT / filepath
        exists = full_path.exists()
        status = "✅" if exists else "❌"
        
        if exists:
            results[category]["ok"] += 1
            size = full_path.stat().st_size
            print(f"{status} {filepath:<45} ({size:>8} bytes) - {description}")
        else:
            results[category]["missing"].append(filepath)
            print(f"{status} {filepath:<45} {'MANQUANT':<8}   - {description}")

# Résumé
print("\n" + "="*80)
print("📋 RÉSUMÉ")
print("="*80)

total_all = 0
ok_all = 0

for category, data in results.items():
    total = data["total"]
    ok = data["ok"]
    missing = len(data["missing"])
    pct = (ok / total * 100) if total > 0 else 0
    
    status = "✅" if missing == 0 else f"⚠️  ({missing} manquant)"
    print(f"{status} {category:<30} : {ok}/{total} ({pct:>5.1f}%)")
    
    total_all += total
    ok_all += ok

pct_total = (ok_all / total_all * 100) if total_all > 0 else 0
print(f"\n{'='*80}")
if ok_all == total_all:
    print(f"✅ TOUS LES FICHIERS SONT PRÉSENTS ! ({ok_all}/{total_all} - {pct_total:.1f}%)")
else:
    print(f"⚠️  FICHIERS MANQUANTS : {total_all - ok_all}/{total_all}")
print(f"{'='*80}\n")

# Détail des fichiers manquants
missing_count = 0
for category, data in results.items():
    if data["missing"]:
        missing_count += len(data["missing"])

if missing_count > 0:
    print("\n🔴 FICHIERS À CRÉER/CORRIGER:\n")
    for category, data in results.items():
        if data["missing"]:
            print(f"{category}:")
            for filepath in data["missing"]:
                print(f"  ❌ {filepath}")
            print()

# Vérifications supplémentaires
print("\n" + "="*80)
print("🔧 VÉRIFICATIONS SUPPLÉMENTAIRES")
print("="*80 + "\n")

# 1. GeoJSON valide ?
print("1️⃣ Validité GeoJSON...")
geojson_path = ROOT / "data/geojson/senegal_departments.json"
if geojson_path.exists():
    try:
        with open(geojson_path) as f:
            data = json.load(f)
        
        features = data.get("features", [])
        print(f"   ✅ GeoJSON valide")
        print(f"   📍 Nombre de départements : {len(features)}")
        
        if len(features) >= 40:
            print(f"   ✅ Au moins 40 départements")
        else:
            print(f"   ⚠️  Moins de 40 départements ({len(features)})")
    except Exception as e:
        print(f"   ❌ Erreur JSON : {e}")
else:
    print(f"   ❌ Fichier manquant")

# 2. Fichiers .WTH valides ?
print("\n2️⃣ Fichiers météo (.WTH)...")
wth_files = list((ROOT / "dssat").glob("*.WTH"))
print(f"   📄 Fichiers trouvés : {len(wth_files)}")
if len(wth_files) >= 5:
    print(f"   ✅ Au moins 5 fichiers météo")
    for f in wth_files:
        size = f.stat().st_size
        lines = len(open(f).readlines())
        print(f"      • {f.name:<15} : {lines:>4} lignes")
else:
    print(f"   ⚠️  Moins de 5 fichiers ({len(wth_files)})")

# 3. Fichier SOL valide ?
print("\n3️⃣ Fichier sol (SENEGAL.SOL)...")
sol_path = ROOT / "dssat/SENEGAL.SOL"
if sol_path.exists():
    size = sol_path.stat().st_size
    with open(sol_path) as f:
        content = f.read()
    
    if "SN-N15Rain" in content:
        print(f"   ✅ Fichier SOL valide")
        print(f"   📍 Taille : {size} bytes")
    else:
        print(f"   ⚠️  Fichier SOL incomplet (manque SN-N15Rain)")
else:
    print(f"   ❌ Fichier manquant")

# 4. Fichiers .X et .SNX ?
print("\n4️⃣ Fichiers simulation (.X et .SNX)...")
x_files = list((ROOT / "dssat/exp").glob("*.X")) if (ROOT / "dssat/exp").exists() else []
snx_files = list((ROOT / "dssat/snx").glob("*.SNX")) if (ROOT / "dssat/snx").exists() else []
print(f"   📄 Fichiers .X : {len(x_files)}")
print(f"   📄 Fichiers .SNX : {len(snx_files)}")
if len(x_files) > 0 or len(snx_files) > 0:
    print(f"   ℹ️  Ces fichiers sont générés dynamiquement (OK)")
else:
    print(f"   ℹ️  Seront créés lors de la simulation")

print("\n" + "="*80)
print("✅ VÉRIFICATION TERMINÉE")
print("="*80 + "\n")