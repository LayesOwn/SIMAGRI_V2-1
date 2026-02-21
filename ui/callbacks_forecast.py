try:
    from dash import html, dcc, ctx
except Exception:
    import dash_html_components as html
    import dash_core_components as dcc
    from dash import callback_context as ctx
from dash.dependencies import Input, Output, State, ALL
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import json
import re
import base64
import io
from pathlib import Path
from datetime import datetime
import copy
import pandas as pd

from domain.geography import get_department_gps, get_department_soil
from domain.scenario import build_scenario_from_ui
from domain.socio_eco import (
    SEEDS,
    compute_seed_cost,
    compute_soil_preparation_cost,
    compute_labor_cost,
    compute_post_harvest_cost,
    compute_total_socio_cost,
)
from domain.fertilisation import compute_fertilization_cost, compute_npk_from_fertilizer
from domain.irrigation import get_irrigation_schedule, DEFAULT_IRRIGATION_PRICE
from domain.climate.forecast import (
    FRESAMPLER_DEFAULT_BLOCK_DAYS,
    forecast_file_for_department,
    generate_fresampler_realizations_for_scenario,
    load_forecast_dataframe,
    write_forecast_wth_from_dataframe,
    write_forecast_wth_for_scenario,
)
from domain.dssat.write_xfile import write_x_file
from domain.dssat.write_snx import write_snx_file
from domain.dssat.run_dssat import run_dssat_simulation
from domain.dssat.validate_forecast_inputs import validate_forecast_inputs


BASE_DIR = Path("/app")
if not BASE_DIR.exists():
    BASE_DIR = Path(__file__).resolve().parents[2]

GEOJSON_PATH = BASE_DIR / "data" / "geojson" / "senegal_departments.json"
NORTH_DEPARTMENTS = {
    "DAGANA",
    "PODOR",
    "SAINT LOUIS",
    "LOUGA",
    "LINGUERE",
    "KEBEMER",
    "MATAM",
    "KANEL",
    "RANEROU",
    "RANEROU FERLO",
}


def _is_north_department(department):
    key = str(department or "").upper().replace("-", " ").strip()
    if key in NORTH_DEPARTMENTS:
        return True
    try:
        lat, _ = get_department_gps(department)
        return lat >= 14.2
    except Exception:
        return False


def _max_consecutive_dry_days(rain_series):
    streak = 0
    max_streak = 0
    for v in rain_series:
        if _to_float(v) and _to_float(v) > 0:
            streak = 0
        else:
            streak += 1
            if streak > max_streak:
                max_streak = streak
    return max_streak


def _recommended_sowing_window(df, target_year, department):
    year_df = df[df["date"].dt.year == int(target_year)].copy()
    year_df = year_df.sort_values("date").reset_index(drop=True)
    if year_df.empty:
        return None, None, "Aucune donnee forecast sur l'annee cible"
    threshold = 15.0 if _is_north_department(department) else 20.0
    candidates = []
    n = len(year_df)
    for i in range(0, n):
        # Rule: cumulative rain threshold over 1 to 3 consecutive days.
        onset_ok = False
        for win in (1, 2, 3):
            if i + win > n:
                break
            rsum = float(year_df.iloc[i : i + win]["rain"].fillna(0).sum())
            if rsum >= threshold:
                onset_ok = True
                break
        if not onset_ok:
            continue
        next20 = year_df.iloc[i + 1 : i + 21]
        if len(next20) < 20:
            continue
        # Reject when followed by a dry spell of 20 consecutive days.
        if _max_consecutive_dry_days(next20["rain"].tolist()) >= 20:
            continue
        candidates.append(year_df.loc[i, "date"].date())
    if not candidates:
        return None, None, (
            f"Aucune date detectee (regle: >= {threshold:.0f} mm sur 1-3 jours "
            f"et pas de pause seche de 20 jours apres)"
        )
    start = candidates[0]
    end = min(candidates[-1], start + pd.Timedelta(days=10))
    return start, end, (
        f"Fenetre conseillee ({int(target_year)}): {start} au {end} "
        f"(seuil {threshold:.0f} mm sur 1-3 jours)"
    )


def _recommended_sowing_climatology(df, target_year, department):
    """
    Recommandation basee sur les annees de reference (ex: ENACTS 2021-2022):
    calcule le DOY median des premiers onsets annuels puis projette sur target_year.
    """
    threshold = 15.0 if _is_north_department(department) else 20.0
    onset_doys = []

    for year, ydf in df.groupby(df["date"].dt.year):
        ydf = ydf.sort_values("date").reset_index(drop=True)
        n = len(ydf)
        found = None
        for i in range(0, n):
            onset_ok = False
            for win in (1, 2, 3):
                if i + win > n:
                    break
                rsum = float(ydf.iloc[i : i + win]["rain"].fillna(0).sum())
                if rsum >= threshold:
                    onset_ok = True
                    break
            if not onset_ok:
                continue
            next20 = ydf.iloc[i + 1 : i + 21]
            if len(next20) < 20:
                continue
            if _max_consecutive_dry_days(next20["rain"].tolist()) >= 20:
                continue
            found = ydf.loc[i, "date"]
            break
        if found is not None:
            onset_doys.append(int(found.dayofyear))

    if not onset_doys:
        return None, None, (
            f"Aucune date detectee sur annees de reference "
            f"(regle: >= {threshold:.0f} mm sur 1-3 jours et pas de pause seche de 20 jours apres)"
        )

    doy = int(round(float(pd.Series(onset_doys).median())))
    start = (pd.Timestamp(int(target_year), 1, 1) + pd.Timedelta(days=doy - 1)).date()
    end = min(start + pd.Timedelta(days=10), pd.Timestamp(int(target_year), 12, 31).date())
    return start, end, (
        f"Fenetre conseillee ({int(target_year)}) basee climatologie recente: {start} au {end} "
        f"(seuil {threshold:.0f} mm sur 1-3 jours)"
    )


def _to_float(value):
    try:
        return float(str(value).strip())
    except Exception:
        return None


def _parse_max_scenarios(simulation_mode):
    """
    Accepte int/str numerique et borne a [1, 3].
    """
    if simulation_mode in (None, ""):
        return 1
    try:
        n = int(simulation_mode)
    except Exception:
        return 1
    return max(1, min(n, 3))


def _snx_has_fertilizer_inputs(snx_path):
    """
    Verifie que le SNX contient au moins un apport fertilisant > 0
    dans la section *FERTILIZERS (INORGANIC).
    """
    try:
        lines = Path(snx_path).read_text(encoding="latin-1", errors="ignore").splitlines()
    except Exception:
        return False

    in_fert = False
    for raw in lines:
        s = raw.strip()
        if not s:
            if in_fert:
                continue
            continue
        if s.startswith("*"):
            in_fert = s.upper().startswith("*FERTILIZERS")
            continue
        if not in_fert or s.startswith("@"):
            continue
        parts = s.split()
        if len(parts) < 8:
            continue
        n_val = _to_float(parts[5])
        p_val = _to_float(parts[6])
        k_val = _to_float(parts[7])
        if (n_val and n_val > 0) or (p_val and p_val > 0) or (k_val and k_val > 0):
            return True
    return False


