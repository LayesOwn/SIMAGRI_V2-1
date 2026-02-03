# Lance ceci APRÈS avoir créé un scénario, JUSTE AVANT de cliquer sur Simuler
# (ou juste après, mais avant de fermer l'app)


from pathlib import Path

dssat_dir = Path("dssat")

print("\n" + "="*80)
print("🔍 VÉRIFICATION FINALE - Dossier dssat/")
print("="*80 + "\n")

# 1. Fichiers dans dssat/
print("📂 Fichiers dans dssat/ :")
all_files = sorted(dssat_dir.glob("*"))
for f in all_files:
    if f.is_file():
        size = f.stat().st_size
        print(f"  • {f.name:<20} ({size:>8} bytes)")

# 2. Vérifier les fichiers clés
print("\n📋 Fichiers critiques :")
critical = [
    ("SCE_1.SNX", "Fichier SNX"),
    ("SCE_1.X", "Fichier X"),
    ("SENEGAL.SOL", "Fichier SOL"),
    ("KAOLA.WTH", "Fichier météo"),
    ("DAKAR.WTH", "Fichier météo"),
]

for filename, desc in critical:
    path = dssat_dir / filename
    exists = "✅" if path.exists() else "❌"
    print(f"  {exists} {filename:<20} - {desc}")

# 3. Compter les fichiers .WTH
wth_count = len(list(dssat_dir.glob("*.WTH")))
print(f"\n📊 Fichiers .WTH trouvés : {wth_count}")

print("\n" + "="*80 + "\n")
