# ==========================================================
# domain/scenario.py
# Construction d’un scénario SIMAGRI → DSSAT
# ==========================================================

from domain.geography import get_department_gps, get_department_code, get_department_soil
from domain.fertilisation import compute_npk_from_fertilizer
from domain.crop import CULTIVARS


DSSAT_COLUMNS = [
    # --- Identité
    "sce_name", "Crop", "Cultivar", "stn_name",
    "PltDate", "FirstYear", "LastYear", "TargetYr",

    # --- Sol
    "soil", "iH2O", "iNO3", "plt_density",

    # --- Fertilisation
    "Fert_1_DOY", "N_1_Kg", "P_1_Kg", "K_1_Kg",
    "Fert_2_DOY", "N_2_Kg", "P_2_Kg", "K_2_Kg",
    "Fert_3_DOY", "N_3_Kg", "P_3_Kg", "K_3_Kg",
    "P_level",

    # --- Irrigation manuelle
    "IR_method",
    "IR_1_DOY", "IR_1_amt",
    "IR_2_DOY", "IR_2_amt",
    "IR_3_DOY", "IR_3_amt",
    "IR_4_DOY", "IR_4_amt",
    "IR_5_DOY", "IR_5_amt",

    # --- Auto-irrigation
    "AutoIR_depth", "AutoIR_thres", "AutoIR_eff",

    # --- Économie
    "CropPrice", "NFertCost", "SeedCost",
    "IrrigCost", "OtherVariableCosts", "FixedCosts",
]

# Scénario DSSAT vide (valeurs par défaut)
def empty_dssat_scenario():
    return {col: -99 for col in DSSAT_COLUMNS}


# Construire un scénario complet à partir de l’UI
def build_scenario_from_ui(
    scenario_id,
    department,
    crop,
    cycle,
    planting_date,
    hist_start_year,
    hist_end_year,
    recommended_sowing_date,
    recommended_sowing_prob,
    fertilization,
    fertilization_plan,
    irrigation,
    irrigation_plan,
    costs,
    socio_eco=None,
):
    """
    Construit UN scénario SIMAGRI + DSSAT complet
    """

    lat, lon = get_department_gps(department)
    station_code = get_department_code(department)
    soil_type = get_department_soil(department)

    # ==================================================
    # 🌾 SCÉNARIO SIMAGRI (LOGIQUE MÉTIER)
    # ==================================================
    scenario = {
        "id_scenario": scenario_id,
        "name": f"{crop}_{cycle}_{department}",

        "location": {
            "department": department,
            "station_code": station_code,
            "lat": lat,
            "lon": lon,
            "soil_code": "SN-N15Rain",
            "soil_type": soil_type,
        },

        "crop": {
            "code": crop,
            "cycle": cycle,
            "cultivar": CULTIVARS[crop][cycle],
            "planting_date": planting_date,
            "density": 5,
        },

        "climate": {
            "hist_start_year": hist_start_year,
            "hist_end_year": hist_end_year,
            "recommended_sowing_date": recommended_sowing_date,
            "recommended_sowing_prob": recommended_sowing_prob,
        },

        "fertilization": {
            "enabled": bool(fertilization),
            "applications": [],
            "total_N": 0.0,
            "total_P": 0.0,
            "total_K": 0.0,
            "cost_fcfa_ha": costs.get("NFertCost", 0),
        },

        "irrigation": {
            "enabled": bool(irrigation),
            "method": "MANUAL" if irrigation else "NO",
            "schedule": irrigation_plan or [],
            "cost_fcfa_ha": costs.get("IrrigCost", 0),
        },

        "socio_eco": socio_eco or {},

        "economy": {
            "CropPrice": costs.get("CropPrice", 200),
            "SeedCost": costs.get("SeedCost", 0),
            "NFertCost": costs.get("NFertCost", 0),
            "IrrigCost": costs.get("IrrigCost", 0),
            "OtherVariableCosts": costs.get("OtherVariableCosts", 0),
            "FixedCosts": costs.get("FixedCosts", 0),
        },
    }

    # ==================================================
    # 🔬 FERTILISATION (SIMAGRI)
    # ==================================================
    if fertilization and fertilization_plan:
        for i, f in enumerate(fertilization_plan):
            fert_type = f.get("type")
            qty = f.get("qty")

            npk = compute_npk_from_fertilizer(fert_type, qty)

            app = {
                "type": fert_type,
                "qty_kg_ha": qty,
                "N": npk["N"],
                "P": npk["P"],
                "K": npk["K"],
                "doy": 15 + i * 20,
            }

            scenario["fertilization"]["applications"].append(app)
            scenario["fertilization"]["total_N"] += npk["N"]
            scenario["fertilization"]["total_P"] += npk["P"]
            scenario["fertilization"]["total_K"] += npk["K"]

    # ==================================================
    # 🧬 SCÉNARIO DSSAT (100 % COMPATIBLE)
    # ==================================================
    dssat = empty_dssat_scenario()

    # --- Identité
    dssat["sce_name"] = scenario_id
    dssat["Crop"] = crop
    dssat["Cultivar"] = CULTIVARS[crop][cycle]
    dssat["stn_name"] = station_code
    dssat["PltDate"] = planting_date
    dssat["FirstYear"] = hist_start_year
    dssat["LastYear"] = hist_end_year
    dssat["TargetYr"] = hist_end_year

    # --- Sol
    dssat["soil"] = "SN-N15Rain"
    dssat["iH2O"] = 0.5
    dssat["iNO3"] = 20
    dssat["plt_density"] = 5

    # --- Fertilisation DSSAT
    for i, app in enumerate(scenario["fertilization"]["applications"][:3], start=1):
        dssat[f"Fert_{i}_DOY"] = app["doy"]
        dssat[f"N_{i}_Kg"] = app["N"]
        dssat[f"P_{i}_Kg"] = app["P"]
        dssat[f"K_{i}_Kg"] = app["K"]

    dssat["P_level"] = "M" if scenario["fertilization"]["applications"] else -99
    dssat["NFertCost"] = scenario["economy"]["NFertCost"]

    # --- Irrigation DSSAT
    if scenario["irrigation"]["enabled"]:
        dssat["IR_method"] = "MANUAL"
        for i, ir in enumerate(scenario["irrigation"]["schedule"][:5], start=1):
            dssat[f"IR_{i}_DOY"] = ir["doy"]
            dssat[f"IR_{i}_amt"] = ir["mm"]
    else:
        dssat["IR_method"] = "NO"

    dssat["IrrigCost"] = scenario["economy"]["IrrigCost"]

    # --- Économie
    dssat["CropPrice"] = scenario["economy"]["CropPrice"]
    dssat["SeedCost"] = scenario["economy"]["SeedCost"]
    dssat["OtherVariableCosts"] = scenario["economy"]["OtherVariableCosts"]
    dssat["FixedCosts"] = scenario["economy"]["FixedCosts"]

    # 👉 Lien final
    scenario["dssat"] = dssat

    return scenario