def _parse_run_metrics_from_stdout(stdout_text):
    """
    Parse la ligne RUN DSSAT (console) pour recuperer des metriques fiables.
    """
    if not stdout_text:
        return {}
    pat = re.compile(
        r"^\s*1\s+\w+\s+1\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)",
        re.MULTILINE,
    )
    m = pat.search(stdout_text)
    if not m:
        return {}
    flo, mat, topwt, harwt, rain, tirr, cet = m.groups()
    return {
        "FLO": flo,
        "MAT": mat,
        "TOPWT": topwt,
        "HARWT": harwt,
        "RAIN": rain,
        "TIRR": tirr,
        "CET": cet,
    }


def _forecast_cycle_days(crop_code):
    """
    Default cycle length (days) for forecast simulations.
    Used to size the WTH window; a small buffer is added at runtime.
    """
    return {
        "ML": 210,
        "SG": 210,
        "RI": 210,
        "PN": 240,
    }.get((crop_code or "").upper(), 210)


def _scenario_ui_agro_totals(scenario):
    """
    Totaux agronomiques derives du scenario UI (forecast):
    - N/P/K (kg/ha) depuis les applications de fertilisation
    - irrigation totale (mm) et nombre de tours depuis le planning UI
    """
    fert = (scenario or {}).get("fertilization", {}) or {}
    irrig = (scenario or {}).get("irrigation", {}) or {}

    n_tot = p_tot = k_tot = 0.0
    for app in (fert.get("applications") or []):
        n_tot += _to_float(app.get("N")) or 0.0
        p_tot += _to_float(app.get("P")) or 0.0
        k_tot += _to_float(app.get("K")) or 0.0

    irr_mm = 0.0
    irr_n = 0
    for ev in (irrig.get("schedule") or []):
        mm = _to_float(ev.get("mm")) or 0.0
        irr_mm += mm
        if mm > 0:
            irr_n += 1

    return {
        "n_tot": n_tot,
        "p_tot": p_tot,
        "k_tot": k_tot,
        "irr_mm": irr_mm,
        "irr_n": irr_n,
    }


def _prepare_forecast_scenario_for_dssat(scenario):
    """
    Forecast-only normalization before SNX write:
    - keep management event dates as DAP/JAS (DSSAT reported events use DAP)
    """
    s = copy.deepcopy(scenario or {})

    crop = (s.get("crop", {}) or {})
    loc = (s.get("location", {}) or {})
    d = (s.get("dssat", {}) or {})

    crop_code = str(crop.get("code") or d.get("Crop") or "ML").upper()
    cultivar = crop.get("cultivar") or d.get("Cultivar")
    station = str(loc.get("station_code") or d.get("stn_name") or "DEPT").upper()[:4]
    soil = loc.get("soil_code") or d.get("soil")
    planting_date = crop.get("planting_date") or d.get("PltDate")
    density = crop.get("density") or d.get("plt_density") or 5

    try:
        y = int(pd.to_datetime(planting_date, errors="coerce").year)
    except Exception:
        y = datetime.now().year

    s["dssat"] = {
        **d,
        "Crop": crop_code,
        "Cultivar": cultivar,
        "stn_name": station,
        "soil": soil,
        "PltDate": planting_date,
        "FirstYear": d.get("FirstYear", y),
        "LastYear": d.get("LastYear", y),
        "TargetYr": d.get("TargetYr", y),
        "plt_density": density,
    }
    return s


def _parse_summary_metrics(summary_path):
    metrics = {}
    sp = Path(summary_path)
    if not sp.exists():
        return metrics
    txt = sp.read_text(encoding="latin-1", errors="ignore").splitlines()
    head = None
    vals = None
    for ln in txt:
        s = ln.strip()
        if not s:
            continue
        if s.startswith("@"):
            head = s.split()
            if head and head[0] == "@":
                head = head[1:]
            continue
        if head and s[:1].isdigit():
            cand = s.split()
            if len(cand) >= 10:
                vals = cand
    if not (head and vals):
        return metrics
    row = {k: vals[idx] for idx, k in enumerate(head) if idx < len(vals)}
    metrics["HARWT"] = row.get("HWAM", "-")
    metrics["TOPWT"] = row.get("CWAM", "-")
    metrics["RAIN"] = row.get("PRCM", "-")
    metrics["RAIN_SEAS"] = row.get("PRCP", "-")
    metrics["TIRR"] = row.get("IRCM", "-")
    metrics["CET"] = row.get("ETCM", "-")
    metrics["MAT"] = row.get("MDAPS", "-")
    metrics["FERTN"] = row.get("NICM", row.get("NI#M", "-"))
    return metrics


def _merge_metrics(run_metrics, summary_metrics):
    m = {"status": "SUCCES"}
    m.update(summary_metrics or {})
    for key in ["HARWT", "TOPWT", "RAIN", "TIRR", "CET", "MAT"]:
        if key in (run_metrics or {}):
            m[key] = run_metrics[key]

    rain_disp = _to_float(m.get("RAIN"))
    rain_seas = _to_float(m.get("RAIN_SEAS"))
    if (rain_disp is None or rain_disp == 0) and (rain_seas is not None and rain_seas > 0):
        m["RAIN"] = f"{rain_seas:.1f}"
    return m


def _aggregate_ensemble_metrics(metrics_list):
    if not metrics_list:
        return {"status": "ERREUR"}

    agg = {"status": "SUCCES"}
    keys = ["HARWT", "TOPWT", "RAIN", "TIRR", "CET", "MAT"]
    for key in keys:
        vals = []
        for m in metrics_list:
            v = _to_float(m.get(key))
            if v is not None:
                vals.append(v)
        if not vals:
            agg[key] = "-"
            continue
        s = pd.Series(vals, dtype=float)
        agg[key] = f"{float(s.median()):.1f}"
        if key in ("HARWT", "TOPWT"):
            agg[f"{key}_P20"] = f"{float(s.quantile(0.2)):.1f}"
            agg[f"{key}_P80"] = f"{float(s.quantile(0.8)):.1f}"
    agg["NREAL"] = len(metrics_list)
    return agg


def _forecast_scenario_to_table_row(s):
    eco = s.get("economy", {}) or {}
    fert_cost = eco.get("NFertCost", 0) or 0
    irrig_cost = eco.get("IrrigCost", 0) or 0
    production_cost = (eco.get("FixedCosts", 0) or 0) if eco.get("SocioEnabled") else 0
    total_cost = fert_cost + irrig_cost + production_cost

    def _amt(v):
        try:
            return str(int(round(float(v or 0))))
        except Exception:
            return "0"

    return {
        "ID": s.get("id_scenario", "-"),
        "Departement": s.get("location", {}).get("department", "-"),
        "Culture": s.get("crop", {}).get("code", "-"),
        "Cycle": s.get("crop", {}).get("cycle", "-"),
        "Semis": s.get("crop", {}).get("planting_date", "-"),
        "Fertilisation": "Oui" if s.get("fertilization", {}).get("enabled") else "Non",
        "Irrigation": "Oui" if s.get("irrigation", {}).get("enabled") else "Non",
        "Cout fertilisation (FCFA)": _amt(fert_cost),
        "Cout irrigation (FCFA)": _amt(irrig_cost),
        "Cout production (FCFA)": _amt(production_cost),
        "Cout total (FCFA)": _amt(total_cost),
    }


