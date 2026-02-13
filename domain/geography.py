# ==========================================================
# domain/geography.py
# Departements du Senegal - Coordonnees GPS et mapping sol DSSAT
# ==========================================================
import unicodedata
from pathlib import Path

DEPARTMENTS = {
    "Louga": {"lat": 15.62, "lon": -16.22},
    "Ranerou": {"lat": 15.30, "lon": -13.97},
    "Bambey": {"lat": 14.70, "lon": -16.47},
    "Thies": {"lat": 14.80, "lon": -16.95},
    "Bakel": {"lat": 14.90, "lon": -12.47},
    "Kaolack": {"lat": 14.15, "lon": -16.07},
    "Diourbel": {"lat": 14.65, "lon": -16.23},
    "Fatick": {"lat": 14.34, "lon": -16.41},
    "Mbacke": {"lat": 14.80, "lon": -15.91},
    "Kebemer": {"lat": 15.37, "lon": -16.47},
    "Linguere": {"lat": 15.39, "lon": -15.12},
    "Saint-Louis": {"lat": 16.05, "lon": -16.46},
    "Dagana": {"lat": 16.51, "lon": -15.51},
    "Podor": {"lat": 16.65, "lon": -14.96},
    "Matam": {"lat": 15.66, "lon": -13.26},
    "Kanel": {"lat": 15.50, "lon": -13.15},
    "Tambacounda": {"lat": 13.77, "lon": -13.67},
    "Goudiry": {"lat": 14.20, "lon": -12.72},
    "Koumpentoum": {"lat": 14.15, "lon": -14.00},
    "Kedougou": {"lat": 12.56, "lon": -12.18},
    "Salemata": {"lat": 12.82, "lon": -12.70},
    "Saraya": {"lat": 12.75, "lon": -11.85},
    "Kolda": {"lat": 12.89, "lon": -14.95},
    "Velingara": {"lat": 12.88, "lon": -14.00},
    "Medina Yoro Foulah": {"lat": 13.03, "lon": -14.35},
    "Sedhiou": {"lat": 12.71, "lon": -15.56},
    "Bounkiling": {"lat": 12.80, "lon": -15.70},
    "Goudomp": {"lat": 12.58, "lon": -15.97},
    "Ziguinchor": {"lat": 12.56, "lon": -16.27},
    "Bignona": {"lat": 12.81, "lon": -16.23},
    "Oussouye": {"lat": 12.48, "lon": -16.55},
}

# Mapping explicite departement -> code de sol DSSAT
# Source: tableau utilisateur (premier code retenu quand plusieurs existent)
DEPARTMENT_SOIL_CODES = {
    "Bakel": "CECE000016",
    "Bambey": "CNBambey15",
    "Bignona": "CR05002013",
    "Bounkiling": "CR08002014",
    "Dagana": "CECE000004",
    "Diourbel": "BYBAMBEY14",
    "Fatick": "CE00000004",
    "Foundiougne": "CE00000004",
    "Gossas": "BYBAMBEY14",
    "Goudiry": "CECE000016",
    "Goudomp": "CR08002014",
    "Guinguineo": "CECE000003",
    "Kaffrine": "CECE000019",
    "Kanel": "CECE000012",
    "Kaolack": "CR06002014",
    "Kebemer": "CECE000011",
    "Kolda": "CR05002014",
    "Koumpentoum": "CECE000018",
    "Koungheul": "CECE000002",
    "Linguere": "CECE000013",
    "Louga": "CECE000013",
    "Malem-Hodar": "CECE000002",
    "Mbacke": "CECE000013",
    "Medina Yoro Foulah": "CE00000003",
    "Nioro du Rip": "NRNIOROSOL",
    "Oussouye": "CR06002014",
    "Ranerou": "CECE000013",
    "Sedhiou": "CR09002014",
    "Tambacounda": "CECE000017",
    "Thies": "BYBAMBEY14",
    "Tivaouane": "CECE000015",
    "Velingara": "CR02002012",
    "Ziguinchor": "CR07002014",
}

DEFAULT_SOIL_CODE = "IB00000010"

# Codes stations DSSAT (WTH)
WTH_STATIONS = {
    "Bambey": "BAMBY",
    "Kaolack": "KAOLA",
    "Louga": "LOUGA",
    "Thies": "THIES",
    "Dakar": "DAKAR",
}

# Couverture WTH pour les 46 départements (fallback vers stations disponibles)
DEPARTMENT_WTH_CODES = {
    "Birkelane": "KAOLA",
    "Foundiougne": "KAOLA",
    "Gossas": "KAOLA",
    "Guediawaye": "DAKAR",
    "Guinguineo": "KAOLA",
    "Kaffrine": "KAOLA",
    "Keur Massar": "DAKAR",
    "Mbour": "THIES",
    "Nioro du Rip": "KAOLA",
    "Pikine": "DAKAR",
    "Rufisque": "DAKAR",
    "Saint Louis": "DAKAR",
    "Saint-Louis": "DAKAR",
    "Tivaouane": "THIES",
}


