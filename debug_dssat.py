from pathlib import Path

print("\n🔍 VÉRIFICATION FICHIERS DSSAT")
print("="*70)

dssat_dir = Path("dssat").resolve()

# 1. Vérifie que les fichiers existent
print(f"\n📂 Dossier DSSAT : {dssat_dir}")

files_to_check = [
    "SENEGAL.SOL",
    "SCE_1.SNX",
    "SCE_1.X",
    "KAOLA.WTH",
    "BAMBY.WTH",
    "DAKAR.WTH",
    "LOUGA.WTH",
    "THIES.WTH",
]

for filename in files_to_check:
    filepath = dssat_dir / filename
    exists = filepath.exists()
    status = "✅" if exists else "❌"
    print(f"{status} {filename}")

# 2. Affiche le contenu du fichier .SNX
print(f"\n📄 Contenu de SCE_1.SNX :")
print("="*70)
snx_file = dssat_dir / "SCE_1.SNX"
if snx_file.exists():
    with open(snx_file) as f:
        content = f.read()
        print(content)
else:
    print("❌ Fichier SNX manquant")

# 3. Affiche le contenu du fichier .X
print(f"\n📄 Contenu de SCE_1.X :")
print("="*70)
x_file = dssat_dir / "SCE_1.X"
if x_file.exists():
    with open(x_file) as f:
        lines = f.readlines()
        for i, line in enumerate(lines, 1):
            print(f"{i:3d}: {line.rstrip()}")
else:
    print("❌ Fichier X manquant")

print("\n" + "="*70 + "\n")