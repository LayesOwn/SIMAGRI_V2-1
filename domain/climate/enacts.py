# domain/climate/enacts.py
import pandas as pd
from pathlib import Path
import re

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "enacts"


# ==========================================================
# Chargement ENACTS
# ==========================================================

from domain.geography import get_department_code


ENACTS_CODE_ALIASES = {
    # Code généré -> nom de fichier réel
    "MEDINA_YORO_FOULAH": "MEDINA_YOROFOULA",
}


def _norm_code(value):
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _resolve_enacts_file(code):
    # 1) correspondance directe
    p = DATA_DIR / f"{code}.csv"
    if p.exists():
        return p

    # 2) alias explicites
    alias = ENACTS_CODE_ALIASES.get(code)
    if alias:
        p = DATA_DIR / f"{alias}.csv"
        if p.exists():
            return p

    # 3) fallback robuste (ignore _, -, espaces)
    target = _norm_code(code)
    for f in DATA_DIR.glob("*.csv"):
        if _norm_code(f.stem) == target:
            return f
    return None

def load_enacts(department):
    """
    Charge les données ENACTS d’un département
    """

    code = get_department_code(department)

    if code is None:
        raise ValueError(f"Département inconnu : {department}")

    filepath = _resolve_enacts_file(code)
    if not filepath:
        raise FileNotFoundError(
            f"Fichier ENACTS introuvable pour '{department}' (code: {code})"
        )

    df = pd.read_csv(filepath)

    # 🔑 standardisation ENACTS → SIMAGRI
    df = df.rename(columns={
        "time": "date",
        "rain": "prcp"
    })

    df["date"] = pd.to_datetime(df["date"])

    for c in ["prcp", "tmax", "tmin"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df = df.dropna(subset=["date", "prcp", "tmax", "tmin"])

    return df


# ==========================================================
# Utilitaires climat
# ==========================================================

def extract_season(df, planting_date, duration_days):
    start = pd.to_datetime(planting_date)
    end = start + pd.Timedelta(days=duration_days)
    return df[(df["date"] >= start) & (df["date"] <= end)]


def write_dssat_weather(df, filepath):
    """
    Écriture DSSAT simple (sans SRAD)
    """
    with open(filepath, "w") as f:
        f.write("*WEATHER DATA : ENACTS\n")
        f.write("@DATE  TMAX  TMIN  RAIN\n")

        for _, r in df.iterrows():
            date = r["date"].strftime("%y%j")
            f.write(
                f"{date:>5} "
                f"{r['tmax']:>5.1f} "
                f"{r['tmin']:>5.1f} "
                f"{r['prcp']:>5.1f}\n"
            )


# ==========================================================
# Début de saison déterministe
# ==========================================================

def compute_onset_date(
    df,
    start_date="05-01",
    rain_window=3,
    rain_threshold=20,
    dry_spell_days=7,
    check_window=10
):
    df = df.sort_values("date").reset_index(drop=True)

    year = df["date"].dt.year.iloc[0]
    start = pd.to_datetime(f"{year}-{start_date}")
    df = df[df["date"] >= start].reset_index(drop=True)

    for i in range(len(df) - check_window):
        rain_sum = df.loc[i:i+rain_window-1, "prcp"].sum()

        if rain_sum >= rain_threshold:
            future = df.loc[i:i+check_window-1, "prcp"]
            max_dry = (
                (future == 0)
                .astype(int)
                .groupby(future.ne(0).cumsum())
                .sum()
                .max()
            )

            if max_dry < dry_spell_days:
                return df.loc[i, "date"]

    return None

# ==========================================================
# Utilitaire : zéros consécutifs (optimisé) 
def max_consecutive_zeros(arr):
    """
    Calcule la longueur maximale de zéros consécutifs
    dans un tableau numpy
    """
    max_run = run = 0
    for v in arr:
        if v == 0:
            run += 1
            max_run = max(max_run, run)
        else:
            run = 0
    return max_run
# ==========================================================
# Début de saison probabiliste (optimisé)
# ==========================================================

def compute_probabilistic_onset(
    df,
    start_year,
    end_year,
    window=2,
    threshold=15,
    dry_spell_days=7,
    check_window=15,
    start_month_day="05-01"
):
    df = df.copy()
    df["year"] = df["date"].dt.year
    df["doy"] = df["date"].dt.dayofyear

    df = df[(df["year"] >= start_year) & (df["year"] <= end_year)]
    if df.empty:
        return None, None

    # Découpage par année
    by_year = {}
    for y in df["year"].unique():
        dff = df[df["year"] == y].sort_values("doy")
        by_year[y] = {
            "doy": dff["doy"].values,
            "prcp": dff["prcp"].values,
            "start_doy": pd.to_datetime(f"{y}-{start_month_day}").dayofyear
        }

    probs = {}

    for doy in range(120, 360):
        success = 0
        total = 0

        for data in by_year.values():

            if doy < data["start_doy"]:
                continue

            # 🔹 pluie utile (15 mm / 2 jours)
            rain_mask = (data["doy"] >= doy) & (data["doy"] < doy + window)
            if rain_mask.sum() != window:
                continue

            if data["prcp"][rain_mask].sum() < threshold:
                continue

            # 🔹 sécheresse après (numpy pur)
            dry_mask = (data["doy"] >= doy + window) & (
                data["doy"] < doy + window + check_window
            )

            future_rain = data["prcp"][dry_mask]

            max_dry = max_consecutive_zeros(future_rain)

            total += 1
            if max_dry < dry_spell_days:
                success += 1

        if total > 0:
            probs[doy] = success / total

    if not probs:
        return None, None

    best_doy = max(probs, key=probs.get)
    ref_date = pd.Timestamp(2001, 1, 1) + pd.Timedelta(days=best_doy - 1)

    return ref_date.strftime("%d %B"), probs[best_doy]
