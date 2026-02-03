# ==========================================================
# domain/crop.py
# Cultures et cultivars DSSAT
# ==========================================================

def get_crop_options():
    return [
        {"label": "Mil", "value": "ML"},
        {"label": "Sorgho", "value": "SG"},
        {"label": "Arachide", "value": "PN"},
        {"label": "Riz", "value": "RI"},
    ]


# 🔑 Cultivars DSSAT par culture et cycle
CULTIVARS = {
    "ML": {  # Mil
        "court": "IB0066",
        "intermediaire": "IB0069",
        "long": "IB0070",
    },
    "SG": {  # Sorgho
        "court": "SG001",
        "intermediaire": "SG002",
        "long": "SG003",
    },
    "PN": {  # Arachide
        "court": "PN001",
        "intermediaire": "PN002",
        "long": "PN003",
    },
    "RI": {  # Riz
        "court": "RI001",
        "intermediaire": "RI002",
        "long": "RI003",
    },
}
