try:
    from dash import html, dcc, ctx
except Exception:
    import dash_html_components as html
    import dash_core_components as dcc
    from dash import callback_context as ctx
from dash.dependencies import Input, Output, State, ALL
import dash_bootstrap_components as dbc
import json
from pathlib import Path
from datetime import datetime
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
from domain.fertilisation import compute_fertilization_cost
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


def _is_north_department(department):
    try:
        lat, _ = get_department_gps(department)
        return lat >= 14.2
    except Exception:
        return False


def _recommended_sowing_window(df, target_year, department):
    year_df = df[df["date"].dt.year == int(target_year)].copy()
    year_df = year_df.sort_values("date").reset_index(drop=True)
    if year_df.empty:
        return None, None, "Aucune donnee forecast sur l'annee cible"
    threshold = 15.0 if _is_north_department(department) else 20.0
    candidates = []
    n = len(year_df)
    for i in range(0, n - 1):
        r2 = float(year_df.loc[i, "rain"] or 0) + float(year_df.loc[i + 1, "rain"] or 0)
        if r2 < threshold:
            continue
        next20 = year_df.iloc[i + 2 : i + 22]
        if len(next20) < 20:
            continue
        # Reject if immediately followed by 20 dry days.
        if float(next20["rain"].sum()) <= 0:
            continue
        candidates.append(year_df.loc[i, "date"].date())
    if not candidates:
        return None, None, (
            f"Aucune date detectee (regle: >= {threshold:.0f} mm sur 2 jours "
            f"et pas 20 jours secs juste apres)"
        )
    start = candidates[0]
    end = min(candidates[-1], start + pd.Timedelta(days=10))
    return start, end, (
        f"Fenetre conseillee ({int(target_year)}): {start} au {end} "
        f"(seuil {threshold:.0f} mm/2j)"
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
            txt = f"{msg}. Regle: 2 jours >= seuil, puis pas 20 jours secs."
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
    def toggle_irrig(use):
        return {"display": "block"} if use else {"display": "none"}

    @app.callback(
        Output("forecast-socio-block", "style"),
        Input("forecast-toggle-socio", "n_clicks"),
        prevent_initial_call=True,
    )
    def toggle_socio(_):
        return {"display": "block"}

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
        [Output("forecast-irrigation-store", "data"), Output("forecast-irrig-cost", "value")],
        [
            Input("forecast-irrigation", "value"),
            Input("forecast-add-irrigation", "n_clicks"),
            Input({"type": "forecast_irrig_name", "index": ALL}, "value"),
            Input({"type": "forecast_irrig_day", "index": ALL}, "value"),
            Input({"type": "forecast_irrig_mm", "index": ALL}, "value"),
            Input({"type": "forecast_irrig_price", "index": ALL}, "value"),
        ],
        State("forecast-irrigation-store", "data"),
    )
    def manage_irrig(use, add_clicks, names, days, mms, prices, store):
        if not use:
            return [], 0
        store = store or [{"name": "Irrigation 1", "doy": 20, "mm": 20, "price": 250}]
        if get_triggered_id() == "forecast-add-irrigation":
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
        if (n_reset or 0) > 0 and (n_reset or 0) >= (n_add or 0):
            return []
        y = int(target_year) if target_year is not None else datetime.now().year
        if y < datetime.now().year:
            y = datetime.now().year
        socio_enabled = (socio_clicks or 0) > 0
        fixed_cost = (total_cost or 0) if socio_enabled else 0
        scenario = build_scenario_from_ui(
            scenario_id=f"F{len(store)+1:03d}",
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
            irrigation=irrig,
            irrigation_plan=irrig_plan or [],
            costs={
                "CropPrice": 200,
                "NFertCost": fert_cost or 0,
                "SeedCost": 0,
                "IrrigCost": irrig_cost or 0,
                "OtherVariableCosts": 0,
                "FixedCosts": fixed_cost,
            },
        )
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
            eco = s.get("economy", {})
            fixed_cost = (eco.get("FixedCosts", 0) or 0) if eco.get("SocioEnabled") else 0
            rows.append({
                "ID": sid,
                "Departement": s.get("location", {}).get("department"),
                "Culture": s.get("crop", {}).get("code"),
                "Semis": s.get("crop", {}).get("planting_date"),
                "Cout total (FCFA)": int(round((eco.get("NFertCost", 0) or 0) + (eco.get("IrrigCost", 0) or 0) + fixed_cost)),
                "DSSAT:Status": m.get("status", "-"),
                "HARWT": m.get("HARWT", "-"),
                "TOPWT": m.get("TOPWT", "-"),
                "RAIN": m.get("RAIN", "-"),
                "TIRR": m.get("TIRR", "-"),
                "CET": m.get("CET", "-"),
                "MAT": m.get("MAT", "-"),
            })
        cols = [{"name": c, "id": c} for c in rows[0].keys()]
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

        out = dict(results_store or {})
        msgs = []
        for i, scenario in enumerate(scenarios, start=1):
            sid = scenario.get("id_scenario")
            try:
                fpath = forecast_file_for_department(scenario.get("location", {}).get("department"))
                if fpath is None or not fpath.exists():
                    out[sid] = {"status": "ERREUR"}
                    msgs.append(f"Scenario {i} - fichier forecast manquant")
                    continue
                load_forecast_dataframe(scenario.get("location", {}).get("department"))

                write_forecast_wth_for_scenario(scenario, BASE_DIR / "dssat", cycle_days=210)
                val = validate_forecast_inputs(scenario, BASE_DIR, cycle_days=210)
                if val.get("errors"):
                    out[sid] = {"status": "ERREUR"}
                    msgs.append(f"Scenario {i} - erreurs validation: {' | '.join(val['errors'][:2])}")
                    continue

                x_path = write_x_file(scenario, output_dir=str(BASE_DIR / "dssat" / "exp"))
                snx_output_dir = BASE_DIR / "dssat" / "snx"
                snx_output_dir.mkdir(parents=True, exist_ok=True)
                snx_path = Path(write_snx_file(scenario, x_path.name, output_dir=str(snx_output_dir)))
                r = run_dssat_simulation(str(snx_path), dssat_workdir=str(BASE_DIR / "dssat"))
                if r.get("returncode") != 0:
                    out[sid] = {"status": "ERREUR"}
                    msgs.append(f"Scenario {i} - DSSAT erreur ({r.get('returncode')})")
                    continue
                # parse rapide Summary.OUT
                m = {"status": "SUCCES"}
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
                            continue
                        if head and s[:1].isdigit():
                            vals = s.split()
                            break
                    if head and vals:
                        row = {k: vals[idx] for idx, k in enumerate(head) if idx < len(vals)}
                        for k in ["HWAM", "CWAM", "PRCM", "IRCM", "ETCM", "MDAPS"]:
                            if k in row:
                                pass
                        m["HARWT"] = row.get("HWAM", "-")
                        m["TOPWT"] = row.get("CWAM", "-")
                        m["RAIN"] = row.get("PRCM", "-")
                        m["TIRR"] = row.get("IRCM", "-")
                        m["CET"] = row.get("ETCM", "-")
                        m["MAT"] = row.get("MDAPS", "-")
                out[sid] = m
                msgs.append(f"Scenario {i} - prevision simulee: HARWT={m.get('HARWT','-')} kg/ha")
            except Exception as e:
                out[sid] = {"status": "ERREUR"}
                msgs.append(f"Scenario {i} - erreur prevision: {str(e)[:180]}")
        return html.Ul([html.Li(m) for m in msgs]), out
