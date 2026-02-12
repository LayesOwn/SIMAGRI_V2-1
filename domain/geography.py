# ==========================================================
# domain/geography.py
# Départements du Sénégal – Coordonnées GPS officielles
# ==========================================================
import unicodedata

DEPARTMENTS = {
    "Louga":        {"lat": 15.62, "lon": -16.22, "soil": "S"},
    "Ranérou":      {"lat": 15.30, "lon": -13.97, "soil": "S"},
    "Bambey":       {"lat": 14.70, "lon": -16.47, "soil": "LS"},
    "Thiès":        {"lat": 14.80, "lon": -16.95, "soil": "S"},
    "Bakel":        {"lat": 14.90, "lon": -12.47, "soil": "S"},
    "Kaolack":      {"lat": 14.15, "lon": -16.07, "soil": "SL"},
    "Diourbel":     {"lat": 14.65, "lon": -16.23, "soil": "LS"},
    "Fatick":       {"lat": 14.34, "lon": -16.41, "soil": "SL"},
    "Mbacké":       {"lat": 14.80, "lon": -15.91, "soil": "LS"},
    "Kébémer":      {"lat": 15.37, "lon": -16.47, "soil": "S"},
    "Linguère":     {"lat": 15.39, "lon": -15.12, "soil": "S"},
    "Saint-Louis":  {"lat": 16.05, "lon": -16.46, "soil": "LS"},
    "Dagana":       {"lat": 16.51, "lon": -15.51, "soil": "LS"},
    "Podor":        {"lat": 16.65, "lon": -14.96, "soil": "LS"},
    "Matam":        {"lat": 15.66, "lon": -13.26, "soil": "S"},
    "Kanel":        {"lat": 15.50, "lon": -13.15, "soil": "S"},
    "Tambacounda":  {"lat": 13.77, "lon": -13.67, "soil": "S"},
    "Goudiry":      {"lat": 14.20, "lon": -12.72, "soil": "S"},
    "Koumpentoum":  {"lat": 14.15, "lon": -14.00, "soil": "S"},
    "Kédougou":     {"lat": 12.56, "lon": -12.18, "soil": "SL"},
    "Salémata":     {"lat": 12.82, "lon": -12.70, "soil": "SL"},
    "Saraya":       {"lat": 12.75, "lon": -11.85, "soil": "SL"},
    "Kolda":        {"lat": 12.89, "lon": -14.95, "soil": "SL"},
    "Vélingara":    {"lat": 12.88, "lon": -14.00, "soil": "SL"},
    "Médina Yoro Foulah": {"lat": 13.03, "lon": -14.35, "soil": "SL"},
    "Sédhiou":      {"lat": 12.71, "lon": -15.56, "soil": "SL"},
    "Bounkiling":   {"lat": 12.80, "lon": -15.70, "soil": "SL"},
    "Goudomp":      {"lat": 12.58, "lon": -15.97, "soil": "SL"},
    "Ziguinchor":   {"lat": 12.56, "lon": -16.27, "soil": "SL"},
    "Bignona":      {"lat": 12.81, "lon": -16.23, "soil": "SL"},
    "Oussouye":     {"lat": 12.48, "lon": -16.55, "soil": "SL"},
}

# Codes de sol DSSAT par type de sol
SOIL_CODES_BY_TYPE = {
    "S": "SN-N15Rain",
    "SL": "SN00840080",
    "LS": "SN-S15Rain",
}

# Mapping explicite par département (ajuster si nécessaire)
DEPARTMENT_SOIL_CODES = {
    "Louga": "SN-N15Rain",
    "RanÃ©rou": "SN-N15Rain",
    "Bambey": "SN-S15Rain",
    "ThiÃ¨s": "SN-N15Rain",
    "Bakel": "SN-N15Rain",
    "Kaolack": "SN00840080",
    "Diourbel": "SN-S15Rain",
    "Fatick": "SN00840080",
    "MbackÃ©": "SN-S15Rain",
    "KÃ©bÃ©mer": "SN-N15Rain",
    "LinguÃ¨re": "SN-N15Rain",
    "Saint-Louis": "SN-S15Rain",
    "Dagana": "SN-S15Rain",
    "Podor": "SN-S15Rain",
    "Matam": "SN-N15Rain",
    "Kanel": "SN-N15Rain",
    "Tambacounda": "SN-N15Rain",
    "Goudiry": "SN-N15Rain",
    "Koumpentoum": "SN-N15Rain",
    "KÃ©dougou": "SN00840080",
    "SalÃ©mata": "SN00840080",
    "Saraya": "SN00840080",
    "Kolda": "SN00840080",
    "VÃ©lingara": "SN00840080",
    "MÃ©dina Yoro Foulah": "SN00840080",
    "SÃ©dhiou": "SN00840080",
    "Bounkiling": "SN00840080",
    "Goudomp": "SN00840080",
    "Ziguinchor": "SN00840080",
    "Bignona": "SN00840080",
    "Oussouye": "SN00840080",
}
# ==========================================================
# Codes stations DSSAT (WTH)
# ==========================================================
WTH_STATIONS = {
    "Bambey": "BAMBY",
    "Kaolack": "KAOLA",
    "Louga": "LOUGA",
    "Thiès": "THIES",
    "Dakar": "DAKAR",
}

# ==========================================================
# Fonctions utilitaires
# ==========================================================

def get_department_options():
    return [{"label": k, "value": k} for k in DEPARTMENTS.keys()]


def get_department_gps(dept_name):
    """Retourne latitude, longitude"""
    d = DEPARTMENTS.get(dept_name)
    if d is None:
        return None, None
    return d["lat"], d["lon"]


def get_department_soil(dept_name):
    """Retourne le type de sol dominant"""
    d = DEPARTMENTS.get(dept_name)
    return d["soil"] if d else None


def get_department_soil_code(dept_name):
    """
    Retourne le code sol DSSAT en fonction du type de sol du d??partement.
    """
    if dept_name in DEPARTMENT_SOIL_CODES:
        return DEPARTMENT_SOIL_CODES[dept_name]
    soil_type = get_department_soil(dept_name)
    return SOIL_CODES_BY_TYPE.get(soil_type, "SN-N15Rain")


def get_department_code(dept_name):
    """
    Génère un code département compatible ENACTS / DSSAT
    ex:
      'Kaolack' -> 'KAOLACK'
      'Médina Yoro Foulah' -> 'MEDINA_YORO_FOULAH'
      'Saint-Louis' -> 'SAINT_LOUIS'
    """

    if dept_name is None:
        return None

    # Supprimer les accents
    name = unicodedata.normalize("NFD", dept_name)
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")

    # Normaliser
    code = (
        name.upper()
        .replace("-", "_")
        .replace(" ", "_")
    )

    return code


def get_department_wth_code(dept_name):
    """
    Retourne le code station DSSAT (WTH) si disponible,
    sinon None.
    """
    return WTH_STATIONS.get(dept_name)
