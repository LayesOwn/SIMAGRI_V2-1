from datetime import datetime, timedelta
from pathlib import Path
import calendar
import random
import unicodedata

import pandas as pd

from domain.geography import (
    get_department_code,
    get_department_gps,
    get_department_wth_code,
    WTH_STATIONS,
)


FORECAST_DIR = Path(__file__).resolve().parents[2] / "data" / "Donnees_meteo"
LEGACY_FORECAST_DIR = Path(__file__).resolve().parents[2] / "data" / "Donnees_Meteo"
ENACTS_DIR = Path(__file__).resolve().parents[2] / "data" / "enacts"
FORECAST_REQUIRED_COLS = ["date", "rain", "tmax", "tmin"]

FRESAMPLER_DEFAULT_REALIZATIONS = 20
FRESAMPLER_DEFAULT_BLOCK_DAYS = 7
DEFAULT_TERCILE_PROBS = {"BN": 33.3, "NN": 33.4, "AN": 33.3}
ENACTS_REFERENCE_YEARS = (1991, 2022)

# For now forecast uses ENACTS historical reference (1991-2022)
# until department-level 2026 forecast files are finalized.
USE_ENACTS_REFERENCE = True

ENACTS_CODE_ALIASES = {
    "MEDINA_YORO_FOULAH": "MEDINA_YOROFOULA",
    "BIRKELANE": "BIERKELANE",
}


def _norm_code(value):
    return "".join(ch for ch in str(value or "").upper() if ch.isalnum())


def _resolve_enacts_file_for_department(department):
    code = get_department_code(department)
    if not code:
        return None

    p = ENACTS_DIR / f"{code}.csv"
    if p.exists():
        return p

    alias = ENACTS_CODE_ALIASES.get(code)
    if alias:
        p = ENACTS_DIR / f"{alias}.csv"
        if p.exists():
            return p

    target = _norm_code(code)
    for f in ENACTS_DIR.glob("*.csv"):
        if _norm_code(f.stem) == target:
            return f
    return None


def forecast_file_for_department(department):
    if USE_ENACTS_REFERENCE:
        p = _resolve_enacts_file_for_department(department)
        if p is not None:
            return p

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


def _load_enacts_reference_dataframe(department):
    p = _resolve_enacts_file_for_department(department)
    if p is None or not p.exists():
        raise FileNotFoundError(f"Fichier ENACTS introuvable pour '{department}'")

    df = pd.read_csv(p)
    # ENACTS attendu: time,rain,tmax,tmin,...
    if "time" not in df.columns:
        raise ValueError(f"Colonne manquante dans {p.name}: time")
    for c in ("rain", "tmax", "tmin"):
        if c not in df.columns:
            raise ValueError(f"Colonne manquante dans {p.name}: {c}")

    out = df.rename(columns={"time": "date"})[["date", "rain", "tmax", "tmin"]].copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    y0, y1 = ENACTS_REFERENCE_YEARS
    out = out[(out["date"].dt.year >= y0) & (out["date"].dt.year <= y1)].copy()
    out["rain"] = pd.to_numeric(out["rain"], errors="coerce")
    out["tmax"] = pd.to_numeric(out["tmax"], errors="coerce")
    out["tmin"] = pd.to_numeric(out["tmin"], errors="coerce")
    out = out.dropna(subset=FORECAST_REQUIRED_COLS).sort_values("date")
    out = out.drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
    return out


def load_forecast_dataframe(department):
    if USE_ENACTS_REFERENCE:
        out = _load_enacts_reference_dataframe(department)
        if out.empty:
            y0, y1 = ENACTS_REFERENCE_YEARS
            raise ValueError(f"ENACTS reference vide pour '{department}' sur {y0}-{y1}")
        return out

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


def validate_reference_pool(df, planting_date, cycle_days):
    """
    Validation pour downscaling probabiliste (FResampler1):
    on exige au moins une saison complete dans le pool de reference.
    """
    errors = []
    warnings = []
    info = []

    if df is None or df.empty:
        return {"errors": ["Pool de reference vide"], "warnings": warnings, "info": info}

    try:
        windows = _windows_by_year(df, planting_date, cycle_days)
    except Exception as e:
        return {"errors": [f"Pool de reference invalide: {e}"], "warnings": warnings, "info": info}

    if not windows:
        errors.append("Aucune saison complete disponible dans le pool de reference")
        return {"errors": errors, "warnings": warnings, "info": info}

    years = sorted({int(w["year"]) for w in windows})
    if len(years) < 2:
        warnings.append("Pool de reference limite (<2 annees completes)")

    info.append(
        f"Pool forecast valide: {len(windows)} saisons completes "
        f"({years[0]}-{years[-1]})"
    )
    return {"errors": errors, "warnings": warnings, "info": info}


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


