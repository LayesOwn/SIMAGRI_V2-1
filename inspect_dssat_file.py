#!/usr/bin/env python3
"""
Script pour inspecter les fichiers DSSAT générés
"""

from pathlib import Path

print("\n" + "="*70)
print("🔍 INSPECTION DES FICHIERS DSSAT GÉNÉRÉS")
print("="*70 + "\n")

# Chercher les fichiers .X et .SNX
dssat_dir = Path("dssat")
if not dssat_dir.exists():
    print(f"❌ Dossier {dssat_dir} n'existe pas")
    exit(1)

# Fichiers .X
exp_dir = dssat_dir / "exp"
snx_dir = dssat_dir / "snx"

print(f"📂 Dossier exp/ : {exp_dir.exists()}")
if exp_dir.exists():
    x_files = list(exp_dir.glob("*.X"))
    print(f"   Fichiers .X : {len(x_files)}")
    for f in x_files:
        print(f"\n   📄 {f.name} ({f.stat().st_size} bytes)")
        print("   " + "-"*66)
        with open(f, 'r') as file:
            lines = file.readlines()
            for i, line in enumerate(lines[:30], 1):  # Premiers 30 lignes
                print(f"   {i:3d}: {line.rstrip()}")
        if len(lines) > 30:
            print(f"   ... ({len(lines) - 30} lignes de plus)")
        print("   " + "-"*66)

print(f"\n📂 Dossier snx/ : {snx_dir.exists()}")
if snx_dir.exists():
    snx_files = list(snx_dir.glob("*.SNX"))
    print(f"   Fichiers .SNX : {len(snx_files)}")
    for f in snx_files:
        print(f"\n   📄 {f.name} ({f.stat().st_size} bytes)")
        print("   " + "-"*66)
        with open(f, 'r') as file:
            lines = file.readlines()
            for i, line in enumerate(lines[:40], 1):  # Premiers 40 lignes
                print(f"   {i:3d}: {line.rstrip()}")
        if len(lines) > 40:
            print(f"   ... ({len(lines) - 40} lignes de plus)")
        print("   " + "-"*66)

print("\n" + "="*70)
print("✅ Inspection terminée")
print("="*70 + "\n")