def _filter_forecast_messages(messages):
    keep = []
    patterns = (
        r"^Scenario\s+\d+\s+-\s+controle UI:",
        r"^Scenario\s+\d+\s+-\s+(FResampler1|Prevision probabiliste):",
        r"^Scenario\s+\d+\s+-\s+prevision simulee",
    )
    for m in (messages or []):
        txt = str(m or "").strip()
        if any(re.match(p, txt) for p in patterns):
            keep.append(txt)
    return keep


def _export_forecast_rows(scenarios, sim_results):
    rows = []
    for s in (scenarios or []):
        sid = s.get("id_scenario")
        m = (sim_results or {}).get(sid, {}) or {}
        totals = _scenario_ui_agro_totals(s)
        rows.append(
            {
                "id_scenario": sid,
                "departement": s.get("location", {}).get("department"),
                "culture": s.get("crop", {}).get("code"),
                "cycle": s.get("crop", {}).get("cycle"),
                "date_semis": s.get("crop", {}).get("planting_date"),
                "fertilisation": bool(s.get("fertilization", {}).get("enabled")),
                "irrigation": bool(s.get("irrigation", {}).get("enabled")),
                "methode_irrigation": s.get("irrigation", {}).get("method"),
                "N_total_kg_ha": f"{totals['n_tot']:.1f}",
                "P_total_kg_ha": f"{totals['p_tot']:.1f}",
                "K_total_kg_ha": f"{totals['k_tot']:.1f}",
                "irrigation_totale_mm": f"{totals['irr_mm']:.1f}",
                "status": m.get("status", ""),
                "HARWT": m.get("HARWT", ""),
                "HARWT_P20": m.get("HARWT_P20", ""),
                "HARWT_P80": m.get("HARWT_P80", ""),
                "TOPWT": m.get("TOPWT", ""),
                "RAIN": m.get("RAIN", ""),
                "TIRR": m.get("TIRR", ""),
                "CET": m.get("CET", ""),
                "MAT": m.get("MAT", ""),
                "scenario_json": json.dumps(s, ensure_ascii=False),
                "result_json": json.dumps(m, ensure_ascii=False),
            }
        )
    return rows


def _read_uploaded_table(contents, filename):
    if not contents:
        return []
    try:
        _, b64 = contents.split(",", 1)
        raw = base64.b64decode(b64)
    except Exception:
        return []

    name = str(filename or "").lower()
    try:
        if name.endswith(".xlsx") or name.endswith(".xls"):
            df = pd.read_excel(io.BytesIO(raw))
        else:
            text = raw.decode("utf-8-sig", errors="ignore")
            df = pd.read_csv(io.StringIO(text))
        return df.to_dict(orient="records")
    except Exception:
        return []


def _import_forecast_scenarios(contents, filename):
    rows = _read_uploaded_table(contents, filename)
    out = []
    for r in rows:
        sj = r.get("scenario_json")
        if not sj:
            continue
        try:
            s = json.loads(sj)
            if isinstance(s, dict):
                out.append(s)
        except Exception:
            continue
    for i, s in enumerate(out, start=1):
        s["id_scenario"] = f"F{i:03d}"
    return out


def _build_forecast_results_view(scenarios, sim_results, messages):
    rows = []
    labels = []
    harwt_vals = []
    topwt_vals = []
    rain_vals = []
    tirr_vals = []
    cet_vals = []
    cost_vals = []
    revenue_vals = []
    margin_vals = []
    p20_vals = []
    p80_vals = []
    metric_lines = []

    for idx, s in enumerate(scenarios, start=1):
        sid = s.get("id_scenario")
        m = (sim_results or {}).get(sid, {})
        status = str(m.get("status", "-"))
        color = "success" if status == "SUCCES" else ("warning" if status == "VIDE" else "danger")

        harwt = _to_float(m.get("HARWT"))
        topwt = _to_float(m.get("TOPWT"))
        rain = _to_float(m.get("RAIN"))
        tirr = _to_float(m.get("TIRR"))
        cet = _to_float(m.get("CET"))
        p20 = _to_float(m.get("HARWT_P20"))
        p80 = _to_float(m.get("HARWT_P80"))
        nreal = m.get("NREAL", "-")

        eco = s.get("economy", {}) or {}
        total_cost = float((eco.get("NFertCost", 0) or 0) + (eco.get("IrrigCost", 0) or 0) + (eco.get("FixedCosts", 0) or 0))
        crop_price = float(eco.get("CropPrice", 0) or 0)
        revenue = (harwt or 0.0) * crop_price
        margin = revenue - total_cost

        rows.append(
            html.Tr(
                [
                    html.Td(f"Scenario {idx}"),
                    html.Td(sid or "-"),
                    html.Td(dbc.Badge(status, color=color, className="me-1")),
                    html.Td(m.get("HARWT", "-")),
                    html.Td(m.get("HARWT_P20", "-")),
                    html.Td(m.get("HARWT_P80", "-")),
                    html.Td(m.get("TOPWT", "-")),
                    html.Td(m.get("RAIN", "-")),
                    html.Td(m.get("TIRR", "-")),
                    html.Td(m.get("CET", "-")),
                    html.Td(m.get("MAT", "-")),
                    html.Td(nreal),
                ]
            )
        )

        labels.append(sid or f"F{idx:03d}")
        harwt_vals.append(harwt or 0)
        topwt_vals.append(topwt or 0)
        rain_vals.append(rain or 0)
        tirr_vals.append(tirr or 0)
        cet_vals.append(cet or 0)
        cost_vals.append(total_cost)
        revenue_vals.append(revenue)
        margin_vals.append(margin)
        p20_vals.append(p20 if p20 is not None else harwt or 0)
        p80_vals.append(p80 if p80 is not None else harwt or 0)

        metric_lines.append(
            f"{sid or f'Scenario {idx}'}: "
            f"HARWT={m.get('HARWT','-')} kg/ha, "
            f"P20={m.get('HARWT_P20','-')}, P80={m.get('HARWT_P80','-')}, "
            f"TOPWT={m.get('TOPWT','-')} kg/ha, "
            f"RAIN={m.get('RAIN','-')} mm, "
            f"TIRR={m.get('TIRR','-')} mm, "
            f"CET={m.get('CET','-')} mm, "
            f"MAT={m.get('MAT','-')} j."
        )

    n_success = sum(1 for v in (sim_results or {}).values() if v.get("status") == "SUCCES")
    n_empty = sum(1 for v in (sim_results or {}).values() if v.get("status") == "VIDE")
    n_error = max(0, len(scenarios) - n_success - n_empty)

    fig_agro = go.Figure()
    fig_agro.add_bar(name="HARWT", x=labels, y=harwt_vals)
    fig_agro.add_bar(name="TOPWT", x=labels, y=topwt_vals)
    fig_agro.update_layout(barmode="group", title="Performance agronomique (kg/ha)", yaxis_title="kg/ha", margin=dict(l=20, r=20, t=50, b=20))

    fig_water = go.Figure()
    fig_water.add_bar(name="RAIN", x=labels, y=rain_vals)
    fig_water.add_bar(name="TIRR", x=labels, y=tirr_vals)
    fig_water.add_bar(name="CET", x=labels, y=cet_vals)
    fig_water.update_layout(barmode="group", title="Bilan hydrique (mm)", yaxis_title="mm", margin=dict(l=20, r=20, t=50, b=20))

    fig_econ = go.Figure()
    fig_econ.add_bar(name="Cout total", x=labels, y=cost_vals)
    fig_econ.add_bar(name="Revenu brut", x=labels, y=revenue_vals)
    fig_econ.add_bar(name="Marge", x=labels, y=margin_vals)
    fig_econ.update_layout(
        barmode="group",
        title="Lecture economique (FCFA/ha)",
        yaxis_title="FCFA/ha",
        yaxis_tickformat=".0f",
        margin=dict(l=20, r=20, t=50, b=20),
    )

    fig_unc = go.Figure()
    fig_unc.add_bar(name="P20", x=labels, y=p20_vals)
    fig_unc.add_bar(name="P80", x=labels, y=p80_vals)
    fig_unc.update_layout(
        barmode="group",
        title="Incertitude previsionnelle HARWT (P20/P80)",
        yaxis_title="kg/ha",
        margin=dict(l=20, r=20, t=50, b=20),
    )

    filtered_messages = _filter_forecast_messages(messages)

    return html.Div(
        [
            html.H5("Resultat des simulations DSSAT (prevision)", className="mb-3"),
            html.Ul([html.Li(m, className="mb-1") for m in filtered_messages]),
            dbc.Table(
                [
                    html.Thead(
                        html.Tr(
                            [
                                html.Th("Scenario"),
                                html.Th("ID"),
                                html.Th("Status"),
                                html.Th("HARWT"),
                                html.Th("P20"),
                                html.Th("P80"),
                                html.Th("TOPWT"),
                                html.Th("RAIN"),
                                html.Th("TIRR"),
                                html.Th("CET"),
                                html.Th("MAT"),
                                html.Th("NREAL"),
                            ]
                        )
                    ),
                    html.Tbody(rows),
                ],
                bordered=True,
                striped=True,
                hover=True,
                size="sm",
                className="mt-3",
            ),
            dbc.Alert(
                "Definitions: BN=below normal, NN=near normal, AN=above normal. "
                "P20/P80 = percentiles de rendement sur les realisations forecast.",
                color="info",
                className="mt-2",
            ),
            dbc.Alert(html.Ul([html.Li(x) for x in metric_lines]), color="secondary", className="mt-2"),
            html.P(f"Total: {len(scenarios)} | Succes: {n_success} | Vides: {n_empty} | Erreurs: {n_error}"),
            dbc.Row([dbc.Col(dcc.Graph(figure=fig_agro), md=6), dbc.Col(dcc.Graph(figure=fig_water), md=6)]),
            dbc.Row([dbc.Col(dcc.Graph(figure=fig_econ), md=6), dbc.Col(dcc.Graph(figure=fig_unc), md=6)]),
        ]
    )


