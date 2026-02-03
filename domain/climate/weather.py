from pathlib import Path
from domain.climate.enacts import load_enacts
from domain.geography import get_department_gps, get_department_code

def write_weather_from_scenario(scenario, output_dir):
    """
    Génère un fichier météo DSSAT (.WTH)
    à partir d'un scénario SIMAGRI
    """

    dept = scenario["department"]
    code = get_department_code(dept)
    lat, lon = get_department_gps(dept)

    # Charger ENACTS
    df = load_enacts(dept)

    # Filtrer période utile
    df = df[
        (df["date"].dt.year >= scenario["hist_start_year"]) &
        (df["date"].dt.year <= scenario["hist_end_year"])
    ]

    # Nom du fichier
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / f"{code}.WTH"

    # Écriture DSSAT
    with open(filepath, "w") as f:
        f.write(f"*WEATHER DATA : {dept}\n")
        f.write("@ INSI      LAT     LONG  ELEV   TAV   AMP REFHT WNDHT\n")
        f.write(
            f"{code[:4]:<4} {lat:8.2f} {lon:8.2f}   10   27.0  10.0  2.0  3.0\n"
        )
        f.write("@DATE  SRAD  TMAX  TMIN  RAIN\n")

        for _, r in df.iterrows():
            date = r["date"].strftime("%y%j")
            srad = 18.0  # provisoire (à améliorer)
            f.write(
                f"{date:>5} {srad:6.1f} {r['tmax']:6.1f} {r['tmin']:6.1f} {r['prcp']:6.1f}\n"
            )

    return filepath