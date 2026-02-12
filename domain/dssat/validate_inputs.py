# domain/dssat/validate_inputs.py
# Validation des entrees DSSAT avant simulation

import re
from datetime import datetime, timedelta
from pathlib import Path

from domain.dssat.write_snx import CROP_CUL_FILES, resolve_cultivar


def _parse_planting_date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    s = str(value)
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    return None


def _find_wth_file(dssat_dir, station_code):
    target = f"{station_code}.WTH"
    p = dssat_dir / target
    if p.exists():
        return p
    # fallback case-insensitive
    for f in dssat_dir.glob("*.WTH"):
        if f.stem.upper() == station_code.upper():
            return f
    return None


def _parse_wth_dates(wth_path):
    dates = []
    header = None
    with open(wth_path, "r", encoding="latin-1", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("@"):
                if line.upper().startswith("@DATE"):
                    header = line.upper()
                continue
            if line.startswith("*"):
                continue
            parts = line.split()
            if not parts:
                continue
            token = parts[0]
            if not token.isdigit():
                continue
            # YYYYDDD ou YYDDD
            if len(token) == 7:
                year = int(token[:4])
                doy = int(token[4:])
            elif len(token) == 5:
                year = 2000 + int(token[:2])
                doy = int(token[2:])
            else:
                continue
            try:
                d = datetime(year, 1, 1) + timedelta(days=doy - 1)
                dates.append(d.date())
            except Exception:
                continue
    return dates, header


def _soil_exists(sol_path, soil_code):
    if not sol_path.exists():
        return False
    pattern = re.compile(rf"^\s*{re.escape(soil_code)}\b")
    with open(sol_path, "r", encoding="latin-1", errors="ignore") as f:
        for line in f:
            if pattern.match(line):
                return True
    return False


def _cultivar_exists(dssat_path, crop, cultivar):
    cul_file = CROP_CUL_FILES.get(crop)
    if not cul_file:
        return False, None
    cul_path = Path(dssat_path) / cul_file
    if not cul_path.exists():
        return False, None
    with open(cul_path, "r", encoding="latin-1", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(("*", "!")):
                continue
            parts = line.split()
            if parts and parts[0] == cultivar:
                return True, parts[1] if len(parts) > 1 else None
    return False, None


def validate_dssat_inputs(scenario, base_dir):
    """
    Retourne un dict:
      - errors: liste d'erreurs bloquantes
      - warnings: liste d'avertissements
      - info: liste d'infos utiles
    """
    errors = []
    warnings = []
    info = []

    base_dir = Path(base_dir)
    dssat_dir = base_dir / "dssat"

    # Station / météo
    station = scenario.get("location", {}).get("station_code")
    if not station:
        errors.append("Station DSSAT (WSTA) manquante")
    else:
        wth_path = _find_wth_file(dssat_dir, station)
        if not wth_path:
            errors.append(f"Fichier météo WTH introuvable pour station '{station}'")
        else:
            dates, header = _parse_wth_dates(wth_path)
            if not dates:
                errors.append(f"WTH '{wth_path.name}' sans lignes météo valides")
            else:
                pdate = _parse_planting_date(scenario.get("crop", {}).get("planting_date"))
                if not pdate:
                    errors.append("Date de semis invalide (format attendu YYYYMMDD ou YYYY-MM-DD)")
                else:
                    if pdate < min(dates) or pdate > max(dates):
                        errors.append(
                            f"WTH '{wth_path.name}' ne couvre pas la date de semis ({pdate})"
                        )
            if header and not all(k in header for k in ["SRAD", "TMAX", "TMIN", "RAIN"]):
                warnings.append(
                    f"En-tête WTH '{wth_path.name}' incomplet: {header}"
                )

    # Sol
    soil_code = scenario.get("location", {}).get("soil_code")
    sol_path = dssat_dir / "SENEGAL.SOL"
    if not soil_code:
        errors.append("Code sol DSSAT manquant")
    elif not _soil_exists(sol_path, soil_code):
        errors.append(f"Code sol '{soil_code}' introuvable dans {sol_path.name}")

    # Cultivar
    crop = scenario.get("crop", {}).get("code")
    cultivar = scenario.get("crop", {}).get("cultivar")
    if crop and cultivar:
        exists, name = _cultivar_exists(dssat_dir, crop, cultivar)
        if not exists:
            # proposer fallback
            fallback, fb_name = resolve_cultivar(crop, cultivar, dssat_dir)
            warnings.append(
                f"Cultivar '{cultivar}' absent de {CROP_CUL_FILES.get(crop,'?')}. "
                f"Fallback proposé: '{fallback}'"
            )
        else:
            info.append(f"Cultivar OK: {cultivar}" + (f" ({name})" if name else ""))
    else:
        errors.append("Culture/cultivar manquant")

    return {
        "errors": errors,
        "warnings": warnings,
        "info": info,
    }
