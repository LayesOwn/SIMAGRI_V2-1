# ==========================================================
# ui/callbacks.py
# Callbacks Dash – SIMAGRI v2
# ==========================================================

from dash import html, dcc, ctx
from dash.dependencies import Input, Output, State, ALL
import dash_bootstrap_components as dbc
import json
from pathlib import Path

# --- Imports domaine métier
from domain.geography import get_department_gps, get_department_soil
from domain.climate.enacts import load_enacts, compute_probabilistic_onset
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
from domain.scenario import build_scenario_from_ui
from domain.decision import evaluate_scenarios
from domain.dssat.write_xfile import write_x_file
from domain.dssat.write_snx import write_snx_file
from domain.dssat.run_dssat import run_dssat_simulation


# ==========================================================
# CONFIGURATION DES CHEMINS
# ==========================================================
BASE_DIR = Path(__file__).resolve().parents[2]  # Remonte à la racine du projet
GEOJSON_PATH = BASE_DIR / "data" / "geojson" / "senegal_departments.json"


# ==========================================================
# 🔧 Fonction utilitaire (TABLE)
# ==========================================================
def scenario_to_table_row(s):
    """
    Convertit un scénario complet en une ligne pour la table d'affichage
    """
    return {
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
        "Coût total (FCFA)": s["economy"]["FixedCosts"],
    }


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
            for f in geo["features"]:
                name = (
                    f["properties"].get("NAME")
                    or f["properties"].get("name")
                    or ""
                )

                if name.lower() == dept_name.lower():
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

        if ctx.triggered_id == "add-irrigation":
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

        if ctx.triggered_id == "add-fertilization":
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
        Output("recommended_sowing_date", "value"),
        [
            Input("department", "value"),
            Input("hist_start_year", "value"),
            Input("hist_end_year", "value")
        ]
    )
    def update_onset(dept, y0, y1):
        """
        Calcule la date de semis recommandée basée sur les données ENACTS
        """
        if not dept or not y0 or not y1:
            return ""
        try:
            df = load_enacts(dept)
            d, p = compute_probabilistic_onset(df, y0, y1)
            return f"{d} (P={p:.0%})" if d else "Pas de date fiable"
        except Exception as e:
            print(f"⚠️ Erreur calcul onset : {e}")
            return "Erreur calcul"


    # ======================================================
    # ➕ AJOUT SCÉNARIO
    # ======================================================
    @app.callback(
        [
            Output("scenario-store", "data"),
            Output("scenario-table", "data"),
            Output("scenario-table", "columns"),
        ],
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
            scenario_id=f"SCE_{len(stored_scenarios) + 1}",
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

        # --------------------------------------------------
        # 3️⃣ Construire la table des scénarios (UI)
        # --------------------------------------------------
        table_data = [scenario_to_table_row(s) for s in stored_scenarios]

        columns = [
            {"name": k, "id": k}
            for k in table_data[0].keys()
        ]

        # --------------------------------------------------
        # 4️⃣ Retour Dash
        # --------------------------------------------------
        return stored_scenarios, table_data, columns


    # ======================================================
    # ▶️ SIMULATION DSSAT
    # ======================================================
    @app.callback(
        Output("comparison-output", "children"),
        Input("run_simulation", "n_clicks"),
        State("scenario-store", "data"),
        prevent_initial_call=True,
    )
    def run_dssat_from_ui(n_clicks, scenarios):
        """
        Lance la simulation DSSAT pour 1 ou plusieurs scénarios
        """

        # ===============================
        # 1️⃣ Sécurité de base
        # ===============================
        if not n_clicks:
            return "Cliquez sur le bouton Simuler"

        if not scenarios or len(scenarios) == 0:
            return "⚠️ Aucun scénario à simuler. Ajoutez au moins un scénario."

        messages = []

        # ===============================
        # 2️⃣ Boucle sur les scénarios
        # ===============================
        for i, scenario in enumerate(scenarios, start=1):

            try:
                # 🔍 DEBUG
                print(f"\n[SIMULATION] Scénario {i}")
                print(f"  ID : {scenario.get('id_scenario')}")
                print(f"  Irrigation activée : {scenario.get('irrigation', {}).get('enabled')}")
                print(f"  Plan irrigation : {scenario.get('irrigation', {}).get('schedule')}")

                # ===============================
                # 3️⃣ Génération des fichiers DSSAT
                # ===============================

                # --- X file ---
                x_path = write_x_file(
                    scenario,
                    output_dir=str(BASE_DIR / "dssat" / "exp")
                )

                if not x_path.exists():
                    raise FileNotFoundError("Fichier X non généré")

                print(f"  ✅ Fichier X créé : {x_path.name}")

                # --- SNX file ---
                snx_path = write_snx_file(
                    scenario,
                    x_path.name,
                    output_dir=str(BASE_DIR / "dssat" / "snx")
                )

                if not snx_path.exists():
                    raise FileNotFoundError("Fichier SNX non généré")

                print(f"  ✅ Fichier SNX créé : {snx_path.name}")

                # ===============================
                # 4️⃣ Lancer DSSAT
                # ===============================
                result = run_dssat_simulation(
                    str(snx_path),
                    dssat_workdir=str(BASE_DIR / "dssat")
                )

                # ===============================
                # 5️⃣ Analyse du résultat
                # ===============================
                if result["returncode"] == 0:
                    messages.append(
                        f"✅ Scénario {i} simulé avec succès ({snx_path.name})"
                    )
                    print(f"  ✅ DSSAT retour : 0 (succès)")
                else:
                    messages.append(
                        f"❌ Scénario {i} – erreur DSSAT : {result['stderr'][:100]}"
                    )
                    print(f"  ❌ DSSAT erreur : {result['stderr'][:200]}")

            except FileNotFoundError as e:
                messages.append(
                    f"❌ Scénario {i} – fichier manquant : {str(e)}"
                )
                print(f"  ❌ Fichier manquant : {e}")

            except Exception as e:
                messages.append(
                    f"❌ Scénario {i} – erreur : {str(e)[:100]}"
                )
                print(f"  ❌ Erreur : {e}")

        # ===============================
        # 6️⃣ Affichage UI
        # ===============================
        return html.Div([
            html.H5("📊 Résultat des simulations DSSAT", className="mb-3"),
            html.Ul([html.Li(m, className="mb-2") for m in messages]),
            html.Hr(),
            html.P(
                f"Total : {len(scenarios)} scénario(s), "
                f"{sum(1 for m in messages if '✅' in m)} succès"
            )
        ])