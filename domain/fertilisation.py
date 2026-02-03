# ==========================================================
# domain/fertilization.py
# Gestion de la fertilisation – SIMAGRI v2
# ==========================================================

FERTILIZERS = {
    "COMPOST": {
        "label": "Compost organique",
        "unit": "kg/ha",
        "default_qty": 2000,
        "price_per_kg": 15,
        # 🔑 Composition (%)
        "N": 1.0,
        "P": 0.5,
        "K": 1.0,
    },
    "NPK": {
        "label": "Engrais NPK (15-15-15)",
        "unit": "kg/ha",
        "default_qty": 150,
        "price_per_kg": 300,
        "N": 15.0,
        "P": 15.0,
        "K": 15.0,
    },
    "UREA": {
        "label": "Urée",
        "unit": "kg/ha",
        "default_qty": 100,
        "price_per_kg": 280,
        "N": 46.0,
        "P": 0.0,
        "K": 0.0,
    },
}

FERTILIZATION_BY_CROP = {
    "ML": ["NPK", "UREA"],
    "SG": ["NPK", "UREA"],
    "PN": ["COMPOST", "NPK"],
    "RI": ["UREA", "NPK"],
}


# ----------------------------------------------------------
# Fonctions existantes (inchangées)
# ----------------------------------------------------------

def get_fertilizer_options(crop):
    return [
        {"label": FERTILIZERS[t]["label"], "value": t}
        for t in FERTILIZATION_BY_CROP.get(crop, [])
    ]


def get_default_quantity(fert_type):
    fert = FERTILIZERS.get(fert_type)
    return fert["default_qty"] if fert else 0


def get_price(fert_type):
    fert = FERTILIZERS.get(fert_type)
    return fert["price_per_kg"] if fert else 0


def compute_fertilization_cost(fert_type, quantity):
    if fert_type is None or quantity is None:
        return 0
    fert = FERTILIZERS.get(fert_type)
    return quantity * fert["price_per_kg"] if fert else 0


# ----------------------------------------------------------
#    NOUVEAU : calcul des apports N-P-K
# ----------------------------------------------------------

def compute_npk_from_fertilizer(fert_type, quantity):
    """
    Retourne les quantités de N, P, K (kg/ha)
    """
    if fert_type is None or quantity is None:
        return {"N": 0, "P": 0, "K": 0}

    fert = FERTILIZERS.get(fert_type)
    if fert is None:
        return {"N": 0, "P": 0, "K": 0}

    return {
        "N": quantity * fert["N"] / 100,
        "P": quantity * fert["P"] / 100,
        "K": quantity * fert["K"] / 100,
    }