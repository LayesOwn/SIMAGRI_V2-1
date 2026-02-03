from pathlib import Path

from pathlib import Path

# Chercher le dernier SNX généré
snx_file = list(Path("dssat").glob("SCE_*.SNX"))
if snx_file:
    snx_file = snx_file[0]
    
    print(f"\n📄 {snx_file.name}\n")
    print("="*80)
    
    with open(snx_file, 'r') as f:
        lines = f.readlines()
    
    # Afficher TOUTES les lignes
    for i, line in enumerate(lines, 1):
        display = line.rstrip('\n')
        print(f"{i:3d} {display}")
    
    print("="*80)
    print(f"\nTotal : {len(lines)} lignes")