def _build_department_wth_map():
    """
    Construit un code station WTH unique (4 caractères) pour chaque département.
    """
    names = sorted(set(DEPARTMENTS.keys()) | set(_load_enacts_departments()))
    used = set()
    out = {}

    for name in names:
        raw = get_department_code(name) or "DEPT"
        base = "".join(c for c in raw if c.isalnum())
        if len(base) < 4:
            base = (base + "XXXX")[:4]

        cand = base[:4]
        if cand in used:
            # tente base[:3] + caractère suivant
            found = None
            for i in range(3, len(base)):
                c2 = base[:3] + base[i]
                if c2 not in used:
                    found = c2
                    break
            if not found:
                # fallback numérique
                for i in range(10):
                    c3 = base[:3] + str(i)
                    if c3 not in used:
                        found = c3
                        break
            cand = found or cand

        used.add(cand)
        out[name] = cand
    return out


ENACTS_NAME_OVERRIDES = {
    "BIERKELANE": "Birkelane",
    "GUEDIAWAYE": "Guediawaye",
    "KEUR_MASSAR": "Keur Massar",
    "MALEM_HODAR": "Malem-Hodar",
    "MEDINA_YOROFOULA": "Medina Yoro Foulah",
    "NIORO_DU_RIP": "Nioro du Rip",
    "SAINT_LOUIS": "Saint-Louis",
    "TIVAOUNE": "Tivaouane",
}


def _load_enacts_departments():
    """
    Lit la liste des départements disponibles dans data/enacts/*.csv.
    """
    data_dir = Path(__file__).resolve().parents[1] / "data" / "enacts"
    names = []
    if not data_dir.exists():
        return names
    for f in data_dir.glob("*.csv"):
        stem = f.stem.upper()
        if stem in ENACTS_NAME_OVERRIDES:
            names.append(ENACTS_NAME_OVERRIDES[stem])
        else:
            names.append(stem.replace("_", " ").title())
    return sorted(set(names))


def _normalize_name(name):
    if not name:
        return ""
    n = unicodedata.normalize("NFD", str(name))
    n = "".join(c for c in n if unicodedata.category(c) != "Mn")
    return n.strip()


def _match_key(name, mapping):
    if name in mapping:
        return name
    normalized = _normalize_name(name).lower()
    for key in mapping.keys():
        if _normalize_name(key).lower() == normalized:
            return key
    return None


def get_department_options():
    # Union des départements géographiques + fichiers ENACTS disponibles.
    names = set(DEPARTMENTS.keys()) | set(_load_enacts_departments())
    ordered = sorted(names)
    return [{"label": k, "value": k} for k in ordered]


def get_department_gps(dept_name):
    """Retourne latitude, longitude"""
    key = _match_key(dept_name, DEPARTMENTS)
    if key is None:
        # Centre par défaut Sénégal pour éviter de casser la carte.
        return 14.15, -16.07
    d = DEPARTMENTS[key]
    return d["lat"], d["lon"]


def get_department_soil(dept_name):
    """Retourne le code de sol DSSAT du departement"""
    key = _match_key(dept_name, DEPARTMENT_SOIL_CODES)
    if key is None:
        return DEFAULT_SOIL_CODE
    return DEPARTMENT_SOIL_CODES[key]


def get_department_soil_code(dept_name):
    """Retourne le code de sol DSSAT pour le departement."""
    return get_department_soil(dept_name)


def get_soil_code_options():
    """Options de codes de sol DSSAT pour affichage UI."""
    codes = sorted(set(DEPARTMENT_SOIL_CODES.values()) | {DEFAULT_SOIL_CODE})
    return [{"label": code, "value": code} for code in codes]


def get_department_code(dept_name):
    """
    Genere un code departement compatible ENACTS / DSSAT
    ex: 'Kaolack' -> 'KAOLACK'
    """
    if dept_name is None:
        return None

    name = _normalize_name(dept_name)
    code = (
        name.upper()
        .replace("-", "_")
        .replace(" ", "_")
    )
    return code


def get_department_wth_code(dept_name):
    """Retourne le code station DSSAT (WTH) si disponible."""
    key = _match_key(dept_name, DEPARTMENT_WTH_MAP)
    if key is not None:
        return DEPARTMENT_WTH_MAP[key]
    return "DEPT"


DEPARTMENT_WTH_MAP = _build_department_wth_map()