def _norm(val):
    if not val:
        return ""
    n = unicodedata.normalize("NFD", str(val))
    n = "".join(c for c in n if unicodedata.category(c) != "Mn")
    return n.strip().lower().replace("-", " ")


def _station_code_for_department(department):
    station = None
    dkey = _norm(department)
    for name, code in WTH_STATIONS.items():
        if _norm(name) == dkey:
            station = code
            break
    station = (station or get_department_wth_code(department) or "DEPT").upper()
    # DSSAT stack here uses 4-char WSTA in SNX and alias layer maps as needed.
    return station[:4]


def _safe_date(year, month, day):
    max_day = calendar.monthrange(int(year), int(month))[1]
    return pd.Timestamp(datetime(int(year), int(month), min(int(day), max_day)))


def _window_bounds_from_planting(planting_date, cycle_days):
    pdate = pd.to_datetime(planting_date, errors="coerce")
    if pd.isna(pdate):
        raise ValueError("Date de semis forecast invalide")
    start = (pdate - timedelta(days=1)).normalize()
    end = (pdate + timedelta(days=int(cycle_days))).normalize()
    return pdate.normalize(), start, end


def _extract_window(df, start, end):
    win = df[(df["date"] >= start) & (df["date"] <= end)].copy().sort_values("date")
    expected = (end - start).days + 1
    if len(win) != expected:
        return None
    idx = pd.date_range(start=start, end=end, freq="D")
    if not (win["date"].dt.normalize().to_numpy() == idx.to_numpy()).all():
        return None
    return win.reset_index(drop=True)


def _write_wth(weather_df, department, station, dssat_dir):
    lat, lon = get_department_gps(department)
    dssat_dir = Path(dssat_dir)
    dssat_dir.mkdir(parents=True, exist_ok=True)
    wth_path = dssat_dir / f"{station}.WTH"

    win = weather_df.copy()
    if "date" not in win.columns:
        raise ValueError("weather_df doit contenir une colonne 'date'")

    with open(wth_path, "w", encoding="ascii", newline="\r\n") as f:
        f.write(f"*WEATHER DATA : {department}\n")
        f.write("@ INSI      LAT     LONG  ELEV   TAV   AMP REFHT WNDHT\n")
        f.write(f"  {station:<4}  {lat:8.3f} {lon:8.3f}    10  27.0  10.0  2.0  3.0\n")
        f.write("@DATE  SRAD  TMAX  TMIN  RAIN\n")
        for _, r in win.iterrows():
            token = pd.to_datetime(r["date"]).strftime("%y%j")
            rain = max(0.0, float(r["rain"]))
            tmax = float(r["tmax"])
            tmin = float(r["tmin"])
            if tmax <= tmin:
                tmax = tmin + 0.1
            # Fixed columns expected by DSSAT parser.
            f.write(f"{token:>5}{18.0:6.1f}{tmax:6.1f}{tmin:6.1f}{rain:6.1f}\n")

    return wth_path


def write_forecast_wth_from_dataframe(scenario, weather_df, dssat_dir):
    department = scenario.get("location", {}).get("department")
    if not department:
        raise ValueError("Departement manquant")
    station = _station_code_for_department(department)
    wth_path = _write_wth(weather_df, department, station, dssat_dir)
    scenario.setdefault("location", {})["station_code"] = station
    scenario.setdefault("dssat", {})["stn_name"] = station
    return wth_path


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

    _pdate, start, end = _window_bounds_from_planting(pdate, cycle_days)
    df = load_forecast_dataframe(department)
    val = validate_forecast_window(df, start, end)
    if val["errors"]:
        raise ValueError(" | ".join(val["errors"]))

    win = _extract_window(df, start, end)
    if win is None:
        raise ValueError("Forecast incomplet sur la fenetre J-1 a J+cycle")
    return write_forecast_wth_from_dataframe(scenario, win, dssat_dir)


def _normalize_tercile_probs(probs):
    src = probs or DEFAULT_TERCILE_PROBS
    bn = float(src.get("BN", src.get("bn", DEFAULT_TERCILE_PROBS["BN"])) or 0)
    nn = float(src.get("NN", src.get("nn", DEFAULT_TERCILE_PROBS["NN"])) or 0)
    an = float(src.get("AN", src.get("an", DEFAULT_TERCILE_PROBS["AN"])) or 0)

    if bn < 0 or nn < 0 or an < 0:
        bn, nn, an = DEFAULT_TERCILE_PROBS["BN"], DEFAULT_TERCILE_PROBS["NN"], DEFAULT_TERCILE_PROBS["AN"]

    total = bn + nn + an
    if total <= 0:
        bn, nn, an = DEFAULT_TERCILE_PROBS["BN"], DEFAULT_TERCILE_PROBS["NN"], DEFAULT_TERCILE_PROBS["AN"]
        total = bn + nn + an

    return {
        "BN": bn / total,
        "NN": nn / total,
        "AN": an / total,
    }


