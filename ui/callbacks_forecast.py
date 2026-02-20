try:
    from dash import html, dcc, ctx
except Exception:
    import dash_html_components as html
    import dash_core_components as dcc
    from dash import callback_context as ctx
from dash.dependencies import Input, Output, State, ALL
import dash_bootstrap_components as dbc
import json
import re
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
    forecast_file_for_department,
    load_forecast_dataframe,
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


def _to_float(value):
    try:
        return float(str(value).strip())
    except Exception:
        return None


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
    return copy.deepcopy(scenario)


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
        allowed_start = max(min_d, yr_start) if not pd.isna(min_d) else yr_start
        allowed_end = min(max_d, yr_end) if not pd.isna(max_d) else yr_end

        start, end, msg = _recommended_sowing_window(df, target_year, department)
        if start is not None:
            recommended = start.isoformat()
            txt = f"{msg}. Regle: cumul pluie >= seuil sur 1-3 jours, puis pas de pause seche de 20 jours."
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
            return [14.15, -16.07], 6, [14.15, -16.07], None, [], None, "Departement"
        lat, lon = get_department_gps(dept_name)
        soil = get_department_soil(dept_name) or "-"
        geojson = None
        try:
            with open(GEOJSON_PATH, encoding="utf-8") as f:
                geo = json.load(f)
            target = str(dept_name).lower().replace("-", " ").strip()
            for ft in geo.get("features", []):
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
        return [lat, lon], 10, [lat, lon], geojson, [{"label": soil, "value": soil}], soil, f"{dept_name} | Sol: {soil}"

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
        [Input("forecast-add-scenario", "n_clicks"), Input("forecast-reset-scenarios", "n_clicks")],
        [
            State("forecast-scenario-store", "data"),
            State("forecast-department", "value"),
            State("forecast-crop", "value"),
            State("forecast-cycle", "value"),
            State("forecast-planting-date", "date"),
            State("forecast-target-year", "value"),
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
    def add_scenario(n_add, n_reset, store, dept, crop, cycle, planting_date, target_year,
                     fert, fert_plan, irrig, irrig_plan, fert_cost, irrig_cost, total_cost, socio_clicks):
        store = store or []
        trig = get_triggered_id()
        if trig == "forecast-reset-scenarios":
            return []
        if trig != "forecast-add-scenario":
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
            "DSSAT:Status", "DSSAT:HARWT", "DSSAT:TOPWT",
            "DSSAT:RAIN", "DSSAT:TIRR", "DSSAT:CET", "DSSAT:MAT",
        ]
        cols = [{"name": c, "id": c} for c in col_order]
        return rows, cols

    @app.callback(
        [Output("forecast-comparison-output", "children"), Output("forecast-results-store", "data")],
        [Input("forecast-run-simulation", "n_clicks"), Input("forecast-reset-scenarios", "n_clicks")],
        [State("forecast-scenario-store", "data"), State("forecast-results-store", "data")],
        prevent_initial_call=True,
    )
    def run_forecast(n_run, n_reset, scenarios, results_store):
        if (n_reset or 0) > 0 and (n_reset or 0) >= (n_run or 0):
            return "Ajoutez un scenario previsionnel puis cliquez sur Simuler.", {}
        scenarios = scenarios or []
        if not scenarios:
            return "Aucun scenario previsionnel a simuler.", (results_store or {})

        trig = get_triggered_id()
        # Always start forecast runs from a clean results set.
        out = {} if trig == "forecast-run-simulation" else dict(results_store or {})
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
                # Prevents two scenarios from writing/reading the same CLMLF00X.SNX.
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
                r = run_dssat_simulation(str(snx_path), dssat_workdir=str(BASE_DIR / "dssat"))
                if r.get("returncode") != 0:
                    out[sid] = {"status": "ERREUR"}
                    msgs.append(f"Scenario {i} - DSSAT erreur ({r.get('returncode')})")
                    continue
                # parse rapide Summary.OUT
                m = {"status": "SUCCES"}
                warns = []
                run_metrics = _parse_run_metrics_from_stdout(r.get("stdout", ""))
                sp = BASE_DIR / "dssat" / "Summary.OUT"
                if sp.exists():
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
                    if head and vals:
                        row = {k: vals[idx] for idx, k in enumerate(head) if idx < len(vals)}
                        for k in ["HWAM", "CWAM", "PRCM", "IRCM", "ETCM", "MDAPS"]:
                            if k in row:
                                pass
                        m["HARWT"] = row.get("HWAM", "-")
                        m["TOPWT"] = row.get("CWAM", "-")
                        m["RAIN"] = row.get("PRCM", "-")
                        m["RAIN_SEAS"] = row.get("PRCP", "-")
                        m["TIRR"] = row.get("IRCM", "-")
                        m["CET"] = row.get("ETCM", "-")
                        m["MAT"] = row.get("MDAPS", "-")
                        m["FERTN"] = row.get("NICM", row.get("NI#M", "-"))
                        if scenario_run.get("irrigation", {}).get("enabled"):
                            tirr_val = _to_float(m.get("TIRR"))
                            if tirr_val is None or tirr_val <= 0:
                                warns.append("irrigation cochee mais TIRR=0 dans les sorties DSSAT")
                        if scenario_run.get("fertilization", {}).get("enabled") and has_fert_inputs:
                            fertn_val = _to_float(m.get("FERTN"))
                            if fertn_val is None or fertn_val <= 0:
                                warns.append("fertilisation bien ecrite dans SNX mais NICM/NI#M=0 (pas d'engrais mineral comptabilise par DSSAT)")
                        rain_prcm = _to_float(m.get("RAIN"))
                        rain_prcp = _to_float(m.get("RAIN_SEAS"))
                        if (rain_prcm is None or rain_prcm == 0) and (rain_prcp is not None and rain_prcp > 0):
                            warns.append(
                                f"RAIN (PRCM)=0 mais PRCP={rain_prcp:.1f} mm dans Summary.OUT (pluie saisonniere detectee)"
                            )
                # Prefer RUN metrics from DSSAT console if available (less ambiguous than Summary split parsing).
                for key in ["HARWT", "TOPWT", "RAIN", "TIRR", "CET", "MAT"]:
                    if key in run_metrics:
                        m[key] = run_metrics[key]
                rain_disp = _to_float(m.get("RAIN"))
                rain_seas = _to_float(m.get("RAIN_SEAS"))
                if (rain_disp is None or rain_disp == 0) and (rain_seas is not None and rain_seas > 0):
                    m["RAIN"] = f"{rain_seas:.1f}"
                # Re-check critical controls against final displayed metrics.
                if scenario_run.get("irrigation", {}).get("enabled"):
                    tirr_val = _to_float(m.get("TIRR"))
                    if tirr_val is None or tirr_val <= 0:
                        warns.append("irrigation cochee mais TIRR=0 dans les sorties DSSAT")
                out[sid] = m
                msgs.append(f"Scenario {i} - prevision simulee: HARWT={m.get('HARWT','-')} kg/ha")
                seen = set()
                for w in warns:
                    if w in seen:
                        continue
                    seen.add(w)
                    msgs.append(f"Scenario {i} - ⚠️ {w}")
            except Exception as e:
                out[sid] = {"status": "ERREUR"}
                msgs.append(f"Scenario {i} - erreur prevision: {str(e)[:180]}")
        return html.Ul([html.Li(m) for m in msgs]), out
