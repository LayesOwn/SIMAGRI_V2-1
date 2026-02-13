# ==========================================================
# ui/callbacks.py
# Callbacks Dash – SIMAGRI v2
# ==========================================================

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
import re
from datetime import datetime, timedelta
import unicodedata

# --- Imports domaine métier
from domain.geography import get_department_gps, get_department_soil
from domain.climate.enacts import load_enacts, compute_probabilistic_onset
from domain.climate.weather import ensure_weather_for_scenario, generate_all_department_wth
from domain.irrigation import get_irrigation_schedule, compute_irrigation_cost
from domain.fertilisation import (
    compute_fertilization_cost,
    compute_npk_from_fertilizer,
)
from domain.socio_eco import (
    SEEDS,
    compute_seed_cost,
    compute_soil_preparation_cost,
    compute_labor_cost,
    compute_post_harvest_cost,
    compute_total_socio_cost,
)
from domain.scenario import build_scenario_from_ui, DSSAT_COLUMNS
from domain.decision import evaluate_scenarios
from domain.dssat.write_xfile import write_x_file
from domain.dssat.write_snx import write_snx_file
from domain.dssat.run_dssat import run_dssat_simulation
from domain.dssat.validate_inputs import validate_dssat_inputs
from domain.dssat.validate_inputs import _find_wth_file, _parse_wth_dates, _parse_planting_date
import os
from pathlib import Path

# ==========================================================
# CONFIGURATION DES CHEMINS
# ==========================================================
# Depuis ui/callbacks.py (ui/ -> SIMAGRI_V3/), on remonte 2 niveaux


# Déterminer BASE_DIR selon l'environnement
if os.getenv('SIMAGRI_ENV') == 'docker':
    # En Docker, on est déjà dans /app
    BASE_DIR = Path('/app')
else:
    # En local (Windows)
    _temp = Path(__file__).resolve().parents[2]
    
    # Assurer que BASE_DIR pointe à SIMAGRI_V3
    if _temp.name == "SIMAGRI_V3":
        BASE_DIR = _temp
    elif _temp.name == "simagri":
        # On a remonté trop haut, aller dans SIMAGRI_V3
        BASE_DIR = _temp / "SIMAGRI_V3"
    else:
        # Default
        BASE_DIR = _temp

print(f"✅ BASE_DIR = {BASE_DIR}")
print(f"   Existe ? {BASE_DIR.exists()}")
print(f"   dssat/ existe ? {(BASE_DIR / 'dssat').exists()}")
print(f"   Fichiers .WTH : {len(list((BASE_DIR / 'dssat').glob('*.WTH')))}")
try:
    generated = generate_all_department_wth(BASE_DIR / "dssat")
    print(f"   WTH générés (départements): {len(generated)}")
except Exception as e:
    print(f"   ⚠️ génération WTH départements: {e}")

GEOJSON_PATH = BASE_DIR / "data" / "geojson" / "senegal_departments.json"


