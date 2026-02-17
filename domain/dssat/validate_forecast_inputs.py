from datetime import datetime, timedelta
from pathlib import Path

from domain.climate.forecast import (
    load_forecast_dataframe,
    validate_forecast_window,
)
from domain.dssat.validate_inputs import (
    CROP_CUL_FILES,
    _cultivar_exists,
    _find_wth_file,
    _parse_planting_date,
    _parse_wth_dates,
    _soil_exists,
    resolve_cultivar,
)


FORECAST_CYCLE_DAYS = 210


def validate_forecast_inputs(scenario, base_dir, cycle_days=FORECAST_CYCLE_DAYS):
    """
    Validation dediee a la prevision.
    - verifie le forecast CSV (schema + couverture J-1 a J+cycle)
    - verifie le WTH genere pour DSSAT
    - verifie sol + cultivar
    """
    errors = []
    warnings = []
    info = []

    base_dir = Path(base_dir)
    dssat_dir = base_dir / "dssat"

    department = scenario.get("location", {}).get("department")
    if not department:
        errors.append("Departement manquant pour la prevision")
        return {"errors": errors, "warnings": warnings, "info": info}

    pdate = _parse_planting_date(
        scenario.get("crop", {}).get("planting_date")
        or scenario.get("dssat", {}).get("PltDate")
    )
    if not pdate:
        errors.append("Date de semis prevision invalide")
        return {"errors": errors, "warnings": warnings, "info": info}

    if pdate.year < datetime.now().year:
        errors.append(
            f"Date de semis prevision ({pdate}) anterieure a l'annee en cours ({datetime.now().year})"
        )

    # 1) Forecast CSV coverage
    try:
        df = load_forecast_dataframe(department)
        start = pdate - timedelta(days=1)
        end = pdate + timedelta(days=cycle_days)
        v = validate_forecast_window(df, start, end)
        errors.extend(v.get("errors", []))
        warnings.extend(v.get("warnings", []))
        info.extend(v.get("info", []))
    except Exception as e:
        errors.append(f"Forecast invalide: {e}")

    # 2) WTH genere
    station = scenario.get("location", {}).get("station_code")
    if not station:
        errors.append("Station DSSAT forecast manquante")
    else:
        wth_path = _find_wth_file(dssat_dir, station)
        if not wth_path:
            errors.append(f"WTH forecast introuvable pour station '{station}'")
        else:
            dates, header = _parse_wth_dates(wth_path)
            if not dates:
                errors.append(f"WTH '{wth_path.name}' sans lignes meteo valides")
            else:
                dmin = min(dates)
                dmax = max(dates)
                if pdate < dmin or pdate > dmax:
                    errors.append(f"WTH '{wth_path.name}' ne couvre pas la date de semis ({pdate})")
                if pdate - timedelta(days=1) < dmin:
                    errors.append(f"WTH '{wth_path.name}' ne couvre pas J-1 ({pdate})")
                if pdate + timedelta(days=cycle_days) > dmax:
                    errors.append(f"WTH '{wth_path.name}' ne couvre pas J+{cycle_days} ({pdate})")
                info.append(f"WTH forecast: {wth_path.name} | plage={dmin}..{dmax}")
            if header and not all(k in header for k in ["SRAD", "TMAX", "TMIN", "RAIN"]):
                warnings.append(f"Entete WTH incomplet: {header}")

    # 3) Sol
    soil_code = scenario.get("location", {}).get("soil_code")
    sol_path = dssat_dir / "SOIL.SOL"
    if not soil_code:
        errors.append("Code sol DSSAT manquant")
    elif not _soil_exists(sol_path, soil_code):
        errors.append(f"Code sol '{soil_code}' introuvable dans {sol_path.name}")

    # 4) Cultivar
    crop = scenario.get("crop", {}).get("code")
    cultivar = scenario.get("crop", {}).get("cultivar")
    if not crop or not cultivar:
        errors.append("Culture/cultivar manquant")
    else:
        exists, _name = _cultivar_exists(dssat_dir, crop, cultivar)
        if not exists:
            fallback, _fb_name = resolve_cultivar(crop, cultivar, dssat_dir)
            warnings.append(
                f"Cultivar '{cultivar}' absent de {CROP_CUL_FILES.get(crop, '?')}. "
                f"Fallback propose: '{fallback}'"
            )

    return {"errors": errors, "warnings": warnings, "info": info}

