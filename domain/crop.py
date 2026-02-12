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
    "ML": {  # Mil (MLCER047.CUL)
        "court": "IB0044",
        "intermediaire": "IB0044",
        "long": "IB0044",
    },
    "SG": {  # Sorgho (SGCER047.CUL)
        "court": "990001",
        "intermediaire": "990001",
        "long": "990001",
    },
    "PN": {  # Arachide (PNGRO047.CUL)
        "court": "990001",
        "intermediaire": "990001",
        "long": "990001",
    },
    "RI": {  # Riz (RICER047.CUL)
        "court": "990001",
        "intermediaire": "990001",
        "long": "990001",
    },
}
