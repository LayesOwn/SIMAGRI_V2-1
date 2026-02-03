from domain.dssat.write_xfile import write_x_file
from domain.dssat.write_snx import write_snx_file
from pathlib import Path

print("\n🧪 TEST WRITE FILES")
print("="*70)

# Scénario test
scenario = {
    "dssat": {
        "sce_name": "TEST_WRITE",
        "Crop": "ML",
        "Cultivar": "IB0066",
        "PltDate": "2026-06-15",
        "plt_density": 5,
        "stn_name": "KAOLA",
        "soil": "SN-N15Rain",
        "Fert_1_DOY": 15,
        "N_1_Kg": 50,
        "P_1_Kg": 25,
        "K_1_Kg": 30,
        "Fert_2_DOY": -99,
        "N_2_Kg": -99,
        "P_2_Kg": -99,
        "K_2_Kg": -99,
        "Fert_3_DOY": -99,
        "N_3_Kg": -99,
        "P_3_Kg": -99,
        "K_3_Kg": -99,
        "IR_method": "NO",
        "IR_1_DOY": -99,
        "IR_1_amt": -99,
        "IR_2_DOY": -99,
        "IR_2_amt": -99,
        "IR_3_DOY": -99,
        "IR_3_amt": -99,
        "IR_4_DOY": -99,
        "IR_4_amt": -99,
        "IR_5_DOY": -99,
        "IR_5_amt": -99,
        "FirstYear": 2026,
        "LastYear": 2026,
        "CropPrice": 200,
        "NFertCost": 1000,
        "SeedCost": 0,
        "IrrigCost": 0,
        "OtherVariableCosts": 0,
        "FixedCosts": 5000,
    }
}

try:
    # Test write_x_file
    print("\n1️⃣ Test write_x_file...")
    x_path = write_x_file(scenario, "dssat/exp")
    
    if x_path.exists():
        print(f"   ✅ Fichier X créé : {x_path.name}")
        print(f"   📍 Chemin : {x_path}")
    else:
        print(f"   ❌ Fichier X NON créé : {x_path}")
    
    # Test write_snx_file
    print("\n2️⃣ Test write_snx_file...")
    snx_path = write_snx_file(scenario, x_path.name, "dssat/snx")
    
    if snx_path.exists():
        print(f"   ✅ Fichier SNX créé : {snx_path.name}")
        print(f"   📍 Chemin : {snx_path}")
    else:
        print(f"   ❌ Fichier SNX NON créé : {snx_path}")
    
    # Vérifier les fichiers créés
    print("\n3️⃣ Vérification...")
    exp_files = list(Path("dssat/exp").glob("*.X"))
    snx_files = list(Path("dssat/snx").glob("*.SNX"))
    
    print(f"   Fichiers .X : {len(exp_files)}")
    print(f"   Fichiers .SNX : {len(snx_files)}")
    
except Exception as e:
    print(f"   ❌ ERREUR : {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70 + "\n")