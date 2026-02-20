from datetime import timedelta
from pathlib import Path
import pandas as pd

import unicodedata
from domain.geography import (
    get_department_code,
    get_department_gps,
    get_department_wth_code,
    WTH_STATIONS,
)


FORECAST_DIR = Path(__file__).resolve().parents[2] / "data" / "Donnees_meteo"
LEGACY_FORECAST_DIR = Path(__file__).resolve().parents[2] / "data" / "Donnees_Meteo"
FORECAST_REQUIRED_COLS = ["date", "rain", "tmax", "tmin"]


def forecast_file_for_department(department):
    code = get_department_code(department)
    if not code:
        return None
    preferred = FORECAST_DIR / f"{code}.csv"
    if preferred.exists():
        return preferred
    legacy = LEGACY_FORECAST_DIR / f"{code}.csv"
    if legacy.exists():
        return legacy
    # Support manual naming such as Kaolack.csv (case-insensitive lookup).
    if FORECAST_DIR.exists():
        for p in FORECAST_DIR.glob("*.csv"):
            if p.stem.upper() == code.upper():
                return p
    if LEGACY_FORECAST_DIR.exists():
        for p in LEGACY_FORECAST_DIR.glob("*.csv"):
            if p.stem.upper() == code.upper():
                return p
    return preferred


def load_forecast_dataframe(department):
    path = forecast_file_for_department(department)
    if path is None or not path.exists():
        raise FileNotFoundError(f"Fichier forecast introuvable pour '{department}'")
    df = pd.read_csv(path)
    for c in FORECAST_REQUIRED_COLS:
        if c not in df.columns:
            raise ValueError(f"Colonne manquante dans {path.name}: {c}")
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["rain"] = pd.to_numeric(out["rain"], errors="coerce")
    out["tmax"] = pd.to_numeric(out["tmax"], errors="coerce")
    out["tmin"] = pd.to_numeric(out["tmin"], errors="coerce")
    out = out.dropna(subset=FORECAST_REQUIRED_COLS).sort_values("date")
    out = out.drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
    return out


def validate_forecast_window(df, start_date, end_date):
    errors = []
    warnings = []
    info = []

    if df is None or df.empty:
        return {"errors": ["Forecast vide"], "warnings": warnings, "info": info}

    start = pd.to_datetime(start_date, errors="coerce")
    end = pd.to_datetime(end_date, errors="coerce")
    if pd.isna(start) or pd.isna(end) or start > end:
        return {"errors": ["Fenetre forecast invalide"], "warnings": warnings, "info": info}

    win = df[(df["date"] >= start) & (df["date"] <= end)].copy()
    if win.empty:
        return {"errors": ["Aucune donnee forecast dans la fenetre requise"], "warnings": warnings, "info": info}

    expected_days = (end.normalize() - start.normalize()).days + 1
    covered_days = win["date"].dt.normalize().nunique()
    if covered_days < expected_days:
        errors.append(f"Forecast incomplet: {covered_days}/{expected_days} jours couverts")

    if (win["rain"] < 0).any():
        errors.append("Pluie negative detectee")
    if (win["tmax"] < win["tmin"]).any():
        errors.append("Lignes avec tmax < tmin")
    if (win["tmax"] == win["tmin"]).any():
        warnings.append("Lignes avec tmax == tmin detectees")

    info.append(
        f"Fenetre forecast validee: {start.date()} -> {end.date()} ({covered_days} jours)"
    )
    return {"errors": errors, "warnings": warnings, "info": info}


def write_forecast_wth_for_scenario(scenario, dssat_dir, cycle_days=210):
    """
    Genere le fichier WTH forecast pour un scenario previsionnel.
    Regles:
    - fenetre meteo obligatoire: J-1 a J+cycle_days
    - format date WTH: YYDDD (5 colonnes)
    """
    department = scenario.get("location", {}).get("department")
    if not department:
        raise ValueError("Departement manquant")

    pdate = pd.to_datetime(
        scenario.get("crop", {}).get("planting_date") or scenario.get("dssat", {}).get("PltDate"),
        errors="coerce",
    )
    if pd.isna(pdate):
        raise ValueError("Date de semis forecast invalide")

    start = (pdate - timedelta(days=1)).date()
    end = (pdate + timedelta(days=cycle_days)).date()
    df = load_forecast_dataframe(department)
    val = validate_forecast_window(df, start, end)
    if val["errors"]:
        raise ValueError(" | ".join(val["errors"]))

    win = df[(df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))].copy()
    win = win.sort_values("date")

    # Keep full DSSAT station code (often 5 chars, e.g. KAOLA) to match historical WTH format.
    def _norm(val):
        if not val:
            return ""
        n = unicodedata.normalize("NFD", str(val))
        n = "".join(c for c in n if unicodedata.category(c) != "Mn")
        return n.strip().lower().replace("-", " ")

    station = None
    dkey = _norm(department)
    for name, code in WTH_STATIONS.items():
        if _norm(name) == dkey:
            station = code
            break
    station = (station or get_department_wth_code(department) or "DEPT").upper()
    # DSSAT WTH header in this stack uses 4-char station codes (YYDDD format).
    station = station[:4]
    lat, lon = get_department_gps(department)
    dssat_dir = Path(dssat_dir)
    dssat_dir.mkdir(parents=True, exist_ok=True)
    wth_path = dssat_dir / f"{station}.WTH"

    with open(wth_path, "w", encoding="ascii", newline="\r\n") as f:
        f.write(f"*WEATHER DATA : {department}\n")
        f.write("@ INSI      LAT     LONG  ELEV   TAV   AMP REFHT WNDHT\n")
        # Match historical writer spacing used in domain/climate/weather.py.
        f.write(f"  {station:<4}  {lat:8.3f} {lon:8.3f}    10  27.0  10.0  2.0  3.0\n")
        f.write("@DATE  SRAD  TMAX  TMIN  RAIN\n")
        for _, r in win.iterrows():
            # Use 5-digit YYDDD (consistent with historical writer).
            token = r["date"].strftime("%y%j")
            rain = float(r["rain"])
            tmax = float(r["tmax"])
            tmin = float(r["tmin"])
            if tmax == tmin:
                tmax += 0.1
            f.write(f"{token:>5} {18.0:6.1f} {tmax:6.1f} {tmin:6.1f} {rain:6.1f}\n")

    scenario.setdefault("location", {})["station_code"] = station
    scenario.setdefault("dssat", {})["stn_name"] = station
    return wth_path
