# domain/dssat/write_weather.py

from pathlib import Path


def write_weather_file(station_code, station_name, lat, lon, output_dir):
    """
    Crée un fichier météo DSSAT .WTH minimal
    
    Args:
        station_code: Code station (ex: 'KAOLA')
        station_name: Nom station (ex: 'KAOLACK')
        lat: Latitude
        lon: Longitude
        output_dir: Dossier de sortie
    
    Returns:
        Path: Chemin du fichier créé
    """
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    filename = f"{station_code}.WTH"
    filepath = output_dir / filename
    
    with open(filepath, "w", encoding="utf-8") as f:
        # En-tête DSSAT
        f.write(f"*WEATHER DATA : {station_name}\n")
        f.write("@ INSI      LAT     LONG  ELEV   TAV   AMP REFHT WNDHT\n")
        f.write(
            f"{station_code:<4} {lat:8.2f} {lon:8.2f}   10   27.0  10.0  2.0  3.0\n"
        )
        
        # En-tête colonnes
        f.write("@DATE  SRAD  TMAX  TMIN  RAIN\n")
        
        # Données météo test (année 2026, 365 jours)
        # Format: YYYDDD SRAD TMAX TMIN RAIN
        for doy in range(1, 366):
            year = 2026
            srad = 18.0  # Radiation solaire (MJ/m2/day)
            tmax = 32.0  # Température max (°C)
            tmin = 22.0  # Température min (°C)
            rain = 2.0   # Pluie (mm)
            
            # Ajuster la pluie pour la saison des pluies (juin-octobre)
            if 152 <= doy <= 304:  # Environ juin à octobre
                rain = 5.0
            else:
                rain = 0.5
            
            date_str = f"{year}{doy:03d}"
            f.write(
                f"{date_str:>5} {srad:6.1f} {tmax:6.1f} {tmin:6.1f} {rain:6.1f}\n"
            )
    
    return filepath


def create_default_weather(output_dir):
    """
    Crée des fichiers météo par défaut pour les stations principales
    """
    
    stations = {
        "KAOLA": ("KAOLACK", 14.15, -16.07),
        "DAKAR": ("DAKAR", 14.67, -17.50),
        "LOUGA": ("LOUGA", 15.62, -16.22),
        "BAMBY": ("BAMBEY", 14.70, -16.47),
        "THIES": ("THIÈS", 14.80, -16.95),
    }
    
    created = []
    for code, (name, lat, lon) in stations.items():
        path = write_weather_file(code, name, lat, lon, output_dir)
        created.append(path)
        print(f"✅ Créé : {path.name}")
    
    return created