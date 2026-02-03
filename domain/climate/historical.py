# domain/climate/historical.py
import pandas as pd
from domain.climate.enacts import load_enacts
from domain.climate.onset import compute_onset_date


def historical_onset_analysis(department, start_year, end_year):
    """
    Analyse historique du début de saison
    entre start_year et end_year
    """

    df = load_enacts(department)

    # 🔒 filtrage strict par département + plage de dates
    df = df[
        (df["date"].dt.year >= start_year) &
        (df["date"].dt.year <= end_year)
    ]

    if df.empty:
        return None

    onsets = []

    for year, g in df.groupby(df["date"].dt.year):
        onset = compute_onset_date(g)
        if onset is not None:
            onsets.append(onset)

    if not onsets:
        return None

    s = pd.Series(onsets)

    return {
        "count": len(s),
        "mean": s.mean(),
        "median": s.median(),
        "min": s.min(),
        "max": s.max(),
        "raw": s.sort_values()
    }