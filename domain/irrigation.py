# ==========================================================
# domain/irrigation.py
# Gestion agronomique de l'irrigation
# ==========================================================

# Jours après semis (JAS) et doses recommandées (mm)
IRRIGATION_RULES = {
    "ML": {  # Mil
        "days": [20, 35, 50],
        "water_mm": 30,
    },
    "SG": {  # Sorgho
        "days": [25, 45, 65],
        "water_mm": 35,
    },
    "PN": {  # Arachide
        "days": [20, 40, 60],
        "water_mm": 30,
    },
    "RI": {  # Riz
        "days": [15, 30, 45, 60],
        "water_mm": 50,
    },
}

# Prix par mm d'eau (FCFA)
DEFAULT_IRRIGATION_PRICE = 250


def get_irrigation_schedule(crop):
    """
    Retourne les jours d'irrigation et la dose recommandée
    """
    rule = IRRIGATION_RULES.get(crop)
    if rule is None:
        return [], 0

    return rule["days"], rule["water_mm"]


def compute_irrigation_cost(days, water_mm, price_per_mm):
    """
    Coût total de l'irrigation (FCFA/ha)
    """
    if not days or water_mm <= 0 or price_per_mm <= 0:
        return 0

    return len(days) * water_mm * price_per_mm

def normalize_irrigation_plan(irrig_days, water_mm):
    """
    Transforme :
      "20,35,50" + 30
    en :
      [{"doy":20,"mm":30}, ...]
    """

    if not irrig_days:
        return []

    if water_mm is None:
        water_mm = 30  # valeur par défaut sécurisée

    # accepter string ou liste
    if isinstance(irrig_days, str):
        days = [
            int(d.strip())
            for d in irrig_days.split(",")
            if d.strip().isdigit()
        ]
    elif isinstance(irrig_days, list):
        days = irrig_days
    else:
        return []

    return [{"doy": d, "mm": water_mm} for d in days]
