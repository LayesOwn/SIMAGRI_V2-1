from pathlib import Path

from domain.climate.enacts import load_enacts
from domain.geography import get_department_gps, get_department_wth_code, get_department_options


def write_weather_for_department(department, output_dir, station_code=None):
    """
    Génère un fichier météo DSSAT (.WTH) depuis data/enacts pour un département.
    """
    df = load_enacts(department).sort_values("date")
    lat, lon = get_department_gps(department)
    code = (station_code or get_department_wth_code(department) or "DEPT")[:4].upper()

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / f"{code}.WTH"

    with open(filepath, "w", encoding="ascii", newline="\r\n") as f:
        f.write(f"*WEATHER DATA : {department}\n")
        f.write("@ INSI      LAT     LONG  ELEV   TAV   AMP REFHT WNDHT\n")
        f.write(f"  {code:<4}  {lat:8.3f} {lon:8.3f}    10  27.0  10.0  2.0  3.0\n")
        f.write("@DATE  SRAD  TMAX  TMIN  RAIN\n")

        for _, r in df.iterrows():
            token = r["date"].strftime("%y%j")
            srad = 18.0  # SRAD placeholder si non disponible dans ENACTS
            f.write(
                f"{token:>5} {srad:6.1f} {float(r['tmax']):6.1f} {float(r['tmin']):6.1f} {float(r['prcp']):6.1f}\n"
            )

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