def register_forecast_callbacks(app):
    def get_triggered_id():
        try:
            return ctx.triggered_id
        except Exception:
            pass
        try:
            trig = ctx.triggered[0]["prop_id"].split(".")[0] if getattr(ctx, "triggered", None) else ""
            return trig or None
        except Exception:
            return None

    @app.callback(
        Output("forecast-export-download", "data"),
        Input("forecast-export-simulation", "n_clicks"),
        State("forecast-scenario-store", "data"),
        State("forecast-results-store", "data"),
        prevent_initial_call=True,
    )
    def export_forecast_simulation(n_clicks, scenarios, sim_results):
        if not n_clicks or not scenarios:
            return None
        rows = _export_forecast_rows(scenarios or [], sim_results or {})
        df = pd.DataFrame(rows)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return dcc.send_data_frame(df.to_csv, f"simagri_forecast_{ts}.csv", index=False, encoding="utf-8-sig")

    @app.callback(
        [
            Output("forecast-recommended-sowing", "children"),
            Output("forecast-planting-date", "min_date_allowed"),
            Output("forecast-planting-date", "max_date_allowed"),
            Output("forecast-planting-date", "date"),
            Output("forecast-target-year", "value"),
        ],
        Input("forecast-department", "value"),
        State("forecast-planting-date", "date"),
    )
    def update_recommended_sowing(department, current_planting):
        target_year = datetime.now().year
        if not department:
            return "Date conseillee: selectionnez un departement", None, None, current_planting, target_year
        try:
            df = load_forecast_dataframe(department)
        except Exception as e:
            return f"Date conseillee: forecast non disponible ({e})", None, None, current_planting, target_year

        min_d = pd.to_datetime(df["date"].min(), errors="coerce")
        max_d = pd.to_datetime(df["date"].max(), errors="coerce")
        yr_start = pd.Timestamp(target_year, 1, 1)
        yr_end = pd.Timestamp(target_year, 12, 31)
        # En mode reference historique (ENACTS 2021-2022), on recommande
        # pour l'annee cible via climatologie et on autorise toute l'annee cible.
        has_target_year = bool((df["date"].dt.year == int(target_year)).any())
        if has_target_year:
            allowed_start = max(min_d, yr_start) if not pd.isna(min_d) else yr_start
            allowed_end = min(max_d, yr_end) if not pd.isna(max_d) else yr_end
            start, end, msg = _recommended_sowing_window(df, target_year, department)
        else:
            allowed_start = yr_start
            allowed_end = yr_end
            start, end, msg = _recommended_sowing_climatology(df, target_year, department)
        if start is not None:
            recommended = start.isoformat()
            txt = f"Date conseillee: [{start.isoformat()} - {end.isoformat()}]"
        else:
            recommended = None
            txt = msg

        chosen = current_planting
        if recommended:
            chosen = recommended
        elif chosen:
            c = pd.to_datetime(chosen, errors="coerce")
            if pd.isna(c) or c < allowed_start or c > allowed_end:
                chosen = allowed_start.date().isoformat()
        else:
            chosen = allowed_start.date().isoformat()

        if allowed_start > allowed_end:
            return (
                "Date conseillee: aucune date disponible sur l'annee cible.",
                None,
                None,
                current_planting,
                target_year,
            )
        return (
            txt,
            allowed_start.date().isoformat(),
            allowed_end.date().isoformat(),
            chosen,
            target_year,
        )

    @app.callback(
        [
            Output("forecast-map", "center"),
            Output("forecast-map", "zoom"),
            Output("forecast-dept-marker", "position"),
            Output("forecast-dept-geojson", "data"),
            Output("forecast-soil-type", "options"),
            Output("forecast-soil-type", "value"),
            Output("forecast-dept-tooltip", "children"),
        ],
        Input("forecast-department", "value"),
    )
    def update_forecast_map_and_soil(dept_name):
        if not dept_name:
            return [14.15, -16.07], 4, [14.15, -16.07], None, [], None, "Departement | Sol: -"
        lat, lon = get_department_gps(dept_name)
        soil = get_department_soil(dept_name) or "-"
        geojson = None
        try:
            with open(GEOJSON_PATH, encoding="utf-8") as f:
                geo = json.load(f)
            features = geo.get("features", [])
            target = str(dept_name).lower().replace("-", " ").strip()
            for ft in features:
                props = ft.get("properties", {})
                name = (
                    props.get("NAME")
                    or props.get("name")
                    or props.get("ADM2_FR")
                    or props.get("ADM2_EN")
                    or ""
                )
                if str(name).lower().replace("-", " ").strip() == target:
                    geojson = {"type": "FeatureCollection", "features": [ft]}
                    break
        except Exception:
            geojson = None
        return (
            [lat, lon],
            4,
            [lat, lon],
            geojson,
            [{"label": soil, "value": soil}],
            soil,
            f"{dept_name} | Sol: {soil}",
        )

    @app.callback(Output("forecast-fertilization-block", "style"), Input("forecast-fertilization", "value"))
    def toggle_fert(use):
        return {"display": "block"} if use else {"display": "none"}

    @app.callback(Output("forecast-irrigation-block", "style"), Input("forecast-irrigation", "value"))
    def toggle_irrig(mode):
        return {"display": "block"} if mode == "MANUAL" else {"display": "none"}

    @app.callback(
        Output("forecast-socio-block", "style"),
        Input("forecast-toggle-socio", "n_clicks"),
        Input("forecast-reset-scenarios", "n_clicks"),
        prevent_initial_call=True,
    )
    def toggle_socio(_toggle, _reset):
        trig = get_triggered_id()
        if trig == "forecast-reset-scenarios":
            return {"display": "none"}
        return {"display": "block"}

    @app.callback(
        [
            Output("forecast-department", "value"),
            Output("forecast-crop", "value"),
            Output("forecast-cycle", "value"),
            Output("forecast-simulation-mode", "value"),
            Output("forecast-downscaling-method", "value"),
            Output("forecast-realizations", "value"),
            Output("forecast-fertilization", "value"),
            Output("forecast-irrigation", "value"),
            Output("forecast-area-ha", "value"),
            Output("forecast-prep-sol", "value"),
            Output("forecast-seed-type", "value"),
            Output("forecast-post-harvest", "value"),
            Output("forecast-labor-type", "value"),
        ],
        Input("forecast-reset-scenarios", "n_clicks"),
        prevent_initial_call=True,
    )
    def reset_forecast_ui(_reset):
        return (
            "Kaolack",      # department
            "ML",           # crop
            "court",        # cycle
            1,              # simulation_mode
            "FRESAMPLER1",  # downscaling method
            20,             # realizations
            False,          # fertilization
            "NONE",         # irrigation
            1,              # area_ha
            ["Labour"],     # prep_sol
            "Semence locale",  # seed_type
            [],             # post_harvest
            ["Semis"],      # labor_type
        )

    @app.callback(
        [
            Output("forecast-seed-qty", "value"),
            Output("forecast-seed-price", "value"),
        ],
        Input("forecast-seed-type", "value"),
    )
    def seed_defaults(seed_type):
        d = SEEDS.get(seed_type, {})
        return d.get("qty", 0), d.get("price", 0)

    @app.callback(
        Output("forecast-prep-sol-cost", "value"),
        [Input("forecast-prep-sol", "value"), Input("forecast-area-ha", "value")],
    )
    def prep_cost(ops, area):
        return compute_soil_preparation_cost(ops, area)

    @app.callback(
        Output("forecast-seed-cost", "value"),
        [
            Input("forecast-seed-qty", "value"),
            Input("forecast-seed-price", "value"),
            Input("forecast-area-ha", "value"),
        ],
    )
    def seed_cost(qty, price, area):
        return compute_seed_cost(qty, price, area)

    @app.callback(
        Output("forecast-labor-cost", "value"),
        [Input("forecast-labor-type", "value"), Input("forecast-area-ha", "value")],
    )
    def labor_cost(ops, area):
        return compute_labor_cost(ops, area)

    @app.callback(
        Output("forecast-post-harvest-cost", "value"),
        [Input("forecast-post-harvest", "value"), Input("forecast-area-ha", "value")],
    )
    def post_cost(ops, area):
        return compute_post_harvest_cost(ops, area)

    @app.callback(
        Output("forecast-total-cost", "value"),
        [
            Input("forecast-prep-sol", "value"),
            Input("forecast-labor-type", "value"),
            Input("forecast-post-harvest", "value"),
            Input("forecast-seed-cost", "value"),
            Input("forecast-area-ha", "value"),
        ],
    )
    def total_cost(soil_ops, labor_ops, post_ops, seed_cost_value, area_ha):
        return compute_total_socio_cost(soil_ops, labor_ops, post_ops, seed_cost_value, area_ha)

    @app.callback(
        [Output("forecast-fertilization-store", "data"), Output("forecast-fert-total-cost", "value")],
        [
            Input("forecast-fertilization", "value"),
            Input("forecast-add-fertilization", "n_clicks"),
            Input({"type": "forecast_fert_type", "index": ALL}, "value"),
            Input({"type": "forecast_fert_qty", "index": ALL}, "value"),
        ],
        State("forecast-fertilization-store", "data"),
    )
    def manage_fert(use, add_clicks, types, qtys, store):
        if not use:
            return [], 0
        store = store or [{"type": "NPK", "qty": 150}]
        triggered = (add_clicks or 0) > len(store) - 1
        if triggered:
            store.append(store[-1].copy())
        total = 0
        for i, r in enumerate(store):
            if i < len(types):
                r["type"] = types[i]
            if i < len(qtys):
                r["qty"] = qtys[i]
            total += compute_fertilization_cost(r.get("type"), r.get("qty"))
        return store, int(round(total))

    @app.callback(Output("forecast-fertilization-lines", "children"), Input("forecast-fertilization-store", "data"))
    def render_fert_lines(data):
        rows = []
        for i, r in enumerate(data or []):
            rows.append(
                dbc.Row(
                    [
                        dbc.Col(
                            dcc.Dropdown(
                                id={"type": "forecast_fert_type", "index": i},
                                options=[
                                    {"label": "Compost", "value": "COMPOST"},
                                    {"label": "NPK", "value": "NPK"},
                                    {"label": "Uree", "value": "UREA"},
                                ],
                                value=r.get("type", "NPK"),
                            ),
                            md=4,
                        ),
                        dbc.Col(dbc.Input(id={"type": "forecast_fert_qty", "index": i}, type="number", value=r.get("qty", 150)), md=4),
                        dbc.Col(dbc.Input(disabled=True, value=int(round(compute_fertilization_cost(r.get("type"), r.get("qty"))))), md=4),
                    ],
                    className="mb-1",
                )
            )
        return rows

    @app.callback(
        Output("forecast-fert-npk-summary", "children"),
        Input("forecast-fertilization-store", "data"),
    )
    def update_forecast_npk_summary(store):
        if not store:
            return "Aucun apport calcule"
        N = P = K = 0.0
        for f in store:
            npk = compute_npk_from_fertilizer(f.get("type"), f.get("qty"))
            N += npk.get("N", 0) or 0
            P += npk.get("P", 0) or 0
            K += npk.get("K", 0) or 0
        return f"N = {N:.1f} | P = {P:.1f} | K = {K:.1f} kg/ha"

    @app.callback(
        [Output("forecast-irrigation-store", "data"), Output("forecast-irrig-cost", "value")],
        [
            Input("forecast-irrigation", "value"),
            Input("forecast-add-irrigation", "n_clicks"),
            Input("forecast-auto-irrigation", "n_clicks"),
            Input({"type": "forecast_irrig_name", "index": ALL}, "value"),
            Input({"type": "forecast_irrig_day", "index": ALL}, "value"),
            Input({"type": "forecast_irrig_mm", "index": ALL}, "value"),
            Input({"type": "forecast_irrig_price", "index": ALL}, "value"),
        ],
        [
            State("forecast-irrigation-store", "data"),
            State("forecast-crop", "value"),
        ],
    )
    def manage_irrig(mode, add_clicks, auto_clicks, names, days, mms, prices, store, crop):
        if mode != "MANUAL":
            return [], 0
        store = store or [{"name": "Irrigation 1", "doy": 20, "mm": 20, "price": 250}]
        trig = get_triggered_id()
        if trig == "forecast-auto-irrigation":
            irr_days, water_mm = get_irrigation_schedule(crop or "ML")
            if irr_days and water_mm:
                store = [
                    {
                        "name": f"Irrigation {i+1}",
                        "doy": int(d),
                        "mm": float(water_mm),
                        "price": float(DEFAULT_IRRIGATION_PRICE),
                    }
                    for i, d in enumerate(irr_days)
                ]
        elif trig == "forecast-add-irrigation":
            i = len(store) + 1
            store.append({"name": f"Irrigation {i}", "doy": 20, "mm": 20, "price": 250})
        for i, r in enumerate(store):
            if i < len(names):
                r["name"] = names[i]
            if i < len(days):
                r["doy"] = days[i]
            if i < len(mms):
                r["mm"] = mms[i]
            if i < len(prices):
                r["price"] = prices[i]
        total = 0
        for r in store:
            total += (r.get("mm") or 0) * (r.get("price") or 0)
        return store, int(round(total))

    @app.callback(Output("forecast-irrigation-lines", "children"), Input("forecast-irrigation-store", "data"))
    def render_irrig_lines(data):
        rows = []
        for i, r in enumerate(data or []):
            cost = int(round((r.get("mm") or 0) * (r.get("price") or 0)))
            rows.append(
                dbc.Row(
                    [
                        dbc.Col(dbc.Input(id={"type": "forecast_irrig_name", "index": i}, type="text", value=r.get("name", f"Irrigation {i+1}")), md=3),
                        dbc.Col(dbc.Input(id={"type": "forecast_irrig_day", "index": i}, type="number", value=r.get("doy", 20)), md=3),
                        dbc.Col(dbc.Input(id={"type": "forecast_irrig_mm", "index": i}, type="number", value=r.get("mm", 20)), md=2),
                        dbc.Col(dbc.Input(id={"type": "forecast_irrig_price", "index": i}, type="number", value=r.get("price", 250)), md=2),
                        dbc.Col(dbc.Input(disabled=True, value=cost), md=2),
                    ],
                    className="mb-1",
                )
            )
        return rows

    @app.callback(
        Output("forecast-irrig-summary", "children"),
        Input("forecast-irrigation-store", "data"),
    )
    def update_irrig_summary(store):
        if not store:
            return "Aucune irrigation definie"
        total_mm = sum((ir.get("mm") or 0) for ir in store)
        total_events = len(store)
        return f"{total_events} irrigations | Eau totale = {total_mm} mm"

    @app.callback(
        Output("forecast-scenario-store", "data"),
        [
            Input("forecast-add-scenario", "n_clicks"),
            Input("forecast-reset-scenarios", "n_clicks"),
            Input("forecast-import-simulation", "contents"),
        ],
        [
            State("forecast-scenario-store", "data"),
            State("forecast-import-simulation", "filename"),
            State("forecast-department", "value"),
            State("forecast-crop", "value"),
            State("forecast-cycle", "value"),
            State("forecast-simulation-mode", "value"),
            State("forecast-planting-date", "date"),
            State("forecast-target-year", "value"),
            State("forecast-downscaling-method", "value"),
            State("forecast-realizations", "value"),
            State("forecast-fertilization", "value"),
            State("forecast-fertilization-store", "data"),
            State("forecast-irrigation", "value"),
            State("forecast-irrigation-store", "data"),
            State("forecast-fert-total-cost", "value"),
            State("forecast-irrig-cost", "value"),
            State("forecast-total-cost", "value"),
            State("forecast-toggle-socio", "n_clicks"),
        ],
        prevent_initial_call=True,
    )
    def add_scenario(n_add, n_reset, import_contents, store, import_filename, dept, crop, cycle, simulation_mode, planting_date, target_year,
                     downscaling_method, realizations, fert, fert_plan, irrig, irrig_plan, fert_cost, irrig_cost, total_cost, socio_clicks):
        store = store or []
        trig = get_triggered_id()
        if trig == "forecast-reset-scenarios":
            return []
        if trig == "forecast-import-simulation":
            imported = _import_forecast_scenarios(import_contents, import_filename)
            max_scenarios = _parse_max_scenarios(simulation_mode)
            return (imported or [])[:max_scenarios]
        if trig != "forecast-add-scenario":
            return store

        max_scenarios = _parse_max_scenarios(simulation_mode)
        if len(store) >= max_scenarios:
            return store

        # Ensure stable unique IDs even after deletes/resets.
        next_idx = 1
        for s in store:
            sid = str(s.get("id_scenario", ""))
            m = re.match(r"^F(\d+)$", sid)
            if m:
                next_idx = max(next_idx, int(m.group(1)) + 1)
        y = int(target_year) if target_year is not None else datetime.now().year
        if y < datetime.now().year:
            y = datetime.now().year
        socio_enabled = (socio_clicks or 0) > 0
        fixed_cost = (total_cost or 0) if socio_enabled else 0
        irrig_enabled = irrig in ("MANUAL", "AUTO")
        irrig_method = irrig if irrig in ("MANUAL", "AUTO") else "NONE"
        scenario = build_scenario_from_ui(
            scenario_id=f"F{next_idx:03d}",
            department=dept,
            crop=crop,
            cycle=cycle,
            planting_date=planting_date,
            hist_start_year=y,
            hist_end_year=y,
            recommended_sowing_date="",
            recommended_sowing_prob=None,
            fertilization=fert,
            fertilization_plan=fert_plan or [],
            irrigation=irrig_enabled,
            irrigation_plan=(irrig_plan or []) if irrig_method == "MANUAL" else [],
            costs={
                "CropPrice": 200,
                "NFertCost": fert_cost or 0,
                "SeedCost": 0,
                "IrrigCost": irrig_cost or 0,
                "OtherVariableCosts": 0,
                "FixedCosts": fixed_cost,
            },
        )
        scenario.setdefault("irrigation", {})["method"] = irrig_method
        scenario.setdefault("dssat", {})["forecast_mode"] = True
        scenario.setdefault("economy", {})["SocioEnabled"] = socio_enabled
        scenario.setdefault("forecast", {})["downscaling_method"] = (downscaling_method or "FRESAMPLER1").upper()
        try:
            n_real = int(realizations or 20)
        except Exception:
            n_real = 20
        scenario.setdefault("forecast", {})["n_realizations"] = max(1, min(200, n_real))
        scenario.setdefault("forecast", {})["block_days"] = FRESAMPLER_DEFAULT_BLOCK_DAYS
        store.append(scenario)
        return store

    @app.callback(
        [Output("forecast-scenario-table", "data"), Output("forecast-scenario-table", "columns")],
        Input("forecast-scenario-store", "data"),
        Input("forecast-results-store", "data"),
    )
    def render_table(scenarios, results):
        scenarios = scenarios or []
        results = results or {}
        if not scenarios:
            return [], []
        rows = []
        for s in scenarios:
            sid = s.get("id_scenario")
            m = results.get(sid, {})
            row = _forecast_scenario_to_table_row(s)
            row["DSSAT:Status"] = m.get("status", "-")
            row["DSSAT:HARWT"] = m.get("HARWT", "-")
            row["DSSAT:HARWT_P20"] = m.get("HARWT_P20", "-")
            row["DSSAT:HARWT_P80"] = m.get("HARWT_P80", "-")
            row["DSSAT:TOPWT"] = m.get("TOPWT", "-")
            row["DSSAT:RAIN"] = m.get("RAIN", "-")
            row["DSSAT:TIRR"] = m.get("TIRR", "-")
            row["DSSAT:CET"] = m.get("CET", "-")
            row["DSSAT:MAT"] = m.get("MAT", "-")
            rows.append(row)

        col_order = [
            "ID", "Departement", "Culture", "Cycle", "Semis",
            "Fertilisation", "Irrigation",
            "Cout fertilisation (FCFA)", "Cout irrigation (FCFA)",
            "Cout production (FCFA)", "Cout total (FCFA)",
            "DSSAT:Status", "DSSAT:HARWT", "DSSAT:HARWT_P20", "DSSAT:HARWT_P80", "DSSAT:TOPWT",
            "DSSAT:RAIN", "DSSAT:TIRR", "DSSAT:CET", "DSSAT:MAT",
        ]
        cols = [{"name": c, "id": c} for c in col_order]
        return rows, cols

    @app.callback(
        [Output("forecast-comparison-output", "children"), Output("forecast-results-store", "data")],
        [
            Input("forecast-run-simulation", "n_clicks"),
            Input("forecast-reset-scenarios", "n_clicks"),
            Input("forecast-import-simulation", "contents"),
        ],
        [
            State("forecast-scenario-store", "data"),
            State("forecast-results-store", "data"),
            State("forecast-simulation-mode", "value"),
        ],
        prevent_initial_call=True,
    )
    def run_forecast(n_run, n_reset, import_contents, scenarios, results_store, simulation_mode):
        trig = get_triggered_id()
        if trig == "forecast-reset-scenarios":
            return "Ajoutez un scenario previsionnel puis cliquez sur Simuler.", {}
        if trig == "forecast-import-simulation":
            return "Simulation importee. Cliquez sur Simuler pour la relancer.", {}
        if trig != "forecast-run-simulation":
            return "Cliquez sur Simuler.", (results_store or {})
        scenarios = scenarios or []
        if not scenarios:
            return "Aucun scenario previsionnel a simuler.", (results_store or {})
        max_scenarios = _parse_max_scenarios(simulation_mode)
        scenarios = scenarios[:max_scenarios]

        # Always start forecast runs from a clean results set.
        out = {}
        msgs = []
        for i, scenario in enumerate(scenarios, start=1):
            sid = scenario.get("id_scenario")
            try:
                # Rebuild each forecast scenario from scratch to avoid carry-over.
                scenario_run = copy.deepcopy(scenario or {})
                scenario_run.pop("dssat", None)
                scenario_run.pop("results", None)
                scenario_run = _prepare_forecast_scenario_for_dssat(scenario_run)
                scenario_run.setdefault("dssat", {})["forecast_mode"] = True
                # Force unique DSSAT run name per scenario in this batch run.
                scenario_run.setdefault("dssat", {})["sce_name"] = f"F{i:03d}"
                base_cycle_days = _forecast_cycle_days(scenario_run.get("crop", {}).get("code"))
                # DSSAT can access a few days beyond harvest; add buffer for WTH coverage.
                wth_cycle_days = base_cycle_days + 15
                scenario_run.setdefault("dssat", {})["cycle_days"] = base_cycle_days
                totals = _scenario_ui_agro_totals(scenario_run)

                # Guardrails: if user enabled fert/irrig, corresponding plans must exist.
                if scenario_run.get("fertilization", {}).get("enabled") and not scenario_run.get("fertilization", {}).get("applications"):
                    out[sid] = {"status": "ERREUR"}
                    msgs.append(f"Scenario {i} - fertilisation activee mais aucun apport defini")
                    continue
                if scenario_run.get("fertilization", {}).get("enabled"):
                    apps = scenario_run.get("fertilization", {}).get("applications") or []
                    total_npk = totals["n_tot"] + totals["p_tot"] + totals["k_tot"]
                    for a in apps:
                        fdate = _to_float(a.get("doy"))
                        # Accept either JAS (0..366) or DSSAT absolute YYDDD (e.g. 26167).
                        is_jas = fdate is not None and 0 <= fdate <= 366
                        is_yydoy = fdate is not None and 10000 <= fdate <= 99366
                        if not (is_jas or is_yydoy):
                            out[sid] = {"status": "ERREUR"}
                            msgs.append(
                                f"Scenario {i} - fertilisation invalide: FDATE doit etre JAS (0..366) "
                                f"ou YYDDD (ex: 26167)"
                            )
                            total_npk = -1
                            break
                    if total_npk < 0:
                        continue
                    if total_npk <= 0:
                        out[sid] = {"status": "ERREUR"}
                        msgs.append(f"Scenario {i} - fertilisation cochee mais apports N/P/K nuls")
                        continue
                if scenario_run.get("irrigation", {}).get("enabled") and (scenario_run.get("irrigation", {}).get("method") == "MANUAL") and not scenario_run.get("irrigation", {}).get("schedule"):
                    out[sid] = {"status": "ERREUR"}
                    msgs.append(f"Scenario {i} - irrigation activee mais aucun tour d'eau defini")
                    continue
                if scenario_run.get("irrigation", {}).get("enabled") and (scenario_run.get("irrigation", {}).get("method") == "MANUAL") and totals["irr_mm"] <= 0:
                    out[sid] = {"status": "ERREUR"}
                    msgs.append(f"Scenario {i} - irrigation activee mais volume total nul")
                    continue
                msgs.append(
                    f"Scenario {i} - controle UI: N={totals['n_tot']:.1f} P={totals['p_tot']:.1f} "
                    f"K={totals['k_tot']:.1f} kg/ha | irrigation={totals['irr_mm']:.1f} mm ({totals['irr_n']} tours)"
                )

                dept = scenario_run.get("location", {}).get("department")
                fpath = forecast_file_for_department(dept)
                if fpath is None or not fpath.exists():
                    out[sid] = {"status": "ERREUR"}
                    msgs.append(f"Scenario {i} - fichier forecast manquant")
                    continue
                msgs.append(
                    f"Scenario {i} - controle entree: semis={scenario_run.get('crop', {}).get('planting_date')} "
                    f"| station={scenario_run.get('location', {}).get('station_code')} | fichier={fpath.name}"
                )
                df_forecast = load_forecast_dataframe(dept)
                pdt = pd.to_datetime(
                    scenario_run.get("crop", {}).get("planting_date") or scenario_run.get("dssat", {}).get("PltDate"),
                    errors="coerce",
                )
                if not pd.isna(pdt):
                    w0 = pdt.normalize()
                    w1 = (pdt + pd.Timedelta(days=210)).normalize()
                    wdf = df_forecast[(df_forecast["date"] >= w0) & (df_forecast["date"] <= w1)]
                    rain_sum = float(wdf["rain"].sum()) if not wdf.empty else 0.0
                    msgs.append(f"Scenario {i} - audit forecast: pluie cumulee fenetre campagne = {rain_sum:.1f} mm ({fpath.name})")

                # Forecast-only stochastic downscaling (FResampler1) configuration.
                fcfg = scenario_run.get("forecast", {}) or {}
                method = str(fcfg.get("downscaling_method", "FRESAMPLER1") or "FRESAMPLER1").upper()
                try:
                    n_real = int(fcfg.get("n_realizations", 20) or 20)
                except Exception:
                    n_real = 20
                n_real = max(1, min(200, n_real))
                try:
                    block_days = int(fcfg.get("block_days", FRESAMPLER_DEFAULT_BLOCK_DAYS) or FRESAMPLER_DEFAULT_BLOCK_DAYS)
                except Exception:
                    block_days = FRESAMPLER_DEFAULT_BLOCK_DAYS
                block_days = max(1, block_days)

                realizations = []
                if method == "FRESAMPLER1":
                    seed = abs(hash(f"{sid}:{i}")) % (2**31)
                    probs = fcfg.get("terciles") or fcfg.get("probs")
                    realizations = generate_fresampler_realizations_for_scenario(
                        scenario_run,
                        cycle_days=wth_cycle_days,
                        n_realizations=n_real,
                        block_days=block_days,
                        probs=probs,
                        random_seed=seed,
                    )
                    counts = {}
                    for rr in realizations:
                        counts[rr["category"]] = counts.get(rr["category"], 0) + 1
                    msgs.append(
                        f"Scenario {i} - Prevision probabiliste: {len(realizations)} realisations "
                        f"(BN={counts.get('BN',0)}, NN={counts.get('NN',0)}, AN={counts.get('AN',0)})"
                    )
                    write_forecast_wth_from_dataframe(scenario_run, realizations[0]["weather_df"], BASE_DIR / "dssat")
                else:
                    write_forecast_wth_for_scenario(scenario_run, BASE_DIR / "dssat", cycle_days=wth_cycle_days)

                val = validate_forecast_inputs(scenario_run, BASE_DIR, cycle_days=wth_cycle_days)
                if val.get("errors"):
                    out[sid] = {"status": "ERREUR"}
                    msgs.append(f"Scenario {i} - erreurs validation: {' | '.join(val['errors'][:2])}")
                    continue

                x_path = write_x_file(scenario_run, output_dir=str(BASE_DIR / "dssat" / "exp"))
                snx_output_dir = BASE_DIR / "dssat" / "snx"
                snx_output_dir.mkdir(parents=True, exist_ok=True)
                snx_path = Path(write_snx_file(scenario_run, x_path.name, output_dir=str(snx_output_dir)))
                has_fert_inputs = _snx_has_fertilizer_inputs(snx_path)
                if scenario_run.get("fertilization", {}).get("enabled") and not has_fert_inputs:
                    out[sid] = {"status": "ERREUR"}
                    msgs.append(f"Scenario {i} - fertilisation cochee mais aucun apport N/P/K > 0 ecrit dans le SNX")
                    continue

                metrics_all = []
                warns = []
                failed_runs = 0
                failed_crop_failure = 0
                run_count = len(realizations) if realizations else 1

                for ridx in range(run_count):
                    if realizations and ridx > 0:
                        write_forecast_wth_from_dataframe(
                            scenario_run,
                            realizations[ridx]["weather_df"],
                            BASE_DIR / "dssat",
                        )

                    r = run_dssat_simulation(str(snx_path), dssat_workdir=str(BASE_DIR / "dssat"))
                    rc = int(r.get("returncode") or 0)
                    if rc != 0:
                        # DSSAT code 10 often indicates crop establishment failure
                        # (no emergence / no growth), not necessarily an input format crash.
                        if rc == 10:
                            failed_crop_failure += 1
                        failed_runs += 1
                        continue

                    run_metrics = _parse_run_metrics_from_stdout(r.get("stdout", ""))
                    summary_metrics = _parse_summary_metrics(BASE_DIR / "dssat" / "Summary.OUT")
                    m_run = _merge_metrics(run_metrics, summary_metrics)
                    metrics_all.append(m_run)

                if not metrics_all:
                    if failed_crop_failure == run_count and run_count > 0:
                        out[sid] = {
                            "status": "VIDE",
                            "HARWT": "0",
                            "HARWT_P20": "0",
                            "HARWT_P80": "0",
                            "TOPWT": "0",
                            "RAIN": "0",
                            "TIRR": "0",
                            "CET": "0",
                            "MAT": "-",
                            "NREAL": run_count,
                        }
                        msgs.append(
                            f"Scenario {i} - toutes les realisations ont echoue a l'installation (code DSSAT 10). "
                            f"Verifier date de semis (souvent trop precoce) et/ou eau au semis."
                        )
                        continue
                    out[sid] = {"status": "ERREUR"}
                    msgs.append(f"Scenario {i} - DSSAT erreur ({failed_runs}/{run_count} realisations en echec)")
                    continue

                m = _aggregate_ensemble_metrics(metrics_all)
                out[sid] = m

                if scenario_run.get("irrigation", {}).get("enabled"):
                    tirr_val = _to_float(m.get("TIRR"))
                    if tirr_val is None or tirr_val <= 0:
                        warns.append("irrigation cochee mais TIRR=0 dans les sorties DSSAT")

                if scenario_run.get("fertilization", {}).get("enabled") and has_fert_inputs:
                    fert_vals = [_to_float(x.get("FERTN")) for x in metrics_all]
                    fert_vals = [v for v in fert_vals if v is not None]
                    if fert_vals and max(fert_vals) <= 0:
                        warns.append("fertilisation bien ecrite dans SNX mais NICM/NI#M=0 (pas d'engrais mineral comptabilise par DSSAT)")

                rain_prcm = _to_float(m.get("RAIN"))
                rain_seas_vals = [_to_float(x.get("RAIN_SEAS")) for x in metrics_all]
                rain_seas_vals = [v for v in rain_seas_vals if v is not None]
                if (rain_prcm is None or rain_prcm == 0) and rain_seas_vals and max(rain_seas_vals) > 0:
                    warns.append(
                        f"RAIN (PRCM)=0 mais PRCP median={pd.Series(rain_seas_vals).median():.1f} mm dans Summary.OUT"
                    )

                if len(metrics_all) > 1:
                    msgs.append(
                        f"Scenario {i} - prevision simulee ({len(metrics_all)} realisations, {failed_runs} echecs): "
                        f"HARWT median={m.get('HARWT','-')} kg/ha "
                        f"[P20={m.get('HARWT_P20','-')} ; P80={m.get('HARWT_P80','-')}]"
                    )
                else:
                    msgs.append(f"Scenario {i} - prevision simulee: HARWT={m.get('HARWT','-')} kg/ha")

                seen = set()
                for w in warns:
                    if w in seen:
                        continue
                    seen.add(w)
                    msgs.append(f"Scenario {i} - {w}")
            except Exception as e:
                out[sid] = {"status": "ERREUR"}
                msgs.append(f"Scenario {i} - erreur prevision: {str(e)[:180]}")
        return _build_forecast_results_view(scenarios, out, msgs), out
