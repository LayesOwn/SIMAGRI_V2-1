# ==========================================================
# domain/sol.py
# Sol de référence par département (SIMAGRI v2)
# ==========================================================

DEPARTMENT_SOIL = {
    # CODE  : soil_code
    "3292": "SL",  # Kaolack → Sandy loam
    "0032": "LS",  # Bambey → Loamy sand
    "3167": "S",   # Thiès → Sandy
    "4871": "LS",  # Mbacké
    "1669": "SL",  # Fatick
    "2014": "SL",  # Foundiougne
    "2843": "S",   # Birkelane
    "2454": "S",   # Koungheul
    "3292": "SL",  # Kaolack
    "5699": "S",   # Nioro du Rip
    # 👉 à compléter jusqu’aux 46 départements
}

SOIL_LABELS = {
    "S": "Sandy (Sableux)",
    "SL": "Sandy loam (Sablo-limoneux)",
    "LS": "Loamy sand (Limon sableux)",
}


def get_soil_by_department(dept_code):
    """
    Retourne le code du sol de référence pour un département
    """
    return DEPARTMENT_SOIL.get(dept_code, "S")


def get_soil_label(soil_code):
    """
    Libellé lisible du sol
    """
    return SOIL_LABELS.get(soil_code, soil_code)
