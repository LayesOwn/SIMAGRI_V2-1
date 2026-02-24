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
        "court": "IB0001",
        "intermediaire": "IB0002",
        "long": "IM0015",
    },
    "SG": {  # Sorgho (SGCER047.CUL)
        "court": "IB0066",
        "intermediaire": "IB0070",
        "long": "IB0069",
    },
    "PN": {  # Arachide (PNGRO047.CUL)
        "court": "990001",
        "intermediaire": "IB0091",
        "long": "IB0091",
    },
    "RI": {  # Riz (RICER047.CUL)
        "court": "NERI81",
        "intermediaire": "NERI81",
        "long": "NERI14",
    },
}
