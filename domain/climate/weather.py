from pathlib import Path
import math

from domain.climate.enacts import load_enacts
from domain.geography import get_department_gps, get_department_wth_code, get_department_options


def write_weather_for_department(department, output_dir, station_code=None):
    """
    Génère un fichier météo DSSAT (.WTH) depuis data/enacts pour un département.
    """
    df = load_enacts(department).sort_values("date")
    df = df.drop_duplicates(subset=["date"]).copy()
    lat, lon = get_department_gps(department)
    code = (station_code or get_department_wth_code(department) or "DEPT")[:4].upper()

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / f"{code}.WTH"

    written = 0
    with open(filepath, "w", encoding="ascii", newline="\r\n") as f:
        f.write(f"*WEATHER DATA : {department}\n")
        f.write("@ INSI      LAT     LONG  ELEV   TAV   AMP REFHT WNDHT\n")
        f.write(f"  {code:<4}  {lat:8.3f} {lon:8.3f}    10  27.0  10.0  2.0  3.0\n")
        f.write("@DATE  SRAD  TMAX  TMIN  RAIN\n")

        for _, r in df.iterrows():
            tmax = float(r["tmax"])
            tmin = float(r["tmin"])
            rain = float(r["prcp"])
            if not (math.isfinite(tmax) and math.isfinite(tmin) and math.isfinite(rain)):
                continue
            # DSSAT weather parser is sensitive to fixed columns.
            # Keep DATE in YYDDD and write contiguous fixed-width numeric fields.
            token = r["date"].strftime("%y%j")
            srad = 18.0  # SRAD placeholder si non disponible dans ENACTS
            f.write(
                f"{token:>5}{srad:6.1f}{tmax:6.1f}{tmin:6.1f}{rain:6.1f}\n"
            )
            written += 1

    if written == 0:
        raise ValueError(f"Aucune ligne météo valide pour {department}")

    return filepath


def ensure_weather_for_scenario(scenario, dssat_dir):
    """
    Assure qu'un fichier WTH existe pour le département du scénario et met à jour la station.
    """
    department = scenario.get("location", {}).get("department")
    if not department:
        return None

    station_code = get_department_wth_code(department)
    path = write_weather_for_department(department, dssat_dir, station_code=station_code)

    scenario.setdefault("location", {})["station_code"] = station_code
    scenario.setdefault("dssat", {})["stn_name"] = station_code
    return path


def generate_all_department_wth(dssat_dir):
    """
    Génère les .WTH pour tous les départements disponibles dans l'UI.
    """
    out = []
    for opt in get_department_options():
        dept = opt.get("value")
        try:
            code = get_department_wth_code(dept)
            out.append(write_weather_for_department(dept, dssat_dir, station_code=code))
        except Exception:
            # Ignore les départements dont les données ENACTS seraient incomplètes.
            continue
    return out