def _windows_by_year(df, planting_date, cycle_days):
    pdate = pd.to_datetime(planting_date, errors="coerce")
    if pd.isna(pdate):
        raise ValueError("Date de semis forecast invalide")

    years = sorted(df["date"].dt.year.dropna().astype(int).unique().tolist())
    windows = []
    for year in years:
        pday = _safe_date(year, pdate.month, pdate.day)
        start = (pday - timedelta(days=1)).normalize()
        end = (pday + timedelta(days=int(cycle_days))).normalize()
        win = _extract_window(df, start, end)
        if win is None:
            continue
        rain_total = float(win.iloc[1:]["rain"].clip(lower=0).sum())
        windows.append(
            {
                "year": year,
                "start": start,
                "end": end,
                "rain_total": rain_total,
                "data": win,
            }
        )
    return windows


def _pick_category(probs, rng):
    x = rng.random()
    if x < probs["BN"]:
        return "BN"
    if x < probs["BN"] + probs["NN"]:
        return "NN"
    return "AN"


def generate_fresampler_realizations_for_scenario(
    scenario,
    cycle_days=210,
    n_realizations=FRESAMPLER_DEFAULT_REALIZATIONS,
    block_days=FRESAMPLER_DEFAULT_BLOCK_DAYS,
    probs=None,
    random_seed=None,
):
    """
    FResampler1 simplifie (forecast-only):
    - construit un pool de saisons historiques de reference (par annee)
    - classe les saisons en BN/NN/AN selon la pluie cumulee saisonniere
    - echantillonne des blocs journaliers conditionnes par la categorie tiree

    Retourne une liste de dicts:
      - index, category, source_years, rain_total_mm, weather_df
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

    df = load_forecast_dataframe(department)
    windows = _windows_by_year(df, pdate, cycle_days)
    if not windows:
        raise ValueError("Impossible de construire des saisons de reference pour FResampler1")

    # Classer les saisons de reference selon terciles empiriques.
    rain_series = pd.Series([w["rain_total"] for w in windows], dtype=float)
    q1 = float(rain_series.quantile(1.0 / 3.0))
    q2 = float(rain_series.quantile(2.0 / 3.0))

    pools = {"BN": [], "NN": [], "AN": []}
    for w in windows:
        if w["rain_total"] <= q1:
            cat = "BN"
        elif w["rain_total"] >= q2:
            cat = "AN"
        else:
            cat = "NN"
        w["category"] = cat
        pools[cat].append(w)

    n_realizations = max(1, int(n_realizations or 1))
    block_days = max(1, int(block_days or 1))
    p = _normalize_tercile_probs(probs)

    rng = random.Random(random_seed)
    target_start = (pdate - timedelta(days=1)).normalize()
    expected_len = len(windows[0]["data"])  # all windows have same duration here

    out = []
    for ridx in range(1, n_realizations + 1):
        cat = _pick_category(p, rng)
        pool = pools.get(cat) or pools.get("NN") or pools.get("BN") or pools.get("AN")
        if not pool:
            raise ValueError("Pool FResampler1 vide")

        chunks = []
        source_years = []
        for start_i in range(0, expected_len, block_days):
            src = rng.choice(pool)
            source_years.append(int(src["year"]))
            chunk = src["data"].iloc[start_i : start_i + block_days][["rain", "tmax", "tmin"]].copy()
            chunks.append(chunk)

        gen = pd.concat(chunks, ignore_index=True).iloc[:expected_len].copy()
        gen["rain"] = pd.to_numeric(gen["rain"], errors="coerce").fillna(0.0).clip(lower=0.0)
        gen["tmax"] = pd.to_numeric(gen["tmax"], errors="coerce")
        gen["tmin"] = pd.to_numeric(gen["tmin"], errors="coerce")

        # securite temperature
        bad = gen["tmax"] <= gen["tmin"]
        if bad.any():
            gen.loc[bad, "tmax"] = gen.loc[bad, "tmin"] + 0.1

        gen.insert(0, "date", pd.date_range(start=target_start, periods=expected_len, freq="D"))
        rain_total = float(gen.iloc[1:]["rain"].sum())
        out.append(
            {
                "index": ridx,
                "category": cat,
                "source_years": source_years,
                "rain_total_mm": rain_total,
                "weather_df": gen,
            }
        )

    return out