def _norm_name(value):
    s = unicodedata.normalize("NFD", str(value or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


# ==========================================================
# 🔧 Fonction utilitaire (TABLE)
# ==========================================================
def scenario_to_table_row(s):
    """
    Convertit un scénario complet en une ligne pour la table d'affichage
    """
    economy = s.get("economy", {})
    fert_cost = economy.get("NFertCost", 0) or 0
    irrig_cost = economy.get("IrrigCost", 0) or 0
    production_cost = economy.get("FixedCosts", 0) or 0
    total_cost = fert_cost + irrig_cost + production_cost

    base = {
        "ID": s["id_scenario"],
        "Département": s["location"]["department"],
        "Culture": s["crop"]["code"],
        "Cycle": s["crop"]["cycle"],
        "Semis": s["crop"]["planting_date"],
        "Semis conseillé": s["climate"]["recommended_sowing_date"] or "-",
        "P(%)": (
            int(100 * s["climate"]["recommended_sowing_prob"])
            if s["climate"]["recommended_sowing_prob"] is not None
            else "-"
        ),
        "Fertilisation": s["fertilization"]["enabled"],
        "Irrigation": s["irrigation"]["enabled"],
        "Coût fertilisation (FCFA)": fert_cost,
        "Coût irrigation (FCFA)": irrig_cost,
        "Coût production (FCFA)": production_cost,
        "Coût total (FCFA)": total_cost,
    }

    dssat = s.get("dssat", {})
    # Ajouter tous les champs DSSAT même s'ils sont vides
    for col in DSSAT_COLUMNS:
        base[f"DSSAT:{col}"] = dssat.get(col, "")

    return base


def get_triggered_id():
    """
    Compat Dash v1/v2 pour récupérer l'id qui a déclenché le callback.
    """
    try:
        return ctx.triggered_id
    except Exception:
        triggered = getattr(ctx, "triggered", None) or []
        if not triggered:
            return None
        prop_id = triggered[0].get("prop_id", "")
        return prop_id.split(".")[0] if prop_id else None


def parse_summary_metrics(summary_path):
    """
    Parse les indicateurs clés DSSAT depuis Summary.OUT.
    """
    if not summary_path.exists():
        return {}

    try:
        lines = summary_path.read_text(encoding="latin-1", errors="ignore").splitlines()
    except Exception:
        return {}

    data_line = None
    for line in lines:
        if line.strip().startswith("RUN") or line.strip().startswith("dap"):
            continue
        if not re.match(r"^\s*\d+\s+[A-Z]{2}\s+", line):
            continue
        parts = line.split()
        if len(parts) >= 14:
            data_line = parts
    if not data_line:
        return {}

    keys = [
        "RUN", "TRT", "FLO", "MAT", "TOPWT", "HARWT",
        "RAIN", "TIRR", "CET", "PESW", "TNUP", "TNLF", "TSON", "TSOC",
    ]
    out = {}
    for i, key in enumerate(keys):
        if i < len(data_line):
            out[key] = data_line[i]
    return out


def format_metrics_short(metrics):
    if not metrics:
        return ""
    return (
        f"HARWT={metrics.get('HARWT', '-')}, "
        f"TOPWT={metrics.get('TOPWT', '-')}, "
        f"RAIN={metrics.get('RAIN', '-')}, "
        f"TIRR={metrics.get('TIRR', '-')}, "
        f"CET={metrics.get('CET', '-')}, "
        f"MAT={metrics.get('MAT', '-')}"
    )


def classify_dssat_status(metrics):
    """
    Retourne un statut simple: SUCCES, VIDE ou ERREUR.
    """
    if not metrics:
        return "ERREUR"
    harwt = str(metrics.get("HARWT", "")).strip()
    topwt = str(metrics.get("TOPWT", "")).strip()
    if harwt in {"-99", ""} and topwt in {"-99", ""}:
        return "VIDE"
    return "SUCCES"


def build_table(scenarios, sim_results):
    table_data = []
    for s in scenarios:
        row = scenario_to_table_row(s)
        sid = s.get("id_scenario")
        m = (sim_results or {}).get(sid, {})
        row["DSSAT:Status"] = m.get("status", "-")
        row["DSSAT:HARWT"] = m.get("HARWT", "-")
        row["DSSAT:TOPWT"] = m.get("TOPWT", "-")
        row["DSSAT:RAIN"] = m.get("RAIN", "-")
        row["DSSAT:TIRR"] = m.get("TIRR", "-")
        row["DSSAT:CET"] = m.get("CET", "-")
        row["DSSAT:MAT"] = m.get("MAT", "-")
        table_data.append(row)

    columns = [{"name": k, "id": k} for k in table_data[0].keys()] if table_data else []
    return table_data, columns


def build_simulation_output(scenarios, sim_results, messages):
    rows = []
    for idx, s in enumerate(scenarios, start=1):
        sid = s.get("id_scenario")
        m = (sim_results or {}).get(sid, {})
        status = m.get("status", "ERREUR")
        color = "success" if status == "SUCCES" else ("warning" if status == "VIDE" else "danger")
        rows.append(
            html.Tr([
                html.Td(f"Scénario {idx}"),
                html.Td(sid or "-"),
                html.Td(dbc.Badge(status, color=color, className="me-1")),
                html.Td(m.get("HARWT", "-")),
                html.Td(m.get("TOPWT", "-")),
                html.Td(m.get("RAIN", "-")),
                html.Td(m.get("TIRR", "-")),
                html.Td(m.get("CET", "-")),
                html.Td(m.get("MAT", "-")),
            ])
        )

    n_success = sum(1 for v in (sim_results or {}).values() if v.get("status") == "SUCCES")
    n_empty = sum(1 for v in (sim_results or {}).values() if v.get("status") == "VIDE")
    n_error = max(0, len(scenarios) - n_success - n_empty)

    return html.Div([
        html.H5("📊 Résultat des simulations DSSAT", className="mb-3"),
        html.Ul([html.Li(m, className="mb-1") for m in messages]),
        dbc.Table(
            [
                html.Thead(html.Tr([
                    html.Th("Scénario"),
                    html.Th("ID"),
                    html.Th("Status"),
                    html.Th("HARWT"),
                    html.Th("TOPWT"),
                    html.Th("RAIN"),
                    html.Th("TIRR"),
                    html.Th("CET"),
                    html.Th("MAT"),
                ])),
                html.Tbody(rows),
            ],
            bordered=True,
            striped=True,
            hover=True,
            size="sm",
            className="mt-3",
        ),
        html.P(f"Total: {len(scenarios)} | Succès: {n_success} | Vides: {n_empty} | Erreurs: {n_error}"),
    ])


def align_planting_date_to_wth_year(scenario, base_dir):
    """
    Aligne l'année de semis sur l'année couverte par le fichier WTH (si nécessaire).
    Retourne un message d'ajustement ou None.
    """
    try:
        station = scenario.get("location", {}).get("station_code")
        if not station:
            return None
        dssat_dir = Path(base_dir) / "dssat"
        wth_path = _find_wth_file(dssat_dir, station)
        if not wth_path:
            return None
        dates, _ = _parse_wth_dates(wth_path)
        if not dates:
            return None

        pdate = _parse_planting_date(scenario.get("crop", {}).get("planting_date"))
        if not pdate:
            return None

        dmin, dmax = min(dates), max(dates)
        if dmin <= pdate <= dmax:
            return None

        target_year = dmax.year
        doy = pdate.timetuple().tm_yday
        max_doy = 366 if (target_year % 4 == 0 and (target_year % 100 != 0 or target_year % 400 == 0)) else 365
        adj_doy = min(doy, max_doy)
        new_date = (datetime(target_year, 1, 1) + timedelta(days=adj_doy - 1)).date()

        scenario["crop"]["planting_date"] = new_date.isoformat()
        if "dssat" in scenario and isinstance(scenario["dssat"], dict):
            scenario["dssat"]["PltDate"] = new_date.isoformat()

        return (
            f"⚠️ Date de semis ajustée pour WTH '{wth_path.name}': "
            f"{pdate} -> {new_date}"
        )
    except Exception:
        return None


# ==========================================================
# 🚀 ENREGISTREMENT DES CALLBACKS
# ==========================================================
def register_callbacks(app):
    """
    Enregistre tous les callbacks Dash pour SIMAGRI v2
    """

    # ======================================================
    # 🗺️ CARTE + SOL
    # ======================================================
    @app.callback(
        [
            Output("map", "center"),
            Output("map", "zoom"),
            Output("dept-marker", "position"),
            Output("dept-geojson", "data"),
            Output("soil_type", "value"),
        ],
        Input("department", "value"),
    )
    def update_map_and_soil(dept_name):
        """
        Met à jour la carte, le marqueur et le type de sol
        en fonction du département sélectionné
        """

        # 🔒 Sécurité
        if not dept_name:
            return [14.15, -16.07], 7, [14.15, -16.07], None, None

        # 📍 GPS
        lat, lon = get_department_gps(dept_name)

        # 🌱 Type de sol
        soil = get_department_soil(dept_name)

        # 🗺️ Charger GeoJSON
        geojson = None
        try:
            with open(GEOJSON_PATH, encoding="utf-8") as f:
                geo = json.load(f)

            feature = None
            target = _norm_name(dept_name)
            for f in geo["features"]:
                name = (
                    f["properties"].get("NAME")
                    or f["properties"].get("name")
                    or f["properties"].get("ADM2_FR")
                    or f["properties"].get("ADM2_EN")
                    or ""
                )
                if _norm_name(name) == target:
                    feature = f
                    break

            if feature:
                geojson = {
                    "type": "FeatureCollection",
                    "features": [feature]
                }

        except Exception as e:
            print(f"⚠️ Erreur chargement GeoJSON : {e}")
            geojson = None

        return (
            [lat, lon],   # center
            12,            # zoom rapproché
            [lat, lon],   # marker
            geojson,      # contour département
            soil          # type de sol
        )

    # ======================================================
    # 🌱 AFFICHAGE BLOCS (Montrer/Cacher)
    # ======================================================
    @app.callback(
        Output("fertilization-block", "style"),
        Input("fertilization", "value")
    )
    def toggle_fert(use):
        """Affiche/cache le bloc fertilisation"""
        return {"display": "block"} if use else {"display": "none"}

    @app.callback(
        Output("irrigation-block", "style"),
        Input("irrigation", "value")
    )
    def toggle_irrig(use):
        """Affiche/cache le bloc irrigation"""
        return {"display": "block"} if use else {"display": "none"}

    @app.callback(
        Output("socio-block", "style"),
        Input("toggle_socio", "n_clicks"),
        prevent_initial_call=True
    )
    def toggle_socio(_):
        """Affiche le bloc socio-économique"""
        return {"display": "block"}


    # ======================================================
    # 💧 IRRIGATION
    # ======================================================
    @app.callback(
        [
            Output("irrigation-store", "data"),
            Output("irrig_cost", "value"),
        ],
        [
            Input("irrigation", "value"),
            Input("add-irrigation", "n_clicks"),
            Input({"type": "irrig_day", "index": ALL}, "value"),
            Input({"type": "irrig_mm", "index": ALL}, "value"),
            Input({"type": "irrig_price", "index": ALL}, "value"),
        ],
        State("irrigation-store", "data"),
    )
    def manage_irrigation(use_irrig, add_clicks, days, mms, prices, store):
        """
        Gère l'ajout et la modification des irrigations
        """

        if not use_irrig:
            return [], 0

        if not store:
            store = [{
                "doy": 20,
                "mm": 30,
                "price": 250
            }]

        if get_triggered_id() == "add-irrigation":
            store.append(store[-1].copy())

        total = 0
        for i, ir in enumerate(store):
            if i < len(days):
                ir["doy"] = days[i]
                ir["mm"] = mms[i]
                ir["price"] = prices[i]

            total += (ir["mm"] or 0) * (ir["price"] or 0)

        return store, total

    # Affichage lignes irrigation
    @app.callback(
        Output("irrigation-lines", "children"),
        Input("irrigation-store", "data"),
    )
    def render_irrigation_lines(data):
        """Affiche les lignes d'irrigation modifiables"""

        rows = []

        for i, ir in enumerate(data):
            cost = (ir["mm"] or 0) * (ir["price"] or 0)

            rows.append(
                dbc.Row([
                    dbc.Col(
                        dbc.Input(
                            id={"type": "irrig_day", "index": i},
                            type="number",
                            value=ir["doy"]
                        ), md=3
                    ),
                    dbc.Col(
                        dbc.Input(
                            id={"type": "irrig_mm", "index": i},
                            type="number",
                            value=ir["mm"]
                        ), md=3
                    ),
                    dbc.Col(
                        dbc.Input(
                            id={"type": "irrig_price", "index": i},
                            type="number",
                            value=ir["price"]
                        ), md=3
                    ),
                    dbc.Col(
                        dbc.Input(
                            value=cost,
                            disabled=True
                        ), md=3
                    ),
                ], className="mb-2")
            )

        return rows

    # Résumé irrigation
    @app.callback(
        Output("irrig_summary", "children"),
        Input("irrigation-store", "data"),
    )
    def update_irrig_summary(store):
        """Affiche un résumé des irrigations"""

        if not store:
            return "Aucune irrigation définie"

        total_mm = sum(ir["mm"] for ir in store if ir["mm"])
        total_events = len(store)

        return (
            f"{total_events} irrigations | "
            f"Eau totale = {total_mm} mm"
        )

    # ======================================================
    # 💰 SOCIO-ÉCONOMIE
    # ======================================================
    @app.callback(
        Output("prep_sol_cost", "value"),
        [
            Input("prep_sol", "value"),
            Input("area_ha", "value")
        ]
    )
    def update_prep_cost(ops, area):
        """Calcule le coût de préparation du sol"""
        return compute_soil_preparation_cost(ops, area)

    @app.callback(
        [
            Output("seed_qty", "value"),
            Output("seed_price", "value")
        ],
        Input("seed_type", "value"),
    )
    def update_seed_defaults(seed_type):
        """Charge les valeurs par défaut pour le type de semence"""
        data = SEEDS.get(seed_type, {})
        return data.get("qty", 0), data.get("price", 0)

    @app.callback(
        Output("seed_cost", "value"),
        [
            Input("seed_qty", "value"),
            Input("seed_price", "value"),
            Input("area_ha", "value")
        ]
    )
    def update_seed_cost(qty, price, area):
        """Calcule le coût des semences"""
        return compute_seed_cost(qty, price, area)

    @app.callback(
        Output("labor_cost", "value"),
        [
            Input("labor_type", "value"),
            Input("area_ha", "value")
        ]
    )
    def update_labor_cost(ops, area):
        """Calcule le coût de main-d'œuvre"""
        return compute_labor_cost(ops, area)

    @app.callback(
        Output("post_harvest_cost", "value"),
        [
            Input("post_harvest", "value"),
            Input("area_ha", "value")
        ]
    )
    def update_post_cost(ops, area):
        """Calcule le coût post-récolte"""
        return compute_post_harvest_cost(ops, area)

    @app.callback(
        Output("total_cost", "value"),
        [
            Input("prep_sol", "value"),
            Input("labor_type", "value"),
            Input("post_harvest", "value"),
            Input("seed_cost", "value"),
            Input("area_ha", "value"),
        ]
    )
    def update_total_cost(soil_ops, labor_ops, post_ops, seed_cost, area_ha):
        """Calcule le coût total de production"""
        return compute_total_socio_cost(
            soil_ops,
            labor_ops,
            post_ops,
            seed_cost,
            area_ha,
        )


    # ======================================================
    # 🌾 FERTILISATION
    # ======================================================
    @app.callback(
        [
            Output("fertilization-store", "data"),
            Output("fert_total_cost", "value")
        ],
        [
            Input("fertilization", "value"),
            Input("add-fertilization", "n_clicks"),
            Input({"type": "fert_type", "index": ALL}, "value"),
            Input({"type": "fert_qty", "index": ALL}, "value")
        ],
        State("fertilization-store", "data"),
    )
    def manage_fert(use, add, types, qtys, store):
        """
        Gère l'ajout et la modification des fertilisants
        """

        if not use:
            return [], 0

        if not store:
            store = [{"type": "NPK", "qty": 150}]

        if get_triggered_id() == "add-fertilization":
            store.append(store[-1].copy())

        total = 0
        for i, f in enumerate(store):
            if i < len(types):
                f["type"] = types[i]
                f["qty"] = qtys[i]
            total += compute_fertilization_cost(f["type"], f["qty"])

        return store, total

    @app.callback(
        Output("fertilization-lines", "children"),
        Input("fertilization-store", "data"),
    )
    def render_fert_lines(data):
        """Affiche les lignes de fertilisation modifiables"""
        rows = []
        for i, f in enumerate(data):
            cost = compute_fertilization_cost(f["type"], f["qty"])
            rows.append(
                dbc.Row([
                    dbc.Col(dcc.Dropdown(
                        id={"type": "fert_type", "index": i},
                        options=[
                            {"label": "Compost", "value": "COMPOST"},
                            {"label": "NPK", "value": "NPK"},
                            {"label": "Urée", "value": "UREA"},
                        ],
                        value=f["type"],
                    ), md=4),
                    dbc.Col(dbc.Input(
                        id={"type": "fert_qty", "index": i},
                        type="number", value=f["qty"]
                    ), md=4),
                    dbc.Col(dbc.Input(value=cost, disabled=True), md=4),
                ])
            )
        return rows

    @app.callback(
        Output("fert_npk_summary", "children"),
        Input("fertilization-store", "data"),
    )
    def update_npk(store):
        """Affiche un résumé des apports NPK"""
        if not store:
            return "Aucun apport calculé"
        N = P = K = 0
        for f in store:
            npk = compute_npk_from_fertilizer(f["type"], f["qty"])
            N += npk["N"]
            P += npk["P"]
            K += npk["K"]
        return f"N = {N:.1f} | P = {P:.1f} | K = {K:.1f} kg/ha"


    # ======================================================
    # 🌧️ DATE DE SEMIS ENACTS
    # ======================================================
    @app.callback(
        [
            Output("recommended_sowing_date", "value"),
            Output("planting_date", "min_date_allowed"),
            Output("planting_date", "max_date_allowed"),
            Output("planting_date", "date"),
        ],
        [
            Input("department", "value"),
            Input("hist_start_year", "value"),
            Input("hist_end_year", "value"),
        ],
        State("planting_date", "date"),
    )
    def update_onset(dept, y0, y1, current_planting_date):
        """
        Calcule la date de semis recommandée basée sur les données ENACTS
        """
        if not dept or not y0 or not y1:
            return "", None, None, current_planting_date
        try:
            df = load_enacts(dept)
            d, p = compute_probabilistic_onset(df, y0, y1)
            if not d:
                return "Pas de date fiable", None, None, current_planting_date

            # Année de référence pour le DatePicker
            if current_planting_date:
                ref_year = datetime.strptime(str(current_planting_date), "%Y-%m-%d").year
            else:
                ref_year = int(df["date"].dt.year.max())

            onset_dt = datetime.strptime(f"{d} {ref_year}", "%d %B %Y").date()
            min_dt = onset_dt - timedelta(days=10)
            max_dt = onset_dt + timedelta(days=10)

            if current_planting_date:
                cur_dt = datetime.strptime(str(current_planting_date), "%Y-%m-%d").date()
                selected_dt = cur_dt if (min_dt <= cur_dt <= max_dt) else onset_dt
            else:
                selected_dt = onset_dt

            msg = (
                f"{d} (P={p:.0%}) | Fenêtre: "
                f"{min_dt.strftime('%d/%m')} - {max_dt.strftime('%d/%m')}"
            )
            return msg, min_dt.isoformat(), max_dt.isoformat(), selected_dt.isoformat()
        except Exception as e:
            print(f"⚠️ Erreur calcul onset : {e}")
            return "Erreur calcul", None, None, current_planting_date


    # ======================================================
    # ➕ AJOUT SCÉNARIO
    # ======================================================
    @app.callback(
        Output("scenario-store", "data"),
        Input("add_scenario", "n_clicks"),
        State("scenario-store", "data"),
        State("department", "value"),
        State("crop", "value"),
        State("cycle", "value"),
        State("planting_date", "date"),
        State("hist_start_year", "value"),
        State("hist_end_year", "value"),
        State("recommended_sowing_date", "value"),
        State("fertilization", "value"),
        State("fertilization-store", "data"),
        State("irrigation", "value"),
        State("irrigation-store", "data"),
        State("fert_total_cost", "value"),
        State("irrig_cost", "value"),
        State("total_cost", "value"),
        prevent_initial_call=True,
    )
    def add_scenario(
        n_clicks,
        stored_scenarios,
        department,
        crop,
        cycle,
        planting_date,
        hist_start_year,
        hist_end_year,
        recommended_sowing_date,
        fertilization,
        fertilization_plan,
        irrigation,
        irrigation_plan,
        fert_cost,
        irrig_cost,
        total_cost,
    ):
        """
        Ajoute un nouveau scénario aux scénarios stockés
        et met à jour le tableau d'affichage
        """

        # 🔒 Sécurité
        if stored_scenarios is None:
            stored_scenarios = []

        # --------------------------------------------------
        # 1️⃣ Construire le scénario COMPLET depuis l'UI
        # --------------------------------------------------
        scenario = build_scenario_from_ui(
            scenario_id=f"S{len(stored_scenarios) + 1:03d}",
            department=department,
            crop=crop,
            cycle=cycle,
            planting_date=planting_date,
            hist_start_year=hist_start_year,
            hist_end_year=hist_end_year,
            recommended_sowing_date=recommended_sowing_date,
            recommended_sowing_prob=None,
            fertilization=fertilization,
            fertilization_plan=fertilization_plan or [],
            irrigation=irrigation,
            irrigation_plan=irrigation_plan or [],
            costs={
                "CropPrice": 200,
                "NFertCost": fert_cost or 0,
                "SeedCost": 0,
                "IrrigCost": irrig_cost or 0,
                "OtherVariableCosts": 0,
                "FixedCosts": total_cost or 0,
            },
        )

        # --------------------------------------------------
        # 2️⃣ Ajouter au scenario-store
        # --------------------------------------------------
        stored_scenarios.append(scenario)

        return stored_scenarios

    @app.callback(
        [
            Output("scenario-table", "data"),
            Output("scenario-table", "columns"),
        ],
        Input("scenario-store", "data"),
        Input("simulation-results-store", "data"),
    )
    def render_scenario_table(stored_scenarios, sim_results):
        if not stored_scenarios:
            return [], []
        return build_table(stored_scenarios, sim_results or {})


    # ======================================================
    # ▶️ SIMULATION DSSAT
    # ======================================================
    @app.callback(
        [
            Output("comparison-output", "children"),
            Output("simulation-results-store", "data"),
        ],
        Input("run_simulation", "n_clicks"),
        State("scenario-store", "data"),
        State("simulation-results-store", "data"),
        prevent_initial_call=True,
    )
    def run_dssat_from_ui(n_clicks, scenarios, sim_results):
        """
        Lance la simulation DSSAT pour 1 ou plusieurs scénarios
        """

        # ===============================
        # 1️⃣ Sécurité de base
        # ===============================
        if not n_clicks:
            return "Cliquez sur le bouton Simuler", (sim_results or {})

        if not scenarios or len(scenarios) == 0:
            return "⚠️ Aucun scénario à simuler. Ajoutez au moins un scénario.", (sim_results or {})

        messages = []
        sim_results = dict(sim_results or {})

        # ===============================
        # 2️⃣ Boucle sur les scénarios
        # ===============================
        for i, scenario in enumerate(scenarios, start=1):

            try:
                # Génère un .WTH propre au département sélectionné et met à jour la station.
                wth_path = ensure_weather_for_scenario(scenario, BASE_DIR / "dssat")
                if wth_path:
                    messages.append(f"Scénario {i} – météo chargée: {wth_path.name}")

                adjust_msg = align_planting_date_to_wth_year(scenario, BASE_DIR)
                if adjust_msg:
                    messages.append(f"Scénario {i} – {adjust_msg}")

                # 🔍 DEBUG
                print(f"\n[SIMULATION] Scénario {i}")
                print(f"  ID : {scenario.get('id_scenario')}")
                print(f"  Irrigation activée : {scenario.get('irrigation', {}).get('enabled')}")
                print(f"  Plan irrigation : {scenario.get('irrigation', {}).get('schedule')}")

                # ===============================
                # 3️⃣ Validation DSSAT (avant génération)
                # ===============================
                validation = validate_dssat_inputs(scenario, BASE_DIR)
                if validation["errors"]:
                    sim_results[scenario.get("id_scenario")] = {"status": "ERREUR"}
                    messages.append(
                        f"❌ Scénario {i} – erreurs DSSAT : "
                        + " | ".join(validation["errors"])
                    )
                    continue
                if validation["warnings"]:
                    messages.append(
                        f"⚠️ Scénario {i} – avertissements DSSAT : "
                        + " | ".join(validation["warnings"])
                    )

                # ===============================
                # 4️⃣ Génération des fichiers DSSAT
                # ===============================

                # --- X file ---
                x_path = write_x_file(
                    scenario,
                    output_dir=str(BASE_DIR / "dssat" / "exp")
                )

                if not x_path.exists():
                    raise FileNotFoundError("Fichier X non généré")

                print(f"  ✅ Fichier X créé : {x_path.name}")
                print(f"  DEBUG BASE_DIR : {BASE_DIR}")
                print(f"  DEBUG x_path : {x_path}")
                print(f"  DEBUG x_path.exists() : {x_path.exists()}")
                print(f"  DEBUG output_dir : {str(BASE_DIR / 'dssat' / 'exp')}")

                # --- SNX file ---
                from pathlib import Path

                # ...

                # Génération SNX
                snx_output_dir = Path("/app/dssat/snx")
                snx_output_dir.mkdir(parents=True, exist_ok=True)

                try:
                    snx_path = Path(write_snx_file(
                    scenario,
                    x_path.name,
                    output_dir=str(snx_output_dir)
                ))
                    print(f"✅ Fichier SNX créé : {snx_path}")
                except Exception as e:
                    print(f"❌ Erreur SNX : {e}")
                    raise

                # ===============================
                # 5️⃣ Lancer DSSAT
                # ===============================
                result = run_dssat_simulation(
                    str(snx_path),
                    dssat_workdir=str(BASE_DIR / "dssat")
                )

                # ===============================
                # 6️⃣ Analyse du résultat
                # ===============================
                if result["returncode"] == 0:
                    parsed = parse_summary_metrics(BASE_DIR / "dssat" / "Summary.OUT")
                    # Run-level success from DSSAT should not be marked as ERREUR
                    # just because Summary parsing is incomplete.
                    metrics = dict(parsed or {})
                    status = classify_dssat_status(parsed) if parsed else "SUCCES"
                    metrics["status"] = status
                    sim_results[scenario.get("id_scenario")] = metrics
                    if status == "VIDE":
                        messages.append(
                            f"⚠️ Scénario {i} simulé ({snx_path.name}) mais résultats vides (-99)"
                        )
                    else:
                        messages.append(
                            f"✅ Scénario {i} simulé avec succès ({snx_path.name}) | {format_metrics_short(metrics)}"
                        )
                    print(f"  ✅ DSSAT retour : 0 (succès)")
                else:
                    sim_results[scenario.get("id_scenario")] = {"status": "ERREUR"}
                    messages.append(
                        f"❌ Scénario {i} – erreur DSSAT : {result['stderr'][:100]}"
                    )
                    print(f"  ❌ DSSAT erreur : {result['stderr'][:200]}")

            except FileNotFoundError as e:
                sim_results[scenario.get("id_scenario")] = {"status": "ERREUR"}
                messages.append(
                    f"❌ Scénario {i} – fichier manquant : {str(e)}"
                )
                print(f"  ❌ Fichier manquant : {e}")

            except Exception as e:
                sim_results[scenario.get("id_scenario")] = {"status": "ERREUR"}
                messages.append(
                    f"❌ Scénario {i} – erreur : {str(e)[:100]}"
                )
                print(f"  ❌ Erreur : {e}")

        # ===============================
        # 6️⃣ Affichage UI
        # ===============================
        return build_simulation_output(scenarios, sim_results, messages), sim_results
